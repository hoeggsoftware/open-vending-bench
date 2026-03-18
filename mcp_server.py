"""
MCP Server Mode for VendingBench Simulator

This module provides an MCP (Model Context Protocol) server interface for the
simulator, allowing external agents to drive the simulation via tool calls over HTTP.

The server wraps all existing simulator tools and enforces:
- Bearer token authentication (via middleware)
- Message budget tracking
- Sequential tool execution
- Database logging identical to internal mode
"""

import json
import uuid
import threading
import time
from datetime import datetime
from typing import Optional

from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.exceptions import ToolError

# Import existing tool implementations with underscore prefix to avoid shadowing
from tools import (
    wait_for_next_day as _wait_for_next_day,
    send_email as _send_email,
    read_email as _read_email,
    check_storage_quantities as _check_storage_quantities,
    get_machine_inventory as _get_machine_inventory,
    get_money_balance as _get_money_balance,
    get_simulation_status as _get_simulation_status,
    ai_web_search as _ai_web_search,
    scratchpad_write as _scratchpad_write,
    read_scratchpad as _read_scratchpad,
    get_kw_value as _get_kw_value,
    set_kw_value as _set_kw_value,
    stock_machine as _stock_machine,
    set_item_price as _set_item_price,
)


class BearerTokenMiddleware(Middleware):
    """FastMCP middleware for Bearer token authentication."""

    def __init__(self, token: str):
        self.token = token

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Validate Bearer token on every tool call."""
        # Access headers through the request context
        # (get_http_headers() doesn't expose Authorization header)
        request = context.fastmcp_context.request_context.request
        headers = dict(request.headers)

        auth_header = headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise ToolError("Unauthorized: Missing or invalid Authorization header")

        provided_token = auth_header[7:]  # Strip "Bearer " prefix
        if provided_token != self.token:
            raise ToolError("Unauthorized: Invalid token")

        return await call_next(context)


class MCPSimulationServer:
    """MCP server for external agent control of VendingBench simulation."""

    def __init__(self, simulation, message_budget: int, port: int, token: str):
        """
        Initialize MCP server for the simulation.

        Args:
            simulation: VendingMachineSimulation instance
            message_budget: Maximum number of tool calls allowed
            port: HTTP port to listen on
            token: Bearer token for authentication
        """
        self.simulation = simulation
        self.message_budget = message_budget
        self.starting_message_count = simulation.message_count
        self.port = port
        self.token = token
        self.mcp = FastMCP("VendingBench Simulator")
        self.shutdown_timer: Optional[threading.Timer] = None
        self._shutdown_event = threading.Event()
        self._run_started = False

        # Add Bearer token authentication middleware
        self.mcp.add_middleware(BearerTokenMiddleware(token=token))

        # Register all tools
        self._register_tools()

    def _check_budget(self) -> bool:
        """Check if message budget has been exhausted.

        Returns:
            True if budget remains, False if exhausted
        """
        messages_used = self.simulation.message_count - self.starting_message_count
        return messages_used < self.message_budget

    def _increment_message_count(self, tool_name: str = "unknown", tool_args: dict = None) -> None:
        """Increment message count and log to database."""
        self._run_started = True
        self.simulation.message_count += 1

        # Log state after each tool call (mirrors internal mode behavior)
        if self.simulation.store_state:
            self.simulation.log_state()
            # Log to logs table so the evaluator can see tool usage
            self.simulation.db.log_message(
                simulation_id=self.simulation.simulation_id,
                timestamp=self.simulation.get_current_time(),
                prompt="[MCP server mode]",
                response=f"[tool: {tool_name}]",
                tool_calls=[{"function": {"name": tool_name, "arguments": json.dumps(tool_args or {})}}],
            )

    def _schedule_shutdown(self) -> None:
        """Schedule server shutdown after 30-second grace period."""
        if self.shutdown_timer is None:
            print("\n⏰ Budget exhausted. Server will shut down in 30 seconds...")
            self.shutdown_timer = threading.Timer(30.0, self._shutdown)
            self.shutdown_timer.start()

    def _shutdown(self) -> None:
        """Signal server shutdown."""
        print("\n🛑 Shutting down MCP server...")
        self._shutdown_event.set()

    def _register_tools(self) -> None:
        """Register all simulator tools as MCP tools."""

        # Helper to create tool wrapper with budget checking
        def make_tool_wrapper(tool_func, name: str, bypass_budget: bool = False):
            def wrapper(**kwargs):
                # Check budget (unless bypassed for get_simulation_status)
                if not bypass_budget and not self._check_budget():
                    self._schedule_shutdown()
                    return {
                        "error": "Message budget exhausted",
                        "message": f"Maximum of {self.message_budget} messages reached. "
                                  f"Call get_simulation_status for final state."
                    }

                # Only increment for tools that count against the budget
                if not bypass_budget:
                    self._increment_message_count(tool_name=name, tool_args=kwargs)

                # Call actual tool
                try:
                    result = tool_func(self.simulation, **kwargs)
                    return {"success": True, "result": result}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            return wrapper

        # State read tools
        @self.mcp.tool()
        def get_machine_inventory() -> dict:
            """Get current vending machine inventory with slot details and prices."""
            wrapper = make_tool_wrapper(lambda sim: _get_machine_inventory(sim), "get_machine_inventory")
            return wrapper()

        @self.mcp.tool()
        def check_storage_quantities() -> dict:
            """Check current inventory in backroom storage."""
            wrapper = make_tool_wrapper(lambda sim: _check_storage_quantities(sim), "check_storage_quantities")
            return wrapper()

        @self.mcp.tool()
        def get_money_balance() -> dict:
            """Get current cash balance."""
            wrapper = make_tool_wrapper(lambda sim: _get_money_balance(sim), "get_money_balance")
            return wrapper()

        @self.mcp.tool()
        def read_email() -> dict:
            """Read next unread email (marks as read)."""
            wrapper = make_tool_wrapper(lambda sim: _read_email(sim), "read_email")
            return wrapper()

        @self.mcp.tool()
        def get_simulation_status() -> dict:
            """Get simulation status: day, date, season, weather, messages used,
            and messages remaining in the current budget."""
            def _status_with_budget(sim):
                base = _get_simulation_status(sim)
                messages_used = sim.message_count - self.starting_message_count
                messages_remaining = max(0, self.message_budget - messages_used)
                return f"{base} | Messages remaining: {messages_remaining}"

            wrapper = make_tool_wrapper(
                _status_with_budget,
                "get_simulation_status",
                bypass_budget=True
            )
            return wrapper()

        # Action tools
        @self.mcp.tool()
        def send_email(
            to: str,
            subject: str,
            body: str
        ) -> dict:
            """Send email to supplier or business contact."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _send_email(sim, kw["to"], kw["subject"], kw["body"]),
                "send_email"
            )
            return wrapper(to=to, subject=subject, body=body)

        @self.mcp.tool()
        def stock_machine(
            item_name: str,
            slot_id: str,
            quantity: int
        ) -> dict:
            """Move items from backroom storage to vending machine slot."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _stock_machine(sim, kw["item_name"], kw["slot_id"], kw["quantity"]),
                "stock_machine"
            )
            return wrapper(item_name=item_name, slot_id=slot_id, quantity=quantity)

        @self.mcp.tool()
        def set_item_price(
            item_name: str,
            price: float
        ) -> dict:
            """Set selling price for an item in the vending machine."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _set_item_price(sim, kw["item_name"], kw["price"]),
                "set_item_price"
            )
            return wrapper(item_name=item_name, price=price)

        # Helper for wait_for_next_day that triggers daily processing
        def _advance_and_process(sim):
            _wait_for_next_day(sim)
            # handle_new_day() contains a guard `if message_count > 1` that was written
            # for internal mode where the count is already > 1 by the first day boundary.
            # Temporarily satisfy it without polluting the externally-visible counter.
            _saved = sim.message_count
            if sim.message_count <= 1:
                sim.message_count = 2
            result = sim.handle_new_day()
            sim.message_count = _saved
            return result

        @self.mcp.tool()
        def wait_for_next_day() -> dict:
            """Advance simulation to 6:00 AM of the next day, processing sales,
            deliveries, fees, and weather for the completed day."""
            wrapper = make_tool_wrapper(_advance_and_process, "wait_for_next_day")
            return wrapper()

        # Utility tools
        @self.mcp.tool()
        def ai_web_search(query: str) -> dict:
            """Search the web using Perplexity API."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _ai_web_search(sim, kw["query"]),
                "ai_web_search"
            )
            return wrapper(query=query)

        @self.mcp.tool()
        def write_scratchpad(content: str) -> dict:
            """Write or overwrite scratchpad memory."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _scratchpad_write(sim, kw["content"]),
                "write_scratchpad"
            )
            return wrapper(content=content)

        @self.mcp.tool()
        def read_scratchpad() -> dict:
            """Read scratchpad memory contents."""
            wrapper = make_tool_wrapper(lambda sim: _read_scratchpad(sim), "read_scratchpad")
            return wrapper()

        @self.mcp.tool()
        def set_memory(key: str, value: str) -> dict:
            """Set a value in the key-value store."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _set_kw_value(sim, kw["key"], kw["value"]),
                "set_memory"
            )
            return wrapper(key=key, value=value)

        @self.mcp.tool()
        def get_memory(key: str) -> dict:
            """Get a value from the key-value store."""
            wrapper = make_tool_wrapper(
                lambda sim, **kw: _get_kw_value(sim, kw["key"]),
                "get_memory"
            )
            return wrapper(key=key)

    def start(self) -> None:
        """Start the MCP server and run until budget exhausted or interrupted."""
        print("\n" + "=" * 60)
        print("🚀 MCP SERVER MODE")
        print("=" * 60)
        print(f"Simulation ID: {self.simulation.simulation_id}")
        print(f"Endpoint: http://localhost:{self.port}")
        print(f"Token: {self.token}")
        print(f"Message budget: {self.message_budget}")
        print(f"Starting balance: ${self.simulation.balance:.2f}")
        print(f"Starting date: {self.simulation.current_time.strftime('%Y-%m-%d')}")
        print("=" * 60)
        print("\n⏳ Waiting for client connections...")
        print("   (Press Ctrl+C to stop)\n")

        # Run FastMCP in daemon thread so main thread can handle shutdown
        server_thread = threading.Thread(
            target=lambda: self.mcp.run(transport="http", port=self.port),
            daemon=True
        )
        server_thread.start()

        try:
            # Wait for shutdown signal or Ctrl+C
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            print("\n\n🛑 Server interrupted by user")
        finally:
            # Cancel shutdown timer if still pending
            if self.shutdown_timer is not None:
                self.shutdown_timer.cancel()

            # Print final stats
            print("\n" + "=" * 60)
            print("SIMULATION COMPLETE")
            print("=" * 60)
            print(f"Total messages: {self.simulation.message_count}")
            print(f"Days passed: {self.simulation.days_passed}")
            print(f"Final balance: ${self.simulation.balance:.2f}")
            print("=" * 60)


# ============================================================================
# Multi-Tenant Server Classes and Helpers
# ============================================================================


class TenantMiddleware(Middleware):
    """FastMCP middleware for multi-tenant bearer token authentication."""

    def __init__(self, registry: dict):
        """
        Initialize middleware with session registry.

        Args:
            registry: Dict mapping tokens to session dicts
        """
        self.registry = registry

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Validate Bearer token and store it in context state for tool access."""
        request = context.fastmcp_context.request_context.request
        auth_header = request.headers.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            raise ToolError("Unauthorized: Missing Authorization header")

        token = auth_header[7:]
        session = self.registry.get(token)

        if session is None:
            raise ToolError("Unauthorized: Invalid token")

        # Store token in context (tools will look up session from registry)
        await context.fastmcp_context.set_state("token", token)
        return await call_next(context)


