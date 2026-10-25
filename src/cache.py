"""SQLite cache for search results and claim text, keyed so repeat runs are cheap."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

DEFAULT_DB_PATH = Path("patent_screener_cache.sqlite")
TTL_SECONDS = 7 * 24 * 60 * 60  # 1 week


class Cache:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, cached_at REAL)"
        )
        self.conn.commit()

    def get(self, key: str) -> dict | list | None:
        row = self.conn.execute("SELECT value, cached_at FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        value, cached_at = row
        if time.time() - cached_at > TTL_SECONDS:
            return None
        return json.loads(value)

    def set(self, key: str, value: dict | list) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, cached_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
