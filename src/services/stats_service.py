"""
Statistics service — high-level facade for UI to query statistics.

Provides convenience methods that the UI layer calls directly.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from src.database.repository import Repository
from src.statistics.engine import StatisticsEngine, StatsSummary

logger = logging.getLogger("token_monitor.services.stats")


class StatsService(QObject):
    """High-level statistics service for UI consumption.

    Wraps StatisticsEngine with Qt-friendly methods.
    """

    # Signal emitted when stats are updated
    summary_updated = pyqtSignal(object)  # StatsSummary
    budget_alert = pyqtSignal(str, int)   # (type, percentage)

    def __init__(self, engine: StatisticsEngine, repository: Repository) -> None:
        """Initialize the stats service.

        Args:
            engine: Statistics engine.
            repository: Database repository.
        """
        super().__init__()
        self._engine = engine
        self._repository = repository
        self._last_summary: StatsSummary | None = None

    def get_summary(self) -> StatsSummary:
        """Get current statistics summary.

        Returns:
            StatsSummary for main page display.
        """
        self._last_summary = self._engine.get_summary()
        self.summary_updated.emit(self._last_summary)
        return self._last_summary

    @property
    def last_summary(self) -> StatsSummary | None:
        """Get the most recently fetched summary."""
        if self._last_summary is None:
            self._last_summary = self._engine.get_summary()
        return self._last_summary

    def get_main_data(self) -> dict[str, Any]:
        """Get all data needed for the main page in one call.

        Returns:
            Dict with summary, top models, recent requests, and budget status.
        """
        summary = self._engine.get_summary()
        recent = self._engine.get_recent_requests(limit=20)
        budget = self._engine.get_budget_status("daily")
        week_budget = self._engine.get_budget_status("weekly")
        month_budget = self._engine.get_budget_status("monthly")

        return {
            "summary": summary,
            "recent_requests": recent,
            "daily_budget": budget,
            "weekly_budget": week_budget,
            "monthly_budget": month_budget,
        }

    def get_history_data(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """Get history data for a date range.

        Args:
            start_date: YYYY-MM-DD start.
            end_date: YYYY-MM-DD end.

        Returns:
            List of daily stat rows.
        """
        return self._engine.get_history(start_date, end_date)

    def get_recent_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent request logs.

        Args:
            limit: Max number of requests.

        Returns:
            List of request log dicts.
        """
        return self._repository.get_recent_requests(limit)

    def check_budgets(self) -> list[dict[str, Any]]:
        """Check all budgets and emit alerts if thresholds crossed.

        Returns:
            List of budget status dicts with alerts.
        """
        alerts = []
        for budget_type in ("daily", "weekly", "monthly"):
            status = self._engine.get_budget_status(budget_type)
            if status.get("trigger_100"):
                self.budget_alert.emit(budget_type, 100)
                alerts.append(status)
            elif status.get("trigger_90"):
                self.budget_alert.emit(budget_type, 90)
                alerts.append(status)
            elif status.get("trigger_80"):
                self.budget_alert.emit(budget_type, 80)
                alerts.append(status)
        return alerts

    def refresh_prices(self) -> None:
        """Refresh the price cache (call after model config changes)."""
        self._engine.calculator.refresh()
