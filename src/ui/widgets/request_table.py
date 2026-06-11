"""
Request log table widget — displays recent API requests.

Used on Dashboard and History pages.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from src.utils.i18n import tr


class RequestTableWidget(QTableWidget):
    """Styled table for displaying recent API requests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the request table.

        Args:
            parent: Parent widget.
        """
        self._col_labels = [
            tr("table.time"), tr("table.provider"), tr("table.model"),
            tr("table.input"), tr("table.output"), tr("table.total"),
            tr("table.cost"), tr("table.latency"),
        ]
        super().__init__(0, len(self._col_labels), parent)
        self.setHorizontalHeaderLabels(self._col_labels)
        self._setup_style()

    def _setup_style(self) -> None:
        """Configure table appearance and behavior."""
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)

        # Column widths
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

        self.setMinimumHeight(220)

    def load_data(self, requests: list[dict[str, Any]]) -> None:
        """Populate the table with request data.

        Args:
            requests: List of request log dicts.
        """
        self.setRowCount(len(requests))

        for row, req in enumerate(requests):
            # Time
            ts = req.get("timestamp", 0)
            time_str = datetime.utcfromtimestamp(ts).strftime("%H:%M:%S") if ts else "—"
            self._set_cell(row, 0, time_str)

            # Provider
            self._set_cell(row, 1, req.get("provider", "—"))

            # Model
            self._set_cell(row, 2, req.get("model", "—"))

            # Input tokens
            inp = req.get("input_tokens", 0)
            self._set_cell(row, 3, _fmt_tokens(inp), align=Qt.AlignmentFlag.AlignRight)

            # Output tokens
            out = req.get("output_tokens", 0)
            self._set_cell(row, 4, _fmt_tokens(out), align=Qt.AlignmentFlag.AlignRight)

            # Total tokens
            total = req.get("total_tokens", 0)
            self._set_cell(row, 5, _fmt_tokens(total), align=Qt.AlignmentFlag.AlignRight, bold=True)

            # Cost
            cost = req.get("cost", 0.0)
            self._set_cell(row, 6, f"${cost:.4f}", align=Qt.AlignmentFlag.AlignRight)

            # Latency
            lat = req.get("latency_ms", 0)
            lat_str = f"{lat:.0f}ms" if lat else "—"
            self._set_cell(row, 7, lat_str, align=Qt.AlignmentFlag.AlignRight)

    def _set_cell(
        self,
        row: int,
        col: int,
        text: str,
        align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
        bold: bool = False,
    ) -> None:
        """Set a cell's content with styling.

        Args:
            row: Row index.
            col: Column index.
            text: Cell text.
            align: Text alignment.
            bold: Whether text is bold.
        """
        item = QTableWidgetItem(text)
        item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)

        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)

        self.setItem(row, col, item)


def _fmt_tokens(n: int) -> str:
    """Format token count for table display.

    Args:
        n: Token count.

    Returns:
        Formatted string.
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)
