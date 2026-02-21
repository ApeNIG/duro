# C:\Users\sibag\.agent\src\autonomy_state.py
"""
Persistent key-value store for autonomy state.

SQLite-backed with JSON serialization for complex values.
This is the foundation - without it, autonomy is a goldfish with opinions.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional


class AutonomyStateStore:
    """
    Thread-safe SQLite key-value store for autonomy state.

    Schema:
        autonomy_state(key TEXT PRIMARY KEY, value_json TEXT, updated_at_unix INTEGER)

    Usage:
        state = AutonomyStateStore("/path/to/db.sqlite")
        state.ensure_schema()
        state.set("maintenance.last_run.decay", 1708531200)
        val = state.get("maintenance.last_run.decay", default=0)
    """

    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    @contextmanager
    def _cursor(self):
        """Context manager for cursor with auto-commit."""
        conn = self._get_conn()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def ensure_schema(self) -> None:
        """Create table if not exists. Safe to call multiple times."""
        with self._cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS autonomy_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at_unix INTEGER NOT NULL
                )
            """)
            # Index for prefix queries (e.g., all "maintenance.last_run.*")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_autonomy_state_key_prefix
                ON autonomy_state(key)
            """)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get value by key. Returns default if not found.

        Values are JSON-deserialized automatically.
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT value_json FROM autonomy_state WHERE key = ?",
                (str(key),)
            )
            row = cur.fetchone()
            if row is None:
                return default
            try:
                return json.loads(row["value_json"])
            except (json.JSONDecodeError, TypeError):
                return default

    def set(self, key: str, value: Any) -> None:
        """
        Set value by key. Value is JSON-serialized.

        Upserts: creates if not exists, updates if exists.
        """
        now = int(time.time())
        value_json = json.dumps(value, separators=(",", ":"), default=str)

        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO autonomy_state (key, value_json, updated_at_unix)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at_unix = excluded.updated_at_unix
            """, (str(key), value_json, now))

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM autonomy_state WHERE key = ?", (str(key),))
            return cur.rowcount > 0

    def get_many(self, prefix: str) -> dict[str, Any]:
        """
        Get all keys matching a prefix.

        Example: get_many("maintenance.last_run.") returns
        {"maintenance.last_run.decay": 123, "maintenance.last_run.health_check": 456}
        """
        with self._cursor() as cur:
            cur.execute(
                "SELECT key, value_json FROM autonomy_state WHERE key LIKE ?",
                (str(prefix) + "%",)
            )
            result = {}
            for row in cur.fetchall():
                try:
                    result[row["key"]] = json.loads(row["value_json"])
                except (json.JSONDecodeError, TypeError):
                    result[row["key"]] = None
            return result

    def delete_many(self, prefix: str) -> int:
        """Delete all keys matching prefix. Returns count deleted."""
        with self._cursor() as cur:
            cur.execute(
                "DELETE FROM autonomy_state WHERE key LIKE ?",
                (str(prefix) + "%",)
            )
            return cur.rowcount

    def keys(self, prefix: Optional[str] = None) -> list[str]:
        """List all keys, optionally filtered by prefix."""
        with self._cursor() as cur:
            if prefix:
                cur.execute(
                    "SELECT key FROM autonomy_state WHERE key LIKE ? ORDER BY key",
                    (str(prefix) + "%",)
                )
            else:
                cur.execute("SELECT key FROM autonomy_state ORDER BY key")
            return [row["key"] for row in cur.fetchall()]

    def count(self, prefix: Optional[str] = None) -> int:
        """Count keys, optionally filtered by prefix."""
        with self._cursor() as cur:
            if prefix:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM autonomy_state WHERE key LIKE ?",
                    (str(prefix) + "%",)
                )
            else:
                cur.execute("SELECT COUNT(*) as cnt FROM autonomy_state")
            return cur.fetchone()["cnt"]

    def clear(self) -> int:
        """Delete all keys. Returns count deleted. Use with caution."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM autonomy_state")
            return cur.rowcount

    def close(self) -> None:
        """Close the connection for this thread."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
