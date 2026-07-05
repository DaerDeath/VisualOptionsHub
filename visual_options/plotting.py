"""Visualización al estilo del libro: diagramas de riesgo P/L y griegas.

Cada estrategia de los capítulos 4-6 se presenta en el libro con su gráfico
de P/L a expiración; aquí añadimos además la curva T+0 valorada con BSM y
los perfiles de griegas frente al precio del subyacente (Cap. 3).
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from visual_options.strategies import Strategy

PROFIT_COLOR = "#2e7d32"
LOSS_COLOR = "#c62828"
T0_COLOR = "#1565c0"


def _spot_grid(strategy: Strategy, spot: float | None) -> np.ndarray:
    strikes = [leg.strike for leg in strategy.legs if hasattr(leg, "strike")]
    anchors = strikes or [spot or 100.0]
    if spot is not None:
        anchors.append(spot)
    lo, hi = min(anchors) * 0.7, max(anchors) * 1.3
    return np.linspace(lo, hi, 600)


def plot_payoff(
    strategy: Strategy,
    path: str | Path,
    spot: float | None = None,
    iv: float | None = None,
    days: float | None = None,
) -> Path:
    """Diagrama de riesgo: P/L a expiración y, si hay IV/días, curva T+0."""
    spots = _spot_grid(strategy, spot)
    payoff = np.asarray(strategy.payoff(spots)) * 100.0  # dólares por contrato

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axhline(0, color="gray", lw=0.8)
    ax.plot(spots, payoff, color="black", lw=2, label="P/L a expiración")
    ax.fill_between(spots, payoff, 0, where=payoff > 0, color=PROFIT_COLOR, alpha=0.25)
    ax.fill_between(spots, payoff, 0, where=payoff < 0, color=LOSS_COLOR, alpha=0.25)

    if iv is not None and days is not None and days > 0:
        t0 = np.array([strategy.value_at(s, days, iv) for s in spots]) * 100.0
        ax.plot(spots, t0, color=T0_COLOR, lw=1.6, ls="--", label=f"T+0 ({days:.0f}d, IV {iv:.0%})")

    for be in strategy.breakevens():
        ax.axvline(be, color="gray", ls=":", lw=1)
        ax.annotate(f"BE {be:.2f}", (be, 0), textcoords="offset points",
                    xytext=(4, 8), fontsize=8, color="gray")
    if spot is not None:
        ax.axvline(spot, color=T0_COLOR, ls="-", lw=0.8, alpha=0.5)
        ax.annotate(f"spot {spot:.2f}", (spot, ax.get_ylim()[1]), textcoords="offset points",
                    xytext=(4, -12), fontsize=8, color=T0_COLOR)

    mp, ml = strategy.max_profit(), strategy.max_loss()
    subtitle = (
        f"max profit: {'∞' if math.isinf(mp) else f'{mp * 100:,.0f} USD'}   "
        f"max riesgo: {'∞' if math.isinf(ml) else f'{ml * 100:,.0f} USD'}   "
        f"sesgo: {strategy.sentiment}"
    )
    ax.set_title(f"{strategy.name} ({strategy.chapter})\n{subtitle}", fontsize=11)
    ax.set_xlabel("Precio del subyacente a expiración")
    ax.set_ylabel("P/L por contrato ($)")
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.25)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_greeks(
    strategy: Strategy,
    path: str | Path,
    spot: float,
    iv: float,
    days: float,
    rate: float = 0.04,
) -> Path:
    """Perfiles de delta, gamma, theta y vega frente al spot (Cap. 3)."""
    spots = _spot_grid(strategy, spot)
    greeks = [strategy.position_greeks(s, days, iv, rate) for s in spots]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    panels = (
        ("Delta", [g.delta for g in greeks]),
        ("Gamma", [g.gamma for g in greeks]),
        ("Theta ($/día)", [g.theta * 100 for g in greeks]),
        ("Vega ($/1% IV)", [g.vega * 100 for g in greeks]),
    )
    for ax, (label, values) in zip(axes.flat, panels):
        ax.plot(spots, values, color=T0_COLOR, lw=1.8)
        ax.axhline(0, color="gray", lw=0.8)
        ax.axvline(spot, color="gray", ls=":", lw=1)
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.25)

    fig.suptitle(f"Griegas de posición — {strategy.name} (IV {iv:.0%}, {days:.0f}d)", fontsize=12)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
