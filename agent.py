from typing import List, Dict
from model_client import call_model
from collections import deque
from datetime import timedelta
from tools import TOOLS_LIST, execute_tool

LOOP_PROMPT = "Continue on your mission by using your tools"
SYSTEM_PROMPT = """
You are an autonomous vending machine operator. Your goal is to run a profitable vending machine business over time by ordering products, stocking your machine, and adapting to market conditions.

BUSINESS DETAILS:
- Your delivery address: 1247 Business Park Drive, Suite 200, Chicago, IL 60601
- Your bank account number: 1234567890
- Starting balance: $500, daily fee: $2

AVAILABLE TOOLS:
- wait_for_next_day: Advance to the next day (triggers sales, weather, deliveries)
- send_email / read_email: Communicate with suppliers to place orders
- check_storage_quantities: Check backroom storage inventory
- get_machine_inventory: View what's currently in the vending machine slots
- get_money_balance: Check your current cash balance
- set_item_price: Set selling prices for items in storage (CRITICAL - items default to $0.00!)
- stock_machine: Move items from storage into vending machine slots
- ai_web_search: Search the web for supplier/product information
- scratchpad_write / read_scratchpad / erase_scratchpad: Keep working notes
- get_kw_value / set_kw_value / delete_kw_value: Persistent key-value storage
- add_to_vector_db / search_vector_db: Store and search text documents

VENDING MACHINE:
- 4 rows x 3 slots = 12 total slots
- Rows 0-1: small items only, Rows 2-3: large items only
- Max 10 units per slot

WORKFLOW:
1. Search for and contact suppliers (ai_web_search, send_email)
2. Order products - include delivery address and account number in emails
3. When deliveries arrive, SET PRICES for items (set_item_price) - items default to $0.00!
4. Stock the vending machine with priced items (stock_machine)
5. Monitor sales reports and balance each day
6. Use memory tools to track strategies and decisions
7. Adapt pricing and product mix based on weather, season, and sales data

When emailing suppliers, you MUST include:
1. Names and quantities of items you want to purchase
2. Your delivery address: 1247 Business Park Drive, Suite 200, Chicago, IL 60601
3. Your account number for billing: 1234567890
"""


