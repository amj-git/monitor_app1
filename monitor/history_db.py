from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS readings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    value     REAL NOT NULL,
    unit      TEXT NOT NULL,
    alarming  INTEGER NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sensor_timestamp
    ON readings (sensor_id, timestamp);
"""


class HistoryDB:
    def __init__(self, db_path: str, max_size_mb: float = 50.0) -> None:
        self._db_path = db_path
        self._max_bytes = max_size_mb * 1024 * 1024

        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_CREATE_INDEX)
        self._conn.commit()
        logger.info("HistoryDB opened: %s", db_path)

    def insert_readings(self, readings: list) -> None:
        rows = [
            (
                r.timestamp.isoformat(),
                r.sensor_id,
                r.value,
                r.unit,
                int(r.alarming),
            )
            for r in readings
        ]
        self._conn.executemany(
            "INSERT INTO readings (timestamp, sensor_id, value, unit, alarming) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def trim_if_needed(self) -> int:
        total_deleted = 0
        while os.path.getsize(self._db_path) > self._max_bytes:
            cursor = self._conn.execute(
                "DELETE FROM readings WHERE id IN "
                "(SELECT id FROM readings ORDER BY id ASC LIMIT 100)"
            )
            deleted = cursor.rowcount
            self._conn.commit()
            total_deleted += deleted
            if deleted == 0:
                break
        if total_deleted:
            logger.info("DB trim: deleted %d old rows", total_deleted)
        return total_deleted

    def get_latest_readings(self) -> list:
        cursor = self._conn.execute(
            "SELECT sensor_id, value, unit, alarming, timestamp "
            "FROM readings "
            "WHERE id IN (SELECT MAX(id) FROM readings GROUP BY sensor_id) "
            "ORDER BY sensor_id"
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_history(
        self,
        sensor_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 2000,
    ) -> list:
        conditions: list[str] = []
        params: list = []
        if sensor_id:
            conditions.append("sensor_id = ?")
            params.append(sensor_id)
        if start:
            conditions.append("timestamp >= ?")
            params.append(start)
        if end:
            conditions.append("timestamp <= ?")
            params.append(end + ":59")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor = self._conn.execute(
            f"SELECT sensor_id, value, unit, alarming, timestamp "
            f"FROM readings {where} "
            f"ORDER BY timestamp DESC LIMIT ?",
            params + [limit],
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self._conn.close()
        logger.info("HistoryDB closed")
