"""Stress test del portafolio real: ¿qué pasa con mi P&L si el subyacente
se mueve X% y la IV Y%? Reutiliza portfolio.py para leer las posiciones
(nunca las modifica) y el propio BSM del toolkit (pricing.py) para
recalcular cada opción bajo el escenario — sin pedir la IV a ningún
proveedor: se resuelve por inversión desde el precio de mercado reportado
en la posición (implied_volatility), así que funciona igual con IBKR que
con Tradier.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime

from visual_options.pricing import bs_price, implied_volatility
from visual_options.stream import portfolio as pf

SPOT_SHOCKS: tuple[float, ...] = (-0.10, -0.075, -0.05, -0.025, 0.0, 0.025, 0.05, 0.075, 0.10)
IV_SHOCKS: tuple[float, ...] = (-0.30, -0.15, 0.0, 0.15, 0.30)


def _days_to_expiry(expiry) -> int | None:
    if not expiry:
        return None
    s = str(expiry)
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d") if "-" in s else datetime.strptime(s[:8], "%Y%m%d")
    except ValueError:
        return None
    return max((dt - datetime.now()).days, 1)


def _fetch_spot_sync(symbol: str) -> float | None:
    import yfinance as yf
    ticker = yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)
    info = getattr(ticker, "fast_info", None)
    try:
        value = float(info["last_price"]) if info is not None else None
    except (KeyError, TypeError, ValueError):
        value = None
    if value and not math.isnan(value):
        return value
    try:
        history = ticker.history(period="5d", interval="1d")
        return float(history["Close"].dropna().iloc[-1])
    except Exception:
        return None


async def _default_spot_fetcher(symbol: str) -> float | None:
    return await asyncio.to_thread(_fetch_spot_sync, symbol)


def _build_model(position: dict, spot0: float | None) -> dict:
    """Prepara cómo re-precificar esta posición: BSM con IV implícita
    resuelta desde su propio precio, o fallback lineal por delta reportada."""
    if spot0 is None:
        return {"pos": position, "mode": "none"}
    if position["kind"] == "stock":
        return {"pos": position, "mode": "linear", "spot0": spot0}

    days = _days_to_expiry(position.get("expiry"))
    strike = position.get("strike")
    price = position.get("price")
    if not days or not strike or not price or price <= 0:
        return {"pos": position, "mode": "delta_only", "spot0": spot0}
    try:
        iv = implied_volatility(position["kind"], price, spot0, strike, days)
    except Exception:
        return {"pos": position, "mode": "delta_only", "spot0": spot0}
    return {"pos": position, "mode": "bsm", "spot0": spot0, "strike": strike,
           "days": days, "iv": iv, "kind": position["kind"]}


def _position_pnl(model: dict, spot_shock: float, iv_shock: float) -> float:
    p = model["pos"]
    mode = model["mode"]
    if mode == "none":
        return 0.0
    spot0 = model["spot0"]
    if mode == "linear":
        return p["qty"] * spot0 * spot_shock
    if mode == "delta_only":
        delta = p.get("delta")
        return delta * spot0 * spot_shock if delta is not None else 0.0
    # mode == "bsm"
    new_spot = spot0 * (1 + spot_shock)
    new_iv = max(0.01, model["iv"] * (1 + iv_shock))
    old_price = bs_price(model["kind"], spot0, model["strike"], model["days"], model["iv"])
    new_price = bs_price(model["kind"], new_spot, model["strike"], model["days"], new_iv)
    return (new_price - old_price) * p["qty"] * 100


async def stress_test(source: str = "ibkr", *, ib_host: str = "127.0.0.1", ib_port: int = 7496,
                      tradier_token: str | None = None, book: dict | None = None,
                      spot_fetcher=None) -> dict:
    """`book` y `spot_fetcher` inyectables para tests (evitan red/broker real)."""
    if book is None:
        if source == "ibkr":
            book = await pf.ibkr_portfolio(host=ib_host, port=ib_port)
        elif source in ("tradier", "tradier-delayed"):
            env = "prod" if source == "tradier" else "sandbox"
            if not tradier_token:
                raise ValueError("falta TRADIER_TOKEN")
            book = await pf.tradier_portfolio(tradier_token, env)
        else:
            raise ValueError("source debe ser 'ibkr', 'tradier' o 'tradier-delayed'")

    positions = book["positions"]
    fetch = spot_fetcher or _default_spot_fetcher
    underlyings = sorted({p["symbol"] for p in positions})
    spot_values = await asyncio.gather(*(fetch(u) for u in underlyings))
    spots = dict(zip(underlyings, spot_values))

    models = [_build_model(p, spots.get(p["symbol"])) for p in positions]
    modeled = sum(1 for m in models if m["mode"] == "bsm")
    linear_only = sum(1 for m in models if m["mode"] in ("linear", "delta_only"))
    unmodeled = sum(1 for m in models if m["mode"] == "none")

    matrix = []
    for iv_shock in IV_SHOCKS:
        row = [round(sum(_position_pnl(m, spot_shock, iv_shock) for m in models), 2)
               for spot_shock in SPOT_SHOCKS]
        matrix.append({"iv_shock": iv_shock, "pnl": row})

    return {
        "source": source, "account": book.get("account"),
        "n_positions": len(positions),
        "modeled_bsm": modeled, "modeled_linear": linear_only, "unmodeled": unmodeled,
        "spot_shocks": list(SPOT_SHOCKS), "iv_shocks": list(IV_SHOCKS),
        "matrix": matrix,
        "base_market_value": round(book["totals"]["market_value"], 2),
        "base_unrealized_pnl": round(book["totals"]["unrealized_pnl"], 2),
    }
