"""Posicionamiento de dealers por strike (réplica de CloutSeeker).

CloutSeeker calcula con Black-Scholes por strike: Call/Put/Net GEX,
Net DEX y call/put/net vanna a partir del open interest y la IV. Aquí
hacemos lo mismo con nuestro propio BSM (visual_options.pricing/greeks).

Convención de signos (la habitual en GEX, la misma del libro de la hoja):
los dealers están largos de calls (+) y cortos de puts (−); un Net GEX
positivo frena el precio, uno negativo lo acelera.

Escalas (en millones de $):
  GEX   = gamma · OI · 100 · spot² · 1%          (por 1% de movimiento)
  DEX   = delta · OI · 100 · spot                 (exposición direccional)
  Vanna = vanna · OI · 100 · spot · 1%            (por 1% de cambio de IV)
"""

from __future__ import annotations

import math

from scipy.stats import norm

from visual_options.greeks import bs_greeks
from visual_options.pricing import DAYS_PER_YEAR, _d1_d2
from visual_options.stream.state import StrikeRow

MILLION = 1e6


def bs_vanna(spot: float, strike: float, days: float, iv: float, rate: float = 0.04) -> float:
    """Vanna = ∂delta/∂sigma = -φ(d1)·d2/σ (por unidad de vol)."""
    t = days / DAYS_PER_YEAR
    if t <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    d1, d2 = _d1_d2(spot, strike, t, iv, rate, 0.0)
    return -norm.pdf(d1) * d2 / iv


def compute_exposures(rows: list[StrikeRow], spot: float, days: float,
                      rate: float = 0.04) -> None:
    """Rellena los campos de exposición de cada StrikeRow desde OI + IV.

    Requiere call_oi/put_oi y una IV por strike (campo iv, >0). Escala en
    millones de dólares. Muta las filas (los StrikeRow del stream son el
    estado vivo del dashboard).
    """
    if spot <= 0 or days <= 0:
        return
    for row in rows:
        iv = row.iv if row.iv > 0 else 0.20
        call = bs_greeks("call", spot, row.strike, days, iv, rate)
        put = bs_greeks("put", spot, row.strike, days, iv, rate)
        vanna = bs_vanna(spot, row.strike, days, iv, rate)

        gex_unit = 100 * spot ** 2 * 0.01 / MILLION
        row.call_gex = call.gamma * row.call_oi * gex_unit
        row.put_gex = -put.gamma * row.put_oi * gex_unit          # dealers cortos de puts
        row.net_gex = row.call_gex + row.put_gex
        row.gamma_exposure = row.net_gex                           # panel de gamma del flujo

        dex_unit = 100 * spot / MILLION
        row.net_dex = (call.delta * row.call_oi + put.delta * row.put_oi) * dex_unit

        vanna_unit = 100 * spot * 0.01 / MILLION
        row.call_vanna = vanna * row.call_oi * vanna_unit
        row.put_vanna = -vanna * row.put_oi * vanna_unit
        row.net_vanna = row.call_vanna + row.put_vanna


def gamma_flip_level(rows: list[StrikeRow]) -> float | None:
    """Strike donde el Net GEX acumulado cruza de negativo a positivo.

    Es el 'gamma flip' que la gente de CloutSeeker/SpotGamma usa como
    frontera entre régimen acelerador y amortiguador.
    """
    ordered = sorted(rows, key=lambda r: r.strike)
    cumulative = 0.0
    previous_strike: float | None = None
    previous_cum = 0.0
    for row in ordered:
        cumulative += row.net_gex
        if previous_strike is not None and previous_cum < 0 <= cumulative:
            span = cumulative - previous_cum
            frac = -previous_cum / span if span else 0.0
            return previous_strike + frac * (row.strike - previous_strike)
        previous_strike = row.strike
        previous_cum = cumulative
    return None
