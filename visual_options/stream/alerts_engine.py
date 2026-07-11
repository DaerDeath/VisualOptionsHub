"""Alertas en el servidor: se evalúan en cada difusión del manager y
disparan notificación de escritorio (notify-send) aunque no haya ninguna
pestaña abierta. Persisten en la misma base SQLite de las sesiones.

Tipos: price_above, price_below (cruce), call_sell_below, put_sell_below
(umbral), gamma_flip (cruce del nivel).
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from visual_options.stream.persistence import DEFAULT_DB

TYPES = ("price_above", "price_below", "call_sell_below", "put_sell_below", "gamma_flip")


def describe(alert: dict) -> str:
    t, v = alert["type"], alert.get("value")
    if t == "price_above":
        return f"precio cruza ↑ {v}"
    if t == "price_below":
        return f"precio cruza ↓ {v}"
    if t == "call_sell_below":
        return f"call sell % < {v} (posible squeeze)"
    if t == "put_sell_below":
        return f"put sell % < {v}"
    if t == "gamma_flip":
        return "precio cruza el gamma flip"
    return t


class AlertEngine:
    def __init__(self, db_path: str | Path | None = None) -> None:
        path = Path(db_path) if db_path else DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._last_spot: dict[str, float] = {}
        self.notify_cmd = shutil.which("notify-send")
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY, symbol TEXT NOT NULL,
                    type TEXT NOT NULL, value REAL, done INTEGER DEFAULT 0)""")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_log (
                    id INTEGER PRIMARY KEY, ts TEXT NOT NULL,
                    symbol TEXT NOT NULL, text TEXT NOT NULL, spot REAL)""")
            self._conn.commit()

    # ------------------------------------------------------------- CRUD

    def create(self, symbol: str, type_: str, value: float | None) -> dict:
        if type_ not in TYPES:
            raise ValueError(f"tipo de alerta desconocido: {type_}")
        if type_ != "gamma_flip" and value is None:
            raise ValueError("esta alerta necesita un valor")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO alerts (symbol, type, value) VALUES (?, ?, ?)",
                (symbol.upper(), type_, value))
            self._conn.commit()
            return {"id": cur.lastrowid, "symbol": symbol.upper(),
                    "type": type_, "value": value, "done": 0}

    def active(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, symbol, type, value FROM alerts WHERE done = 0 ORDER BY id").fetchall()
        return [{"id": i, "symbol": s, "type": t, "value": v} for i, s, t, v in rows]

    def delete(self, alert_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            self._conn.commit()

    def log(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, symbol, text, spot FROM alert_log ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        return [{"ts": ts, "symbol": s, "text": t, "spot": sp} for ts, s, t, sp in rows]

    def clear_log(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM alert_log")
            self._conn.commit()

    # ------------------------------------------------------------ chequeo

    def check_state(self, state) -> None:
        """Evalúa las alertas del símbolo contra el DashboardState vivo."""
        spot = float(state.spot or 0)
        if spot <= 0:
            return
        symbol = state.symbol
        last = state.series[-1] if state.series else None
        call_sell = last.call_sell_pct if last else None
        put_sell = last.put_sell_pct if last else None
        previous = self._last_spot.get(symbol)
        self._last_spot[symbol] = spot

        for alert in self.active():
            if alert["symbol"] != symbol:
                continue
            v, t = alert["value"], alert["type"]
            hit = False
            if t == "price_above":
                hit = previous is not None and previous < v <= spot
            elif t == "price_below":
                hit = previous is not None and previous > v >= spot
            elif t == "call_sell_below":
                hit = call_sell is not None and call_sell < v
            elif t == "put_sell_below":
                hit = put_sell is not None and put_sell < v
            elif t == "gamma_flip" and state.gamma_flip and previous is not None:
                flip = state.gamma_flip
                hit = (previous - flip) * (spot - flip) < 0
            if hit:
                self._fire(alert, spot)

    def _fire(self, alert: dict, spot: float) -> None:
        text = describe(alert)
        with self._lock:
            self._conn.execute("UPDATE alerts SET done = 1 WHERE id = ?", (alert["id"],))
            self._conn.execute(
                "INSERT INTO alert_log (ts, symbol, text, spot) VALUES (?, ?, ?, ?)",
                (datetime.now().strftime("%H:%M:%S"), alert["symbol"], text, spot))
            self._conn.commit()
        if self.notify_cmd:
            try:
                subprocess.Popen(
                    [self.notify_cmd, "-u", "critical", "-a", "visual-options",
                     f"⚡ {alert['symbol']}: {text}", f"spot {spot:.2f}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            self._conn.close()
