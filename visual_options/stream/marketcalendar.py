"""Calendario mensual de Tradier: feriados y medios días — lo que el
market clock por sí solo no anticipa (el clock dice el estado de HOY,
esto dice cuándo el cierre no va a ser a las 16:00 de siempre, tipo
Black Friday o víspera de Año Nuevo). Se cachea en memoria por mes: el
calendario no cambia en el día, así que no tiene sentido pedirlo cada
vez que el badge del header se refresca.
"""

from __future__ import annotations

import time
from datetime import datetime

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}
CACHE_TTL = 6 * 3600.0  # 6 horas

_cache: dict[tuple[str, int, int], tuple[float, list[dict]]] = {}


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _shape_day(day: dict) -> dict:
    open_block = day.get("open") or {}
    close_time = open_block.get("end")
    half_day = day.get("status") == "open" and close_time not in (None, "16:00")
    return {
        "date": day.get("date"),
        "status": day.get("status"),
        "description": day.get("description", ""),
        "open": open_block.get("start"),
        "close": close_time,
        "half_day": half_day,
    }


async def market_calendar(token: str, env: str = "prod", month: int | None = None,
                          year: int | None = None, client=None) -> dict:
    """`client` inyectable para tests. month/year por defecto = mes actual."""
    if env not in TRADIER_URLS:
        raise ValueError(f"entorno tradier desconocido: {env!r}")
    now = datetime.now()
    month = month or now.month
    year = year or now.year
    key = (env, year, month)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL:
        days = cached[1]
    else:
        import httpx
        base = TRADIER_URLS[env]
        owns_client = client is None
        client = client or httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=10.0)
        try:
            response = await client.get(f"{base}/markets/calendar", params={"month": month, "year": year})
            response.raise_for_status()
            raw = (response.json().get("calendar") or {}).get("days", {})
            raw = raw.get("day") if isinstance(raw, dict) else None
            days = [_shape_day(d) for d in _as_list(raw)]
            _cache[key] = (time.monotonic(), days)
        finally:
            if owns_client:
                await client.aclose()

    return {
        "month": month, "year": year, "days": days,
        "half_days": [d for d in days if d["half_day"]],
        "holidays": [d for d in days if d["status"] == "closed" and d["description"]],
    }


async def today_entry(token: str, env: str = "prod", client=None) -> dict | None:
    """Solo la entrada de HOY del calendario — usado por marketclock.py
    para saber si el cierre de hoy no es a las 16:00 de siempre."""
    result = await market_calendar(token, env, client=client)
    today = datetime.now().strftime("%Y-%m-%d")
    return next((d for d in result["days"] if d["date"] == today), None)
