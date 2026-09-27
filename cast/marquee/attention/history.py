"""Bounded SQLite history. Observations are diagnostic, never replayed as truth."""

import json
import sqlite3
from typing import Any


class History:
    def __init__(self, path: str = ":memory:", limit: int = 2000, retention: float = 604800) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.limit, self.retention = limit, retention
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, "
            "at REAL NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS controls (key TEXT PRIMARY KEY, "
            "expires REAL NOT NULL, data TEXT NOT NULL)"
        )
        self.db.commit()

    def prune(self, now: float) -> None:
        self.db.execute("DELETE FROM history WHERE at < ?", (now - self.retention,))
        self.db.execute(
            "DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)",
            (self.limit,),
        )
        self.db.execute("DELETE FROM controls WHERE expires <= ?", (now,))
        self.db.commit()

    def record(self, now: float, kind: str, **data: Any) -> None:
        encoded = json.dumps(data, ensure_ascii=False, default=str)
        if len(encoded.encode()) > 8192:
            encoded = json.dumps({"truncated": True, "id": str(data.get("id", ""))[:120]})
        self.db.execute("INSERT INTO history(at,kind,data) VALUES (?,?,?)", (now, kind, encoded))
        self.prune(now)

    def read(self, now: float, limit: int = 100) -> list[dict[str, Any]]:
        self.prune(now)
        return [
            {"at": at, "kind": kind, **json.loads(data)}
            for at, kind, data in self.db.execute(
                "SELECT at,kind,data FROM history ORDER BY id DESC LIMIT ?", (min(limit, self.limit),)
            )
        ]

    def save_control(self, key: str, expires: float, data: dict[str, Any]) -> None:
        self.db.execute("INSERT OR REPLACE INTO controls VALUES (?,?,?)", (key, expires, json.dumps(data)))
        self.db.commit()

    def controls(self, now: float) -> dict[str, dict[str, Any]]:
        self.prune(now)
        return {
            key: json.loads(data)
            for key, data in self.db.execute("SELECT key,data FROM controls WHERE expires > ?", (now,))
        }

    def close(self) -> None:
        self.db.close()
