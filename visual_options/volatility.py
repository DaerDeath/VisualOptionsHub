"""Análisis de volatilidad (Cap. 2 y 7).

El libro insiste: "todo vuelve a la volatilidad". Aquí están las
herramientas que usa: volatilidad histórica (HV), comparación IV/HV para
decidir si eres comprador o vendedor neto, y rank/percentil de IV.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

TRADING_DAYS_PER_YEAR = 252


def historical_volatility(closes: Sequence[float], window: int | None = None) -> float:
    """HV anualizada close-to-close (desviación estándar de retornos log)."""
    prices = np.asarray(closes, dtype=float)
    if window is not None:
        prices = prices[-(window + 1):]
    if len(prices) < 3:
        raise ValueError("se necesitan al menos 3 cierres")
    log_returns = np.diff(np.log(prices))
    return float(np.std(log_returns, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


def iv_hv_ratio(iv: float, hv: float) -> float:
    """IV relativa a HV. >1 opciones 'caras' (favorece vender), <1 'baratas'.

    Cap. 2 (grading, criterio 4c): "relativamente baja si eres comprador
    neto, alta si eres vendedor neto".
    """
    if hv <= 0:
        raise ValueError("hv debe ser positiva")
    return iv / hv


def iv_rank(current_iv: float, iv_history: Sequence[float]) -> float:
    """Posición de la IV actual dentro del rango [min, max] histórico, 0-100."""
    history = np.asarray(iv_history, dtype=float)
    lo, hi = float(history.min()), float(history.max())
    if hi == lo:
        return 50.0
    return 100.0 * (current_iv - lo) / (hi - lo)


def iv_percentile(current_iv: float, iv_history: Sequence[float]) -> float:
    """Porcentaje de días históricos con IV por debajo de la actual, 0-100."""
    history = np.asarray(iv_history, dtype=float)
    if len(history) == 0:
        raise ValueError("iv_history vacío")
    return 100.0 * float(np.mean(history < current_iv))


def volatility_bias(iv: float, hv: float, expensive_threshold: float = 1.2, cheap_threshold: float = 0.8) -> str:
    """Recomendación cualitativa del libro según IV relativa.

    IV >> HV → estrategias de venta de prima (verticales de crédito, iron
    condor corto, mariposa larga). IV << HV → compra de prima (straddle,
    strangle, verticales de débito).
    """
    ratio = iv_hv_ratio(iv, hv)
    if ratio >= expensive_threshold:
        return "vendedor"
    if ratio <= cheap_threshold:
        return "comprador"
    return "neutral"
