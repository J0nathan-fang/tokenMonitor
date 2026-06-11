"""
Main page — primary overview of token usage and costs.

Shows stat cards, model distribution chart, and recent requests.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.event_bus import EventBus
from src.services.stats_service import StatsService
from src.ui.widgets.chart_widgets import ModelDistributionChart
from src.ui.widgets.request_table import RequestTableWidget
from src.ui.widgets.token_card import TokenCard, format_cost, format_token_count
from src.utils.i18n import tr


class DashboardPage(QWidget):
    """Main overview page with real-time statistics."""

    def __init__(
        self,
        stats_service: StatsService,
        event_bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the main page.

        Args:
            stats_service: Statistics service for data queries.
            event_bus: Event bus for real-time updates.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._stats = stats_service
        self._event_bus = event_bus

        self._setup_ui()

        # Connect to event bus for real-time updates
        self._event_bus.stats_updated.connect(self.refresh)
        self._event_bus.new_request.connect(lambda _: self.refresh())

        # Initial data load
        self.refresh()

        # Auto-refresh timer (every 5 seconds as fallback)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)

    def _setup_ui(self) -> None:
        """Build the main page layout."""
        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        main = QWidget()
        scroll.setWidget(main)

        layout = QVBoxLayout(main)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(24)

        # Header
        self._header = QLabel(tr("main.title"))
        self._header.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(self._header)

        # Stat cards grid
        cards_grid = QGridLayout()
        cards_grid.setSpacing(14)

        self._card_today_tokens = TokenCard(
            tr("main.today_tokens"), "—", "", accent_color="#58a6ff",
        )
        self._card_today_cost = TokenCard(
            tr("main.today_cost"), "—", "", accent_color="#3fb950",
        )
        self._card_week_tokens = TokenCard(
            tr("main.week_tokens"), "—", "", accent_color="#a371f7",
        )
        self._card_month_tokens = TokenCard(
            tr("main.month_tokens"), "—", "", accent_color="#d2991d",
        )
        self._card_month_cost = TokenCard(
            tr("main.month_cost"), "—", "", accent_color="#f85149",
        )
        self._card_active_models = TokenCard(
            tr("main.active_models"), "—", "", accent_color="#39c5cf",
        )

        cards_grid.addWidget(self._card_today_tokens, 0, 0)
        cards_grid.addWidget(self._card_today_cost, 0, 1)
        cards_grid.addWidget(self._card_week_tokens, 1, 0)
        cards_grid.addWidget(self._card_month_tokens, 1, 1)
        cards_grid.addWidget(self._card_month_cost, 2, 0)
        cards_grid.addWidget(self._card_active_models, 2, 1)

        layout.addLayout(cards_grid)

        # Bottom section: chart + recent requests
        bottom = QHBoxLayout()
        bottom.setSpacing(18)

        # Model distribution chart
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)

        self._chart_title = QLabel(tr("main.model_distribution"))
        self._chart_title.setProperty("subheading", True)
        self._chart_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #8b949e;")
        chart_layout.addWidget(self._chart_title)

        self._model_chart = ModelDistributionChart()
        chart_layout.addWidget(self._model_chart)
        bottom.addWidget(chart_container, stretch=2)

        # Recent requests
        requests_container = QWidget()
        requests_layout = QVBoxLayout(requests_container)
        requests_layout.setContentsMargins(0, 0, 0, 0)

        self._requests_title = QLabel(tr("main.recent_requests"))
        self._requests_title.setProperty("subheading", True)
        self._requests_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #8b949e;")
        requests_layout.addWidget(self._requests_title)

        self._request_table = RequestTableWidget()
        requests_layout.addWidget(self._request_table)
        bottom.addWidget(requests_container, stretch=3)

        layout.addLayout(bottom)

        # Outer layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self) -> None:
        """Refresh all main page data from the statistics service."""
        try:
            data = self._stats.get_main_data()
        except Exception:
            return

        summary = data.get("summary")
        if summary is None:
            return

        # Update cards
        self._card_today_tokens.set_value(format_token_count(summary.today_tokens))
        self._card_today_tokens.set_subtitle(
            tr("main.in_out",
               input=format_token_count(summary.today_input_tokens),
               output=format_token_count(summary.today_output_tokens))
        )

        self._card_today_cost.set_value(format_cost(summary.today_cost))
        self._card_today_cost.set_subtitle(
            tr("main.requests_today", n=summary.today_requests)
        )

        self._card_week_tokens.set_value(format_token_count(summary.week_tokens))
        self._card_week_tokens.set_subtitle(
            tr("main.week_cost", cost=format_cost(summary.week_cost))
        )

        self._card_month_tokens.set_value(format_token_count(summary.month_tokens))
        self._card_month_tokens.set_subtitle(
            tr("main.month_cost_label", cost=format_cost(summary.month_cost))
        )

        self._card_month_cost.set_value(format_cost(summary.month_cost))

        active_count = len(summary.active_models)
        self._card_active_models.set_value(str(active_count))
        if active_count > 0:
            self._card_active_models.set_subtitle(", ".join(summary.active_models[:3]))

        # Update chart
        top_models = summary.top_models
        if top_models:
            labels = [m["model"] for m in top_models]
            values = [m["total_tokens"] for m in top_models]
            self._model_chart.plot(labels, values)

        # Update recent requests table
        recent = data.get("recent_requests", [])
        self._request_table.load_data(recent)
