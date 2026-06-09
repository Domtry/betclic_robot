from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class MultiplierStore:
    """SQLite storage for scraped multiplier rounds."""

    def __init__(self, db_path: str | Path = "data/bot.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS multipliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_at TEXT NOT NULL,
                    raw TEXT NOT NULL,
                    value REAL NOT NULL,
                    level TEXT,
                    source_index INTEGER,
                    event_hash TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_multipliers_observed_at ON multipliers(observed_at)"
            )

    @staticmethod
    def _normalize_observed_at(observed_at: datetime | None = None) -> datetime:
        observed_at = observed_at or datetime.now(timezone.utc)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        return observed_at.astimezone(timezone.utc)

    @staticmethod
    def _event_hash(observed_at: datetime, raw: str, value: float, source_index: int | None) -> str:
        # Round timestamp to the second so the same scraped result is not stored twice in one polling tick.
        # Include source_index so two identical multipliers displayed in the same history are preserved.
        key = f"{observed_at.replace(microsecond=0).isoformat()}|{source_index}|{raw}|{value:.6f}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def save_multipliers(self, multipliers: Iterable[dict], observed_at: datetime | None = None) -> int:
        observed_at = self._normalize_observed_at(observed_at)
        observed_iso = observed_at.isoformat()
        inserted = 0
        with self._connect() as conn:
            for item in multipliers:
                value = float(item["value"])
                raw = str(item.get("raw", f"{value}x"))
                source_index = item.get("index")
                event_hash = self._event_hash(observed_at, raw, value, source_index)
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO multipliers
                        (observed_at, raw, value, level, source_index, event_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observed_iso,
                        raw,
                        value,
                        item.get("level"),
                        item.get("index"),
                        event_hash,
                    ),
                )
                inserted += cur.rowcount
        return inserted

    def fetch_latest(self, limit: int = 200) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT observed_at, raw, value, level, source_index
                FROM multipliers
                ORDER BY observed_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def fetch_day(self, day: str) -> list[dict]:
        start = f"{day}T00:00:00"
        end = f"{day}T23:59:59.999999"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT observed_at, raw, value, level, source_index
                FROM multipliers
                WHERE observed_at >= ? AND observed_at <= ?
                ORDER BY observed_at ASC, id ASC
                """,
                (start, end),
            ).fetchall()
        return [dict(row) for row in rows]
