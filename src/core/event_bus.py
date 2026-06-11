"""
Event bus for decoupled inter-module communication.

Uses PyQt6 signals so events are thread-safe and integrate
naturally with the Qt event loop.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger("token_monitor.core.event_bus")


class EventBus(QObject):
    """Central event bus using Qt signals/slots.

    Signals:
        stats_updated: Emitted when new usage data is recorded.
        budget_warning: Emitted when budget threshold is crossed (percentage: int).
        proxy_status_changed: Emitted when proxy starts/stops (running: bool).
        new_request: Emitted for each completed request (usage_data: dict).
        model_config_changed: Emitted when model configs are modified.
    """

    stats_updated = pyqtSignal()
    budget_warning = pyqtSignal(int)
    proxy_status_changed = pyqtSignal(bool)
    new_request = pyqtSignal(dict)
    model_config_changed = pyqtSignal()

    _instance: EventBus | None = None

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the event bus. Use get_instance() for singleton access."""
        super().__init__(parent)

    @classmethod
    def get_instance(cls) -> EventBus:
        """Get or create the singleton EventBus instance.

        Returns:
            The singleton EventBus.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def destroy_instance(cls) -> None:
        """Destroy the singleton instance (for clean shutdown)."""
        if cls._instance is not None:
            cls._instance.deleteLater()
            cls._instance = None
