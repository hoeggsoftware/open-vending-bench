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

    args = parser.parse_args()

    store_state = not args.no_store_state

    if args.verbose:
        print(f"Configuration:")
        print(f"  Max messages: {args.max_messages}")
        print(f"  Model: {args.model or 'default'}")
        print(f"  Store state: {store_state}")
        print(f"  Evaluate: {args.evaluate}")
        print()

    simulation = VendingMachineSimulation(
        store_state=store_state,
        model_type=args.model,
    )

    if args.starting_balance is not None:
        simulation.balance = args.starting_balance

    try:
        simulation.start_simulation(args.max_messages)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    finally:
        if args.evaluate and store_state:
            from evaluation import SimulationEvaluator

            evaluator = SimulationEvaluator(simulation.db.db_path)
            evaluator.print_report(simulation.simulation_id)
            evaluator.close()

        simulation.db.close()
        print("Simulation complete.")


if __name__ == "__main__":
    main()
