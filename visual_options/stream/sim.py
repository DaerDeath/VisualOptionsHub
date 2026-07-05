"""Simulador de sesión: genera flujo con la dinámica que describe el vídeo.

Reglas del autor codificadas en la simulación:
  - "cuando el call sell % sube, el precio cae; cuando se venden muchos
    puts, el precio vuelve a subir" → el precio responde a la señal
    (put_sell - call_sell)
  - "el call sell % cae muy bajo (~10%) y el precio sube exponencialmente"
    → régimen squeeze ocasional
  - calls OTM más vendidos que los ATM (techo), volumen concentrado cerca
    del dinero y en strikes redondos
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

from visual_options.stream.dealer import compute_exposures, gamma_flip_level
from visual_options.stream.footprint import FootprintBuilder
from visual_options.stream.state import DashboardState, SeriesPoint, StrikeRow

STRIKE_SPAN = 11          # strikes a cada lado del spot
SQUEEZE_PROBABILITY = 0.004
FOOTPRINT_BAR_MINUTES = 5

# Precios base plausibles para el simulador por símbolo (jul 2026 aprox.)
BASE_PRICES: dict[str, float] = {
    "QQQ": 719.9, "SPY": 634.0, "SPX": 6360.0, "IWM": 228.0, "DIA": 448.0,
    "NVDA": 172.0, "TSLA": 318.0, "AAPL": 212.0, "MSFT": 498.0, "AMZN": 224.0,
    "META": 725.0, "AMD": 138.0, "GOOGL": 180.0, "NFLX": 1290.0, "COIN": 355.0,
}
DEFAULT_BASE_PRICE = 100.0


def base_price_for(symbol: str) -> float:
    return BASE_PRICES.get(symbol.upper(), DEFAULT_BASE_PRICE)


def strike_step_for(spot: float) -> float:
    """Espaciado de strikes según el nivel del subyacente (SPX usa 10, QQQ 1…)."""
    if spot >= 3000:
        return 10.0
    if spot >= 1000:
        return 5.0
    if spot >= 50:
        return 1.0
    return 0.5


class SessionSimulator:
    """Evoluciona un DashboardState con ticks discretos."""

    def __init__(self, symbol: str = "QQQ", spot: float | None = None, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        spot = spot if spot is not None else base_price_for(symbol)
        self.spot0 = spot
        self.footprint = FootprintBuilder()
        self.put_sell = 12.0 + self.rng.uniform(-2, 2)
        self.call_sell = 16.0 + self.rng.uniform(-2, 2)
        self.squeeze_ticks = 0
        self.clock = datetime.now().replace(hour=6, minute=30, second=0, microsecond=0)
        step = strike_step_for(spot)
        base = round(spot / step) * step
        self.state = DashboardState(
            symbol=symbol.upper(),
            spot=spot,
            source="sim",
            strikes=[StrikeRow(strike=float(base + i * step))
                     for i in range(-STRIKE_SPAN, STRIKE_SPAN + 1)],
        )
        self.state.expiry_days = 1.0  # cadena 0DTE
        self._seed_magnet_profile()
        self._seed_open_interest()
        for _ in range(40):  # arranque con algo de historia
            self.tick(seconds=60)

    def _seed_magnet_profile(self) -> None:
        """Perfil 'magnet strikes' ~ campana sesgada alrededor de un imán."""
        magnet_strike = self.spot0 + self.rng.uniform(-3, 5)
        skew = self.rng.uniform(-0.4, 0.6)
        for row in self.state.strikes:
            z = (row.strike - magnet_strike) / 6.0
            row.magnet = max(0.0, math.exp(-0.5 * z * z) * (1 + skew * z) + self.rng.uniform(0, 0.05))

    def tick(self, seconds: float = 1.0) -> None:
        rng = self.rng
        state = self.state
        scale = math.sqrt(seconds / 60.0)

        # Regímenes: flujo normal mean-reverting o squeeze (call sell colapsa)
        if self.squeeze_ticks > 0:
            self.squeeze_ticks -= 1
            self.call_sell += (9.0 - self.call_sell) * 0.15 * scale
            self.put_sell += (14.0 - self.put_sell) * 0.05 * scale
        else:
            if rng.random() < SQUEEZE_PROBABILITY * seconds:
                self.squeeze_ticks = int(600 / max(seconds, 1))
            self.call_sell += (15.5 - self.call_sell) * 0.02 * scale + rng.gauss(0, 0.9) * scale
            self.put_sell += (12.0 - self.put_sell) * 0.02 * scale + rng.gauss(0, 0.8) * scale
        self.call_sell = min(45.0, max(5.0, self.call_sell))
        self.put_sell = min(45.0, max(3.0, self.put_sell))

        # El precio sigue al flujo (regla del vídeo) más ruido
        prev_spot = state.spot
        point_scale = self.spot0 / 720.0  # el sim está calibrado sobre QQQ~720
        flow_signal = (self.put_sell - 12.0) * 0.010 - (self.call_sell - 15.5) * 0.014
        state.spot += (flow_signal * seconds / 60.0 + rng.gauss(0, 0.11) * scale) * point_scale
        state.spot = max(self.spot0 * 0.97, min(self.spot0 * 1.03, state.spot))

        self._update_strikes(seconds)
        self.clock += timedelta(seconds=seconds)
        state.timestamp = self.clock.strftime("%H:%M:%S")
        self._emit_trades(prev_spot, seconds)
        state.append_point(SeriesPoint(
            t=state.timestamp,
            price=round(state.spot, 2),
            put_sell_pct=round(self.put_sell, 3),
            call_sell_pct=round(self.call_sell, 3),
        ))

    def _seed_open_interest(self) -> None:
        """OI en campana alrededor del dinero con extra en strikes redondos,
        e IV con smile (skew a la baja, típico de índices)."""
        rng = self.rng
        step = strike_step_for(self.spot0)
        for row in self.state.strikes:
            distance = (row.strike - self.spot0) / step
            bell = math.exp(-0.5 * (distance / 7.0) ** 2)
            boost = 1.9 if row.strike % 5 == 0 else 1.0
            row.call_oi = int(bell * boost * rng.uniform(4000, 14000) * (1.25 if distance > 0 else 1.0))
            row.put_oi = int(bell * boost * rng.uniform(4000, 14000) * (1.25 if distance < 0 else 1.0))
            moneyness = (row.strike - self.spot0) / self.spot0
            row.iv = max(0.08, 0.17 - moneyness * 0.9 + abs(moneyness) * 1.6 + rng.gauss(0, 0.004))

    def _emit_trades(self, prev_spot: float, seconds: float) -> None:
        """Genera prints sintéticos entre prev_spot y el spot actual para el footprint."""
        rng = self.rng
        n_trades = max(3, int(seconds / 4))
        direction_bias = 0.5 + _clamp((self.state.spot - prev_spot) / max(prev_spot * 4e-4, 1e-9), -0.35, 0.35)
        trades: list[tuple[float, int, bool]] = []
        for i in range(n_trades):
            frac = (i + 1) / n_trades
            price = prev_spot + (self.state.spot - prev_spot) * frac + rng.gauss(0, prev_spot * 6e-5)
            size = max(1, int(rng.expovariate(1 / 40)))
            trades.append((price, size, rng.random() < direction_bias))
        bar_minute = (self.clock.minute // FOOTPRINT_BAR_MINUTES) * FOOTPRINT_BAR_MINUTES
        bar_key = f"{self.clock.hour:02d}:{bar_minute:02d}"
        self.footprint.add_trades(self.state.timestamp, trades, bar_key=bar_key)

    def _update_strikes(self, seconds: float) -> None:
        rng = self.rng
        state = self.state
        step = strike_step_for(state.spot)
        for row in state.strikes:
            distance = (row.strike - state.spot) / step
            # volumen: campana alrededor del dinero, calls pesados arriba
            call_intensity = math.exp(-0.5 * ((distance - 3.5) / 5.0) ** 2)
            put_intensity = math.exp(-0.5 * ((distance + 2.5) / 5.0) ** 2)
            if row.strike % 5 == 0:  # strikes redondos atraen volumen
                call_intensity *= 1.6
                put_intensity *= 1.6
            call_added = int(rng.expovariate(1 / (call_intensity * 28 + 1)) * seconds)
            put_added = int(rng.expovariate(1 / (put_intensity * 24 + 1)) * seconds)
            row.call_volume += call_added
            row.put_volume += put_added
            self._maybe_emit_tape(row, "call", call_added, row.call_sold_pct)
            self._maybe_emit_tape(row, "put", put_added, row.put_sold_pct)

            # % vendido por strike: sigue el agregado; calls OTM más vendidos
            otm_call_bias = max(0.0, distance) * 1.8
            otm_put_bias = max(0.0, -distance) * 1.2
            row.call_sold_pct = _clamp(
                row.call_sold_pct + (55 + self.call_sell + otm_call_bias - row.call_sold_pct) * 0.05
                + rng.gauss(0, 1.2), 10, 95)
            row.put_sold_pct = _clamp(
                row.put_sold_pct + (45 + self.put_sell + otm_put_bias - row.put_sold_pct) * 0.05
                + rng.gauss(0, 1.2), 5, 90)

            # el OI se mueve poco intradía; la IV respira con el flujo
            row.call_oi = max(0, row.call_oi + int(rng.gauss(0, 6) * seconds / 60))
            row.put_oi = max(0, row.put_oi + int(rng.gauss(0, 6) * seconds / 60))
            row.iv = max(0.05, row.iv + rng.gauss(0, 0.0006) * math.sqrt(seconds / 60))

            row.magnet = max(0.0, row.magnet + rng.gauss(0, 0.004))

        # exposiciones dealer (GEX/DEX/vanna) con el BSM real
        compute_exposures(state.strikes, state.spot, state.expiry_days)
        state.gamma_flip = gamma_flip_level(state.strikes)
        state.snapshot_gex_column()

    def _maybe_emit_tape(self, row: StrikeRow, kind: str, added: int, sold_pct: float) -> None:
        """Operación destacada: bloque grande de volumen en un strike."""
        if added < 400:
            return
        side = "sell" if self.rng.random() * 100 < sold_pct else "buy"
        distance = abs(row.strike - self.state.spot)
        premium_per_contract = max(0.05, 2.2 - distance * 0.25 + self.rng.uniform(-0.2, 0.4))
        self.state.append_tape(row.strike, kind, side, added,
                               added * premium_per_contract * 100)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
