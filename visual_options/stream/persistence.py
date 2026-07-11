"""Persistencia de sesiones: snapshots comprimidos en SQLite.

Cada difusión del manager pasa por el Recorder, que guarda como mucho un
snapshot cada RECORD_INTERVAL segundos por sesión (día completo ≈ 20 MB
por símbolo). Sobre esto se montan el replay (rebobinar la sesión barra a
barra) y el histórico entre días.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
from datetime import datetime
from pathlib import Path

RECORD_INTERVAL = 10.0  # segundos entre snapshots guardados por sesión

DEFAULT_DB = Path.home() / ".visual-options" / "sessions.db"


class Recorder:
    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._last_write: dict[str, float] = {}
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY,
                    day TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    expiry INTEGER NOT NULL DEFAULT 0,
                    ts TEXT NOT NULL,
                    payload BLOB NOT NULL
                )""")
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snap
                ON snapshots (symbol, day, source, expiry, id)""")
            self._conn.commit()

    def record(self, session_key: str, payload_json: str) -> bool:
        """session_key con formato 'source:symbol:expiry'. Devuelve si escribió."""
        now = time.time()
        if now - self._last_write.get(session_key, 0.0) < RECORD_INTERVAL:
            return False
        try:
            source, symbol, expiry = session_key.split(":")
        except ValueError:
            return False
        self._last_write[session_key] = now
        blob = zlib.compress(payload_json.encode(), level=6)
        day = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self._conn.execute(
                "INSERT INTO snapshots (day, symbol, source, expiry, ts, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (day, symbol, source, int(expiry), ts, blob))
            self._conn.commit()
        return True

    def days(self, symbol: str) -> list[dict]:
        """Sesiones grabadas para un símbolo, la más reciente primero."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT day, source, expiry, COUNT(*), MIN(ts), MAX(ts) "
                "FROM snapshots WHERE symbol = ? "
                "GROUP BY day, source, expiry ORDER BY day DESC",
                (symbol.upper(),)).fetchall()
        return [{"day": d, "source": s, "expiry": e, "count": c,
                 "from": lo, "to": hi} for d, s, e, c, lo, hi in rows]

    def get(self, symbol: str, day: str, source: str, expiry: int,
            index: int) -> dict | None:
        """Snapshot nº `index` (0-based, orden temporal) de esa sesión."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) FROM snapshots "
                "WHERE symbol=? AND day=? AND source=? AND expiry=?",
                (symbol.upper(), day, source, int(expiry))).fetchone()
            total = total_row[0]
            if total == 0:
                return None
            index = max(0, min(int(index), total - 1))
            row = self._conn.execute(
                "SELECT ts, payload FROM snapshots "
                "WHERE symbol=? AND day=? AND source=? AND expiry=? "
                "ORDER BY id LIMIT 1 OFFSET ?",
                (symbol.upper(), day, source, int(expiry), index)).fetchone()
        ts, blob = row
        return {"total": total, "index": index, "ts": ts,
                "payload": json.loads(zlib.decompress(blob).decode())}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
