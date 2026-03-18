#!/usr/bin/env python
"""
VendingBench Simulation Runner - CLI entry point
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from main_simulation import VendingMachineSimulation


def main():
    parser = argparse.ArgumentParser(
        description="VendingBench - AI Agent Business Simulation Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_sim.py                          # Default: 50 messages, state stored
  python run_sim.py -m 200                   # Longer run
  python run_sim.py --model cerebras         # Use Cerebras model
  python run_sim.py --no-store-state         # Don't log to database
  python run_sim.py --evaluate               # Run evaluation after simulation
  python run_sim.py -m 100 -e -v             # 100 messages, evaluate, verbose
        """,
    )
    parser.add_argument(
        "--max-messages",
        "-m",
        type=int,
        default=50,
        help="Maximum number of agent messages/actions (default: 50)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (e.g., 'cerebras', 'claude-4-sonnet', 'gpt-4o')",
    )
    parser.add_argument(
        "--no-store-state",
        action="store_true",
        help="Disable database state logging",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--evaluate",
        "-e",
        action="store_true",
        help="Run evaluation report after simulation completes",
    )
    parser.add_argument(
        "--starting-balance",
        type=float,
        default=None,
        help="Override starting balance (default: $500)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to database file (for storing simulation state)",
    )
    parser.add_argument(
        "--strategy-prompt",
        type=str,
        default=None,
        help="Path to text file containing custom strategy/system prompt",
    )
    parser.add_argument(
        "--playbook",
        type=str,
        default=None,
        help="Path to text file containing playbook (loaded into KV store)",
    )
    parser.add_argument(
        "--weather-seed",
        type=int,
        default=None,
        help="Random seed for deterministic weather (for reproducible simulations)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Simulation start date in YYYY-MM-DD format (e.g., 2026-07-01)",
    )
    parser.add_argument(
        "--restore",
        type=str,
        default=None,
        help="Path to existing database to restore simulation from",
    )
    parser.add_argument(
        "--kv-persist-path",
        type=str,
        default=None,
        help="Custom path for KV store persistence file (for contestant isolation)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["internal", "server", "multi-server"],
        default="internal",
        help="Simulation mode: 'internal' (default, built-in agent), 'server' (MCP server for single external agent), or 'multi-server' (multi-tenant MCP server)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for MCP server mode (default: 8000)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Bearer token for MCP server auth (generates random UUID if not provided)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file for multi-server mode (defines contestants and their tokens)",
    )

    args = parser.parse_args()

    store_state = not args.no_store_state

    if args.verbose:
        print(f"Configuration:")
        print(f"  Max messages: {args.max_messages}")
        print(f"  Model: {args.model or 'default'}")
        print(f"  Store state: {store_state}")
        print(f"  Evaluate: {args.evaluate}")
        if args.restore:
            print(f"  Restore from: {args.restore}")
        if args.db_path:
            print(f"  Database path: {args.db_path}")
        if args.start_date:
            print(f"  Start date: {args.start_date}")
        if args.weather_seed is not None:
            print(f"  Weather seed: {args.weather_seed}")
        print()

    # Load strategy prompt from file if provided
    strategy_prompt = None
    if args.strategy_prompt:
        with open(args.strategy_prompt, 'r') as f:
            strategy_prompt = f.read()

    # Load playbook from file if provided
    playbook = None
    if args.playbook:
        with open(args.playbook, 'r') as f:
            playbook = f.read()

    # Create simulation for internal and server modes
    # (multi-server mode creates its own simulations from config file)
    simulation = None
    if args.mode != "multi-server":
        if args.restore:
            simulation = VendingMachineSimulation.from_database(
                db_path=args.restore,
                model_type=args.model,
                store_state=store_state,
                strategy_prompt=strategy_prompt,
                playbook=playbook,
                start_date=args.start_date,
                weather_seed=args.weather_seed,
                kv_persist_path=args.kv_persist_path,
            )
        else:
            simulation = VendingMachineSimulation(
                store_state=store_state,
                model_type=args.model,
                db_path=args.db_path,
                starting_balance=args.starting_balance,
                start_date=args.start_date,
                weather_seed=args.weather_seed,
                strategy_prompt=strategy_prompt,
                playbook=playbook,
                kv_persist_path=args.kv_persist_path,
            )

    try:
        if args.mode == "internal":
            # Internal mode: use built-in agent loop (existing behavior)
            simulation.start_simulation(args.max_messages)
        elif args.mode == "server":
            # Server mode: start MCP server for single external agent
            if args.no_store_state:
                print("ERROR: --no-store-state cannot be used with --mode server.")
                print("Server mode requires state logging for tournament scoring.")
                sys.exit(1)

            import uuid
            from mcp_server import MCPSimulationServer

            # Generate token if not provided
            token = args.token if args.token else str(uuid.uuid4())

            # Create and start MCP server
            server = MCPSimulationServer(
                simulation=simulation,
                message_budget=args.max_messages,
                port=args.port,
                token=token
            )
            server.start()
        else:
            # Multi-server mode: start multi-tenant MCP server for multiple contestants
            if not args.config:
                print("ERROR: --config is required for --mode multi-server")
                sys.exit(1)

            import yaml
            from mcp_server import MultiTenantMCPServer

            with open(args.config) as f:
                config = yaml.safe_load(f)

            server = MultiTenantMCPServer(
                contestants=config["contestants"],
                port=args.port,
            )
            server.start()

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    finally:
        # Only run evaluation and cleanup for internal/server modes
        # (multi-server mode manages its own database connections)
        if args.mode != "multi-server":
            if args.evaluate and store_state:
                from evaluation import SimulationEvaluator

                evaluator = SimulationEvaluator(simulation.db.db_path)
                evaluator.print_report(simulation.simulation_id)
                evaluator.close()

            simulation.db.close()
            print("Simulation complete.")


if __name__ == "__main__":
    main()
