"""Estado real del mercado vía /markets/clock de Tradier (exacto: incluye
feriados y medios días) con fallback heurístico cuando no hay token
(modo sim/Yahoo) para que el indicador del header funcione siempre,
solo que con menos precisión — nunca se cae ni queda en blanco.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}
NY = ZoneInfo("America/New_York")
MARKET_OPEN, MARKET_CLOSE = time(9, 30), time(16, 0)


def _heuristic_clock(now: datetime | None = None) -> dict:
    now = (now or datetime.now(NY)).astimezone(NY)
    is_open = now.weekday() < 5 and MARKET_OPEN <= now.time() < MARKET_CLOSE
    return {
        "state": "open" if is_open else "closed",
        "description": ("mercado abierto (estimado, no cuenta feriados)" if is_open
                        else "mercado cerrado (estimado, no cuenta feriados)"),
        "next_change": None,
        "next_state": None,
        "half_day": False,
        "source": "heuristic",
    }


async def _today_half_day(token: str, env: str, client: httpx.AsyncClient) -> bool:
    """Nunca debe tumbar el clock: si el calendario falla, se asume que
    no es medio día en vez de romper el badge entero."""
    from visual_options.stream.marketcalendar import today_entry
    try:
        entry = await today_entry(token, env, client=client)
        return bool(entry and entry.get("half_day"))
    except Exception:
        return False


async def market_clock(token: str | None = None, env: str = "prod",
                       client: httpx.AsyncClient | None = None,
                       now: datetime | None = None) -> dict:
    if not token:
        return _heuristic_clock(now)
    if env not in TRADIER_URLS:
        raise ValueError(f"entorno tradier desconocido: {env!r}")
    base = TRADIER_URLS[env]
    owns_client = client is None
    client = client or httpx.AsyncClient(headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json",
    }, timeout=15.0)
    try:
        response = await client.get(f"{base}/markets/clock")
        response.raise_for_status()
        clock = response.json().get("clock") or {}
        return {
            "state": clock.get("state", "unknown"),
            "description": clock.get("description", ""),
            "next_change": clock.get("next_change"),
            "next_state": clock.get("next_state"),
            "half_day": await _today_half_day(token, env, client),
            "source": "tradier",
        }
    except httpx.HTTPError:
        return _heuristic_clock(now)
    finally:
        if owns_client:
            await client.aclose()
