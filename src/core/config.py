"""
Configuration management for TokenMonitor.

Loads configuration from config.yaml and the settings database table.
Database settings take precedence over YAML defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("token_monitor.core.config")

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass
class AppConfig:
    """Application configuration with defaults."""

    # Proxy
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 8910

    # Gateway (M1+)
    gateway_enabled: bool = True

    # Database
    db_path: str = "token_monitor.db"

    # UI
    theme: str = "dark"
    language: str = "en"
    floating_enabled: bool = True
    floating_width: int = 220
    floating_height: int = 70
    floating_opacity: float = 0.85

    # Behavior
    startup_auto_run: bool = False
    close_to_tray: bool = True
    minimize_to_tray: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str = "token_monitor.log"
    log_max_size_mb: int = 10
    log_backup_count: int = 3


class ConfigManager:
    """Manages application configuration from YAML and database.

    Loads YAML first, then overrides with database settings if available.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """Initialize the config manager.

        Args:
            config_path: Path to config.yaml. Uses default if None.
        """
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: AppConfig = AppConfig()
        self._db_settings: dict[str, str] = {}

    def load(self) -> AppConfig:
        """Load configuration from YAML file.

        Returns:
            AppConfig instance with loaded values.
        """
        yaml_data: dict[str, Any] = {}
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    yaml_data = yaml.safe_load(f) or {}
                logger.info("Loaded config from %s", self._config_path)
            except (yaml.YAMLError, OSError) as e:
                logger.warning("Failed to load config.yaml: %s", e)

        # Proxy
        proxy = yaml_data.get("proxy", {})
        self._config.proxy_host = proxy.get("host", "127.0.0.1")
        self._config.proxy_port = int(proxy.get("port", 8910))

        # Gateway
        gateway = yaml_data.get("gateway", {})
        self._config.gateway_enabled = gateway.get("enabled", True)

        # Database
        db = yaml_data.get("database", {})
        self._config.db_path = db.get("path", "token_monitor.db")

        # UI
        ui = yaml_data.get("ui", {})
        self._config.theme = ui.get("theme", "dark")
        self._config.language = ui.get("language", "en")
        floating = ui.get("floating_widget", {})
        self._config.floating_enabled = floating.get("enabled", True)
        self._config.floating_width = int(floating.get("width", 220))
        self._config.floating_height = int(floating.get("height", 70))
        self._config.floating_opacity = float(floating.get("opacity", 0.85))

        # Behavior
        behavior = yaml_data.get("behavior", {})
        self._config.startup_auto_run = behavior.get("startup_auto_run", False)
        self._config.close_to_tray = behavior.get("close_to_tray", True)
        self._config.minimize_to_tray = behavior.get("minimize_to_tray", True)

        # Logging
        log_cfg = yaml_data.get("logging", {})
        self._config.log_level = log_cfg.get("level", "INFO")
        self._config.log_file = log_cfg.get("file", "token_monitor.log")
        self._config.log_max_size_mb = int(log_cfg.get("max_size_mb", 10))
        self._config.log_backup_count = int(log_cfg.get("backup_count", 3))

        return self._config

    def override_from_db(self, db_settings: dict[str, str]) -> None:
        """Override config with values from the database settings table.

        Args:
            db_settings: Dict of key -> value from the settings table.
        """
        self._db_settings = db_settings
        mapping = {
            "proxy_host": ("proxy_host", str),
            "proxy_port": ("proxy_port", int),
            "startup_auto_run": ("startup_auto_run", lambda v: v == "1"),
            "close_to_tray": ("close_to_tray", lambda v: v == "1"),
            "show_floating": ("floating_enabled", lambda v: v == "1"),
            "theme": ("theme", str),
        }
        for db_key, (attr, converter) in mapping.items():
            if db_key in db_settings:
                setattr(self._config, attr, converter(db_settings[db_key]))
        logger.debug("Applied %d overrides from database", len(db_settings))

    def save_yaml(self) -> None:
        """Save current config back to config.yaml."""
        data = {
            "proxy": {
                "host": self._config.proxy_host,
                "port": self._config.proxy_port,
            },
            "gateway": {
                "enabled": self._config.gateway_enabled,
            },
            "database": {
                "path": self._config.db_path,
            },
            "ui": {
                "theme": self._config.theme,
                "language": self._config.language,
                "floating_widget": {
                    "enabled": self._config.floating_enabled,
                    "width": self._config.floating_width,
                    "height": self._config.floating_height,
                    "opacity": self._config.floating_opacity,
                },
            },
            "behavior": {
                "startup_auto_run": self._config.startup_auto_run,
                "close_to_tray": self._config.close_to_tray,
                "minimize_to_tray": self._config.minimize_to_tray,
            },
            "logging": {
                "level": self._config.log_level,
                "file": self._config.log_file,
                "max_size_mb": self._config.log_max_size_mb,
                "backup_count": self._config.log_backup_count,
            },
        }
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.info("Saved config to %s", self._config_path)
        except OSError as e:
            logger.error("Failed to save config.yaml: %s", e)

    @property
    def config(self) -> AppConfig:
        """Get the current application configuration."""
        return self._config
