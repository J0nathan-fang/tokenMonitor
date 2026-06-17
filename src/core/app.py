"""
Application bootstrap and lifecycle management.

Orchestrates: config → database → proxy → UI startup.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.core.config import ConfigManager, AppConfig
from src.core.event_bus import EventBus
from src.database.manager import DatabaseManager
from src.database.repository import Repository
from src.services.proxy_service import ProxyServiceThread
from src.utils.logger import setup_logging

logger = logging.getLogger("token_monitor.core.app")


class Application:
    """Main application class that owns the lifecycle.

    Usage:
        app = Application()
        app.initialize()
        app.run()
    """

    def __init__(self) -> None:
        self._config_manager = ConfigManager()
        self._config: AppConfig | None = None
        self._db: DatabaseManager | None = None
        self._repository: Repository | None = None
        self._event_bus: EventBus | None = None
        self._qt_app: QApplication | None = None
        self._proxy_thread: ProxyServiceThread | None = None

    def initialize(self) -> AppConfig:
        """Initialize all subsystems in order.

        Returns:
            The loaded AppConfig.
        """
        # 1. Load configuration
        self._config = self._config_manager.load()

        # 2. Setup logging
        setup_logging(
            log_level=self._config.log_level,
            log_file=self._config.log_file,
            max_size_mb=self._config.log_max_size_mb,
            backup_count=self._config.log_backup_count,
        )
        logger.info("TokenMonitor starting...")

        # 3. Initialize database
        self._db = DatabaseManager(self._config.db_path)
        self._db.initialize_schema()

        # 4. Apply database setting overrides
        settings = self._db.get_all_settings()
        if settings:
            self._config_manager.override_from_db(settings)

        # 5. Create repository
        self._repository = Repository(self._db)

        # 6. Create Qt application
        self._qt_app = QApplication(sys.argv)
        self._qt_app.setApplicationName("TokenMonitor")
        self._qt_app.setOrganizationName("TokenMonitor")

        # 7. Setup event bus
        self._event_bus = EventBus.get_instance()

        # 8. Seed default model prices
        self._seed_default_models()

        logger.info("Application initialized successfully")
        return self._config

    def _seed_default_models(self) -> None:
        """Insert default model pricing if model_configs is empty."""
        existing = self._db.execute("SELECT COUNT(*) FROM model_configs").fetchone()
        if existing and existing[0] > 0:
            return

        defaults = [
            # OpenAI
            ("openai", "gpt-4o", "GPT-4o", "https://api.openai.com/v1", 2.50, 10.00),
            ("openai", "gpt-4o-mini", "GPT-4o Mini", "https://api.openai.com/v1", 0.15, 0.60),
            ("openai", "o4-mini", "o4 Mini", "https://api.openai.com/v1", 1.10, 4.40),
            ("openai", "gpt-4.1", "GPT-4.1", "https://api.openai.com/v1", 2.00, 8.00),
            ("openai", "gpt-4.1-mini", "GPT-4.1 Mini", "https://api.openai.com/v1", 0.40, 1.60),
            ("openai", "gpt-4.1-nano", "GPT-4.1 Nano", "https://api.openai.com/v1", 0.10, 0.40),
            ("openai", "gpt-5", "GPT-5", "https://api.openai.com/v1", 1.25, 10.00),
            ("openai", "gpt-5-mini", "GPT-5 Mini", "https://api.openai.com/v1", 0.25, 2.00),
            ("openai", "gpt-5-nano", "GPT-5 Nano", "https://api.openai.com/v1", 0.05, 0.40),
            # Anthropic
            ("anthropic", "claude-sonnet-4-20250514", "Claude Sonnet 4", "https://api.anthropic.com/v1", 3.00, 15.00),
            ("anthropic", "claude-opus-4-20250514", "Claude Opus 4", "https://api.anthropic.com/v1", 15.00, 75.00),
            ("anthropic", "claude-haiku-4-5-20251001", "Claude Haiku 4.5", "https://api.anthropic.com/v1", 1.00, 5.00),
            # Gemini
            ("gemini", "gemini-2.5-pro", "Gemini 2.5 Pro", "https://generativelanguage.googleapis.com/v1beta", 1.25, 10.00),
            ("gemini", "gemini-2.5-flash", "Gemini 2.5 Flash", "https://generativelanguage.googleapis.com/v1beta", 0.15, 0.60),
            # DeepSeek
            ("deepseek", "deepseek-chat", "DeepSeek Chat", "https://api.deepseek.com/v1", 0.27, 1.10),
            ("deepseek", "deepseek-reasoner", "DeepSeek Reasoner", "https://api.deepseek.com/v1", 0.55, 2.19),
            ("deepseek", "deepseek-v4-flash", "DeepSeek V4 Flash", "https://api.deepseek.com/v1", 0.27, 1.10),
            ("deepseek", "deepseek-v4-pro", "DeepSeek V4 Pro", "https://api.deepseek.com/v1", 0.55, 2.19),
            # OpenRouter
            ("openrouter", "openrouter", "OpenRouter (default)", "https://openrouter.ai/api/v1", 0.0, 0.0),
        ]
        for provider, model_name, display, url, inp, out in defaults:
            self._db.execute(
                """INSERT OR IGNORE INTO model_configs
                   (provider, model_name, display_name, api_url, input_price, output_price)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (provider, model_name, display, url, inp, out),
            )
        self._db.commit()
        logger.info("Seeded %d default model configs", len(defaults))

    def run(self) -> int:
        """Start the Qt event loop.

        Returns:
            Exit code from QApplication.
        """
        if self._qt_app is None:
            logger.critical("Application not initialized. Call initialize() first.")
            return 1

        # Import UI here to avoid circular imports and ensure QApplication exists first
        from src.ui.main_window import MainWindow

        self._main_window = MainWindow(
            config=self._config,
            repository=self._repository,
            event_bus=self._event_bus,
            config_manager=self._config_manager,
        )
        self._main_window.show()

        # Start Gateway proxy server
        self._proxy_thread = ProxyServiceThread(
            config=self._config,
            repository=self._repository,
            event_bus=self._event_bus,
        )
        self._proxy_thread.started_signal.connect(
            lambda: logger.info("Gateway proxy server ready on %s:%d",
                                self._config.proxy_host, self._config.proxy_port)
        )
        self._proxy_thread.error_signal.connect(
            lambda msg: logger.error("Proxy server error: %s", msg)
        )
        self._proxy_thread.start()

        # Setup signal handling for graceful shutdown
        signal.signal(signal.SIGINT, lambda *a: self._qt_app.quit())
        # Windows: timer to allow Python signal handler to run
        timer = QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(200)

        logger.info("Starting Qt event loop")
        exit_code = self._qt_app.exec()

        self.shutdown()
        return exit_code

    def shutdown(self) -> None:
        """Clean shutdown: stop proxy, close DB, destroy singletons."""
        logger.info("Shutting down...")

        # Stop proxy if running
        if self._proxy_thread is not None:
            try:
                self._proxy_thread.stop()
                self._proxy_thread.quit()
                self._proxy_thread.wait(5000)
            except Exception as e:
                logger.warning("Error stopping proxy: %s", e)

        # Close database
        if self._db is not None:
            self._db.close()

        # Clean up singletons
        EventBus.destroy_instance()

        logger.info("Shutdown complete")

    @property
    def config(self) -> AppConfig | None:
        return self._config

    @property
    def repository(self) -> Repository | None:
        return self._repository

    @property
    def event_bus(self) -> EventBus | None:
        return self._event_bus