class VendingMachineAgent:
    def __init__(
        self,
        name: str = "VendingBot",
        max_context_tokens: int = 30000,
        simulation_ref=None,
        system_prompt=None,
    ):
        self.name = name
        self.conversation_history: List[Dict[str, str]] = []
        self.tools = TOOLS_LIST  # Placeholder for future tools
        self.max_context_tokens = max_context_tokens
        self.simulation = simulation_ref  # Reference to parent simulation
        self.last_6am_time = None  # Track last 6 AM timestamp we processed

        # Store custom system prompt, defaulting to the module-level SYSTEM_PROMPT
        self.system_prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT

        # Sliding window for context management
        self.context_window: deque = deque()
        self.current_context_tokens = 0

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the full conversation history"""
        return self.conversation_history.copy()

    def clear_history(self):
        """Clear conversation history and context window"""
        self.conversation_history = []
        self.context_window.clear()
        self.current_context_tokens = 0

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of tokens (approximately 4 characters per token)"""
        return len(text) // 4

    def _summarize_dropped_context(self, dropped_entries: list):
        """Summarize dropped context entries using the LLM"""
        combined_text = "\n".join(entry["text"] for entry in dropped_entries)
        combined_tokens = self._estimate_tokens(combined_text)

        # Only summarize if there's enough content to be worth it
        if combined_tokens < 200:
            return None

        summary_prompt = (
            "Summarize the following conversation history into a concise summary "
            "preserving key decisions, strategies, financial changes, orders placed, "
            "deliveries received, and important observations. Keep it under 500 words.\n\n"
            f"{combined_text}"
        )

        try:
            result = call_model(summary_prompt)
            summary_text = result.get("content", "") if isinstance(result, dict) else str(result)
            if not summary_text:
                return None
            return {
                "text": f"[CONTEXT SUMMARY]: {summary_text}",
                "tokens": self._estimate_tokens(summary_text),
            }
        except Exception:
            return None

    def _add_to_context_window(self, entry: Dict[str, str]):
        """Add entry to sliding context window, summarizing old entries if needed"""
        entry_text = f"{entry['role'].upper()}: {entry['content']}"
        entry_tokens = self._estimate_tokens(entry_text)

        # Add new entry
        self.context_window.append({"text": entry_text, "tokens": entry_tokens})
        self.current_context_tokens += entry_tokens

        # Collect entries that need to be dropped
        dropped = []
        while (
            self.current_context_tokens > self.max_context_tokens
            and self.context_window
        ):
            oldest = self.context_window.popleft()
            self.current_context_tokens -= oldest["tokens"]
            dropped.append(oldest)

        # Summarize dropped entries and prepend to context
        if dropped:
            summary = self._summarize_dropped_context(dropped)
            if summary:
                # Remove any existing summary entry at the front
                if (
                    self.context_window
                    and self.context_window[0]["text"].startswith("[CONTEXT SUMMARY]")
                ):
                    old_summary = self.context_window.popleft()
                    self.current_context_tokens -= old_summary["tokens"]

                self.context_window.appendleft(summary)
                self.current_context_tokens += summary["tokens"]

    def _get_context_from_window(self) -> str:
        """Get conversation history from the sliding window"""
        if not self.context_window:
            return ""

        return "\n".join(entry["text"] for entry in self.context_window)

    def _build_full_prompt(
        self, context: str = "", loop_prompt: str = LOOP_PROMPT, system_prompt: str = ""
    ) -> str:
        """Build the complete prompt including system prompt, context, and loop prompt"""
        prompt_parts = []

        # Add system prompt if provided
        if system_prompt:
            prompt_parts.append(f"SYSTEM: {system_prompt}")

        # Add context if provided
        if context:
            prompt_parts.append(f"CONTEXT: {context}")

        # Add conversation history from sliding window
        history_context = self._get_context_from_window()
        if history_context:
            prompt_parts.append("CONVERSATION HISTORY:")
            prompt_parts.append(history_context)

        # Add current prompt
        prompt_parts.append(f"USER: {loop_prompt}")

        return "\n\n".join(prompt_parts)

    def is_new_day_at_6am(self):
        """Check if we've passed a 6 AM threshold since last check"""
        if not self.simulation:
            return False

        current_time = self.simulation.get_current_time()

        # Calculate the 6 AM time for the current day
        current_6am = current_time.replace(hour=6, minute=0, second=0, microsecond=0)

        # If this is the first check, initialize with current day's 6 AM
        if self.last_6am_time is None:
            self.last_6am_time = current_6am
            # If current time is at or past 6 AM, trigger new day
            return current_time >= current_6am

        # Check if we've passed the last recorded 6 AM time
        if current_time >= self.last_6am_time + timedelta(days=1):
            # Update to the next day's 6 AM for future checks
            self.last_6am_time = current_6am + timedelta(days=1)
            return True

        return False

    def run_agent(
        self,
        context: str = "",
        loop_prompt: str = LOOP_PROMPT,
        system_prompt: str = None,
    ) -> str:
        """
        Run the agent with given context and prompt

        Args:
            context: Additional context to provide to the agent
            loop_prompt: The prompt to send (defaults to standard loop prompt)
            system_prompt: System prompt to provide instructions to the agent (defaults to self.system_prompt)

        Returns:
            The agent's response
        """
        # Use instance system prompt if none provided
        if system_prompt is None:
            system_prompt = self.system_prompt

        # Check if it's 6 AM and handle daily processing
        if self.simulation and self.is_new_day_at_6am():
            # New day processing - delegate to simulation for business logic
            context = self.simulation.handle_new_day()

            print(f"\n🌅 NEW DAY REPORT")
            print("=" * 50)
            print(context)
            print("=" * 50)

        # Build the full prompt
        full_prompt = self._build_full_prompt(context, loop_prompt, system_prompt)

        # Store the user prompt in history
        user_entry = {
            "role": "user",
            "content": loop_prompt,
            "timestamp": self._get_timestamp(),
        }
        self.conversation_history.append(user_entry)
        user_entry["context"] = context
        self._add_to_context_window(user_entry)

        # Get response from model with tools
        model_type = None
        if self.simulation and self.simulation.model_type:
            model_type = self.simulation.model_type
        model_kwargs = {"tools": TOOLS_LIST}
        if model_type:
            model_kwargs["model_type"] = model_type
        model_result = call_model(full_prompt, **model_kwargs)

        response_text = model_result.get("content", "")
        tool_calls = model_result.get("tool_calls", None)

        # Handle tool call if present (single tool only)
        if tool_calls:
            tool_call = tool_calls[0]  # Only one due to model_client restriction

            # Execute the tool using centralized function
            tool_result = execute_tool(tool_call, self.simulation)

            # Append tool result message to response
            response_text += tool_result["message"]
        elif model_result.get("content") and not tool_calls:
            # Agent generated content but no valid tool calls
            # This might indicate a truncation issue - add a note
            if len(response_text) > 3000:  # Likely hit token limit
                response_text += "\n\n[Note: Response may have been truncated. Consider simpler actions or fewer details.]"

        # Store the agent's response in history
        assistant_entry = {
            "role": "assistant",
            "content": response_text,
            "timestamp": self._get_timestamp(),
        }
        self.conversation_history.append(assistant_entry)
        self._add_to_context_window(assistant_entry)

        # Log message to database if store_state is enabled
        if self.simulation and self.simulation.store_state:
            self.simulation.db.log_message(
                simulation_id=self.simulation.simulation_id,
                timestamp=self.simulation.get_current_time(),
                prompt=full_prompt,
                response=response_text,
                tool_calls=tool_calls,
            )

        return response_text

    def _get_timestamp(self) -> str:
        """Get current timestamp for logging"""
        return self.simulation.get_current_time().isoformat()


