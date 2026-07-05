"""Piezas básicas de una posición: patas de opción y de acciones (Cap. 1).

Conceptos del libro implementados aquí: moneyness (ITM/ATM/OTM), valor
intrínseco y extrínseco (tiempo), y el payoff a expiración de cada pata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

Kind = Literal["call", "put"]

CONTRACT_MULTIPLIER = 100


@dataclass(frozen=True)
class OptionLeg:
    """Una pata de opción. quantity > 0 es compra (long), < 0 es venta (short)."""

    kind: Kind
    strike: float
    premium: float
    quantity: int = 1

    def __post_init__(self) -> None:
        if self.kind not in ("call", "put"):
            raise ValueError(f"kind debe ser 'call' o 'put', no {self.kind!r}")
        if self.strike <= 0:
            raise ValueError("strike debe ser positivo")
        if self.premium < 0:
            raise ValueError("premium no puede ser negativa")
        if self.quantity == 0:
            raise ValueError("quantity no puede ser 0")

    def intrinsic_value(self, spot: float) -> float:
        """Valor intrínseco por acción (Cap. 1)."""
        if self.kind == "call":
            return max(spot - self.strike, 0.0)
        return max(self.strike - spot, 0.0)

    def extrinsic_value(self, spot: float) -> float:
        """Valor extrínseco (de tiempo) por acción: prima - intrínseco."""
        return max(self.premium - self.intrinsic_value(spot), 0.0)

    def moneyness(self, spot: float, atm_tolerance: float = 0.005) -> str:
        """ITM / ATM / OTM respecto al spot (Cap. 1)."""
        if abs(spot - self.strike) <= atm_tolerance * spot:
            return "ATM"
        if self.intrinsic_value(spot) > 0:
            return "ITM"
        return "OTM"

    def payoff_at_expiry(self, spot: np.ndarray | float) -> np.ndarray | float:
        """P/L por acción a expiración (prima incluida)."""
        spot = np.asarray(spot, dtype=float)
        if self.kind == "call":
            intrinsic = np.maximum(spot - self.strike, 0.0)
        else:
            intrinsic = np.maximum(self.strike - spot, 0.0)
        return self.quantity * (intrinsic - self.premium)


@dataclass(frozen=True)
class StockLeg:
    """Pata de acciones. quantity en acciones; cost_basis por acción."""

    cost_basis: float
    quantity: int = 100

    def __post_init__(self) -> None:
        if self.cost_basis <= 0:
            raise ValueError("cost_basis debe ser positivo")
        if self.quantity == 0:
            raise ValueError("quantity no puede ser 0")

    def payoff_at_expiry(self, spot: np.ndarray | float) -> np.ndarray | float:
        """P/L por acción de esta pata, normalizado a 100 acciones por contrato."""
        spot = np.asarray(spot, dtype=float)
        return (self.quantity / CONTRACT_MULTIPLIER) * (spot - self.cost_basis)
