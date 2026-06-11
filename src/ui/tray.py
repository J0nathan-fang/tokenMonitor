"""
System tray manager — provides system tray icon and context menu.

Supports: minimize to tray, tray menu, and notifications.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from src.utils.i18n import tr

logger = logging.getLogger("token_monitor.ui.tray")

# Create a simple programmatic icon since we don't have an .ico file yet
def _create_tray_icon() -> QIcon:
    """Create a simple programmatic icon for the tray.

    Returns:
        A QIcon with a simple 'T' letter on colored background.
    """
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background circle
    painter.setBrush(QColor("#3fb950"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)

    # Letter
    painter.setPen(QColor("#ffffff"))
    font = QFont("Segoe UI", 32, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "T")

    painter.end()
    return QIcon(pixmap)


class TrayManager:
    """Manages the system tray icon and context menu."""

    def __init__(self, main_window: QWidget) -> None:
        """Initialize the tray manager.

        Args:
            main_window: The MainWindow instance for show/hide actions.
        """
        self._main_window = main_window

        # Create tray icon
        icon = _create_tray_icon()
        self._tray_icon = QSystemTrayIcon(icon, main_window)
        self._tray_icon.setToolTip(tr("tray.tooltip"))

        # Create menu
        self._menu = QMenu()

        # Open action
        self._open_action = QAction(tr("tray.open"), self._menu)
        self._open_action.triggered.connect(self._show_main)
        self._menu.addAction(self._open_action)

        # Floating widget toggle
        self._float_action = QAction(tr("tray.show_float"), self._menu)
        self._float_action.triggered.connect(self._toggle_floating)
        self._menu.addAction(self._float_action)

        self._menu.addSeparator()

        # Settings
        self._settings_action = QAction(tr("tray.settings"), self._menu)
        self._settings_action.triggered.connect(self._show_settings)
        self._menu.addAction(self._settings_action)

        self._menu.addSeparator()

        # Exit
        self._exit_action = QAction(tr("tray.exit"), self._menu)
        self._exit_action.triggered.connect(self._exit_app)
        self._menu.addAction(self._exit_action)

        self._tray_icon.setContextMenu(self._menu)

        # Double-click tray icon to show main window
        self._tray_icon.activated.connect(self._on_activated)

    def refresh_language(self) -> None:
        """Refresh all menu text after language change."""
        self._tray_icon.setToolTip(tr("tray.tooltip"))
        self._open_action.setText(tr("tray.open"))
        self._float_action.setText(tr("tray.show_float"))
        self._settings_action.setText(tr("tray.settings"))
        self._exit_action.setText(tr("tray.exit"))

    def show(self) -> None:
        """Show the tray icon."""
        self._tray_icon.show()
        logger.debug("Tray icon shown")

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray_icon.hide()

    def show_notification(self, title: str, message: str, duration_ms: int = 3000) -> None:
        """Show a tray notification balloon.

        Args:
            title: Notification title.
            message: Notification body text.
            duration_ms: How long to show the notification (ms).
        """
        if self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms
            )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click/double-click).

        Args:
            reason: The activation reason.
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main()

    def _show_main(self) -> None:
        """Show and activate the main window."""
        self._main_window.show_main()

    def _toggle_floating(self) -> None:
        """Toggle floating widget visibility."""
        self._main_window.toggle_floating()

    def _show_settings(self) -> None:
        """Show main window with settings page."""
        self._main_window.show_main()

    def _exit_app(self) -> None:
        """Exit the application completely."""
        logger.info("Exit requested from tray menu")
        QApplication.quit()
