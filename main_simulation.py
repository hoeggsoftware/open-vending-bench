# Main program entry point to run the economic agent simulation
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
from database import SimulationDatabase
from weather import generate_next_weather
from agent import VendingMachineAgent
from email_system import EmailSystem
from storage import StorageSystem
from vending_machine import VendingMachine
from economic_environment import calculate_total_sales_and_report
from scratchpad import Scratchpad
from kv_store import KVStore
from vector_db import SimpleVectorDB

STARTING_BALANCE = 500
DAILY_FEE = 2


class VendingMachineSimulation:
    def __init__(self, store_state=True, model_type=None):
        self.simulation_id = str(uuid.uuid4())
        self.balance = STARTING_BALANCE
        self.model_type = model_type
        # Backroom storage system (handles inventory AND deliveries)
        self.storage = StorageSystem()
        # Vending machine (4x3 slots)
        self.vending_machine = VendingMachine()
        # Memory systems
        self.scratchpad = Scratchpad()
        self.kv_store = KVStore()
        self.vector_db = SimpleVectorDB()
        # Sales tracking
        self.last_sales_report = "No sales data yet."
        self.last_sales_total = 0.0
        # Start at 6:00 AM UTC - the daily anchor time
        now = datetime.now(timezone.utc)
        self.current_time = datetime(
            now.year, now.month, now.day, 6, 0, 0, tzinfo=timezone.utc
        )
        # Initialize counters
        self.message_count = 0
        self.days_passed = 0
        # Initialize weather
        self.current_weather = "sunny"  # Start with sunny weather
        # Initialize database
        self.db = SimulationDatabase()
        # give DB a back‑reference so it can read the vending‑machine state when logging
        self.db.simulation = self
        # Initialize email system (needs db and simulation_id)
        self.email_system = EmailSystem(db=self.db, simulation_id=self.simulation_id)
        # Initialize agent
        self.agent = VendingMachineAgent("VendingBot", simulation_ref=self)
        self.store_state = store_state
        self.log_state()

    def get_current_time(self):
        return self.current_time

    def get_day_of_week(self):
        """Get current day of the week"""
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return days[self.current_time.weekday()]

    def get_month(self):
        """Get current month name"""
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        return months[self.current_time.month - 1]

    def log_state(self, include_day=False):
        """Log current state to database, optionally including day number."""
        if include_day:
            self.db.log_state(
                self.simulation_id,
                self.current_time,
                self.balance,
                day_number=self.days_passed,
            )
        else:
            self.db.log_state(self.simulation_id, self.current_time, self.balance)

    def advance_time(self, days=0, minutes=0):
        """Advance simulation time by specified days and minutes"""
        self.current_time += timedelta(days=days, minutes=minutes)
        return self.current_time

    def get_day_report(self):
        """Generate comprehensive daily report for the agent, now includes storage report"""
        day_of_week = self.get_day_of_week()
        month = self.get_month()
        day = self.current_time.day
        year = self.current_time.year
        time_str = self.current_time.strftime("%H:%M UTC")

        report = f"""
 DAILY BUSINESS REPORT - {day_of_week}, {month} {day}, {year} at {time_str}
 =================================================================
 
 FINANCIAL STATUS:
 - Current Balance: ${self.balance}
 - Days in Operation: {self.days_passed}
 - Daily Fee: ${DAILY_FEE}
 
 ENVIRONMENTAL CONDITIONS:
 - Weather: {self.current_weather}
 - Season: {self.get_season()}
 
 OPERATIONAL STATUS:
 - Total Messages/Actions: {self.message_count}
 - Simulation ID: {self.simulation_id}
 - Unread Emails: {len(self.email_system.get_unread_emails())}
 
 INVENTORY: (Placeholder - to be implemented)
 - [Inventory details will be added when vending machine integration is complete]
 
 BACKROOM STORAGE:
 {self.storage_report if hasattr(self, "storage_report") else "No storage report available."}
 
 YESTERDAY'S SALES: (Placeholder - to be implemented)
 - [Sales data will be added when sales simulation is integrated]
 
 ACTION REQUIRED: Continue managing your vending machine business.
 """
        return report.strip()

    def get_season(self):
        """Get current season based on month"""
        month = self.current_time.month
        if month in [12, 1, 2]:
            return "Winter"
        elif month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        else:
            return "Fall"

    def handle_new_day(self):
        """Handle daily processing and return daily report"""
        # New day processing
        if self.message_count > 1:  # Don't increment on first run
            self.days_passed += 1
            self.balance -= DAILY_FEE

        print(f"NEW DAY REACHED")

        # Generate weather for the new day
        self.current_weather = generate_next_weather(
            self.current_time.month, self.current_weather
        )

        # Simulate daily sales from the vending machine
        has_items = any(
            slot["item"] is not None
            for slot in self.vending_machine.get_slots().values()
        )
        if has_items:
            total_revenue, sales_report = calculate_total_sales_and_report(
                self.vending_machine,
                weather=self.current_weather,
                month=self.current_time.month,
                day_of_week=self.current_time.weekday(),
            )
            self.balance += total_revenue
            self.last_sales_report = sales_report
            self.last_sales_total = total_revenue
            # Log sales to database
            if self.store_state:
                self.db.log_sale(
                    self.simulation_id,
                    self.current_time,
                    "daily_total",
                    0,
                    total_revenue,
                )
        else:
            self.last_sales_report = (
                "No items in vending machine. Stock items to generate sales."
            )
            self.last_sales_total = 0.0

        # Generate supplier email responses (may schedule deliveries)
        self.email_system.generate_supplier_responses(self)

        # Process any arrivals scheduled for today
        def send_delivery_email(supplier, reference, body):
            self.email_system.receive_email(
                sender=supplier,
                subject="Delivery Notice",
                body=body,
                email_type="delivery_notice",
            )

        total_delivery_cost = self.storage.process_arrivals(
            self.current_time, on_arrival=send_delivery_email
        )
        self.balance -= total_delivery_cost

        # Log state with day number after daily processing
        self.log_state(include_day=True)

        # Get daily report for agent context
        return self.get_day_report()

    def run_agent(self):
        """Run the agent for one action"""
        self.message_count += 1

        # Run agent - it will handle 6 AM check internally
        response = self.agent.run_agent()

        print(f"ACTION #{self.message_count} at {self.current_time.strftime('%H:%M')}")
        print(f"Response: {response}")

        # Log state after each action
        if self.store_state:
            self.log_state()

        return response

    def start_simulation(self, max_messages):
        """Run agent-driven simulation until max_messages is reached"""
        print(f"🚀 Starting Agent-Driven VendingBench Simulation")
        print(f"Simulation ID: {self.simulation_id}")
        print(f"Starting time: {self.current_time.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Target messages: {max_messages}")
        print("=" * 60)

        while self.message_count < max_messages:
            try:
                # Run agent for one action
                self.run_agent()

                # Early exit if we've reached message limit
                if self.message_count >= max_messages:
                    break

            except KeyboardInterrupt:
                print("\n⏹Simulation interrupted by user")
                break
            except Exception as e:
                print(f"\nError during simulation: {e}")
                break

        print(f"\nSimulation complete")
        print(
            f"Final Stats: {self.message_count} messages, {self.days_passed} days, Balance: ${self.balance}"
        )


def run_simulation(max_messages=10):
    simulation = VendingMachineSimulation(store_state=False)

    try:
        simulation.start_simulation(max_messages)
    finally:
        simulation.db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="VendingBench Recreation - AI Agent Business Simulation"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=10,
        help="Maximum number of agent actions/messages (default: 10)",
    )

    args = parser.parse_args()

    simulation = VendingMachineSimulation(store_state=False)

    try:
        simulation.start_simulation(args.max_messages)
    finally:
        simulation.db.close()
