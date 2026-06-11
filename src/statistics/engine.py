"""
Statistics engine — aggregates usage data and produces summaries.

This is the core business logic that sits between the proxy layer
and the UI/database layers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from src.database.repository import Repository
from src.parser.base import UsageData
from src.statistics.calculator import CostCalculator, CostResult

logger = logging.getLogger("token_monitor.statistics.engine")


@dataclass
class StatsSummary:
    """Summary statistics for main page display."""

    today_tokens: int = 0
    week_tokens: int = 0
    month_tokens: int = 0
    today_input_tokens: int = 0
    today_output_tokens: int = 0
    today_cost: float = 0.0
    week_cost: float = 0.0
    month_cost: float = 0.0
    today_requests: int = 0
    active_models: list[str] = field(default_factory=list)
    top_models: list[dict[str, Any]] = field(default_factory=list)
    last_request_time: str | None = None


class StatisticsEngine:
    """Core statistics aggregation engine.

    Records usage data, updates daily aggregates, and provides
    query methods for the UI layer.
    """

    def __init__(self, repository: Repository, calculator: CostCalculator | None = None) -> None:
        """Initialize the statistics engine.

        Args:
            repository: Repository for database operations.
            calculator: CostCalculator instance. Created if not provided.
        """
        self._repository = repository
        self._calculator = calculator or CostCalculator(repository)

    def record(self, usage: UsageData) -> StatsSummary:
        """Record a new usage data point.

        This is the main entry point called after every completed request.
        It:
        1. Calculates cost
        2. Inserts into request_logs
        3. Upserts into daily_stats
        4. Returns updated summary for UI refresh

        Args:
            usage: Parsed UsageData from the proxy layer.

        Returns:
            Updated StatsSummary for immediate UI refresh.
        """
        # Calculate cost
        cost_result = self._calculator.calculate(
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_tokens,
            cache_write_tokens=usage.cache_write_tokens,
        )

        # Build request log entry
        log_entry = usage.to_dict()
        log_entry["cost"] = cost_result.total_cost
        log_entry["currency"] = cost_result.currency

        # Insert request log
        try:
            self._repository.insert_request_log(log_entry)
            logger.debug("Request log inserted: %s/%s", usage.provider, usage.model)
        except Exception as e:
            logger.error("Failed to insert request log: %s", e, exc_info=True)

        # Update daily stats
        today = date.today().isoformat()
        try:
            self._repository.upsert_daily_stats({
                "date": today,
                "provider": usage.provider,
                "model": usage.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "request_count": 1,
                "cost": cost_result.total_cost,
                "currency": cost_result.currency,
            })
        except Exception as e:
            logger.error("Failed to upsert daily stats: %s", e, exc_info=True)

        # Return updated summary
        return self.get_summary()

    def get_summary(self) -> StatsSummary:
        """Get current statistics summary for main page display.

        Returns:
            StatsSummary with today/week/month aggregates.
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        today_str = today.isoformat()
        week_start_str = week_start.isoformat()
        month_start_str = month_start.isoformat()

        # Query today's aggregate
        today_rows = self._repository.get_daily_stats(today_str)
        today_tokens = sum(r["total_tokens"] for r in today_rows)
        today_input = sum(r["input_tokens"] for r in today_rows)
        today_output = sum(r["output_tokens"] for r in today_rows)
        today_cost = float(sum(r["cost"] for r in today_rows))
        today_requests = sum(r["request_count"] for r in today_rows)

        # This week (Monday to today)
        week_rows = self._repository.get_stats_range(week_start_str, today_str)
        week_tokens = sum(r["total_tokens"] for r in week_rows)
        week_cost = float(sum(r["cost"] for r in week_rows))

        # This month
        month_rows = self._repository.get_stats_range(month_start_str, today_str)
        month_tokens = sum(r["total_tokens"] for r in month_rows)
        month_cost = float(sum(r["cost"] for r in month_rows))

        # Active models today
        active_models = list({r["model"] for r in today_rows})

        # Top models today
        top_models = sorted(today_rows, key=lambda r: r["total_tokens"], reverse=True)[:5]
        top_models_list = [
            {
                "model": r["model"],
                "provider": r["provider"],
                "total_tokens": r["total_tokens"],
                "cost": r["cost"],
            }
            for r in top_models
        ]

        # Last request time
        recent = self._repository.get_recent_requests(limit=1)
        last_time = None
        if recent:
            ts = recent[0].get("timestamp", 0)
            if ts:
                last_time = datetime.utcfromtimestamp(ts).strftime("%H:%M:%S")

        return StatsSummary(
            today_tokens=today_tokens,
            week_tokens=week_tokens,
            month_tokens=month_tokens,
            today_input_tokens=today_input,
            today_output_tokens=today_output,
            today_cost=round(today_cost, 4),
            week_cost=round(week_cost, 4),
            month_cost=round(month_cost, 4),
            today_requests=today_requests,
            active_models=active_models,
            top_models=top_models_list,
            last_request_time=last_time,
        )

    def get_history(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Get daily stats for a date range.

        Args:
            start_date: Start date YYYY-MM-DD (inclusive).
            end_date: End date YYYY-MM-DD (inclusive).

        Returns:
            List of daily stat rows.
        """
        return self._repository.get_stats_range(start_date, end_date)

    def get_recent_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent request logs.

        Args:
            limit: Max number of requests.

        Returns:
            List of request log dicts.
        """
        return self._repository.get_recent_requests(limit)

    def get_budget_status(self, budget_type: str = "daily") -> dict[str, Any]:
        """Check budget status and return percentage used.

        Args:
            budget_type: 'daily', 'weekly', or 'monthly'.

        Returns:
            Dict with budget amount, spent, percentage, and threshold flags.
        """
        budget = self._repository.get_budget(budget_type)
        if budget is None:
            return {"configured": False, "percentage": 0}

        today = date.today()
        if budget_type == "daily":
            start = today.isoformat()
            end = start
        elif budget_type == "weekly":
            start = (today - timedelta(days=today.weekday())).isoformat()
            end = today.isoformat()
        else:  # monthly
            start = today.replace(day=1).isoformat()
            end = today.isoformat()

        spent = self._repository.get_cost_in_range(start, end)
        amount = budget["amount"]
        percentage = round((spent / amount * 100), 1) if amount > 0 else 0.0

        return {
            "configured": True,
            "budget_type": budget_type,
            "amount": amount,
            "spent": round(spent, 4),
            "percentage": percentage,
            "currency": budget.get("currency", "USD"),
            "trigger_80": percentage >= 80 and budget.get("notify_80"),
            "trigger_90": percentage >= 90 and budget.get("notify_90"),
            "trigger_100": percentage >= 100 and budget.get("notify_100"),
        }

    @property
    def calculator(self) -> CostCalculator:
        """Get the cost calculator instance."""
        return self._calculator
