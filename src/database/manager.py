"""
DatabaseManager — central SQLite database access.

All SQL execution goes through this class.
Provides connection pooling (single connection with WAL mode).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("token_monitor.database.manager")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS request_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       REAL NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    endpoint        TEXT,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens   INTEGER DEFAULT 0,
    cache_write_tokens  INTEGER DEFAULT 0,
    cost            REAL NOT NULL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    latency_ms      REAL,
    status_code     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_request_logs_provider ON request_logs(provider);
CREATE INDEX IF NOT EXISTS idx_request_logs_model ON request_logs(model);

CREATE TABLE IF NOT EXISTS daily_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    request_count   INTEGER NOT NULL DEFAULT 0,
    cost            REAL NOT NULL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    UNIQUE(date, provider, model)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
CREATE INDEX IF NOT EXISTS idx_daily_stats_model ON daily_stats(model);

CREATE TABLE IF NOT EXISTS model_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider        TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    display_name    TEXT,
    api_url         TEXT,
    input_price     REAL NOT NULL DEFAULT 0.0,
    output_price    REAL NOT NULL DEFAULT 0.0,
    cache_read_price    REAL DEFAULT 0.0,
    cache_write_price   REAL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT 'USD',
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(provider, model_name)
);

CREATE TABLE IF NOT EXISTS budget_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_type     TEXT NOT NULL,
    amount          REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    notify_80       INTEGER NOT NULL DEFAULT 1,
    notify_90       INTEGER NOT NULL DEFAULT 1,
    notify_100      INTEGER NOT NULL DEFAULT 1,
    enabled         INTEGER NOT NULL DEFAULT 1,
    UNIQUE(budget_type)
);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('proxy_port', '7890'),
    ('proxy_host', '127.0.0.1'),
    ('startup_auto_run', '0'),
    ('close_to_tray', '1'),
    ('show_floating', '1'),
    ('theme', 'dark'),
    ('first_run', '1');
"""


class DatabaseManager:
    """Singleton-style SQLite database manager with WAL mode.

    Thread-safe via a threading.Lock. All SQL must be parameterized.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the database connection (not thread-safe, call with lock).

        Returns:
            An sqlite3.Connection in WAL mode with foreign keys enabled.
        """
        if self._connection is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
                isolation_level=None,  # Autocommit mode
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            logger.info("Database connection opened: %s", self._db_path)
        return self._connection

    def initialize_schema(self) -> None:
        """Create all tables and indexes if they don't exist."""
        with self._lock:
            conn = self._get_connection()
            conn.executescript(SCHEMA_SQL)
        logger.info("Database schema initialized")

    def execute(self, sql: str, params: tuple | None = None) -> sqlite3.Cursor:
        """Execute a parameterized SQL statement.

        Args:
            sql: The SQL statement with ? placeholders.
            params: Tuple of parameters to bind.

        Returns:
            The sqlite3.Cursor after execution.
        """
        with self._lock:
            conn = self._get_connection()
            if params:
                cursor = conn.execute(sql, params)
            else:
                cursor = conn.execute(sql)
            return cursor

    def execute_many(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a parameterized SQL statement with multiple parameter sets.

        Args:
            sql: The SQL statement with ? placeholders.
            params_list: List of parameter tuples.

        Returns:
            The sqlite3.Cursor after execution.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.executemany(sql, params_list)
            return cursor

    def commit(self) -> None:
        """Explicitly commit the current transaction."""
        with self._lock:
            if self._connection:
                self._connection.commit()

    def get_all_settings(self) -> dict[str, str]:
        """Fetch all settings as a dict.

        Returns:
            Dict of key -> value.
        """
        with self._lock:
            conn = self._get_connection()
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {row["key"]: row["value"] for row in rows}

    def close(self) -> None:
        """Close the database connection cleanly."""
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None
                logger.info("Database connection closed")
