"""Órdenes reales de la cuenta Tradier — SOLO LECTURA. Lista lo que ya
está pendiente, ejecutado o cancelado; nunca coloca, modifica ni cancela
ninguna orden. Complemento de portfolio.py: mismas posiciones no cuentan
una orden que quedó parcialmente ejecutada o que sigue trabajando.
"""

from __future__ import annotations

import math

from visual_options.stream.portfolio import TRADIER_URLS, resolve_tradier_account


def _num(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else value


def _as_list(value: object) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _shape_order(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "symbol": item.get("symbol"),
        "kind": item.get("class"),
        "side": item.get("side"),
        "qty": _num(item.get("quantity")),
        "type": item.get("type"),
        "status": item.get("status"),
        "price": _num(item.get("price")),
        "avg_fill_price": _num(item.get("avg_fill_price")),
        "filled_qty": _num(item.get("exec_quantity")),
        "duration": item.get("duration"),
        "created_at": item.get("create_date"),
        "option_symbol": item.get("option_symbol"),
    }


async def tradier_orders(token: str, env: str = "prod", client=None) -> dict:
    """`client` inyectable para tests. Nunca coloca/edita/cancela nada."""
    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15.0)
    try:
        account_id = await resolve_tradier_account(client, base)
        response = await client.get(f"{base}/accounts/{account_id}/orders")
        response.raise_for_status()
        raw = (response.json().get("orders") or {}).get("order")
        orders = [_shape_order(o) for o in _as_list(raw)]
        orders.sort(key=lambda o: o.get("created_at") or "", reverse=True)
        return {"account": account_id, "orders": orders}
    finally:
        if owns_client:
            await client.aclose()
