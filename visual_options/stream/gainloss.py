"""P&L realizado de operaciones YA CERRADAS en la cuenta Tradier —
SOLO LECTURA. Portfolio.py muestra lo que sigue abierto; esto muestra
cómo salieron las que ya cerraste, con coste base, proceeds y ganancia/
pérdida real — el número que le falta al Diario y al Grading para saber
si el checklist del libro de verdad se traduce en resultados.
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


def _shape_closed(item: dict) -> dict:
    gain = _num(item.get("gain_loss")) or 0.0
    cost = _num(item.get("cost")) or 0.0
    return {
        "symbol": item.get("symbol"),
        "close_date": item.get("close_date"),
        "open_date": item.get("open_date"),
        "qty": _num(item.get("quantity")),
        "cost_basis": round(cost, 2),
        "proceeds": round(_num(item.get("proceeds")) or 0.0, 2),
        "gain_loss": round(gain, 2),
        "gain_loss_pct": round(_num(item.get("gain_loss_percent")) or 0.0, 2),
        "term": item.get("term"),
    }


def _summarize(closed: list[dict]) -> dict:
    if not closed:
        return {"n_trades": 0, "wins": 0, "losses": 0, "win_rate": None,
               "total_pnl": 0.0, "avg_win": None, "avg_loss": None}
    wins = [c["gain_loss"] for c in closed if c["gain_loss"] > 0]
    losses = [c["gain_loss"] for c in closed if c["gain_loss"] < 0]
    return {
        "n_trades": len(closed),
        "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1),
        "total_pnl": round(sum(c["gain_loss"] for c in closed), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
    }


async def tradier_gainloss(token: str, env: str = "prod", client=None) -> dict:
    """`client` inyectable para tests. Solo lee — Tradier no permite
    modificar históricos de todas formas, pero por claridad: esta llamada
    es un GET puro."""
    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15.0)
    try:
        account_id = await resolve_tradier_account(client, base)
        response = await client.get(f"{base}/accounts/{account_id}/gainloss")
        response.raise_for_status()
        raw = (response.json().get("gainloss") or {}).get("closed_position")
        closed = [_shape_closed(c) for c in _as_list(raw)]
        closed.sort(key=lambda c: c.get("close_date") or "", reverse=True)
        return {"account": account_id, "closed": closed, "summary": _summarize(closed)}
    finally:
        if owns_client:
            await client.aclose()
