"""Lista Easy-To-Borrow de Tradier: qué acciones se pueden pedir
prestadas sin fricción para venderlas en corto. Poca relación directa
con las verticales de opciones que arma el resto del toolkit (ahí no
hace falta pedir prestado nada), pero es contexto rápido para la ficha
de Empresa junto al short interest que ya se lee de Yahoo.

La lista completa son miles de símbolos y no cambia intradía, así que
se cachea en memoria por entorno en vez de pedirla en cada consulta.
"""

from __future__ import annotations

import time

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}
CACHE_TTL = 6 * 3600.0  # 6 horas

_cache: dict[str, tuple[float, set[str]]] = {}


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


async def _fetch_etb_set(token: str, env: str, client=None) -> set[str]:
    cached = _cache.get(env)
    if cached and time.monotonic() - cached[0] < CACHE_TTL:
        return cached[1]

    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15.0)
    try:
        response = await client.get(f"{base}/markets/etb")
        response.raise_for_status()
        raw = (response.json().get("securities") or {}).get("security")
        symbols: set[str] = set()
        for item in _as_list(raw):
            symbol = item.get("symbol") if isinstance(item, dict) else item
            if symbol:
                symbols.add(str(symbol).upper())
        _cache[env] = (time.monotonic(), symbols)
        return symbols
    finally:
        if owns_client:
            await client.aclose()


async def is_easy_to_borrow(symbol: str, token: str, env: str = "prod", client=None) -> bool:
    """`client` inyectable para tests."""
    symbols = await _fetch_etb_set(token, env, client=client)
    return symbol.upper() in symbols
