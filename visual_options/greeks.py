"""Las griegas (Cap. 3): delta, gamma, theta, vega y rho.

Convenciones del libro: theta por día natural, vega y rho por punto
porcentual (1%) de cambio. Las griegas de posición son la suma ponderada
por cantidad de cada pata.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm

from visual_options.pricing import DAYS_PER_YEAR, _d1_d2


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float  # por día
    vega: float   # por 1% de IV
    rho: float    # por 1% de tipo

    def __add__(self, other: "Greeks") -> "Greeks":
        return Greeks(
            self.delta + other.delta,
            self.gamma + other.gamma,
            self.theta + other.theta,
            self.vega + other.vega,
            self.rho + other.rho,
        )

    def scaled(self, quantity: float) -> "Greeks":
        return Greeks(
            self.delta * quantity,
            self.gamma * quantity,
            self.theta * quantity,
            self.vega * quantity,
            self.rho * quantity,
        )


ZERO_GREEKS = Greeks(0.0, 0.0, 0.0, 0.0, 0.0)


def bs_greeks(
    kind: str,
    spot: float,
    strike: float,
    days: float,
    iv: float,
    rate: float = 0.04,
    div_yield: float = 0.0,
) -> Greeks:
    """Griegas BSM de una opción individual (por acción)."""
    t = days / DAYS_PER_YEAR
    d1, d2 = _d1_d2(spot, strike, t, iv, rate, div_yield)
    disc_div = math.exp(-div_yield * t)
    disc_rate = math.exp(-rate * t)
    pdf_d1 = norm.pdf(d1)

    gamma = disc_div * pdf_d1 / (spot * iv * math.sqrt(t))
    vega = spot * disc_div * pdf_d1 * math.sqrt(t) / 100.0

    common_theta = -spot * disc_div * pdf_d1 * iv / (2.0 * math.sqrt(t))
    if kind == "call":
        delta = disc_div * norm.cdf(d1)
        theta = (
            common_theta
            - rate * strike * disc_rate * norm.cdf(d2)
            + div_yield * spot * disc_div * norm.cdf(d1)
        ) / DAYS_PER_YEAR
        rho = strike * t * disc_rate * norm.cdf(d2) / 100.0
    else:
        delta = -disc_div * norm.cdf(-d1)
        theta = (
            common_theta
            + rate * strike * disc_rate * norm.cdf(-d2)
            - div_yield * spot * disc_div * norm.cdf(-d1)
        ) / DAYS_PER_YEAR
        rho = -strike * t * disc_rate * norm.cdf(-d2) / 100.0

    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)


def stock_greeks(quantity: int) -> Greeks:
    """Las acciones tienen delta 1 por acción (normalizado a contratos de 100)."""
    return Greeks(delta=quantity / 100.0, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
