"""
Tests for statistics engine and cost calculator.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.manager import DatabaseManager
from src.database.repository import Repository
from src.statistics.calculator import CostCalculator, CostResult
from src.statistics.engine import StatisticsEngine, StatsSummary
from src.parser.base import UsageData


class TestCostCalculator(unittest.TestCase):
    """Test cost calculation logic."""

    def setUp(self) -> None:
        """Set up with a real DB containing seeded models."""
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = DatabaseManager(self._tmp.name)
        self.db.initialize_schema()
        self.repo = Repository(self.db)

        # Seed test model prices
        self.repo.insert_model({
            "provider": "openai",
            "model_name": "gpt-4o",
            "display_name": "GPT-4o",
            "input_price": 2.50,
            "output_price": 10.00,
        })
        self.repo.insert_model({
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "input_price": 0.15,
            "output_price": 0.60,
        })
        self.repo.insert_model({
            "provider": "anthropic",
            "model_name": "claude-sonnet-4-20250514",
            "display_name": "Claude Sonnet 4",
            "input_price": 3.00,
            "output_price": 15.00,
        })

        self.calc = CostCalculator(self.repo)

    def tearDown(self) -> None:
        self.db.close()
        os.unlink(self._tmp.name)

    def test_gpt4o_pricing(self) -> None:
        """Test GPT-4o pricing: $2.50/1M input, $10.00/1M output."""
        result = self.calc.calculate(
            model="gpt-4o",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        self.assertAlmostEqual(result.input_cost, 2.50, places=2)
        self.assertAlmostEqual(result.output_cost, 10.00, places=2)
        self.assertAlmostEqual(result.total_cost, 12.50, places=2)

    def test_small_tokens(self) -> None:
        """Small token counts still calculate correctly."""
        result = self.calc.calculate(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
        )
        # gpt-4o-mini: $0.15/$0.60 per 1M
        # input: 1000 * 0.15/1M = 0.00015
        # output: 500 * 0.60/1M = 0.00030
        # total: 0.00045
        self.assertAlmostEqual(result.input_cost, 0.00015, places=6)
        self.assertAlmostEqual(result.output_cost, 0.00030, places=6)
        self.assertAlmostEqual(result.total_cost, 0.00045, places=6)

    def test_unknown_model_returns_zero(self) -> None:
        """Unknown models get zero pricing."""
        result = self.calc.calculate(
            model="nonexistent-model-xyz",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        self.assertAlmostEqual(result.total_cost, 0.0)

    def test_claude_pricing(self) -> None:
        """Test Claude Sonnet 4 pricing."""
        result = self.calc.calculate(
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        self.assertAlmostEqual(result.input_cost, 3.00, places=2)


class TestStatisticsEngine(unittest.TestCase):
    """Test statistics aggregation."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = DatabaseManager(self._tmp.name)
        self.db.initialize_schema()
        self.repo = Repository(self.db)
        self.calc = CostCalculator(self.repo)
        self.engine = StatisticsEngine(self.repo, self.calc)

    def tearDown(self) -> None:
        self.db.close()
        os.unlink(self._tmp.name)

    def test_record_single_request(self) -> None:
        """Record one request and verify summary."""
        usage = UsageData(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            latency_ms=200.0,
        )
        summary = self.engine.record(usage)

        self.assertIsInstance(summary, StatsSummary)
        self.assertGreaterEqual(summary.today_tokens, 1500)
        self.assertGreaterEqual(summary.today_requests, 1)

        # Verify DB has the data
        logs = self.repo.get_recent_requests(limit=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["model"], "gpt-4o")

    def test_record_multiple_requests(self) -> None:
        """Multiple records should aggregate correctly."""
        for i in range(5):
            self.engine.record(UsageData(
                provider="openai",
                model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
            ))

        summary = self.engine.get_summary()
        self.assertGreaterEqual(summary.today_tokens, 750)
        self.assertGreaterEqual(summary.today_requests, 5)

    def test_get_summary_returns_all_fields(self) -> None:
        """Summary should have all expected fields."""
        summary = self.engine.get_summary()
        self.assertIsNotNone(summary)
        self.assertIsInstance(summary.today_tokens, int)
        self.assertIsInstance(summary.today_cost, float)
        self.assertIsInstance(summary.active_models, list)
        self.assertIsInstance(summary.top_models, list)

    def test_budget_status_not_configured(self) -> None:
        """Budget status when no budget is set."""
        status = self.engine.get_budget_status("daily")
        self.assertFalse(status["configured"])


if __name__ == "__main__":
    unittest.main()
