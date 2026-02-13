import sqlite3
from datetime import datetime


class SimulationDatabase:
    def __init__(self, db_path="vending_simulation.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        """Create simulation tracking tables"""
        cursor = self.conn.cursor()

        # Main simulation state table (balance tracking)
        # Additional tables for detailed logging
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_progress (
                day_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                weather TEXT,
                PRIMARY KEY (day_number, simulation_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather (
                day_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                condition TEXT,
                PRIMARY KEY (day_number, simulation_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_state (
                timestamp TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                balance REAL NOT NULL,
                PRIMARY KEY (timestamp, simulation_id)
            );
            CREATE TABLE IF NOT EXISTS machine_slots (
                slot_id TEXT NOT NULL,
                simulation_id TEXT NOT NULL,
                item TEXT,
                quantity INTEGER,
                size_type TEXT,
                PRIMARY KEY (slot_id, simulation_id)
            )        """)

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
        if hasattr(self, 'simulation') and hasattr(self.simulation, 'vending_machine'):
            for slot_id, slot in self.simulation.vending_machine.get_slots().items():
                item_name = slot['item'].name if slot['item'] else None
                qty = slot['quantity']
                size = slot['size_type']
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO machine_slots (slot_id, simulation_id, item, quantity, size_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (slot_id, simulation_id, item_name, qty, size),
                )
        self.conn.commit()        """Log current simulation state (balance, optional day number)"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO simulation_state (timestamp, simulation_id, balance)
            VALUES (?, ?, ?)
            """,
            (timestamp.isoformat(), simulation_id, balance),
        )
        # Optional time/day tracking
        if day_number is not None:
            cursor.execute(
                "INSERT OR REPLACE INTO time_progress (day_number, timestamp, simulation_id, weather) VALUES (?, ?, ?, ?)",
                (day_number, timestamp.isoformat(), simulation_id, None),
            )
        self.conn.commit()

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
