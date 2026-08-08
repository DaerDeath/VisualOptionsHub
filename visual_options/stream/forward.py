"""Forward price y coste de acarreo (NOVM), método exacto del libro (Cap. 2).

Interés SIMPLE, no capitalización continua — así lo hace el ejemplo de
IBM del libro: multiplicador de interés = días/365; monto de interés =
Spot × tasa × multiplicador; Cost of Carry = interés − dividendos hasta
el vencimiento; Forward = Spot + Cost of Carry.

La tasa libre de riesgo se toma del rendimiento del T-bill a 13 semanas
(^IRX en Yahoo, ya viene en % anualizado) — "el treasury correspondiente
al plazo hasta el vencimiento" que pide el libro — pero es editable en
la UI porque, como dice el libro, "esto puede variar de persona a
persona" según el plazo exacto.

De propina: el forward por capitalización continua (S·e^((r-q)T)), la
convención académica estándar que usa el resto del toolkit (pricing.py),
para comparar los dos métodos lado a lado.
"""

from __future__ import annotations

import math
from datetime import datetime

DAYS_PER_YEAR = 365.0
DEFAULT_RATE = 0.043  # fallback si no se puede leer ^IRX


def _ticker(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    return yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)


def _spot(ticker) -> float:
    info = getattr(ticker, "fast_info", None)
    for key in ("last_price", "lastPrice"):
        try:
            value = float(info[key]) if info is not None else None
        except (KeyError, TypeError, ValueError):
            value = None
        if value and not math.isnan(value):
            return value
    history = ticker.history(period="5d", interval="1d")
    return float(history["Close"].dropna().iloc[-1])


def risk_free_rate(rate_ticker_factory=None) -> float:
    """Rendimiento del T-bill a 13 semanas (^IRX), como fracción anual."""
    factory = rate_ticker_factory or (lambda: _ticker("IRX"))
    try:
        history = factory().history(period="5d", interval="1d")
        value = float(history["Close"].dropna().iloc[-1])
        if 0 < value < 30:
            return round(value / 100.0, 5)
    except Exception:
        pass
    return DEFAULT_RATE


TARGET_DEFAULT_DAYS = 30  # front-month: el coste de acarreo se aprecia mejor que a 0-1 día


def nearest_expiry_days(ticker) -> int:
    """Vencimiento por defecto: el más cercano a ~30 días (front month),
    no literalmente el primero — a 0-1 día el cost of carry es invisible."""
    expirations = ticker.options
    if not expirations:
        return TARGET_DEFAULT_DAYS
    now = datetime.now()
    candidates = [max(1, (datetime.strptime(e, "%Y-%m-%d") - now).days) for e in expirations]
    return min(candidates, key=lambda d: abs(d - TARGET_DEFAULT_DAYS))


def forward_analysis(symbol: str, days: int | None = None, rate: float | None = None,
                     ticker=None, rate_ticker_factory=None) -> dict:
    """Réplica exacta del método del libro, con desglose paso a paso."""
    ticker = ticker or _ticker(symbol)
    spot = _spot(ticker)
    if days is None:
        days = nearest_expiry_days(ticker)
    if days <= 0:
        raise ValueError("days debe ser positivo")
    rate_source = "manual"
    if rate is None:
        rate = risk_free_rate(rate_ticker_factory)
        rate_source = "T-bill 13 semanas (^IRX)"
    if not (0 <= rate <= 1):
        raise ValueError("rate debe ser una fracción entre 0 y 1 (ej. 0.043 = 4.3%)")

    info = getattr(ticker, "info", {}) or {}
    annual_dividend = float(info.get("dividendRate") or 0.0)
    dividends_to_expiry = round(annual_dividend * days / DAYS_PER_YEAR, 4)

    interest_multiplier = round(days / DAYS_PER_YEAR, 4)
    interest_amount = round(spot * rate * interest_multiplier, 4)
    cost_of_carry = round(interest_amount - dividends_to_expiry, 4)
    forward_simple = round(spot + cost_of_carry, 4)

    # de propina: forward por capitalización continua, para comparar
    div_yield = (annual_dividend / spot) if spot else 0.0
    t_years = days / DAYS_PER_YEAR
    forward_continuous = round(spot * math.exp((rate - div_yield) * t_years), 4)

    put_over_call_atm = round(spot - forward_simple, 4)

    steps = [
        {"label": "Precio spot", "formula": "S", "value": round(spot, 4)},
        {"label": "Multiplicador de interés", "formula": "días / 365",
         "value": interest_multiplier, "detail": f"{days} / 365"},
        {"label": "Monto de interés", "formula": "S × tasa × multiplicador",
         "value": interest_amount,
         "detail": f"{spot:.2f} × {rate * 100:.3f}% × {interest_multiplier:.4f}"},
        {"label": "Dividendos hasta el vencimiento", "formula": "dividendo anual × (días / 365)",
         "value": dividends_to_expiry,
         "detail": f"{annual_dividend:.2f} × {interest_multiplier:.4f}"},
        {"label": "Cost of Carry", "formula": "interés − dividendos",
         "value": cost_of_carry, "detail": f"{interest_amount:.4f} − {dividends_to_expiry:.4f}"},
        {"label": "Forward Price", "formula": "S + Cost of Carry",
         "value": forward_simple, "detail": f"{spot:.4f} + {cost_of_carry:.4f}"},
    ]

    return {
        "symbol": symbol.upper(), "spot": round(spot, 4), "days": days,
        "rate": rate, "rate_source": rate_source,
        "annual_dividend": annual_dividend, "dividends_to_expiry": dividends_to_expiry,
        "interest_multiplier": interest_multiplier, "interest_amount": interest_amount,
        "cost_of_carry": cost_of_carry,
        "forward_simple": forward_simple, "forward_continuous": forward_continuous,
        "put_over_call_atm": put_over_call_atm,
        "carry_direction": "dividendos superan al interés (forward < spot, puts más caros)"
                           if cost_of_carry < 0 else
                           "interés supera a los dividendos (forward > spot, calls más caros)",
        "steps": steps,
    }
