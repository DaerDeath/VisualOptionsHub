"""Clase Strategy: analítica común a todas las estrategias (Cap. 4-6).

El payoff a expiración de cualquier combinación de opciones y acciones es
lineal a trozos con quiebres en los strikes; eso permite calcular max
profit, max risk, breakevens y zonas de beneficio de forma exacta, y
verificar contra las fórmulas literales del libro (ver builders.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from visual_options.contracts import OptionLeg, StockLeg
from visual_options.greeks import ZERO_GREEKS, Greeks, bs_greeks, stock_greeks
from visual_options.pricing import DAYS_PER_YEAR, bs_price

Leg = OptionLeg | StockLeg

_FAR_MULTIPLE = 4.0


@dataclass(frozen=True)
class Strategy:
    """Posición de opciones con metadatos del libro."""

    name: str
    sentiment: str
    chapter: str
    legs: tuple[Leg, ...]
    notes: str = ""
    book_max_profit: str = ""
    book_max_risk: str = ""
    book_breakeven: str = ""
    _kinks: tuple[float, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError("una estrategia necesita al menos una pata")
        strikes = sorted({leg.strike for leg in self.legs if isinstance(leg, OptionLeg)})
        object.__setattr__(self, "_kinks", tuple(strikes))

    # ------------------------------------------------------------------ payoff

    def payoff(self, spots: np.ndarray | float) -> np.ndarray | float:
        """P/L por contrato (por acción, multiplicar por 100 para dólares)."""
        spots = np.asarray(spots, dtype=float)
        total = np.zeros_like(spots)
        for leg in self.legs:
            total = total + leg.payoff_at_expiry(spots)
        return total

    def net_premium(self) -> float:
        """Prima neta de las patas de opción: >0 débito pagado, <0 crédito."""
        return sum(leg.quantity * leg.premium for leg in self.legs if isinstance(leg, OptionLeg))

    def _reference_points(self) -> np.ndarray:
        """Puntos donde el payoff puede alcanzar extremos: 0+, strikes y lejos."""
        kinks = list(self._kinks) or [100.0]
        far = max(kinks) * _FAR_MULTIPLE
        return np.array([1e-9, *kinks, far])

    def _edge_slopes(self) -> tuple[float, float]:
        """Pendiente del payoff en los extremos (abajo, arriba)."""
        points = self._reference_points()
        low_slope = float((self.payoff(points[1]) - self.payoff(points[0])) / (points[1] - points[0])) if len(points) > 1 else 0.0
        eps = points[-1] * 0.01
        high_slope = float((self.payoff(points[-1] + eps) - self.payoff(points[-1])) / eps)
        return low_slope, high_slope

    def max_profit(self) -> float:
        """Beneficio máximo por acción; math.inf si es ilimitado."""
        _, high_slope = self._edge_slopes()
        if high_slope > 1e-12:
            return math.inf
        return float(np.max(self.payoff(self._reference_points())))

    def max_loss(self) -> float:
        """Pérdida máxima por acción (valor positivo); math.inf si ilimitada."""
        low_slope, high_slope = self._edge_slopes()
        if high_slope < -1e-12:
            return math.inf
        worst = float(np.min(self.payoff(self._reference_points())))
        if low_slope > 1e-12:
            worst = min(worst, float(self.payoff(1e-9)))
        return -worst if worst < 0 else 0.0

    def breakevens(self) -> tuple[float, ...]:
        """Puntos de equilibrio a expiración (interpolación exacta entre quiebres)."""
        points = self._reference_points()
        values = np.asarray(self.payoff(points))
        result: list[float] = []
        for i in range(len(points) - 1):
            v0, v1 = values[i], values[i + 1]
            if v0 == 0.0 and points[i] > 1e-6:
                result.append(float(points[i]))
            if v0 * v1 < 0:
                x = points[i] + (points[i + 1] - points[i]) * (-v0 / (v1 - v0))
                result.append(float(x))
        return tuple(sorted(set(round(x, 6) for x in result)))

    def profit_zones(self) -> tuple[tuple[float, float], ...]:
        """Rangos de spot a expiración con P/L positivo (Cap. 6: 'profit zone')."""
        boundaries = [0.0, *self.breakevens(), math.inf]
        zones: list[tuple[float, float]] = []
        for lo, hi in zip(boundaries[:-1], boundaries[1:]):
            probe = lo + 1.0 if math.isinf(hi) else (lo + hi) / 2.0
            if float(self.payoff(probe)) > 1e-9:
                zones.append((lo, hi))
        return tuple(zones)

    # ------------------------------------------------------- probabilidad y valor

    def probability_of_profit(self, spot: float, iv: float, days: float, rate: float = 0.04) -> float:
        """Probabilidad (lognormal risk-neutral) de expirar en zona de beneficio."""
        t = days / DAYS_PER_YEAR
        if t <= 0 or iv <= 0:
            raise ValueError("days e iv deben ser positivos")

        def prob_below(x: float) -> float:
            if x <= 0:
                return 0.0
            if math.isinf(x):
                return 1.0
            d2 = (math.log(spot / x) + (rate - 0.5 * iv**2) * t) / (iv * math.sqrt(t))
            return float(norm.cdf(-d2))

        return sum(prob_below(hi) - prob_below(lo) for lo, hi in self.profit_zones())

    def value_at(self, spot: float, days_left: float, iv: float, rate: float = 0.04) -> float:
        """P/L marcado a modelo antes de expiración (curva T+x del libro)."""
        total = 0.0
        for leg in self.legs:
            if isinstance(leg, StockLeg):
                total += (leg.quantity / 100.0) * (spot - leg.cost_basis)
            else:
                mark = bs_price(leg.kind, spot, leg.strike, days_left, iv, rate)
                total += leg.quantity * (mark - leg.premium)
        return total

    def position_greeks(self, spot: float, days: float, iv: float, rate: float = 0.04) -> Greeks:
        """Griegas agregadas de la posición (Cap. 3)."""
        total = ZERO_GREEKS
        for leg in self.legs:
            if isinstance(leg, StockLeg):
                total = total + stock_greeks(leg.quantity)
            else:
                total = total + bs_greeks(leg.kind, spot, leg.strike, days, iv, rate).scaled(leg.quantity)
        return total

    # ------------------------------------------------------------------ resumen

    def summary(self, spot: float | None = None, iv: float | None = None, days: float | None = None) -> str:
        """Resumen en texto con las métricas y las fórmulas del libro."""
        lines = [
            f"Estrategia : {self.name}  ({self.chapter})",
            f"Sesgo      : {self.sentiment}",
        ]
        premium = self.net_premium()
        side = "débito pagado" if premium > 0 else "crédito recibido"
        lines.append(f"Prima neta : {abs(premium):.2f} ({side})")
        mp, ml = self.max_profit(), self.max_loss()
        lines.append(f"Max profit : {'ilimitado' if math.isinf(mp) else f'{mp:.2f}'}"
                     + (f"   [libro: {self.book_max_profit}]" if self.book_max_profit else ""))
        lines.append(f"Max riesgo : {'ilimitado' if math.isinf(ml) else f'{ml:.2f}'}"
                     + (f"   [libro: {self.book_max_risk}]" if self.book_max_risk else ""))
        bes = self.breakevens()
        lines.append(f"Breakevens : {', '.join(f'{b:.2f}' for b in bes) if bes else '—'}"
                     + (f"   [libro: {self.book_breakeven}]" if self.book_breakeven else ""))
        zones = self.profit_zones()
        if zones:
            zone_txt = "; ".join(f"{lo:.2f} → {'∞' if math.isinf(hi) else f'{hi:.2f}'}" for lo, hi in zones)
            lines.append(f"Zona +     : {zone_txt}")
        if spot is not None and iv is not None and days is not None:
            pop = self.probability_of_profit(spot, iv, days)
            greeks = self.position_greeks(spot, days, iv)
            lines.append(f"Prob. beneficio (spot {spot:.2f}, IV {iv:.0%}, {days:.0f}d): {pop:.1%}")
            lines.append(
                f"Griegas    : Δ {greeks.delta:+.3f}  Γ {greeks.gamma:+.4f}  "
                f"Θ {greeks.theta:+.4f}/día  V {greeks.vega:+.4f}/1%  ρ {greeks.rho:+.4f}/1%"
            )
        if self.notes:
            lines.append(f"Libro      : {self.notes}")
        return "\n".join(lines)


# Registro que rellena builders.py; importarlo aquí crearía un ciclo,
# así que builders.py lo pobla al importarse desde __init__ o cli.
STRATEGY_BUILDERS: dict[str, object] = {}