def _execute(session: dict, tool_name: str, tool_func, tool_args: dict = None,
             bypass_budget: bool = False) -> dict:
    """
    Execute a tool call against the session's simulation.

    Args:
        session: Session dict containing simulation and budget info
        tool_name: Name of the tool being called
        tool_func: Function to execute (takes simulation as argument)
        tool_args: Tool arguments for logging
        bypass_budget: If True, don't check/increment budget

    Returns:
        dict: {"success": True, "result": ...} or {"error": ..., "message": ...}
    """
    sim = session["simulation"]
    budget = session["message_budget"]
    start = session["starting_message_count"]

    with session["lock"]:  # Serialize per-session tool calls
        messages_used = sim.message_count - start

        if not bypass_budget and messages_used >= budget:
            return {
                "error": "Message budget exhausted",
                "message": f"Maximum of {budget} messages reached. "
                           "Call get_simulation_status for final state."
            }

        if not bypass_budget:
            _increment(session, tool_name, tool_args)

        try:
            result = tool_func(sim)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


def _increment(session: dict, tool_name: str, tool_args: dict = None) -> None:
    """
    Increment message count and log to database.

    Args:
        session: Session dict containing simulation
        tool_name: Name of the tool being called
        tool_args: Tool arguments for logging
    """
    sim = session["simulation"]
    sim.message_count += 1

    if sim.store_state:
        sim.log_state()
        sim.db.log_message(
            simulation_id=sim.simulation_id,
            timestamp=sim.get_current_time(),
            prompt="[MCP server mode]",
            response=f"[tool: {tool_name}]",
            tool_calls=[{"function": {"name": tool_name,
                                      "arguments": json.dumps(tool_args or {})}}],
        )


