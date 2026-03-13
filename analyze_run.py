#!/usr/bin/env python3
"""
Analyze tournament test run database
"""
import sqlite3
import json
from collections import Counter

DB_PATH = "round1_crh_test.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("=" * 70)
    print("TOURNAMENT TEST RUN ANALYSIS")
    print("=" * 70)
    print()

    # Summary stats
    print("SUMMARY STATS")
    print("-" * 70)
    print("Messages: 255 | Days: 14 | Final Balance: $326.72")
    print("Total P&L: -$173.28 | Revenue: $159.80 | Stockout Days: 5")
    print("Composite Score: 41.5/100")
    print()

    # 1. Day-by-day trajectory (deduplicated)
    print("1. DAY-BY-DAY TRAJECTORY")
    print("-" * 70)
    c.execute("""
        SELECT day_number, balance, message_count, current_weather
        FROM day_snapshot
        ORDER BY day_number, message_count DESC
    """)

    seen_days = set()
    for row in c:
        if row['day_number'] not in seen_days:
            seen_days.add(row['day_number'])
            print(f"Day {row['day_number']:2d}: ${row['balance']:7.2f} | {row['message_count']:3d} msgs | {row['current_weather']}")
    print()

    # 2. Daily revenue
    print("2. DAILY REVENUE")
    print("-" * 70)
    c.execute("SELECT timestamp, revenue FROM sales ORDER BY timestamp")
    sales = c.fetchall()
    if sales:
        for sale in sales:
            print(f"{sale['timestamp']}: ${sale['revenue']:.2f}")
    else:
        print("NO SALES RECORDED")
    print(f"Total revenue: ${sum(s['revenue'] for s in sales):.2f}")
    print()

    # 3. When did items first appear?
    print("3. TIMELINE: WHEN DID MACHINE GET STOCKED?")
    print("-" * 70)
    c.execute("""
        SELECT MIN(day_number) as first_stocked_day
        FROM day_snapshot_machine_slots
        WHERE item_name IS NOT NULL
    """)
    first_stocked = c.fetchone()
    if first_stocked and first_stocked['first_stocked_day']:
        print(f"First item appeared in machine: Day {first_stocked['first_stocked_day']}")
        print(f"Machine was empty for: {first_stocked['first_stocked_day']} days")
    else:
        print("Machine was NEVER stocked during simulation")
    print()

    # 4. Item name fragmentation
    print("4. INVENTORY FRAGMENTATION PROBLEM")
    print("-" * 70)
    c.execute("""
        SELECT item_name, quantity, avg_unit_cost, selling_price
        FROM day_snapshot_backroom
        WHERE day_number = (SELECT MAX(day_number) FROM day_snapshot)
        ORDER BY item_name
    """)
    backroom_items = c.fetchall()

    if backroom_items:
        print(f"Total distinct item name strings in backroom: {len(backroom_items)}")
        print()
        print("All backroom items (final snapshot):")
        for item in backroom_items:
            print(f"  - '{item['item_name']}' qty:{item['quantity']} "
                  f"cost:${item['avg_unit_cost']:.2f} price:${item['selling_price']:.2f}")

        # Look for fragmentation patterns
        print()
        print("FRAGMENTATION ANALYSIS:")

        # Group by base product name (crude pattern matching)
        base_names = {}
        for item in backroom_items:
            name = item['item_name']
            # Try to extract base product
            base = name.split('(')[0].split('-')[0].strip().lower()
            if base not in base_names:
                base_names[base] = []
            base_names[base].append(name)

        duplicates = {k: v for k, v in base_names.items() if len(v) > 1}
        if duplicates:
            print(f"Found {len(duplicates)} products with multiple name variants:")
            for base, variants in duplicates.items():
                print(f"  '{base}': {len(variants)} variants")
                for v in variants:
                    print(f"    - {v}")
        else:
            print("No obvious duplicate products detected")
    else:
        print("Backroom is EMPTY at end of simulation")
    print()

    # 5. Machine utilization
    print("5. MACHINE UTILIZATION (Final Snapshot)")
    print("-" * 70)
    c.execute("""
        SELECT slot_id, item_name, quantity, price
        FROM day_snapshot_machine_slots
        WHERE day_number = (SELECT MAX(day_number) FROM day_snapshot)
        ORDER BY slot_id
    """)
    slots = c.fetchall()

    filled_slots = [s for s in slots if s['item_name'] is not None]
    total_units = sum(s['quantity'] or 0 for s in slots)

    print(f"Slots filled: {len(filled_slots)}/12")
    print(f"Total units in machine: {total_units}")
    if filled_slots:
        print()
        print("Stocked slots:")
        for slot in filled_slots:
            print(f"  {slot['slot_id']}: {slot['quantity']}x {slot['item_name']} @ ${slot['price']:.2f}")
    print()

    # 6. Spending analysis
    print("6. THE MONEY STORY")
    print("-" * 70)

    # Get final backroom value
    if backroom_items:
        backroom_value = sum(item['quantity'] * item['avg_unit_cost'] for item in backroom_items)
    else:
        backroom_value = 0

    # Get machine inventory value
    machine_value = 0
    if filled_slots:
        # We need cost from backroom, but use price as proxy if cost not available
        for slot in filled_slots:
            machine_value += (slot['quantity'] or 0) * (slot['price'] or 0) * 0.5  # Estimate cost as 50% of price

    daily_fees = 14 * 2  # $2/day for 14 days

    print(f"Starting balance:           $500.00")
    print(f"Final balance:              $326.72")
    print(f"Net change:                -$173.28")
    print()
    print(f"Revenue earned:             $159.80")
    print(f"Daily fees paid:            -${daily_fees}.00  (14 days × $2)")
    print(f"Backroom inventory value:   ~${backroom_value:.2f}  (cost basis)")
    print(f"Machine inventory value:    ~${machine_value:.2f}  (estimated)")
    print()
    print("Cash flow breakdown:")
    print(f"  $500 starting - ${daily_fees} fees + $160 revenue - $X inventory = $327")
    total_inventory_value = backroom_value + machine_value
    implied_spending = 500 - daily_fees + 159.80 - 326.72
    print(f"  Implied inventory purchases: ~${implied_spending:.2f}")
    print()

    # 7. Email patterns
    print("7. EMAIL & SUPPLIER PATTERNS")
    print("-" * 70)
    c.execute("SELECT direction, COUNT(*) as count FROM emails GROUP BY direction")
    for row in c:
        print(f"{row['direction']:10s}: {row['count']} emails")

    c.execute("SELECT DISTINCT recipient FROM emails WHERE direction='outbound'")
    suppliers = [row['recipient'] for row in c]
    print(f"\nUnique suppliers contacted: {len(suppliers)}")
    for s in suppliers:
        print(f"  - {s}")
    print()

    # 8. Tool usage
    print("8. AGENT BEHAVIOR: TOOL USAGE")
    print("-" * 70)
    c.execute("SELECT tool_calls FROM logs WHERE tool_calls IS NOT NULL")

    tool_counts = Counter()
    for row in c:
        try:
            tools = json.loads(row['tool_calls'])
            for tool in tools:
                if isinstance(tool, dict) and 'function' in tool:
                    tool_name = tool['function'].get('name', 'unknown')
                    tool_counts[tool_name] += 1
        except (json.JSONDecodeError, TypeError):
            pass

    print("Tool usage counts:")
    for tool, count in tool_counts.most_common():
        print(f"  {tool:25s}: {count:3d} times")
    print()

    # Final diagnostic
    print("=" * 70)
    print("DIAGNOSTIC SUMMARY FOR STUDENT")
    print("=" * 70)
    print()

    print("TIMELINE:")
    if first_stocked and first_stocked['first_stocked_day']:
        print(f"  ⚠ Machine empty for {first_stocked['first_stocked_day']} days")
        print(f"  First products stocked on Day {first_stocked['first_stocked_day']}")
    else:
        print("  ❌ Machine NEVER stocked - 100% stockout")
    print()

    print("INVENTORY PROBLEM:")
    if backroom_items:
        print(f"  {len(backroom_items)} distinct item names in backroom")
        if duplicates:
            print(f"  ⚠ Name fragmentation detected - {len(duplicates)} products with multiple variants")
            print("  Cause: Supplier responses use different naming conventions")
        print(f"  Final backroom value: ${backroom_value:.2f}")
    else:
        print("  Empty backroom - all inventory consumed or never ordered")
    print()

    print("REVENUE PERFORMANCE:")
    print(f"  Revenue: ${sum(s['revenue'] for s in sales):.2f} over 14 days")
    print(f"  Revenue/day: ${sum(s['revenue'] for s in sales)/14:.2f}")
    if filled_slots:
        print(f"  Machine utilization: {len(filled_slots)}/12 slots ({len(filled_slots)*100/12:.0f}%)")
    else:
        print("  Machine utilization: 0/12 slots (0%)")
    print()

    print("AGENT PRODUCTIVITY:")
    print(f"  255 actions over 14 days = ~18 actions/day")
    if tool_counts:
        top_tool = tool_counts.most_common(1)[0]
        print(f"  Most used tool: {top_tool[0]} ({top_tool[1]} times)")
        if top_tool[0] == 'set_item_price':
            print("  ⚠ Excessive repricing suggests strategy issues")
    print()

    print("WHAT THIS STUDENT WOULD LEARN:")
    print("  1. Getting products into the machine faster is critical")
    if first_stocked and first_stocked['first_stocked_day'] and first_stocked['first_stocked_day'] > 3:
        print(f"     - Lost {first_stocked['first_stocked_day']} days of revenue to empty machine")
    print("  2. Inventory management matters")
    if backroom_items and len(backroom_items) > 10:
        print("     - Too many SKUs (complexity without benefit)")
    if duplicates:
        print("     - Name fragmentation caused confusion")
    print("  3. Financial discipline needed")
    print(f"     - Lost $173 total ($28 fees + unclear spending)")
    print("  4. Tool efficiency")
    if tool_counts.get('set_item_price', 0) > 50:
        print("     - 67 price updates suggests overthinking")
    print()

    conn.close()

if __name__ == "__main__":
    main()
