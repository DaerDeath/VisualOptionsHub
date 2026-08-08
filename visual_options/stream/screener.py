"""Screener multi-símbolo de verticales de crédito según las reglas del
Cap. 2 del libro: strike corto vendido a ≥1 desviación estándar del spot
y rendimiento (crédito / riesgo) de al menos 12-15% (nunca por debajo del
10%). Combina tres piezas del toolkit que ya existían por separado:
`pricing.expected_move` para el ≥1σ, la cadena real de opciones (mismo
yfinance que grading_live.py/company.py, sin coste) para strikes y primas,
y `builders`/`strategies.Strategy` (el motor de la Calculadora) para
max profit/max risk/probabilidad de beneficio — así el número de
rendimiento que muestra el screener es el mismo que vería el usuario si
metiera la posición a mano en la Calculadora.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime

from visual_options import builders as _builders  # noqa: F401 (puebla el registro)
from visual_options.pricing import expected_move
from visual_options.strategies import STRATEGY_BUILDERS

DEFAULT_SYMBOLS: tuple[str, ...] = ("QQQ", "SPY", "IWM", "AAPL", "MSFT", "NVDA", "AMZN", "TSLA")
DEFAULT_MIN_DAYS = 25
DEFAULT_MAX_DAYS = 45
DEFAULT_MIN_RETURN = 0.12  # 12%, el mínimo del libro
DEFAULT_MIN_SIGMA = 1.0


def _ticker_default(symbol: str):
    import yfinance as yf
    return yf.Ticker(symbol.upper())


def _spot_of(ticker) -> float | None:
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


def _pick_expiry(ticker, min_days: int, max_days: int) -> tuple[str, int] | None:
    """Primer vencimiento dentro de [min_days, max_days]; si ninguno cae en el
    rango, el más cercano a max_days como fallback (mejor eso que nada)."""
    today = datetime.now()
    fallback = None
    for expiry in ticker.options:
        try:
            dt = datetime.strptime(expiry, "%Y-%m-%d")
        except ValueError:
            continue
        days = (dt - today).days
        if days < min_days:
            continue
        if min_days <= days <= max_days:
            return expiry, days
        if fallback is None or days < fallback[1]:
            fallback = (expiry, days)
    return fallback


def _mid_price(row) -> float | None:
    bid, ask, last = row.get("bid"), row.get("ask"), row.get("lastPrice")
    if bid and ask and ask > 0 and ask >= bid:
        return float((bid + ask) / 2)
    if last and last > 0:
        return float(last)
    return None


def _atm_iv(frame, spot: float) -> float | None:
    if frame is None or not len(frame):
        return None
    nearest = (frame["strike"] - spot).abs().idxmin()
    iv = frame.loc[nearest].get("impliedVolatility")
    if iv is None or (isinstance(iv, float) and math.isnan(iv)) or not (0.01 < iv < 5):
        return None
    return float(iv)


def _short_strike_row(frame, target: float, side: str):
    """side='put': strike más cercano al spot entre los que están a ≥1σ por
    debajo (maximiza la prima sin romper la regla). side='call': análogo
    por encima."""
    if side == "put":
        candidates = frame[frame["strike"] <= target]
        if candidates.empty:
            return None
        return candidates.loc[candidates["strike"].idxmax()]
    candidates = frame[frame["strike"] >= target]
    if candidates.empty:
        return None
    return candidates.loc[candidates["strike"].idxmin()]


def _long_strike_row(frame, short_strike: float, side: str):
    """El siguiente strike disponible un peldaño más OTM que el corto, para
    definir el riesgo (vertical, no naked)."""
    if side == "put":
        candidates = frame[frame["strike"] < short_strike]
        if candidates.empty:
            return None
        return candidates.loc[candidates["strike"].idxmax()]
    candidates = frame[frame["strike"] > short_strike]
    if candidates.empty:
        return None
    return candidates.loc[candidates["strike"].idxmin()]


def _build_candidate(symbol: str, side: str, spot: float, expiry: str, days: int,
                     frame, min_return: float, min_sigma: float) -> dict | None:
    iv_atm = _atm_iv(frame, spot)
    if iv_atm is None:
        return None
    sigma_move = expected_move(spot, iv_atm, days)
    if sigma_move <= 0:
        return None
    target = spot - min_sigma * sigma_move if side == "put" else spot + min_sigma * sigma_move

    short_row = _short_strike_row(frame, target, side)
    if short_row is None:
        return None
    long_row = _long_strike_row(frame, float(short_row["strike"]), side)
    if long_row is None:
        return None

    short_premium = _mid_price(short_row)
    long_premium = _mid_price(long_row)
    if short_premium is None or long_premium is None or short_premium <= long_premium:
        return None

    builder_name = "bull_put_spread" if side == "put" else "bear_call_spread"
    builder = STRATEGY_BUILDERS[builder_name]
    if side == "put":
        strategy = builder(float(short_row["strike"]), short_premium, float(long_row["strike"]), long_premium)
    else:
        strategy = builder(float(short_row["strike"]), short_premium, float(long_row["strike"]), long_premium)

    max_profit = strategy.max_profit()
    max_loss = strategy.max_loss()
    if max_loss <= 0 or math.isinf(max_loss):
        return None
    return_pct = max_profit / max_loss
    if return_pct < min_return:
        return None

    sigma_distance = abs(float(short_row["strike"]) - spot) / sigma_move
    try:
        pop = strategy.probability_of_profit(spot, iv_atm, days)
    except ValueError:
        pop = None

    return {
        "symbol": symbol,
        "strategy": "Bull put spread" if side == "put" else "Bear call spread",
        "side": side,
        "spot": round(spot, 2),
        "expiry": expiry,
        "days": days,
        "short_strike": float(short_row["strike"]),
        "long_strike": float(long_row["strike"]),
        "credit": round(max_profit, 3),
        "max_risk": round(max_loss, 3),
        "return_pct": round(return_pct, 4),
        "sigma_distance": round(sigma_distance, 2),
        "iv_atm": round(iv_atm, 4),
        "pop": round(pop, 4) if pop is not None else None,
    }


def scan_symbol(symbol: str, *, ticker=None, min_days: int = DEFAULT_MIN_DAYS,
                max_days: int = DEFAULT_MAX_DAYS, min_return: float = DEFAULT_MIN_RETURN,
                min_sigma: float = DEFAULT_MIN_SIGMA, sides: tuple[str, ...] = ("put", "call")) -> dict:
    """Sin red si `ticker` viene inyectado (tests). Devuelve
    {"candidates": [...], "skip_reason": str | None}."""
    symbol = symbol.upper()
    tk = ticker if ticker is not None else _ticker_default(symbol)

    spot = _spot_of(tk)
    if spot is None:
        return {"candidates": [], "skip_reason": "sin precio del subyacente"}

    options = getattr(tk, "options", ())
    if not options:
        return {"candidates": [], "skip_reason": "sin cadena de opciones"}

    picked = _pick_expiry(tk, min_days, max_days)
    if picked is None:
        return {"candidates": [], "skip_reason": "sin vencimiento en el rango de días pedido"}
    expiry, days = picked

    chain = tk.option_chain(expiry)
    candidates = []
    if "put" in sides and chain.puts is not None and len(chain.puts):
        c = _build_candidate(symbol, "put", spot, expiry, days, chain.puts, min_return, min_sigma)
        if c:
            candidates.append(c)
    if "call" in sides and chain.calls is not None and len(chain.calls):
        c = _build_candidate(symbol, "call", spot, expiry, days, chain.calls, min_return, min_sigma)
        if c:
            candidates.append(c)

    if not candidates:
        return {"candidates": [], "skip_reason": "ningún spread cumple ≥1σ y rendimiento mínimo"}
    return {"candidates": candidates, "skip_reason": None}


async def scan(symbols: tuple[str, ...] = DEFAULT_SYMBOLS, *, min_days: int = DEFAULT_MIN_DAYS,
               max_days: int = DEFAULT_MAX_DAYS, min_return: float = DEFAULT_MIN_RETURN,
               min_sigma: float = DEFAULT_MIN_SIGMA, sides: tuple[str, ...] = ("put", "call"),
               scanner=None) -> dict:
    """`scanner` inyectable en tests: callable(symbol) -> dict (evita red real)."""
    fn = scanner or (lambda s: scan_symbol(s, min_days=min_days, max_days=max_days,
                                           min_return=min_return, min_sigma=min_sigma, sides=sides))
    results = await asyncio.gather(*(asyncio.to_thread(fn, s) for s in symbols))

    candidates: list[dict] = []
    skipped: list[dict] = []
    for symbol, result in zip(symbols, results):
        if result["candidates"]:
            candidates.extend(result["candidates"])
        else:
            skipped.append({"symbol": symbol.upper(), "reason": result["skip_reason"]})

    candidates.sort(key=lambda c: c["return_pct"], reverse=True)
    return {
        "candidates": candidates,
        "skipped": skipped,
        "scanned": len(symbols),
        "min_return": min_return,
        "min_sigma": min_sigma,
    }