class MultiTenantMCPServer:
    """Multi-tenant MCP server for simultaneous contestant access."""

    def __init__(self, contestants: list, port: int):
        """
        Initialize multi-tenant MCP server.

        Args:
            contestants: List of contestant config dicts from YAML
            port: HTTP port to listen on
        """
        from main_simulation import VendingMachineSimulation

        self.port = port
        self.mcp = FastMCP("VendingBench Simulator")

        # Build session registry: token -> session
        self.registry = {}

        for contestant in contestants:
            # Create simulation for this contestant
            sim = VendingMachineSimulation(
                store_state=True,
                start_date=contestant["start_date"],
                weather_seed=contestant["weather_seed"],
                db_path=contestant["db_path"],
                starting_balance=contestant.get("starting_balance", 500),
            )

            # Create session entry
            session = {
                "name": contestant["name"],
                "token": contestant["token"],
                "simulation": sim,
                "message_budget": contestant["message_budget"],
                "starting_message_count": sim.message_count,
                "config": {
                    "weather_seed": contestant["weather_seed"],
                    "start_date": contestant["start_date"],
                    "db_path": contestant["db_path"],
                    "starting_balance": contestant.get("starting_balance", 500),
                },
                "lock": threading.Lock(),
            }

            self.registry[contestant["token"]] = session

        # Add tenant-aware authentication middleware
        self.mcp.add_middleware(TenantMiddleware(registry=self.registry))

        # Register all tools
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all simulator tools as MCP tools with Context injection."""

        # Helper to get session from token
        async def get_session(ctx: Context) -> dict:
            """Get session from registry using token in context."""
            token = await ctx.get_state("token")
            return self.registry[token]

        # State read tools
        @self.mcp.tool()
        async def get_machine_inventory(ctx: Context) -> dict:
            """Get current vending machine inventory with slot details and prices."""
            session = await get_session(ctx)
            return _execute(session, "get_machine_inventory", _get_machine_inventory)

        @self.mcp.tool()
        async def check_storage_quantities(ctx: Context) -> dict:
            """Check current inventory in backroom storage."""
            session = await get_session(ctx)
            return _execute(session, "check_storage_quantities", _check_storage_quantities)

        @self.mcp.tool()
        async def get_money_balance(ctx: Context) -> dict:
            """Get current cash balance."""
            session = await get_session(ctx)
            return _execute(session, "get_money_balance", _get_money_balance)

        @self.mcp.tool()
        async def read_email(ctx: Context) -> dict:
            """Read next unread email (marks as read)."""
            session = await get_session(ctx)
            return _execute(session, "read_email", _read_email)

        @self.mcp.tool()
        async def get_simulation_status(ctx: Context) -> dict:
            """Get simulation status: day, date, season, weather, messages used,
            and messages remaining in the current budget."""
            session = await get_session(ctx)
            sim = session["simulation"]

            def _status(s):
                base = _get_simulation_status(s)
                used = s.message_count - session["starting_message_count"]
                remaining = max(0, session["message_budget"] - used)
                return f"{base} | Messages remaining: {remaining}"

            return _execute(session, "get_simulation_status", _status, bypass_budget=True)

        # Action tools
        @self.mcp.tool()
        async def send_email(to: str, subject: str, body: str, ctx: Context) -> dict:
            """Send email to supplier or business contact."""
            session = await get_session(ctx)
            return _execute(
                session, "send_email",
                lambda sim: _send_email(sim, to, subject, body),
                tool_args={"to": to, "subject": subject, "body": body}
            )

        @self.mcp.tool()
        async def stock_machine(item_name: str, slot_id: str, quantity: int, ctx: Context) -> dict:
            """Move items from backroom storage to vending machine slot."""
            session = await get_session(ctx)
            return _execute(
                session, "stock_machine",
                lambda sim: _stock_machine(sim, item_name, slot_id, quantity),
                tool_args={"item_name": item_name, "slot_id": slot_id, "quantity": quantity}
            )

        @self.mcp.tool()
        async def set_item_price(item_name: str, price: float, ctx: Context) -> dict:
            """Set selling price for an item in the vending machine."""
            session = await get_session(ctx)
            return _execute(
                session, "set_item_price",
                lambda sim: _set_item_price(sim, item_name, price),
                tool_args={"item_name": item_name, "price": price}
            )

        @self.mcp.tool()
        async def wait_for_next_day(ctx: Context) -> dict:
            """Advance simulation to 6:00 AM of the next day, processing sales,
            deliveries, fees, and weather for the completed day."""
            session = await get_session(ctx)

            def _advance(sim):
                _wait_for_next_day(sim)
                # Preserve the guard fix from single-tenant mode
                _saved = sim.message_count
                if sim.message_count <= 1:
                    sim.message_count = 2
                result = sim.handle_new_day()
                sim.message_count = _saved
                return result

            return _execute(session, "wait_for_next_day", _advance)

        # Utility tools
        @self.mcp.tool()
        async def ai_web_search(query: str, ctx: Context) -> dict:
            """Search the web using Perplexity API."""
            session = await get_session(ctx)
            return _execute(
                session, "ai_web_search",
                lambda sim: _ai_web_search(sim, query),
                tool_args={"query": query}
            )

        @self.mcp.tool()
        async def write_scratchpad(content: str, ctx: Context) -> dict:
            """Write or overwrite scratchpad memory."""
            session = await get_session(ctx)
            return _execute(
                session, "write_scratchpad",
                lambda sim: _scratchpad_write(sim, content),
                tool_args={"content": content}
            )

        @self.mcp.tool()
        async def read_scratchpad(ctx: Context) -> dict:
            """Read scratchpad memory contents."""
            session = await get_session(ctx)
            return _execute(session, "read_scratchpad", _read_scratchpad)

        @self.mcp.tool()
        async def set_memory(key: str, value: str, ctx: Context) -> dict:
            """Set a value in the key-value store."""
            session = await get_session(ctx)
            return _execute(
                session, "set_memory",
                lambda sim: _set_kw_value(sim, key, value),
                tool_args={"key": key, "value": value}
            )

        @self.mcp.tool()
        async def get_memory(key: str, ctx: Context) -> dict:
            """Get a value from the key-value store."""
            session = await get_session(ctx)
            return _execute(
                session, "get_memory",
                lambda sim: _get_kw_value(sim, key),
                tool_args={"key": key}
            )

        @self.mcp.tool()
        async def restart_simulation(ctx: Context) -> dict:
            """Reset your simulation to the initial state. Your token stays the same.
            All progress (balance, inventory, emails, days) is discarded. The message
            budget resets to its original value. Use this to start a fresh run."""
            from main_simulation import VendingMachineSimulation

            session = await get_session(ctx)

            with session["lock"]:
                config = session["config"]

                # Close the old database connection cleanly
                try:
                    session["simulation"].db.close()
                except Exception:
                    pass

                # Re-create the simulation from scratch with the same config
                new_sim = VendingMachineSimulation(
                    store_state=True,
                    start_date=config["start_date"],
                    weather_seed=config["weather_seed"],
                    db_path=config["db_path"],
                    starting_balance=config.get("starting_balance", 500),
                )

                session["simulation"] = new_sim
                session["starting_message_count"] = new_sim.message_count

                name = session["name"]
                print(f"[{name}] Simulation restarted (new ID: {new_sim.simulation_id})")

            return {
                "success": True,
                "result": f"Simulation restarted. New simulation ID: {new_sim.simulation_id}. "
                          f"Balance: ${new_sim.balance:.2f}. Budget reset to {session['message_budget']} messages."
            }

    def start(self) -> None:
        """Start the multi-tenant MCP server and run until interrupted."""
        print("\n" + "=" * 60)
        print("🚀 MULTI-TENANT MCP SERVER")
        print("=" * 60)
        print(f"Endpoint: http://localhost:{self.port}/mcp")
        print(f"Contestants: {len(self.registry)}")
        print()

        for session in self.registry.values():
            name = session["name"]
            token = session["token"]
            budget = session["message_budget"]
            db_path = session["config"]["db_path"]
            print(f"  {name:10} → token: {token:30} budget: {budget:3}  db: {db_path}")

        print("\n" + "=" * 60)
        print("\n⏳ Waiting for client connections...")
        print("   (Press Ctrl+C to stop)\n")

        try:
            self.mcp.run(transport="http", port=self.port)
        except KeyboardInterrupt:
            print("\n🛑 Server stopped")
        finally:
            for session in self.registry.values():
                try:
                    session["simulation"].db.close()
                except Exception:
                    pass
