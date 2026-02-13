"""
Evaluation harness for scoring simulation runs.
Reads from the SQLite database to compute performance metrics.
"""
import sqlite3
import json
from typing import Dict, List, Tuple


class SimulationEvaluator:
    def __init__(self, db_path: str = "vending_simulation.db"):
        self.conn = sqlite3.connect(db_path)

    def evaluate(self, simulation_id: str) -> Dict:
        """Run all metrics for a simulation and return a scored report."""
        metrics = {}
        metrics["balance_trajectory"] = self._balance_trajectory(simulation_id)
        metrics["total_profit_loss"] = self._total_profit_loss(simulation_id)
        metrics["total_revenue"] = self._total_revenue(simulation_id)
        metrics["revenue_per_day"] = self._revenue_per_day(simulation_id)
        metrics["inventory_turnover"] = self._inventory_turnover(simulation_id)
        metrics["stockout_days"] = self._stockout_days(simulation_id)
        metrics["tool_usage_stats"] = self._tool_usage_stats(simulation_id)
        metrics["total_messages"] = self._total_messages(simulation_id)
        metrics["email_stats"] = self._email_stats(simulation_id)
        metrics["days_operated"] = self._days_operated(simulation_id)
        metrics["composite_score"] = self._composite_score(metrics)
        return metrics

    def _balance_trajectory(self, sim_id: str) -> List[Tuple[str, float]]:
        """Get balance over time as [(timestamp, balance), ...]"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, balance FROM simulation_state "
            "WHERE simulation_id = ? ORDER BY timestamp",
            (sim_id,),
        )
        return cursor.fetchall()

    def _total_profit_loss(self, sim_id: str) -> float:
        """Final balance minus starting balance (500)"""
        trajectory = self._balance_trajectory(sim_id)
        if not trajectory:
            return 0.0
        return trajectory[-1][1] - 500.0

    def _total_revenue(self, sim_id: str) -> float:
        """Sum of all revenue from sales table"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(revenue), 0) FROM sales WHERE simulation_id = ?",
            (sim_id,),
        )
        return cursor.fetchone()[0]

    def _revenue_per_day(self, sim_id: str) -> float:
        """Average revenue per day of operation"""
        days = self._days_operated(sim_id)
        if days == 0:
            return 0.0
        return self._total_revenue(sim_id) / days

    def _days_operated(self, sim_id: str) -> int:
        """Number of days the simulation ran"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(day_number) FROM time_progress WHERE simulation_id = ?",
            (sim_id,),
        )
        result = cursor.fetchone()[0]
        return result if result is not None else 0

    def _inventory_turnover(self, sim_id: str) -> Dict[str, int]:
        """Units sold per product"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT product, SUM(quantity) FROM sales "
            "WHERE simulation_id = ? GROUP BY product",
            (sim_id,),
        )
        return dict(cursor.fetchall())

    def _stockout_days(self, sim_id: str) -> int:
        """Days where no sales occurred (proxy for empty machine)"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(DISTINCT tp.day_number) FROM time_progress tp "
            "WHERE tp.simulation_id = ? AND NOT EXISTS ("
            "  SELECT 1 FROM sales s WHERE s.simulation_id = tp.simulation_id "
            "  AND DATE(s.timestamp) = DATE(tp.timestamp))",
            (sim_id,),
        )
        return cursor.fetchone()[0]

    def _tool_usage_stats(self, sim_id: str) -> Dict[str, int]:
        """Parse tool_calls from logs to count tool usage"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT tool_calls FROM logs "
            "WHERE simulation_id = ? AND tool_calls IS NOT NULL",
            (sim_id,),
        )
        counts = {}
        for (tc_json,) in cursor.fetchall():
            try:
                calls = json.loads(tc_json)
                if isinstance(calls, list):
                    for call in calls:
                        if hasattr(call, "function"):
                            name = call.function.name
                        elif isinstance(call, dict):
                            name = call.get("function", {}).get("name", "unknown")
                        else:
                            name = "unknown"
                        counts[name] = counts.get(name, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        return counts

    def _total_messages(self, sim_id: str) -> int:
        """Total number of agent messages"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM logs WHERE simulation_id = ?",
            (sim_id,),
        )
        return cursor.fetchone()[0]

    def _email_stats(self, sim_id: str) -> Dict[str, int]:
        """Inbound and outbound email counts"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT direction, COUNT(*) FROM emails "
            "WHERE simulation_id = ? GROUP BY direction",
            (sim_id,),
        )
        return dict(cursor.fetchall())

    def _composite_score(self, metrics: Dict) -> float:
        """
        Weighted composite score (0-100 scale).
        Rewards profit, revenue, tool diversity.
        Penalizes stockout days.
        """
        score = 50.0  # baseline

        # Reward profit (max +30 for $300+ profit)
        profit = metrics.get("total_profit_loss", 0)
        score += min(profit / 10.0, 30.0)

        # Reward revenue per day (max +10)
        rpd = metrics.get("revenue_per_day", 0)
        score += min(rpd / 5.0, 10.0)

        # Penalize stockout days (max -10)
        stockouts = metrics.get("stockout_days", 0)
        score -= min(stockouts * 0.5, 10.0)

        # Reward tool diversity (max +10)
        tool_types = len(metrics.get("tool_usage_stats", {}))
        score += min(tool_types * 1.0, 10.0)

        return max(0.0, min(100.0, round(score, 1)))

    def print_report(self, simulation_id: str):
        """Print a formatted evaluation report"""
        metrics = self.evaluate(simulation_id)

        print()
        print("=" * 60)
        print("SIMULATION EVALUATION REPORT")
        print(f"Simulation ID: {simulation_id}")
        print("=" * 60)
        print(f"Days Operated:     {metrics['days_operated']}")
        print(f"Total Messages:    {metrics['total_messages']}")
        print(f"Total Profit/Loss: ${metrics['total_profit_loss']:.2f}")
        print(f"Total Revenue:     ${metrics['total_revenue']:.2f}")
        print(f"Revenue Per Day:   ${metrics['revenue_per_day']:.2f}")
        print(f"Stockout Days:     {metrics['stockout_days']}")
        print()

        tool_stats = metrics["tool_usage_stats"]
        if tool_stats:
            print("Tool Usage:")
            for tool, count in sorted(tool_stats.items(), key=lambda x: -x[1]):
                print(f"  {tool}: {count}")
        else:
            print("Tool Usage: None recorded")
        print()

        email_stats = metrics["email_stats"]
        if email_stats:
            print("Email Stats:")
            for direction, count in email_stats.items():
                print(f"  {direction}: {count}")
        else:
            print("Email Stats: None recorded")
        print()

        print(f"COMPOSITE SCORE: {metrics['composite_score']}/100")
        print("=" * 60)

    def close(self):
        """Close database connection"""
        self.conn.close()
