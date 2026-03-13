# Main program entry point to run the economic agent simulation
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from database import SimulationDatabase
from weather import generate_next_weather
from agent import VendingMachineAgent
from email_system import EmailSystem, Email
from storage import StorageSystem
from vending_machine import VendingMachine
from economic_environment import calculate_total_sales_and_report
from scratchpad import Scratchpad
from kv_store import KVStore
from vector_db import SimpleVectorDB

STARTING_BALANCE = 500
DAILY_FEE = 2


class VendingMachineSimulation:
    def __init__(
        self,
        store_state=True,
        model_type=None,
        db_path=None,
        starting_balance=None,
        start_date=None,
        weather_seed=None,
        strategy_prompt=None,
        playbook=None,
        kv_persist_path=None,
    ):
        import random

        self.simulation_id = str(uuid.uuid4())
        self.balance = starting_balance if starting_balance is not None else STARTING_BALANCE
        self.model_type = model_type

        # Apply weather seed if provided (before any random calls)
        if weather_seed is not None:
            random.seed(weather_seed)

        # Backroom storage system (handles inventory AND deliveries)
        self.storage = StorageSystem()
        # Vending machine (4x3 slots)
        self.vending_machine = VendingMachine()
        # Memory systems
        self.scratchpad = Scratchpad()
        # KV store with optional custom persist path
        if kv_persist_path is not None:
            self.kv_store = KVStore(persist_path=kv_persist_path)
        else:
            self.kv_store = KVStore()
        self.vector_db = SimpleVectorDB()

        # Load playbook into KV store if provided
        if playbook is not None:
            self.kv_store.set("playbook", playbook)

        # Sales tracking
        self.last_sales_report = "No sales data yet."
        self.last_sales_total = 0.0

        # Set start time - use provided date or default to today at 6:00 AM UTC
        if start_date is not None:
            # Handle both datetime.date and string formats
            if isinstance(start_date, str):
                from datetime import date
                year, month, day = map(int, start_date.split('-'))
                self.current_time = datetime(year, month, day, 6, 0, 0, tzinfo=timezone.utc)
            else:
                # Assume it's a datetime.date object
                self.current_time = datetime(
                    start_date.year, start_date.month, start_date.day, 6, 0, 0, tzinfo=timezone.utc
                )
        else:
            now = datetime.now(timezone.utc)
            self.current_time = datetime(
                now.year, now.month, now.day, 6, 0, 0, tzinfo=timezone.utc
            )

        # Initialize counters
        self.message_count = 0
        self.days_passed = 0
        # Initialize weather
        self.current_weather = "sunny"  # Start with sunny weather
        # Day boundary flag for message budget stopping
        self._at_day_boundary = True  # Start at a boundary (beginning of day)

        # Initialize database with optional custom path
        if db_path is not None:
            self.db = SimulationDatabase(db_path=db_path)
        else:
            self.db = SimulationDatabase()

        # give DB a back‑reference so it can read the vending‑machine state when logging
        self.db.simulation = self
        # Initialize email system (needs db and simulation_id)
        self.email_system = EmailSystem(db=self.db, simulation_id=self.simulation_id)

        # Store strategy prompt for agent
        self.strategy_prompt = strategy_prompt

        # Initialize agent with custom strategy prompt if provided
        self.agent = VendingMachineAgent("VendingBot", simulation_ref=self, system_prompt=strategy_prompt)
        self.store_state = store_state
        self.log_state()

        # Capture initial state snapshot (day 0)
        if self.store_state:
            self.db.log_day_snapshot(self)

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

    def _get_inventory_summary(self):
        """Generate a concise inventory summary for the daily report"""
        slots = self.vending_machine.get_slots()
        stocked_count = sum(1 for slot in slots.values() if slot['item'] is not None)
        total_items = sum(slot['quantity'] for slot in slots.values())

        if stocked_count == 0:
            return " - Machine is empty (0/12 slots stocked, 0 total items)"

        lines = [f" - {stocked_count}/12 slots stocked, {total_items} total items"]
        # Show top 3 products by quantity
        product_totals = {}
        for slot in slots.values():
            if slot['item']:
                name = slot['item'].name
                product_totals[name] = product_totals.get(name, 0) + slot['quantity']

        if product_totals:
            top_3 = sorted(product_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            for product, qty in top_3:
                lines.append(f" - {product}: {qty} units")

        return "\n".join(lines)

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

 VENDING MACHINE INVENTORY:
 {self._get_inventory_summary()}

 BACKROOM STORAGE:
 {self.storage_report if hasattr(self, "storage_report") else "No storage report available."}

 YESTERDAY'S SALES:
 {self.last_sales_report if hasattr(self, "last_sales_report") else "No sales yet - machine not stocked."}
 
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

        # Generate storage report so get_day_report() can use it (bug fix)
        self.storage_report = self.storage.get_storage_report()

        # Log state with day number after daily processing
        self.log_state(include_day=True)

        # Capture full day snapshot for reporting and restore
        if self.store_state:
            self.db.log_day_snapshot(self)

        # Set day boundary flag (used by message budget stopping)
        self._at_day_boundary = True

        # Get daily report for agent context
        return self.get_day_report()

    def run_agent(self):
        """Run the agent for one action"""
        # Clear day boundary flag when starting a new action
        self._at_day_boundary = False

        self.message_count += 1

        # Run agent - it will handle 6 AM check internally
        response = self.agent.run_agent()

        print(f"ACTION #{self.message_count} at {self.current_time.strftime('%H:%M')}")
        print(f"Response: {response}")

        # Log state after each action
        if self.store_state:
            self.log_state()

        return response

    def start_simulation(self, message_budget):
        """Run simulation for message_budget additional agent actions, stopping at a day boundary."""
        target = self.message_count + message_budget
        budget_exhausted = False

        print(f"Starting simulation")
        print(f"Simulation ID: {self.simulation_id}")
        print(f"Starting time: {self.current_time.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"Message budget: {message_budget} (starting from {self.message_count})")
        print("=" * 60)

        while True:
            try:
                self.run_agent()

                if self.message_count >= target:
                    budget_exhausted = True

                # If budget is exhausted, keep running until we hit a day boundary
                if budget_exhausted and self._at_day_boundary:
                    break

            except KeyboardInterrupt:
                print("\nSimulation interrupted by user")
                break
            except Exception as e:
                print(f"\nError during simulation: {e}")
                break

        print(f"\nSimulation complete")
        print(f"Final Stats: {self.message_count} messages, {self.days_passed} days, Balance: ${self.balance}")

    @classmethod
    def from_database(
        cls,
        db_path,
        model_type=None,
        store_state=True,
        strategy_prompt=None,
        playbook=None,
        start_date=None,
        weather_seed=None,
        kv_persist_path=None,
    ):
        """
        Construct a VendingMachineSimulation from the latest day snapshot
        in the given database. Used to resume a simulation after a pause.

        Args:
            db_path: Path to existing SQLite database with snapshot data
            model_type: AI model to use for the restored simulation
            store_state: Whether to continue logging to the database
            strategy_prompt: Optional new strategy prompt to use
            playbook: Optional new playbook to load
            start_date: Optional date to override current_time (for season changes)
            weather_seed: Optional weather seed to override
            kv_persist_path: Optional custom KV store persist path

        Returns:
            A VendingMachineSimulation with all state restored from the snapshot
        """
        import sqlite3
        import json
        import random
        from collections import Counter
        from vending_machine import Item

        # Open the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Read the latest day_snapshot row
        cursor.execute(
            "SELECT * FROM day_snapshot ORDER BY day_number DESC LIMIT 1"
        )
        snapshot_row = cursor.fetchone()
        if not snapshot_row:
            raise ValueError("No day snapshot found in database")

        # Parse the snapshot row (column order matches CREATE TABLE)
        (
            day_number,
            simulation_id,
            timestamp,
            balance,
            message_count,
            days_passed,
            current_weather,
            current_month,
            current_day,
            current_year,
            last_sales_total,
            phase,
        ) = snapshot_row

        # Create a new instance using object.__new__ to bypass __init__
        instance = object.__new__(cls)

        # Restore basic attributes
        instance.simulation_id = simulation_id
        instance.balance = balance
        instance.message_count = message_count
        instance.days_passed = days_passed
        instance.current_weather = current_weather
        instance.last_sales_total = last_sales_total
        instance.model_type = model_type
        instance.store_state = False  # Temporarily disable to avoid double-logging during restore

        # Apply weather seed if provided
        if weather_seed is not None:
            random.seed(weather_seed)

        # Restore or override current_time
        if start_date is not None:
            # Override with new date (for Round 2->3 season change)
            if isinstance(start_date, str):
                year, month, day = map(int, start_date.split('-'))
                instance.current_time = datetime(year, month, day, 6, 0, 0, tzinfo=timezone.utc)
            else:
                instance.current_time = datetime(
                    start_date.year, start_date.month, start_date.day, 6, 0, 0, tzinfo=timezone.utc
                )
        else:
            # Restore from snapshot
            instance.current_time = datetime(
                current_year, current_month, current_day, 6, 0, 0, tzinfo=timezone.utc
            )

        # Initialize storage system
        instance.storage = StorageSystem()

        # Restore backroom inventory
        cursor.execute(
            """
            SELECT item_name, item_size, quantity, avg_unit_cost, selling_price
            FROM day_snapshot_backroom
            WHERE day_number = ? AND simulation_id = ?
            """,
            (day_number, simulation_id),
        )
        for item_name, item_size, quantity, avg_unit_cost, selling_price in cursor.fetchall():
            item = Item(item_name, item_size, selling_price, avg_unit_cost)
            instance.storage.items[item_name] = {
                "item": item,
                "quantity": quantity,
                "avg_unit_cost": avg_unit_cost,
            }

        # Restore pending deliveries
        cursor.execute(
            """
            SELECT arrival_time, supplier, items_json, reference
            FROM day_snapshot_pending_deliveries
            WHERE day_number = ? AND simulation_id = ?
            ORDER BY delivery_index
            """,
            (day_number, simulation_id),
        )
        for arrival_time_str, supplier, items_json, reference in cursor.fetchall():
            from datetime import datetime as dt
            arrival_time = dt.fromisoformat(arrival_time_str)
            items = json.loads(items_json)
            delivery = {
                "arrival_time": arrival_time,
                "supplier": supplier,
                "items": items,
                "reference": reference,
            }
            instance.storage.pending_deliveries.append(delivery)

        # Initialize vending machine
        instance.vending_machine = VendingMachine()

        # Restore machine slots
        cursor.execute(
            """
            SELECT slot_id, item_name, item_size, quantity, price, cost
            FROM day_snapshot_machine_slots
            WHERE day_number = ? AND simulation_id = ?
            """,
            (day_number, simulation_id),
        )
        for slot_id, item_name, item_size, quantity, price, cost in cursor.fetchall():
            if item_name is not None:
                item = Item(item_name, item_size, price, cost)
                instance.vending_machine.slots[slot_id]["item"] = item
                instance.vending_machine.slots[slot_id]["quantity"] = quantity

        # Restore scratchpad
        instance.scratchpad = Scratchpad()
        cursor.execute(
            "SELECT content FROM day_snapshot_scratchpad WHERE day_number = ? AND simulation_id = ?",
            (day_number, simulation_id),
        )
        scratchpad_row = cursor.fetchone()
        if scratchpad_row:
            instance.scratchpad.content = scratchpad_row[0]

        # Restore KV store (with override for playbook)
        if kv_persist_path is not None:
            instance.kv_store = KVStore(persist_path=kv_persist_path, skip_file_load=True)
        else:
            instance.kv_store = KVStore(skip_file_load=True)

        cursor.execute(
            "SELECT data_json FROM day_snapshot_kv_store WHERE day_number = ? AND simulation_id = ?",
            (day_number, simulation_id),
        )
        kv_row = cursor.fetchone()
        if kv_row:
            instance.kv_store.data = json.loads(kv_row[0])

        # Override playbook if provided
        if playbook is not None:
            instance.kv_store.data["playbook"] = playbook

        # Restore vector DB
        instance.vector_db = SimpleVectorDB()
        cursor.execute(
            "SELECT documents_json, next_id FROM day_snapshot_vector_db WHERE day_number = ? AND simulation_id = ?",
            (day_number, simulation_id),
        )
        vector_row = cursor.fetchone()
        if vector_row:
            documents_json, next_id = vector_row
            parsed_docs = json.loads(documents_json)
            for doc_data in parsed_docs:
                doc = {
                    "id": doc_data["id"],
                    "text": doc_data["text"],
                    "terms": Counter(instance.vector_db._tokenize(doc_data["text"])),
                }
                instance.vector_db.documents.append(doc)
            instance.vector_db.next_id = next_id

        # Point to the same database
        instance.db = SimulationDatabase(db_path=db_path)
        instance.db.simulation = instance

        # Restore email system
        instance.email_system = EmailSystem(db=instance.db, simulation_id=simulation_id)

        # Restore emails from the emails table
        cursor.execute(
            "SELECT timestamp, direction, email_id, sender, recipient, subject, body FROM emails WHERE simulation_id = ? ORDER BY timestamp",
            (simulation_id,),
        )
        all_emails = cursor.fetchall()
        total_email_count = len(all_emails)

        for email_timestamp, direction, email_id, sender, recipient, subject, body in all_emails:
            email = Email(sender, recipient, subject, body)
            email.id = email_id
            email.timestamp = datetime.fromisoformat(email_timestamp)
            email.read = True  # Mark all restored emails as read

            if direction == "inbound":
                instance.email_system.inbox.append(email)
            else:
                instance.email_system.outbox.append(email)

        # Set email counter to total count
        instance.email_system.email_counter = total_email_count

        # Restore recipient profiles
        cursor.execute(
            "SELECT email_address, profile_text FROM day_snapshot_recipient_profiles WHERE day_number = ? AND simulation_id = ?",
            (day_number, simulation_id),
        )
        for email_address, profile_text in cursor.fetchall():
            instance.email_system.recipient_profiles[email_address] = profile_text

        # Initialize other attributes
        instance.last_sales_report = "Simulation restored from checkpoint."
        instance._at_day_boundary = True  # Restored at a clean boundary

        # Store strategy prompt or use provided one
        instance.strategy_prompt = strategy_prompt

        # Initialize agent with custom strategy prompt if provided
        instance.agent = VendingMachineAgent(
            "VendingBot",
            simulation_ref=instance,
            system_prompt=strategy_prompt,
        )

        # Re-enable state storage as requested
        instance.store_state = store_state

        conn.close()

        return instance


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
