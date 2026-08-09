"""Watchlists reales de la cuenta Tradier: para que el Screener y el
Scanner puedan partir de los símbolos que el usuario ya sigue en su
broker en vez de una lista genérica. Solo lectura — nunca crea, edita
ni borra watchlists en la cuenta.

Nota de la API: Tradier viene de convertir XML a JSON, así que cuando
hay un único elemento (una sola watchlist, o una watchlist con un solo
símbolo) el campo llega como objeto suelto en vez de lista — `_as_list`
normaliza ambos casos.
"""

from __future__ import annotations

import httpx

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


async def list_watchlists(token: str, env: str = "prod",
                          client: httpx.AsyncClient | None = None) -> list[dict]:
    """[{"id": ..., "name": ..., "symbols": [...]}, ...]"""
    if env not in TRADIER_URLS:
        raise ValueError(f"entorno tradier desconocido: {env!r}")
    base = TRADIER_URLS[env]
    owns_client = client is None
    client = client or httpx.AsyncClient(headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json",
    }, timeout=15.0)
    try:
        response = await client.get(f"{base}/watchlists")
        response.raise_for_status()
        raw = (response.json().get("watchlists") or {}).get("watchlist")
        result = []
        for wl in _as_list(raw):
            items = _as_list((wl.get("items") or {}).get("item"))
            symbols = sorted({it["symbol"] for it in items if "symbol" in it})
            result.append({"id": wl.get("id"), "name": wl.get("name", ""), "symbols": symbols})
        return result
    finally:
        if owns_client:
            await client.aclose()
