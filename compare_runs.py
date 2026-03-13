#!/usr/bin/env python3
"""
Compare V1 and V2 tournament test runs
"""
import sqlite3
from collections import Counter

V1_DB = "round1_crh_test.db"
V2_DB = "round1_v2_test.db"

def get_metrics(db_path):
    """Extract key metrics from a simulation database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    metrics = {}

    # Get final snapshot
    c.execute("SELECT * FROM day_snapshot ORDER BY day_number DESC LIMIT 1")
    final_day = c.fetchone()
    if final_day:
        metrics['final_balance'] = final_day['balance']
        metrics['days_operated'] = final_day['day_number']
        metrics['total_messages'] = final_day['message_count']

    # Get revenue
    c.execute("SELECT SUM(revenue) as total_revenue FROM sales")
    revenue = c.fetchone()
    metrics['total_revenue'] = revenue['total_revenue'] or 0.0

    # Calculate P&L
    starting_balance = 500.0
    metrics['total_pl'] = metrics['final_balance'] - starting_balance
    metrics['revenue_per_day'] = metrics['total_revenue'] / max(metrics['days_operated'], 1)

    # Get first stocked day
    c.execute("""
        SELECT MIN(day_number) as first_stocked
        FROM day_snapshot_machine_slots
        WHERE item_name IS NOT NULL
    """)
    first_stocked = c.fetchone()
    metrics['first_stocked_day'] = first_stocked['first_stocked'] if first_stocked and first_stocked['first_stocked'] else None

    # Get unique suppliers
    c.execute("SELECT DISTINCT recipient FROM emails WHERE direction='outbound'")
    suppliers = c.fetchall()
    metrics['unique_suppliers'] = len(suppliers)

    # Get distinct item names in backroom
    c.execute("""
        SELECT COUNT(DISTINCT item_name) as count
        FROM day_snapshot_backroom
        WHERE day_number = (SELECT MAX(day_number) FROM day_snapshot)
    """)
    backroom = c.fetchone()
    metrics['backroom_item_names'] = backroom['count'] if backroom else 0

    # Get final machine state
    c.execute("""
        SELECT COUNT(*) as filled, SUM(quantity) as total_qty
        FROM day_snapshot_machine_slots
        WHERE day_number = (SELECT MAX(day_number) FROM day_snapshot)
          AND item_name IS NOT NULL
    """)
    machine = c.fetchone()
    metrics['slots_filled'] = machine['filled'] if machine else 0
    metrics['machine_qty'] = machine['total_qty'] if machine and machine['total_qty'] else 0

    # Count stockout days
    c.execute("""
        SELECT COUNT(DISTINCT day_number) as stockout_days
        FROM day_snapshot ds
        WHERE NOT EXISTS (
            SELECT 1 FROM day_snapshot_machine_slots dms
            WHERE dms.day_number = ds.day_number
              AND dms.item_name IS NOT NULL
        )
    """)
    stockout = c.fetchone()
    metrics['stockout_days'] = stockout['stockout_days'] if stockout else metrics['days_operated']

    # Composite score (simplified calculation)
    revenue_score = min(metrics['total_revenue'] / 10, 40)  # Max 40 points
    speed_score = max(0, 30 - (metrics['first_stocked_day'] or 30) * 3) if metrics['first_stocked_day'] else 0  # Max 30 points
    utilization_score = (metrics['slots_filled'] / 12) * 30  # Max 30 points
    metrics['composite_score'] = revenue_score + speed_score + utilization_score

    conn.close()
    return metrics

def print_comparison():
    print("=" * 80)
    print("V1 vs V2 STRATEGY COMPARISON")
    print("=" * 80)
    print()

    v1 = get_metrics(V1_DB)
    v2 = get_metrics(V2_DB)

    print("| Metric | V1 (original) | V2 (improved) | Change |")
    print("|--------|---------------|---------------|--------|")

    def format_change(v1_val, v2_val, is_positive_good=True, is_money=False, is_int=False):
        if v1_val == v2_val:
            symbol = "="
        elif (v2_val > v1_val and is_positive_good) or (v2_val < v1_val and not is_positive_good):
            symbol = "✅"
        else:
            symbol = "⚠️"

        diff = v2_val - v1_val
        if is_money:
            change_str = f"${diff:+.2f}"
        elif is_int:
            change_str = f"{diff:+d}"
        else:
            change_str = f"{diff:+.2f}"

        return f"{symbol} {change_str}"

    print(f"| Final Balance | ${v1['final_balance']:.2f} | ${v2['final_balance']:.2f} | {format_change(v1['final_balance'], v2['final_balance'], True, True)} |")
    print(f"| Total P&L | ${v1['total_pl']:.2f} | ${v2['total_pl']:.2f} | {format_change(v1['total_pl'], v2['total_pl'], True, True)} |")
    print(f"| Total Revenue | ${v1['total_revenue']:.2f} | ${v2['total_revenue']:.2f} | {format_change(v1['total_revenue'], v2['total_revenue'], True, True)} |")
    print(f"| Revenue Per Day | ${v1['revenue_per_day']:.2f} | ${v2['revenue_per_day']:.2f} | {format_change(v1['revenue_per_day'], v2['revenue_per_day'], True, True)} |")
    print(f"| Days Operated | {v1['days_operated']} | {v2['days_operated']} | {format_change(v1['days_operated'], v2['days_operated'], True, False, True)} |")
    print(f"| Stockout Days | {v1['stockout_days']} | {v2['stockout_days']} | {format_change(v1['stockout_days'], v2['stockout_days'], False, False, True)} |")
    print(f"| Composite Score | {v1['composite_score']:.1f} | {v2['composite_score']:.1f} | {format_change(v1['composite_score'], v2['composite_score'], True)} |")
    print(f"| First Day with Items | Day {v1['first_stocked_day'] or 'Never'} | Day {v2['first_stocked_day'] or 'Never'} | {format_change(v1['first_stocked_day'] or 999, v2['first_stocked_day'] or 999, False, False, True) if v1['first_stocked_day'] and v2['first_stocked_day'] else 'N/A'} |")
    print(f"| Distinct Suppliers | {v1['unique_suppliers']} | {v2['unique_suppliers']} | {format_change(v1['unique_suppliers'], v2['unique_suppliers'], False, False, True)} |")
    print(f"| Backroom Item Names | {v1['backroom_item_names']} | {v2['backroom_item_names']} | {format_change(v1['backroom_item_names'], v2['backroom_item_names'], False, False, True)} |")
    print(f"| Slots Filled (final) | {v1['slots_filled']}/12 | {v2['slots_filled']}/12 | {format_change(v1['slots_filled'], v2['slots_filled'], True, False, True)} |")
    print(f"| Total Messages | {v1['total_messages']} | {v2['total_messages']} | {format_change(v1['total_messages'], v2['total_messages'], False, False, True)} |")

    print()
    print("=" * 80)
    print("NARRATIVE SUMMARY")
    print("=" * 80)
    print()

    # Speed to market
    if v2['first_stocked_day'] and v1['first_stocked_day']:
        if v2['first_stocked_day'] < v1['first_stocked_day']:
            print(f"✅ **Speed to Market Improved**: V2 stocked the machine {v1['first_stocked_day'] - v2['first_stocked_day']} days faster (Day {v2['first_stocked_day']} vs Day {v1['first_stocked_day']})")
        else:
            print(f"⚠️ **Speed to Market Worsened**: V2 took {v2['first_stocked_day'] - v1['first_stocked_day']} more days to stock (Day {v2['first_stocked_day']} vs Day {v1['first_stocked_day']})")

    # Supplier consolidation
    if v2['unique_suppliers'] < v1['unique_suppliers']:
        print(f"✅ **Supplier Consolidation Worked**: V2 used {v2['unique_suppliers']} suppliers vs V1's {v1['unique_suppliers']}, reducing fragmentation")
    else:
        print(f"⚠️ **Supplier Consolidation Failed**: V2 used {v2['unique_suppliers']} suppliers vs V1's {v1['unique_suppliers']}")

    # Item fragmentation
    if v2['backroom_item_names'] < v1['backroom_item_names']:
        print(f"✅ **Naming Discipline Improved**: V2 has {v2['backroom_item_names']} distinct items vs V1's {v1['backroom_item_names']}, better inventory management")
    else:
        print(f"⚠️ **Naming Discipline Not Effective**: V2 has {v2['backroom_item_names']} distinct items vs V1's {v1['backroom_item_names']}")

    # Financial performance
    revenue_change = v2['total_revenue'] - v1['total_revenue']
    if revenue_change > 0:
        print(f"✅ **Revenue Increased**: V2 earned ${revenue_change:.2f} more (${v2['total_revenue']:.2f} vs ${v1['total_revenue']:.2f})")
    else:
        print(f"⚠️ **Revenue Decreased**: V2 earned ${abs(revenue_change):.2f} less (${v2['total_revenue']:.2f} vs ${v1['total_revenue']:.2f})")

    # Overall
    score_change = v2['composite_score'] - v1['composite_score']
    print()
    if score_change > 5:
        print(f"**Overall**: The V2 strategy significantly outperformed V1 (+{score_change:.1f} points)")
    elif score_change > 0:
        print(f"**Overall**: The V2 strategy slightly outperformed V1 (+{score_change:.1f} points)")
    elif score_change > -5:
        print(f"**Overall**: The strategies performed similarly ({score_change:+.1f} points)")
    else:
        print(f"**Overall**: The V1 strategy outperformed V2 ({score_change:.1f} points)")
    print()

if __name__ == "__main__":
    print_comparison()
