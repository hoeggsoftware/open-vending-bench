"""
Simple reporting script for the vending‑bench simulation.
It connects to the SQLite database (default path /home/hnai/vending_simulation.db)
and prints concise summaries:
- Balance evolution over time
- Number of emails sent/received
- Current back‑room storage inventory
- Sales totals per day
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("/home/hnai/vending_simulation.db")


def _connect():
    return sqlite3.connect(DB_PATH)


def balance_over_time(conn):
    print("--- Balance over time ---")
    for row in conn.execute(
        "SELECT timestamp, balance FROM simulation_state ORDER BY timestamp"
    ):
        print(f"{row[0]}  ->  ${row[1]:.2f}")
    print()


def email_summary(conn):
    print("--- Email summary ---")
    total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    inbound = conn.execute(
        "SELECT COUNT(*) FROM emails WHERE direction='inbound'"
    ).fetchone()[0]
    outbound = conn.execute(
        "SELECT COUNT(*) FROM emails WHERE direction='outbound'"
    ).fetchone()[0]
    print(f"Total emails: {total} (inbound: {inbound}, outbound: {outbound})")
    print()


def storage_report(conn):
    print("--- Back‑room storage ---")
    cur = conn.execute("SELECT item, quantity FROM inventory")
    rows = cur.fetchall()
    if not rows:
        print("Storage is empty.")
    else:
        total_value = 0.0
        for item, qty in rows:
            # No unit cost stored; just report quantity.
            print(f"{item:20} qty={qty:<4}")
            # If you ever add cost tracking, uncomment the following lines:
            # value = qty * cost
            # total_value += value
            # print(f"{item:20} qty={qty:<4} unit_cost=${cost:.2f}  value=${value:.2f}")
        print(f"Total storage value: ${total_value:.2f}")
    print()


def sales_summary(conn):
    print("--- Sales summary ---")
    cur = conn.execute(
        "SELECT timestamp, product, quantity, revenue FROM sales ORDER BY timestamp"
    )
    rows = cur.fetchall()
    if not rows:
        print("No sales recorded yet.")
    else:
        daily = {}
        for ts, prod, qty, rev in rows:
            day = ts.split("T")[0]
            daily.setdefault(day, 0.0)
            daily[day] += rev
        for day, total in sorted(daily.items()):
            print(f"{day}: ${total:.2f}")
    print()


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return
    conn = _connect()
    try:
        balance_over_time(conn)
        email_summary(conn)
        storage_report(conn)
        sales_summary(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
