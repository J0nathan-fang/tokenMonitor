"""
History page — view token usage over time with charts and export.

Supports daily, weekly, monthly, and custom date range views.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from typing import Any

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.services.stats_service import StatsService
from src.ui.widgets.chart_widgets import LineChartWidget, BarChartWidget
from src.utils.i18n import tr


class HistoryPage(QWidget):
    """History and analytics page with charts and data export."""

    def __init__(self, stats_service: StatsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._stats = stats_service
        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        """Build the history page layout."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        main = QWidget()
        scroll.setWidget(main)

        layout = QVBoxLayout(main)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # Header with controls
        header = QHBoxLayout()
        self._title = QLabel(tr("history.title"))
        self._title.setStyleSheet("font-size: 28px; font-weight: 700;")
        header.addWidget(self._title)
        header.addStretch()

        # Time range selector
        range_label = QLabel(tr("history.range"))
        header.addWidget(range_label)

        self._range_combo = QComboBox()
        self._range_combo.addItems([
            tr("history.range_today"),
            tr("history.range_7days"),
            tr("history.range_30days"),
            tr("history.range_month"),
            tr("history.range_custom"),
        ])
        self._range_combo.currentTextChanged.connect(self._on_range_changed)
        self._range_combo.setFixedWidth(180)
        header.addWidget(self._range_combo)

        # Custom date range
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDate(QDate.currentDate().addDays(-7))
        self._start_date.setVisible(False)
        header.addWidget(self._start_date)

        self._to_label = QLabel(tr("history.to"))
        self._to_label.setVisible(False)
        header.addWidget(self._to_label)

        self._end_date = QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setVisible(False)
        header.addWidget(self._end_date)

        # Export buttons
        self._export_csv_btn = QPushButton(tr("history.export_csv"))
        self._export_csv_btn.clicked.connect(self._export_csv)
        header.addWidget(self._export_csv_btn)

        self._export_excel_btn = QPushButton(tr("history.export_excel"))
        self._export_excel_btn.clicked.connect(self._export_excel)
        header.addWidget(self._export_excel_btn)

        layout.addLayout(header)

        # Charts area
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(18)

        # Token trend line chart
        token_container = QWidget()
        token_layout = QVBoxLayout(token_container)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.addWidget(QLabel(tr("history.token_trend")))
        self._token_chart = LineChartWidget(tr("history.tokens"))
        token_layout.addWidget(self._token_chart)
        charts_layout.addWidget(token_container)

        # Cost trend line chart
        cost_container = QWidget()
        cost_layout = QVBoxLayout(cost_container)
        cost_layout.setContentsMargins(0, 0, 0, 0)
        cost_layout.addWidget(QLabel(tr("history.cost_trend")))
        self._cost_chart = LineChartWidget(tr("history.cost_usd"))
        cost_layout.addWidget(self._cost_chart)
        charts_layout.addWidget(cost_container)

        layout.addLayout(charts_layout)

        # Bar chart for daily breakdown
        bar_section = QWidget()
        bar_layout = QVBoxLayout(bar_section)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(QLabel(tr("history.daily_breakdown")))
        self._bar_chart = BarChartWidget(tr("history.tokens"))
        bar_layout.addWidget(self._bar_chart)
        layout.addWidget(bar_section)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_range_changed(self, text: str) -> None:
        """Handle time range selection change."""
        is_custom = text == tr("history.range_custom")
        self._start_date.setVisible(is_custom)
        self._end_date.setVisible(is_custom)
        self._to_label.setVisible(is_custom)
        if not is_custom:
            self._load_data()

    def _get_date_range(self) -> tuple[str, str]:
        """Get the currently selected date range."""
        range_text = self._range_combo.currentText()
        today = date.today()

        if range_text == tr("history.range_today"):
            return today.isoformat(), today.isoformat()
        elif range_text == tr("history.range_7days"):
            start = today - timedelta(days=6)
            return start.isoformat(), today.isoformat()
        elif range_text == tr("history.range_30days"):
            start = today - timedelta(days=29)
            return start.isoformat(), today.isoformat()
        elif range_text == tr("history.range_month"):
            return today.replace(day=1).isoformat(), today.isoformat()
        else:
            start = self._start_date.date().toPyDate()
            end = self._end_date.date().toPyDate()
            return start.isoformat(), end.isoformat()

    def _load_data(self) -> None:
        """Load history data for the selected range and update charts."""
        start, end = self._get_date_range()
        rows = self._stats.get_history_data(start, end)

        if not rows:
            self._token_chart.plot([], [], "")
            self._cost_chart.plot([], [], "")
            self._bar_chart.plot([], [])
            return

        dates: dict[str, dict[str, float]] = {}
        for row in rows:
            d = row["date"]
            if d not in dates:
                dates[d] = {"tokens": 0, "cost": 0.0}
            dates[d]["tokens"] += row["total_tokens"]
            dates[d]["cost"] += row["cost"]

        sorted_dates = sorted(dates.keys())
        token_values = [dates[d]["tokens"] for d in sorted_dates]
        cost_values = [dates[d]["cost"] for d in sorted_dates]

        self._token_chart.plot(sorted_dates, token_values, tr("history.tokens"), "#58a6ff")
        self._cost_chart.plot(sorted_dates, cost_values, tr("history.cost_usd"), "#3fb950")

        recent_dates = sorted_dates[-7:]
        recent_tokens = [dates[d]["tokens"] for d in recent_dates]
        self._bar_chart.plot(recent_dates, recent_tokens, "#a371f7")

    def _export_csv(self) -> None:
        """Export history data to CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self, tr("export.csv_title"), tr("export.csv_file"),
            tr("export.csv_filter")
        )
        if not path:
            return

        start, end = self._get_date_range()
        rows = self._stats.get_history_data(start, end)

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    tr("table.time"), tr("table.provider"), tr("table.model"),
                    tr("table.input"), tr("table.output"), tr("table.total"),
                    "# Requests", tr("table.cost"),
                ])
                for row in rows:
                    writer.writerow([
                        row.get("date", ""), row.get("provider", ""),
                        row.get("model", ""), row.get("input_tokens", 0),
                        row.get("output_tokens", 0), row.get("total_tokens", 0),
                        row.get("request_count", 0), row.get("cost", 0.0),
                    ])
            QMessageBox.information(self, tr("export.complete"),
                                    tr("export.msg", path=path))
        except OSError as e:
            QMessageBox.critical(self, tr("export.failed"), str(e))

    def _export_excel(self) -> None:
        """Export history data to Excel (XLSX)."""
        path, _ = QFileDialog.getSaveFileName(
            self, tr("export.excel_title"), tr("export.excel_file"),
            tr("export.excel_filter")
        )
        if not path:
            return

        try:
            import openpyxl
        except ImportError:
            QMessageBox.critical(
                self, tr("settings.missing_dep"),
                tr("settings.missing_dep_msg")
            )
            return

        start, end = self._get_date_range()
        rows = self._stats.get_history_data(start, end)

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Token History"
            ws.append([
                tr("table.time"), tr("table.provider"), tr("table.model"),
                tr("table.input"), tr("table.output"), tr("table.total"),
                "# Requests", tr("table.cost"),
            ])
            for row in rows:
                ws.append([
                    row.get("date", ""), row.get("provider", ""),
                    row.get("model", ""), row.get("input_tokens", 0),
                    row.get("output_tokens", 0), row.get("total_tokens", 0),
                    row.get("request_count", 0), row.get("cost", 0.0),
                ])
            wb.save(path)
            QMessageBox.information(self, tr("export.complete"),
                                    tr("export.msg", path=path))
        except OSError as e:
            QMessageBox.critical(self, tr("export.failed"), str(e))
