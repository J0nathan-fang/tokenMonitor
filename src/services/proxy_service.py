"""
Proxy service — manages proxy server lifecycle as a background task.

Integrates with the Qt event loop via qasync for async proxy operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.config import AppConfig
from src.core.event_bus import EventBus
from src.database.repository import Repository
from src.proxy.server import ProxyServer

logger = logging.getLogger("token_monitor.services.proxy")


class ProxyServiceThread(QThread):
    """QThread that runs the async proxy server in an event loop."""

    started_signal = pyqtSignal()
    stopped_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        config: AppConfig,
        repository: Repository,
        event_bus: EventBus,
    ) -> None:
        """Initialize the proxy service thread.

        Args:
            config: Application configuration.
            repository: Database repository.
            event_bus: Event bus for notifications.
        """
        super().__init__()
        self._config = config
        self._repository = repository
        self._event_bus = event_bus
        self._server: ProxyServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self) -> None:
        """Run the proxy server in an async event loop."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            self._server = ProxyServer(
                host=self._config.proxy_host,
                port=self._config.proxy_port,
                repository=self._repository,
                event_bus=self._event_bus,
            )

            self._loop.run_until_complete(self._server.start())
            self.started_signal.emit()
            logger.info("Proxy service thread running")

            # Keep the loop alive
            self._loop.run_forever()
        except Exception as e:
            logger.error("Proxy service error: %s", e, exc_info=True)
            self.error_signal.emit(str(e))

    def stop(self) -> None:
        """Gracefully stop the proxy server."""
        if self._server and self._loop:
            async def _stop():
                await self._server.stop()

            try:
                future = asyncio.run_coroutine_threadsafe(_stop(), self._loop)
                future.result(timeout=5)
            except Exception as e:
                logger.warning("Error during proxy stop: %s", e)

        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        self.stopped_signal.emit()
        logger.info("Proxy service thread stopped")

    @property
    def server(self) -> ProxyServer | None:
        return self._server