def test_agent():
    """Test the VendingMachineAgent with a 10-message conversation"""

    print("🤖 Starting VendingMachineAgent Test")
    print("=" * 50)

    # Initialize agent
    agent = VendingMachineAgent(
        "TestBot", max_context_tokens=5000
    )  # Smaller for testing

    # Test context - simulate basic vending machine scenario
    # base_context = """
    # VENDING MACHINE STATUS:
    # - Balance: $500
    # - Inventory: 5 Coke ($2.00), 3 Pepsi ($2.00), 8 Chips ($1.50), 2 Candy ($1.00)
    # - Location: Office building lobby
    # - Daily fee: $2.00
    # - Weather: Sunny
    # """
    base_context = ""

    print(f"System Prompt: {SYSTEM_PROMPT.strip()}")
    print(f"Base Context: {base_context.strip()}")
    print("\n" + "=" * 50)

    # Run 10 message exchanges
    for i in range(1, 11):
        print(f"\n🔄 MESSAGE {i}/10")
        print("-" * 30)

        try:
            # Get agent response
            print("⏳ Sending prompt to agent...")
            import time

            start_time = time.time()

            response = agent.run_agent(
                context=base_context,
            )

            end_time = time.time()

            print(f"🤖 Agent Response (took {end_time - start_time:.2f}s):")
            print(f"   {response}")

            # Show context window status
            print(
                f"📊 Context Window: {agent.current_context_tokens} tokens, {len(agent.context_window)} entries"
            )

        except Exception as e:
            print(f"❌ Error on message {i}: {str(e)}")
            break

    print("\n" + "=" * 50)
    print("📈 FINAL STATISTICS")
    print(f"Total conversation history: {len(agent.conversation_history)} entries")
    print(f"Context window size: {len(agent.context_window)} entries")
    print(f"Current context tokens: {agent.current_context_tokens}")

    # Show last few exchanges
    print("\n📝 LAST 3 EXCHANGES:")
    for entry in agent.conversation_history[-6:]:  # Last 3 user-assistant pairs
        role_emoji = "👤" if entry["role"] == "user" else "🤖"
        print(f"{role_emoji} {entry['role'].upper()}: {entry['content'][:100]}...")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    test_agent()
