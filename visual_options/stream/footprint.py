"""Footprint: barras OHLC con volumen comprado/vendido por nivel de precio.

Cada barra agrega los trades de un intervalo; cada celda es un nivel de
precio con volumen agresor comprador (al ask / uptick) y vendedor (al bid
/ downtick). Se marca el POC (nivel con más volumen) y los imbalances.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_BARS = 80
IMBALANCE_RATIO = 3.0  # x3 en diagonal se considera imbalance (convención común)


def tick_size_for(price: float) -> float:
    """Tamaño de nivel según el precio del subyacente."""
    if price >= 2000:
        return 2.5
    if price >= 500:
        return 0.5
    if price >= 100:
        return 0.25
    return 0.1


@dataclass
class FootprintBar:
    t: str                        # etiqueta HH:MM del intervalo
    open: float
    high: float
    low: float
    close: float
    cells: dict[float, list[int]] = field(default_factory=dict)  # nivel → [buy, sell]

    def add_trade(self, price: float, size: int, is_buy: bool, tick: float) -> None:
        level = round(round(price / tick) * tick, 4)
        cell = self.cells.setdefault(level, [0, 0])
        cell[0 if is_buy else 1] += size
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price

    @property
    def delta(self) -> int:
        return sum(c[0] for c in self.cells.values()) - sum(c[1] for c in self.cells.values())

    @property
    def volume(self) -> int:
        return sum(c[0] + c[1] for c in self.cells.values())

    def poc(self) -> float | None:
        if not self.cells:
            return None
        return max(self.cells, key=lambda lvl: sum(self.cells[lvl]))

    def to_dict(self) -> dict:
        levels = sorted(self.cells, reverse=True)
        return {
            "t": self.t,
            "open": round(self.open, 4), "high": round(self.high, 4),
            "low": round(self.low, 4), "close": round(self.close, 4),
            "delta": self.delta, "volume": self.volume, "poc": self.poc(),
            "cells": [{"price": lvl, "buy": self.cells[lvl][0], "sell": self.cells[lvl][1]}
                      for lvl in levels],
        }


class FootprintBuilder:
    """Acumula trades en barras por intervalo de tiempo."""

    def __init__(self, bar_label_len: int = 5) -> None:
        self.bars: list[FootprintBar] = []
        self._bar_label_len = bar_label_len  # HH:MM

    def add_trades(self, timestamp: str, trades: list[tuple[float, int, bool]],
                   bar_key: str | None = None) -> None:
        """trades: lista de (precio, tamaño, es_compra)."""
        if not trades:
            return
        key = (bar_key or timestamp)[: self._bar_label_len]
        first_price = trades[0][0]
        if not self.bars or self.bars[-1].t != key:
            self.bars.append(FootprintBar(t=key, open=first_price, high=first_price,
                                          low=first_price, close=first_price))
            if len(self.bars) > MAX_BARS:
                del self.bars[: len(self.bars) - MAX_BARS]
        bar = self.bars[-1]
        tick = tick_size_for(first_price)
        for price, size, is_buy in trades:
            bar.add_trade(price, size, is_buy, tick)

    def snapshot(self, last_n: int = 40) -> dict:
        bars = self.bars[-last_n:]
        return {
            "bars": [b.to_dict() for b in bars],
            "imbalance_ratio": IMBALANCE_RATIO,
            "tick": tick_size_for(bars[-1].close) if bars else 0.25,
        }
