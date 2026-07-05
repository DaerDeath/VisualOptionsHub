"""Valoración Black-Scholes-Merton y probabilidades (Cap. 1-2).

Incluye lo que el libro usa constantemente: precio teórico, volatilidad
implícita, probabilidad de terminar ITM, movimiento esperado (1 desviación
estándar ≈ 68-70% según el libro) y paridad put-call.
"""

from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm

DAYS_PER_YEAR = 365.0


def _d1_d2(spot: float, strike: float, t_years: float, iv: float, rate: float, div_yield: float) -> tuple[float, float]:
    if t_years <= 0 or iv <= 0:
        raise ValueError("t_years e iv deben ser positivos")
    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * iv**2) * t_years) / (iv * math.sqrt(t_years))
    return d1, d1 - iv * math.sqrt(t_years)


def bs_price(
    kind: str,
    spot: float,
    strike: float,
    days: float,
    iv: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> float:
    """Precio teórico BSM por acción. days = días naturales a expiración."""
    t = days / DAYS_PER_YEAR
    if t <= 0:
        return max(spot - strike, 0.0) if kind == "call" else max(strike - spot, 0.0)
    d1, d2 = _d1_d2(spot, strike, t, iv, rate, div_yield)
    if kind == "call":
        return spot * math.exp(-div_yield * t) * norm.cdf(d1) - strike * math.exp(-rate * t) * norm.cdf(d2)
    return strike * math.exp(-rate * t) * norm.cdf(-d2) - spot * math.exp(-div_yield * t) * norm.cdf(-d1)


def implied_volatility(
    kind: str,
    market_price: float,
    spot: float,
    strike: float,
    days: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> float:
    """Resuelve la IV que reproduce el precio de mercado (Brent, 1%-500%)."""
    if market_price <= 0:
        raise ValueError("market_price debe ser positivo")

    def objective(iv: float) -> float:
        return bs_price(kind, spot, strike, days, iv, rate, div_yield) - market_price

    return brentq(objective, 1e-2, 5.0, xtol=1e-8)


def probability_itm(
    kind: str,
    spot: float,
    strike: float,
    days: float,
    iv: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> float:
    """Probabilidad (risk-neutral) de expirar ITM: N(d2) para calls, N(-d2) para puts."""
    t = days / DAYS_PER_YEAR
    _, d2 = _d1_d2(spot, strike, t, iv, rate, div_yield)
    return float(norm.cdf(d2) if kind == "call" else norm.cdf(-d2))


def expected_move(spot: float, iv: float, days: float) -> float:
    """Movimiento esperado de 1 desviación estándar hasta expiración.

    El libro (Cap. 2) lo usa para posicionar strikes cortos: "una desviación
    estándar es aproximadamente el 70 por ciento".
    """
    return spot * iv * math.sqrt(days / DAYS_PER_YEAR)


def straddle_expected_move(straddle_price: float, spot: float) -> float:
    """Movimiento implícito por el precio del straddle ATM como % del spot.

    Cap. 7: contrastar el straddle ATM (<10 días) como porcentaje del precio
    del subyacente con el movimiento implícito a un día.
    """
    return straddle_price / spot


def put_call_parity_put(call_price: float, spot: float, strike: float, days: float, rate: float = 0.04) -> float:
    """Precio del put por paridad put-call: P = C - S + K·e^(-rT)."""
    t = days / DAYS_PER_YEAR
    return call_price - spot + strike * math.exp(-rate * t)
