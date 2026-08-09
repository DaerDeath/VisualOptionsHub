"""Búsqueda real de símbolos vía Tradier (/markets/lookup por ticker +
/markets/search por nombre de empresa) — reemplaza en el frontend la
lista estática de ~80 tickers de symbols.js cuando hay token, cubriendo
miles de acciones y ETFs reales en vez de solo los que elegí a mano.
"""

from __future__ import annotations

import asyncio

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


async def search_symbols(query: str, token: str, env: str = "prod",
                         client=None, limit: int = 12) -> list[dict]:
    """`client` inyectable para tests. [{"symbol": ..., "name": ...}, ...]"""
    query = query.strip()
    if not query:
        return []
    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=10.0)
    try:
        lookup_resp, search_resp = await asyncio.gather(
            client.get(f"{base}/markets/lookup", params={"q": query, "types": "stock,etf"}),
            client.get(f"{base}/markets/search", params={"q": query}),
            return_exceptions=True,
        )
        results: dict[str, dict] = {}
        for resp in (lookup_resp, search_resp):
            if isinstance(resp, Exception) or resp.status_code != 200:
                continue
            raw = (resp.json().get("securities") or {}).get("security")
            for item in _as_list(raw):
                symbol = item.get("symbol")
                if symbol and symbol not in results:
                    results[symbol] = {"symbol": symbol, "name": item.get("description", "")}
        if not results and isinstance(lookup_resp, Exception) and isinstance(search_resp, Exception):
            raise lookup_resp
        return list(results.values())[:limit]
    finally:
        if owns_client:
            await client.aclose()
