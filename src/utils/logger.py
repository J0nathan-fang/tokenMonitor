"""
Logging configuration for TokenMonitor.

Provides structured logging with rotation support.
All modules use this instead of print().
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "token_monitor.log",
    max_size_mb: int = 10,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure and return the root logger for the application.

    Args:
        log_level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_file: Path to the log file.
        max_size_mb: Max log file size before rotation.
        backup_count: Number of rotated files to keep.

    Returns:
        The configured root logger.
    """
    logger = logging.getLogger("token_monitor")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers on re-init
    if logger.handlers:
        return logger

    # Formatter
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning("Cannot create log file %s: %s", log_file, e)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with the given name.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        A logger instance.
    """
    return logging.getLogger(f"token_monitor.{name}")
