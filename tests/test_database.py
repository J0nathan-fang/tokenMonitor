"""
Tests for the database layer: DatabaseManager and Repository.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.manager import DatabaseManager
from src.database.repository import Repository


class TestDatabaseManager(unittest.TestCase):
    """Test DatabaseManager schema and basic operations."""

    def setUp(self) -> None:
        """Create a temporary database for each test."""
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = DatabaseManager(self._tmp.name)
        self.db.initialize_schema()

    def tearDown(self) -> None:
        """Clean up the temporary database."""
        self.db.close()
        os.unlink(self._tmp.name)

    def test_schema_created(self) -> None:
        """Verify all tables are created."""
        tables = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in tables}
        expected = {"request_logs", "daily_stats", "model_configs", "budget_config", "settings"}
        self.assertTrue(expected.issubset(table_names), f"Missing tables: {expected - table_names}")

    def test_default_settings(self) -> None:
        """Verify default settings are inserted."""
        settings = self.db.get_all_settings()
        self.assertIn("proxy_port", settings)
        self.assertEqual(settings["proxy_port"], "7890")
        self.assertIn("theme", settings)
        self.assertEqual(settings["theme"], "dark")

    def test_insert_and_query(self) -> None:
        """Test basic insert and select."""
        self.db.execute(
            "INSERT INTO request_logs (timestamp, provider, model, input_tokens, output_tokens, total_tokens)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (1000.0, "openai", "gpt-4o", 100, 200, 300),
        )
        row = self.db.execute("SELECT * FROM request_logs WHERE provider = ?", ("openai",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["model"], "gpt-4o")
        self.assertEqual(row["total_tokens"], 300)


class TestRepository(unittest.TestCase):
    """Test Repository CRUD operations."""

    def setUp(self) -> None:
        """Create a temporary database and repository."""
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = DatabaseManager(self._tmp.name)
        self.db.initialize_schema()
        self.repo = Repository(self.db)

    def tearDown(self) -> None:
        """Clean up."""
        self.db.close()
        os.unlink(self._tmp.name)

    def test_insert_request_log(self) -> None:
        """Test inserting a request log."""
        rid = self.repo.insert_request_log({
            "timestamp": 1234567890.0,
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "input_tokens": 500,
            "output_tokens": 300,
            "total_tokens": 800,
            "cost": 0.015,
            "latency_ms": 1234.5,
        })
        self.assertGreater(rid, 0)

        logs = self.repo.get_recent_requests(limit=10)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["provider"], "anthropic")

    def test_upsert_daily_stats(self) -> None:
        """Test daily stats aggregation."""
        self.repo.upsert_daily_stats({
            "date": "2026-06-08",
            "provider": "openai",
            "model": "gpt-4o",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "request_count": 1,
            "cost": 0.00125,
        })
        # Second call should aggregate
        self.repo.upsert_daily_stats({
            "date": "2026-06-08",
            "provider": "openai",
            "model": "gpt-4o",
            "input_tokens": 200,
            "output_tokens": 100,
            "total_tokens": 300,
            "request_count": 2,
            "cost": 0.00250,
        })

        stats = self.repo.get_daily_stats("2026-06-08")
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["input_tokens"], 300)
        self.assertEqual(stats[0]["total_tokens"], 450)
        self.assertEqual(stats[0]["request_count"], 3)

    def test_model_crud(self) -> None:
        """Test model config CRUD operations."""
        # Insert
        mid = self.repo.insert_model({
            "provider": "openai",
            "model_name": "test-model",
            "display_name": "Test Model",
            "input_price": 1.0,
            "output_price": 2.0,
        })
        self.assertGreater(mid, 0)

        # Read
        model = self.repo.get_model("openai", "test-model")
        self.assertIsNotNone(model)
        self.assertEqual(model["input_price"], 1.0)

        # Update
        self.repo.update_model(mid, {"input_price": 3.0})
        model = self.repo.get_model("openai", "test-model")
        self.assertEqual(model["input_price"], 3.0)

        # Delete
        self.repo.delete_model(mid)
        model = self.repo.get_model("openai", "test-model")
        self.assertIsNone(model)

    def test_budget_crud(self) -> None:
        """Test budget config operations."""
        self.repo.set_budget("daily", 10.0)
        budget = self.repo.get_budget("daily")
        self.assertIsNotNone(budget)
        self.assertEqual(budget["amount"], 10.0)

    def test_settings(self) -> None:
        """Test settings get/set."""
        val = self.repo.get_setting("proxy_port")
        self.assertEqual(val, "7890")

        self.repo.set_setting("proxy_port", "9999")
        val = self.repo.get_setting("proxy_port")
        self.assertEqual(val, "9999")


if __name__ == "__main__":
    unittest.main()
