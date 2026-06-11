"""
Floating widget — compact desktop overlay showing real-time token stats.

Features:
- 260x80 default size, rounded, semi-transparent
- Always on top, frameless, draggable
- Shows: active model, today's token count
- Hover to expand with details
- Left click to open main window, right click for menu
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
)

from src.core.event_bus import EventBus
from src.services.stats_service import StatsService
from src.ui.widgets.token_card import format_token_count, format_cost
from src.utils.i18n import tr

logger = logging.getLogger("token_monitor.ui.floating")


class FloatingWidget(QFrame):
    """Desktop floating overlay widget."""

    # Signals
    open_main_requested = pyqtSignal()
    reset_today_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(
        self,
        stats_service: StatsService,
        event_bus: EventBus,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the floating widget.

        Args:
            stats_service: Statistics service for data.
            event_bus: Event bus for real-time updates.
            parent: Parent widget (MainWindow).
        """
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self._stats = stats_service
        self._event_bus = event_bus

        self._expanded = False
        self._drag_pos: QPoint | None = None

        self._setup_ui()
        self._setup_flags()
        self._apply_expanded_style(False)

        # Connect events
        self._event_bus.stats_updated.connect(self.refresh)
        self._event_bus.new_request.connect(lambda _: self.refresh())

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)

        # Initial position: top-right corner
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - 280, geo.top() + 20)

        logger.info("Floating widget created")

    def _setup_flags(self) -> None:
        """Set window flags for floating behavior."""
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def _setup_ui(self) -> None:
        """Build the floating widget layout."""
        self.setFixedSize(260, 80)

        # Main container
        self._container = QWidget(self)
        self._container.setGeometry(0, 0, 260, 80)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        # Top row: model name
        self._model_label = QLabel(tr("floating.no_activity"))
        self._model_label.setStyleSheet(
            "color: #8b949e; font-size: 14px; font-weight: 500; background: transparent;"
        )
        layout.addWidget(self._model_label)

        # Main stat: token count
        self._token_label = QLabel("—")
        self._token_label.setStyleSheet(
            "color: #e6edf3; font-size: 22px; font-weight: 700;"
            "font-family: 'Cascadia Code', 'Consolas', monospace;"
            "background: transparent;"
        )
        layout.addWidget(self._token_label)

        # Hidden details (shown on hover)
        self._details_widget = QWidget()
        details_layout = QVBoxLayout(self._details_widget)
        details_layout.setContentsMargins(0, 6, 0, 0)
        details_layout.setSpacing(3)

        self._input_label = QLabel("")
        self._input_label.setStyleSheet("color: #8b949e; font-size: 14px; background: transparent;")
        details_layout.addWidget(self._input_label)

        self._output_label = QLabel("")
        self._output_label.setStyleSheet("color: #8b949e; font-size: 14px; background: transparent;")
        details_layout.addWidget(self._output_label)

        self._cost_label = QLabel("")
        self._cost_label.setStyleSheet("color: #3fb950; font-size: 14px; font-weight: 500; background: transparent;")
        details_layout.addWidget(self._cost_label)

        self._time_label = QLabel("")
        self._time_label.setStyleSheet("color: #484f58; font-size: 13px; background: transparent;")
        details_layout.addWidget(self._time_label)

        self._details_widget.setVisible(False)
        layout.addWidget(self._details_widget)

        # Opacity effect
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(0.88)
        self.setGraphicsEffect(effect)

    def _apply_expanded_style(self, expanded: bool) -> None:
        """Update widget size and style for expanded/collapsed state.

        Args:
            expanded: True to expand, False to collapse.
        """
        if expanded:
            self.setFixedSize(260, 180)
            self._container.setGeometry(0, 0, 260, 180)
        else:
            self.setFixedSize(260, 80)
            self._container.setGeometry(0, 0, 260, 80)

        self._container.setStyleSheet("""
            QWidget {
                background-color: #1c2128;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
        """)

    # ── Mouse Events ────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for drag and click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release — single click opens main window."""
        if event.button() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            current = event.globalPosition().toPoint()
            start = self._drag_pos
            if (current - start).manhattanLength() < 5:
                self.open_main_requested.emit()
        self._drag_pos = None

    def enterEvent(self, event: Any) -> None:
        """Expand on mouse hover."""
        self._expanded = True
        self._apply_expanded_style(True)
        self._details_widget.setVisible(True)
        self.refresh()

    def leaveEvent(self, event: Any) -> None:
        """Collapse when mouse leaves."""
        self._expanded = False
        self._apply_expanded_style(False)
        self._details_widget.setVisible(False)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show right-click context menu."""
        menu = QMenu(self)

        open_action = menu.addAction(tr("floating.open_main"))
        open_action.triggered.connect(self.open_main_requested.emit)

        menu.addSeparator()

        reset_action = menu.addAction(tr("floating.reset_today"))
        reset_action.triggered.connect(self.reset_today_requested.emit)

        hide_action = menu.addAction(tr("floating.hide_float"))
        hide_action.triggered.connect(self.hide_requested.emit)

        menu.addSeparator()

        exit_action = menu.addAction(tr("floating.exit"))
        exit_action.triggered.connect(self.exit_requested.emit)

        menu.exec(pos)

    # ── Data Refresh ────────────────────────────

    def refresh(self) -> None:
        """Refresh the displayed statistics."""
        try:
            summary = self._stats.last_summary
            if summary is None:
                summary = self._stats.get_summary()
        except Exception:
            return

        # Active model
        if summary.active_models:
            self._model_label.setText(" | ".join(summary.active_models[:2]))
        else:
            self._model_label.setText(tr("floating.no_activity"))

        # Today tokens
        self._token_label.setText(format_token_count(summary.today_tokens))

        # Details
        self._input_label.setText(
            tr("floating.in", tokens=format_token_count(summary.today_input_tokens))
        )
        self._output_label.setText(
            tr("floating.out", tokens=format_token_count(summary.today_output_tokens))
        )
        self._cost_label.setText(
            tr("floating.cost", cost=format_cost(summary.today_cost))
        )

        if summary.last_request_time:
            self._time_label.setText(
                tr("floating.last", time=summary.last_request_time)
            )
        else:
            self._time_label.setText(tr("floating.last", time="—"))
