"""
Repository pattern — data access layer.

All database operations go through this class.
Business logic never touches SQL directly.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from src.database.manager import DatabaseManager

logger = logging.getLogger("token_monitor.database.repository")


class Repository:
    """Data access layer abstracting all SQLite operations."""

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize with a DatabaseManager instance.

        Args:
            db: The database manager.
        """
        self._db = db

    # ── Request Logs ────────────────────────────────────────────

    def insert_request_log(self, data: dict[str, Any]) -> int:
        """Insert a new request log entry.

        Args:
            data: Dict with keys: timestamp, provider, model, endpoint,
                  input_tokens, output_tokens, total_tokens,
                  cache_read_tokens, cache_write_tokens,
                  cost, currency, latency_ms, status_code.

        Returns:
            The new row ID.
        """
        cursor = self._db.execute(
            """INSERT INTO request_logs
               (timestamp, provider, model, endpoint,
                input_tokens, output_tokens, total_tokens,
                cache_read_tokens, cache_write_tokens,
                cost, currency, latency_ms, status_code)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("timestamp", datetime.utcnow().timestamp()),
                data["provider"],
                data["model"],
                data.get("endpoint", ""),
                data.get("input_tokens", 0),
                data.get("output_tokens", 0),
                data.get("total_tokens", 0),
                data.get("cache_read_tokens", 0),
                data.get("cache_write_tokens", 0),
                data.get("cost", 0.0),
                data.get("currency", "USD"),
                data.get("latency_ms", 0.0),
                data.get("status_code", 200),
            ),
        )
        return cursor.lastrowid or 0

    def get_recent_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get the most recent request logs.

        Args:
            limit: Maximum number of rows to return.

        Returns:
            List of request log dicts.
        """
        rows = self._db.execute(
            "SELECT * FROM request_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_requests_by_date(self, target_date: str) -> list[dict[str, Any]]:
        """Get all request logs for a specific date.

        Args:
            target_date: Date string in YYYY-MM-DD format.

        Returns:
            List of request log dicts.
        """
        start_ts = datetime.strptime(target_date, "%Y-%m-%d").timestamp()
        end_ts = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).timestamp()
        rows = self._db.execute(
            "SELECT * FROM request_logs WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp DESC",
            (start_ts, end_ts),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Daily Stats ─────────────────────────────────────────────

    def upsert_daily_stats(self, data: dict[str, Any]) -> None:
        """Insert or update daily aggregated stats.

        Args:
            data: Dict with: date, provider, model, input_tokens,
                  output_tokens, total_tokens, request_count, cost, currency.
        """
        self._db.execute(
            """INSERT INTO daily_stats
               (date, provider, model, input_tokens, output_tokens,
                total_tokens, request_count, cost, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(date, provider, model) DO UPDATE SET
                input_tokens = input_tokens + excluded.input_tokens,
                output_tokens = output_tokens + excluded.output_tokens,
                total_tokens = total_tokens + excluded.total_tokens,
                request_count = request_count + excluded.request_count,
                cost = cost + excluded.cost""",
            (
                data["date"],
                data["provider"],
                data["model"],
                data.get("input_tokens", 0),
                data.get("output_tokens", 0),
                data.get("total_tokens", 0),
                data.get("request_count", 1),
                data.get("cost", 0.0),
                data.get("currency", "USD"),
            ),
        )

    def get_daily_stats(self, target_date: str) -> list[dict[str, Any]]:
        """Get daily stats for a specific date.

        Args:
            target_date: Date string YYYY-MM-DD.

        Returns:
            List of daily stat dicts.
        """
        rows = self._db.execute(
            "SELECT * FROM daily_stats WHERE date = ? ORDER BY total_tokens DESC",
            (target_date,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Get daily stats for a date range.

        Args:
            start_date: Start date YYYY-MM-DD (inclusive).
            end_date: End date YYYY-MM-DD (inclusive).

        Returns:
            List of daily stat dicts.
        """
        rows = self._db.execute(
            "SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date, total_tokens DESC",
            (start_date, end_date),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_total_tokens_for_date(self, target_date: str) -> int:
        """Get total tokens for a specific date.

        Args:
            target_date: Date string YYYY-MM-DD.

        Returns:
            Total token count.
        """
        row = self._db.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) as total FROM daily_stats WHERE date = ?",
            (target_date,),
        ).fetchone()
        return row["total"] if row else 0

    def get_total_cost_for_date(self, target_date: str) -> float:
        """Get total cost for a specific date.

        Args:
            target_date: Date string YYYY-MM-DD.

        Returns:
            Total cost.
        """
        row = self._db.execute(
            "SELECT COALESCE(SUM(cost), 0.0) as total FROM daily_stats WHERE date = ?",
            (target_date,),
        ).fetchone()
        return row["total"] if row else 0.0

    def get_top_models_for_date(self, target_date: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get top models by token usage for a date.

        Args:
            target_date: Date string YYYY-MM-DD.
            limit: Max number of models to return.

        Returns:
            List of dicts with model, provider, total_tokens, cost.
        """
        rows = self._db.execute(
            """SELECT model, provider, SUM(total_tokens) as total_tokens, SUM(cost) as cost
               FROM daily_stats WHERE date = ? GROUP BY model, provider
               ORDER BY total_tokens DESC LIMIT ?""",
            (target_date, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_active_models_today(self) -> list[str]:
        """Get list of models used today.

        Returns:
            List of model names.
        """
        today = date.today().isoformat()
        rows = self._db.execute(
            "SELECT DISTINCT model FROM daily_stats WHERE date = ?",
            (today,),
        ).fetchall()
        return [r["model"] for r in rows]

    # ── Model Configs ───────────────────────────────────────────

    def get_all_models(self) -> list[dict[str, Any]]:
        """Get all model configurations."""
        rows = self._db.execute(
            "SELECT * FROM model_configs ORDER BY provider, model_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_enabled_models(self) -> list[dict[str, Any]]:
        """Get only enabled model configurations."""
        rows = self._db.execute(
            "SELECT * FROM model_configs WHERE enabled = 1 ORDER BY provider, model_name"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_model(self, provider: str, model_name: str) -> dict[str, Any] | None:
        """Get a specific model config.

        Args:
            provider: Provider name.
            model_name: Model name.

        Returns:
            Model config dict or None.
        """
        row = self._db.execute(
            "SELECT * FROM model_configs WHERE provider = ? AND model_name = ?",
            (provider, model_name),
        ).fetchone()
        return dict(row) if row else None

    def get_model_price(self, model_name: str) -> dict[str, Any] | None:
        """Get pricing for a model by name (fuzzy match).

        Args:
            model_name: Model name (exact or prefix match).

        Returns:
            Dict with input_price, output_price or None.
        """
        # Try exact match first
        row = self._db.execute(
            "SELECT * FROM model_configs WHERE model_name = ? AND enabled = 1",
            (model_name,),
        ).fetchone()
        if row:
            return dict(row)

        # Try prefix match (e.g., "gpt-4o-2024-08-06" matches "gpt-4o")
        row = self._db.execute(
            """SELECT * FROM model_configs
               WHERE ? LIKE (model_name || '%') AND enabled = 1
               ORDER BY LENGTH(model_name) DESC LIMIT 1""",
            (model_name,),
        ).fetchone()
        return dict(row) if row else None

    def insert_model(self, data: dict[str, Any]) -> int:
        """Insert a new model configuration.

        Args:
            data: Model config fields.

        Returns:
            New row ID.
        """
        cursor = self._db.execute(
            """INSERT INTO model_configs
               (provider, model_name, display_name, api_url,
                input_price, output_price, cache_read_price, cache_write_price,
                currency, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["provider"],
                data["model_name"],
                data.get("display_name", data["model_name"]),
                data.get("api_url", ""),
                data.get("input_price", 0.0),
                data.get("output_price", 0.0),
                data.get("cache_read_price", 0.0),
                data.get("cache_write_price", 0.0),
                data.get("currency", "USD"),
                data.get("enabled", 1),
            ),
        )
        return cursor.lastrowid or 0

    def update_model(self, model_id: int, data: dict[str, Any]) -> None:
        """Update a model configuration.

        Args:
            model_id: The model's ID.
            data: Fields to update.
        """
        fields = []
        values = []
        for key in ("provider", "model_name", "display_name", "api_url",
                     "input_price", "output_price", "cache_read_price",
                     "cache_write_price", "currency", "enabled"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])
        if not fields:
            return
        fields.append("updated_at = datetime('now')")
        values.append(model_id)
        self._db.execute(
            f"UPDATE model_configs SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )

    def delete_model(self, model_id: int) -> None:
        """Delete a model configuration.

        Args:
            model_id: The model's ID.
        """
        self._db.execute("DELETE FROM model_configs WHERE id = ?", (model_id,))

    # ── Budget ──────────────────────────────────────────────────

    def get_budget(self, budget_type: str) -> dict[str, Any] | None:
        """Get budget config for a type.

        Args:
            budget_type: 'daily', 'weekly', or 'monthly'.

        Returns:
            Budget dict or None.
        """
        row = self._db.execute(
            "SELECT * FROM budget_config WHERE budget_type = ? AND enabled = 1",
            (budget_type,),
        ).fetchone()
        return dict(row) if row else None

    def set_budget(self, budget_type: str, amount: float, currency: str = "USD") -> None:
        """Set or update a budget.

        Args:
            budget_type: 'daily', 'weekly', or 'monthly'.
            amount: Budget amount.
            currency: Currency code.
        """
        self._db.execute(
            """INSERT INTO budget_config (budget_type, amount, currency)
               VALUES (?, ?, ?)
               ON CONFLICT(budget_type) DO UPDATE SET amount = excluded.amount, currency = excluded.currency""",
            (budget_type, amount, currency),
        )

    def get_cost_in_range(self, start_date: str, end_date: str) -> float:
        """Get total cost for a date range.

        Args:
            start_date: Start date YYYY-MM-DD.
            end_date: End date YYYY-MM-DD.

        Returns:
            Total cost in the range.
        """
        row = self._db.execute(
            "SELECT COALESCE(SUM(cost), 0.0) as total FROM daily_stats WHERE date >= ? AND date <= ?",
            (start_date, end_date),
        ).fetchone()
        return row["total"] if row else 0.0

    # ── Settings ────────────────────────────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a setting value.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            Setting value or default.
        """
        row = self._db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value.

        Args:
            key: Setting key.
            value: Setting value.
        """
        self._db.execute(
            """INSERT INTO settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value),
        )

    def get_all_settings(self) -> dict[str, str]:
        """Get all settings as a dict."""
        return self._db.get_all_settings()
