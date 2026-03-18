import sqlite3
from datetime import datetime


class SimulationDatabase:
    # Optional back‑reference to the simulation (set by main_simulation)
    simulation = None

    def __init__(self, db_path="vending_simulation.db"):
        self.db_path = db_path
        # Allow connection to be used across threads (safe because tool calls are serialized)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        """Create all simulation tracking tables (one statement per execute)."""
        cursor = self.conn.cursor()
        # logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                prompt TEXT,
                response TEXT,
                tool_calls TEXT
            )
        """)
        # emails
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                direction TEXT CHECK(direction IN ('inbound','outbound')),
                email_id TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                body TEXT,
                PRIMARY KEY (timestamp, simulation_id, email_id)
            )
        """)
        # inventory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                item TEXT,
                quantity INTEGER,
                change_type TEXT,
                PRIMARY KEY (timestamp, simulation_id, item)
            )
        """)
        # sales
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                product TEXT,
                quantity INTEGER,
                revenue REAL,
                PRIMARY KEY (timestamp, simulation_id, product)
            )
        """)
        # time_progress
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_progress (
                day_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                weather TEXT,
                PRIMARY KEY (day_number, simulation_id)
            )
        """)
        # weather
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                day_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                condition TEXT,
                PRIMARY KEY (day_number, simulation_id)
            )
        """)
        # simulation_state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_state (
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                balance REAL NOT NULL,
                PRIMARY KEY (timestamp, simulation_id)
            )
        """)
        # machine_slots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machine_slots (
                slot_id TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                item TEXT,
                quantity INTEGER,
                size_type TEXT,
                PRIMARY KEY (slot_id, simulation_id)
            )
        """)

        # day_snapshot - Core state at each day boundary
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                balance REAL NOT NULL,
                message_count INTEGER NOT NULL,
                days_passed INTEGER NOT NULL,
                current_weather TEXT NOT NULL,
                current_month INTEGER NOT NULL,
                current_day INTEGER NOT NULL,
                current_year INTEGER NOT NULL,
                last_sales_total REAL NOT NULL DEFAULT 0.0,
                phase TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (day_number, simulation_id)
            )
        """)

        # day_snapshot_machine_slots - Full vending machine state
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_machine_slots (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                item_name TEXT,
                item_size TEXT,
                quantity INTEGER NOT NULL DEFAULT 0,
                price REAL,
                cost REAL,
                PRIMARY KEY (day_number, simulation_id, slot_id)
            )
        """)

        # day_snapshot_backroom - Backroom storage inventory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_backroom (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_size TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_unit_cost REAL NOT NULL,
                selling_price REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (day_number, simulation_id, item_name)
            )
        """)

        # day_snapshot_pending_deliveries - Ordered but undelivered shipments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_pending_deliveries (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                delivery_index INTEGER NOT NULL,
                arrival_time TEXT NOT NULL,
                supplier TEXT,
                items_json TEXT NOT NULL,
                reference TEXT,
                PRIMARY KEY (day_number, simulation_id, delivery_index)
            )
        """)

        # day_snapshot_scratchpad - Agent's scratchpad text
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_scratchpad (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (day_number, simulation_id)
            )
        """)

        # day_snapshot_kv_store - Key-value store as JSON blob
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_kv_store (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                data_json TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (day_number, simulation_id)
            )
        """)

        # day_snapshot_vector_db - Vector DB documents as JSON
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_vector_db (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                documents_json TEXT NOT NULL DEFAULT '[]',
                next_id INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (day_number, simulation_id)
            )
        """)

        # day_snapshot_recipient_profiles - Cached supplier profile data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS day_snapshot_recipient_profiles (
                day_number INTEGER NOT NULL,
                simulation_id TEXT NOT NULL,
                email_address TEXT NOT NULL,
                profile_text TEXT NOT NULL,
                PRIMARY KEY (day_number, simulation_id, email_address)
            )
        """)

        self.conn.commit()

    def log_state(self, simulation_id, timestamp, balance, day_number=None):
        """Log current simulation state (balance, optional day number) and vending‑machine slots."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO simulation_state (timestamp, simulation_id, balance)
            VALUES (?, ?, ?)
            """,
            (timestamp.isoformat(), simulation_id, balance),
        )
        # Optional day tracking
        if day_number is not None:
            cursor.execute(
                "INSERT OR REPLACE INTO time_progress (day_number, timestamp, simulation_id, weather) VALUES (?, ?, ?, ?)",
                (day_number, timestamp.isoformat(), simulation_id, None),
            )
        # Persist current vending‑machine slot states (if simulation holds a reference to the machine)
        if hasattr(self, "simulation") and hasattr(self.simulation, "vending_machine"):
            for slot_id, slot in self.simulation.vending_machine.get_slots().items():
                item_name = slot["item"].name if slot["item"] else None
                qty = slot["quantity"]
                size = slot["size_type"]
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO machine_slots (slot_id, simulation_id, item, quantity, size_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (slot_id, simulation_id, item_name, qty, size),
                )

    def log_message(self, simulation_id, timestamp, prompt, response, tool_calls=None):
        """Store an agent interaction (prompt, response, tool calls)."""
        import json

        cursor = self.conn.cursor()

        tool_calls_json = None
        if tool_calls:
            tool_calls_json = json.dumps(tool_calls)

        cursor.execute(
            """
            INSERT INTO logs (timestamp, simulation_id, prompt, response, tool_calls)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp.isoformat(),
                simulation_id,
                prompt,
                response,
                tool_calls_json,
            ),
        )
        self.conn.commit()

    def log_email(
        # Existing method unchanged
        self,
        simulation_id,
        timestamp,
        direction,
        email_id,
        sender,
        recipient,
        subject,
        body,
    ):
        """Record an inbound or outbound email."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO emails (timestamp, simulation_id, direction, email_id, sender, recipient, subject, body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp.isoformat(),
                simulation_id,
                direction,
                email_id,
                sender,
                recipient,
                subject,
                body,
            ),
        )
        self.conn.commit()

    def log_inventory(self, simulation_id, timestamp, item, quantity, change_type):
        """Track inventory changes (add/remove)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO inventory (timestamp, simulation_id, item, quantity, change_type)
            VALUES (?, ?, ?, ?, ?)
        """,
            (timestamp.isoformat(), simulation_id, item, quantity, change_type),
        )
        self.conn.commit()

    def log_sale(self, simulation_id, timestamp, product, quantity, revenue):
        """Record a sale event."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO sales (timestamp, simulation_id, product, quantity, revenue)
            VALUES (?, ?, ?, ?, ?)
        """,
            (timestamp.isoformat(), simulation_id, product, quantity, revenue),
        )
        self.conn.commit()

    def log_weather(self, simulation_id, day_number, timestamp, condition):
        """Store weather condition for a given day."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO weather (day_number, timestamp, simulation_id, condition)
            VALUES (?, ?, ?, ?)
        """,
            (day_number, timestamp.isoformat(), simulation_id, condition),
        )
        self.conn.commit()

    def log_day_snapshot(self, simulation):
        """
        Capture complete business state at a day boundary.
        Called at the end of handle_new_day() after all daily processing.
        """
        import json

        cursor = self.conn.cursor()
        day_number = simulation.days_passed
        simulation_id = simulation.simulation_id

        # 1. Core state snapshot
        cursor.execute(
            """
            INSERT OR REPLACE INTO day_snapshot
            (day_number, simulation_id, timestamp, balance, message_count, days_passed,
             current_weather, current_month, current_day, current_year, last_sales_total, phase)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                day_number,
                simulation_id,
                simulation.current_time.isoformat(),
                simulation.balance,
                simulation.message_count,
                simulation.days_passed,
                simulation.current_weather,
                simulation.current_time.month,
                simulation.current_time.day,
                simulation.current_time.year,
                simulation.last_sales_total,
                "",  # phase defaults to empty string
            ),
        )

        # 2. Machine slots snapshot
        for slot_id, slot in simulation.vending_machine.get_slots().items():
            item_name = slot["item"].name if slot["item"] else None
            item_size = slot["item"].size if slot["item"] else None
            quantity = slot["quantity"]
            price = slot["item"].price if slot["item"] else None
            cost = slot["item"].cost if slot["item"] else None

            cursor.execute(
                """
                INSERT OR REPLACE INTO day_snapshot_machine_slots
                (day_number, simulation_id, slot_id, item_name, item_size, quantity, price, cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (day_number, simulation_id, slot_id, item_name, item_size, quantity, price, cost),
            )

        # 3. Backroom inventory snapshot
        for item_name, record in simulation.storage.items.items():
            cursor.execute(
                """
                INSERT OR REPLACE INTO day_snapshot_backroom
                (day_number, simulation_id, item_name, item_size, quantity, avg_unit_cost, selling_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    day_number,
                    simulation_id,
                    item_name,
                    record["item"].size,
                    record["quantity"],
                    record["avg_unit_cost"],
                    record["item"].price,
                ),
            )

        # 4. Pending deliveries snapshot
        for delivery_index, delivery in enumerate(simulation.storage.pending_deliveries):
            cursor.execute(
                """
                INSERT OR REPLACE INTO day_snapshot_pending_deliveries
                (day_number, simulation_id, delivery_index, arrival_time, supplier, items_json, reference)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    day_number,
                    simulation_id,
                    delivery_index,
                    delivery["arrival_time"].isoformat(),
                    delivery.get("supplier"),
                    json.dumps(delivery["items"]),
                    delivery.get("reference"),
                ),
            )

        # 5. Scratchpad snapshot
        cursor.execute(
            """
            INSERT OR REPLACE INTO day_snapshot_scratchpad
            (day_number, simulation_id, content)
            VALUES (?, ?, ?)
            """,
            (day_number, simulation_id, simulation.scratchpad.content),
        )

        # 6. KV store snapshot
        cursor.execute(
            """
            INSERT OR REPLACE INTO day_snapshot_kv_store
            (day_number, simulation_id, data_json)
            VALUES (?, ?, ?)
            """,
            (day_number, simulation_id, json.dumps(simulation.kv_store.data)),
        )

        # 7. Vector DB snapshot
        documents_data = [
            {"id": doc["id"], "text": doc["text"]}
            for doc in simulation.vector_db.documents
        ]
        cursor.execute(
            """
            INSERT OR REPLACE INTO day_snapshot_vector_db
            (day_number, simulation_id, documents_json, next_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                day_number,
                simulation_id,
                json.dumps(documents_data),
                simulation.vector_db.next_id,
            ),
        )

        # 8. Recipient profiles snapshot
        for email_address, profile_text in simulation.email_system.recipient_profiles.items():
            cursor.execute(
                """
                INSERT OR REPLACE INTO day_snapshot_recipient_profiles
                (day_number, simulation_id, email_address, profile_text)
                VALUES (?, ?, ?, ?)
                """,
                (day_number, simulation_id, email_address, profile_text),
            )

        # Commit all changes in a single transaction
        self.conn.commit()

    def get_simulation_history(self, simulation_id):
        """Get all states for a simulation"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, balance FROM simulation_state
            WHERE simulation_id = ?
            ORDER BY timestamp
        """,
            (simulation_id,),
        )
        return cursor.fetchall()

    def close(self):
        """Close database connection"""
        self.conn.close()


def clear_database():
    """Clear all data from the simulation database"""
    db = SimulationDatabase()
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM simulation_state")
    db.conn.commit()
    print("Database cleared successfully")
    db.close()
