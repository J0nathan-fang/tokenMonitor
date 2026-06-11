"""
MainWindow — primary application window with sidebar navigation.

Uses a sidebar + stacked page layout pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig, ConfigManager
from src.core.event_bus import EventBus
from src.database.repository import Repository
from src.statistics.calculator import CostCalculator
from src.statistics.engine import StatisticsEngine
from src.services.stats_service import StatsService
from src.ui.budget.page import BudgetPage
from src.ui.dashboard.page import DashboardPage
from src.ui.history.page import HistoryPage
from src.ui.models_page.page import ModelsPage
from src.ui.settings.page import SettingsPage
from src.ui.floating import FloatingWidget
from src.ui.tray import TrayManager
from src.utils.i18n import tr, set_language, get_language

logger = logging.getLogger("token_monitor.ui.main_window")

NAV_ITEMS = [
    ("🏠 Main", "main"),
    ("📈 History", "history"),
    ("🤖 Models", "models"),
    ("💰 Budget", "budget"),
    ("⚙️ Settings", "settings"),
]


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and stacked pages."""

    def __init__(
        self,
        config: AppConfig,
        repository: Repository,
        event_bus: EventBus,
        config_manager: ConfigManager,
    ) -> None:
        """Initialize the main window.

        Args:
            config: Application configuration.
            repository: Database repository.
            event_bus: Event bus for real-time updates.
            config_manager: Configuration manager.
        """
        super().__init__()
        self._config = config
        self._repo = repository
        self._event_bus = event_bus
        self._config_manager = config_manager

        # Apply language from settings
        lang = repository.get_setting("language", "en")
        set_language(lang or "en")

        # Initialize services
        self._calculator = CostCalculator(repository)
        self._engine = StatisticsEngine(repository, self._calculator)
        self._stats_service = StatsService(self._engine, repository)

        # UI state
        self._floating: FloatingWidget | None = None
        self._tray: TrayManager | None = None

        self._setup_window()
        self._setup_ui()
        self._setup_tray()
        self._setup_floating()

        # Navigate to main page by default
        self._nav_list.setCurrentRow(0)

        logger.info("MainWindow initialized")

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle(tr("app.title"))
        self.setMinimumSize(1280, 860)
        self.resize(1440, 960)

        # Center on screen
        screen = self.screen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _setup_ui(self) -> None:
        """Build the main window layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ───────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background-color: #161b22;")

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # App logo/title
        logo = QLabel("TokenMonitor")
        logo.setStyleSheet(
            "color: #ffffff; font-size: 28px; font-weight: 700; padding: 24px 20px 20px;"
        )
        sidebar_layout.addWidget(logo)

        # Nav list
        self._nav_list = QListWidget()
        self._nav_list.setStyleSheet("font-size: 20px; color: #ffffff;")
        self._rebuild_nav()
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list)

        # Version / status at bottom
        sidebar_layout.addStretch()
        self._version_label = QLabel(tr("app.version"))
        self._version_label.setStyleSheet("color: #484f58; font-size: 15px; padding: 16px 20px;")
        sidebar_layout.addWidget(self._version_label)

        main_layout.addWidget(sidebar)

        # ── Content Area ──────────────────────────
        self._stack = QStackedWidget()

        # Create pages
        self._dashboard_page = DashboardPage(self._stats_service, self._event_bus)
        self._history_page = HistoryPage(self._stats_service)
        self._models_page = ModelsPage(self._repo, self._calculator)
        self._budget_page = BudgetPage(self._repo, self._engine)
        self._settings_page = SettingsPage(self._config, self._config_manager, self._repo)

        self._stack.addWidget(self._dashboard_page)   # 0
        self._stack.addWidget(self._history_page)     # 1
        self._stack.addWidget(self._models_page)      # 2
        self._stack.addWidget(self._budget_page)      # 3
        self._stack.addWidget(self._settings_page)    # 4

        main_layout.addWidget(self._stack)

    def _get_nav_items(self) -> list[tuple[str, str]]:
        """Get translated sidebar navigation items."""
        return [
            (tr("nav.main"), "main"),
            (tr("nav.history"), "history"),
            (tr("nav.models"), "models"),
            (tr("nav.budget"), "budget"),
            (tr("nav.settings"), "settings"),
        ]

    def _rebuild_nav(self) -> None:
        """Rebuild the navigation list with current language."""
        was_blocked = self._nav_list.blockSignals(True)
        self._nav_list.clear()
        items = self._get_nav_items()
        for label, key in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, 52))
            self._nav_list.addItem(item)
        self._nav_list.blockSignals(was_blocked)

    def refresh_language(self) -> None:
        """Refresh all UI text after language change."""
        self.setWindowTitle(tr("app.title"))
        self._version_label.setText(tr("app.version"))
        self._rebuild_nav()
        # Notify pages to refresh their text
        self._settings_page.refresh_language()

    def _on_nav_changed(self, index: int) -> None:
        """Handle sidebar navigation changes.

        Args:
            index: Selected item index.
        """
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)

    def _setup_tray(self) -> None:
        """Initialize the system tray icon and menu."""
        self._tray = TrayManager(self)
        self._tray.show()

    def _setup_floating(self) -> None:
        """Initialize the floating widget if enabled."""
        if self._config.floating_enabled:
            self._floating = FloatingWidget(
                self._stats_service,
                self._event_bus,
                self,
            )
            # Wire floating widget signals to main window slots
            self._floating.open_main_requested.connect(self.show_main)
            self._floating.hide_requested.connect(lambda: self._floating.hide() if self._floating else None)
            self._floating.exit_requested.connect(self._do_exit)
            self._floating.show()
            logger.info("Floating widget shown")

    # ── Window lifecycle ────────────────────────

    def closeEvent(self, event: Any) -> None:
        """Handle window close — minimize to tray instead of quitting.

        Args:
            event: The QCloseEvent.
        """
        if self._config.close_to_tray and self._tray:
            self.hide()
            if self._floating:
                self._floating.show()
            event.ignore()
            self._tray.show_notification(
                tr("tray.notify_title"),
                tr("tray.notify_minimized")
            )
        else:
            self._cleanup()
            event.accept()

    def _cleanup(self) -> None:
        """Clean up resources before exit."""
        if self._floating:
            self._floating.close()
        if self._tray:
            self._tray.hide()

    def show_main(self) -> None:
        """Bring the main window to the foreground."""
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_floating(self) -> None:
        """Toggle the floating widget visibility."""
        if self._floating:
            if self._floating.isVisible():
                self._floating.hide()
            else:
                self._floating.show()

    def _do_exit(self) -> None:
        """Exit the application completely."""
        self._cleanup()
        QApplication.instance().quit()

    # ── Accessors ───────────────────────────────

    @property
    def stats_service(self) -> StatsService:
        return self._stats_service

    @property
    def floating_widget(self) -> FloatingWidget | None:
        return self._floating

    @property
    def tray_manager(self) -> TrayManager | None:
        return self._tray
