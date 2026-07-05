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

from visual_options.stream.state import DashboardState, SeriesPoint, StrikeRow

STRIKE_SPAN = 11          # strikes a cada lado del spot
SQUEEZE_PROBABILITY = 0.004


class SessionSimulator:
    """Evoluciona un DashboardState con ticks discretos."""

    def __init__(self, symbol: str = "QQQ", spot: float = 719.9, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self.spot0 = spot
        self.put_sell = 12.0 + self.rng.uniform(-2, 2)
        self.call_sell = 16.0 + self.rng.uniform(-2, 2)
        self.squeeze_ticks = 0
        self.clock = datetime.now().replace(hour=6, minute=30, second=0, microsecond=0)
        base = round(spot)
        self.state = DashboardState(
            symbol=symbol,
            spot=spot,
            source="sim",
            strikes=[StrikeRow(strike=float(k)) for k in range(base - STRIKE_SPAN, base + STRIKE_SPAN + 1)],
        )
        self._seed_magnet_profile()
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
        flow_signal = (self.put_sell - 12.0) * 0.010 - (self.call_sell - 15.5) * 0.014
        state.spot += flow_signal * seconds / 60.0 + rng.gauss(0, 0.11) * scale
        state.spot = max(self.spot0 * 0.97, min(self.spot0 * 1.03, state.spot))

        self._update_strikes(seconds)
        self.clock += timedelta(seconds=seconds)
        state.timestamp = self.clock.strftime("%H:%M:%S")
        state.append_point(SeriesPoint(
            t=state.timestamp,
            price=round(state.spot, 2),
            put_sell_pct=round(self.put_sell, 3),
            call_sell_pct=round(self.call_sell, 3),
        ))

    def _update_strikes(self, seconds: float) -> None:
        rng = self.rng
        state = self.state
        for row in state.strikes:
            distance = row.strike - state.spot
            # volumen: campana alrededor del dinero, calls pesados arriba
            call_intensity = math.exp(-0.5 * ((distance - 3.5) / 5.0) ** 2)
            put_intensity = math.exp(-0.5 * ((distance + 2.5) / 5.0) ** 2)
            if row.strike % 5 == 0:  # strikes redondos atraen volumen
                call_intensity *= 1.6
                put_intensity *= 1.6
            row.call_volume += int(rng.expovariate(1 / (call_intensity * 28 + 1)) * seconds)
            row.put_volume += int(rng.expovariate(1 / (put_intensity * 24 + 1)) * seconds)

            # % vendido por strike: sigue el agregado; calls OTM más vendidos
            otm_call_bias = max(0.0, distance) * 1.8
            otm_put_bias = max(0.0, -distance) * 1.2
            row.call_sold_pct = _clamp(
                row.call_sold_pct + (55 + self.call_sell + otm_call_bias - row.call_sold_pct) * 0.05
                + rng.gauss(0, 1.2), 10, 95)
            row.put_sold_pct = _clamp(
                row.put_sold_pct + (45 + self.put_sell + otm_put_bias - row.put_sold_pct) * 0.05
                + rng.gauss(0, 1.2), 5, 90)

            # GEX: positivo bajo el spot, bolsas negativas en strikes clave
            base_gamma = math.exp(-0.5 * (distance / 6.0) ** 2)
            sign = 1.0 if distance < 0 else -0.6
            if row.strike % 5 == 0 and distance > 0:
                sign = -1.4
            row.gamma_exposure += (sign * base_gamma * 20 - row.gamma_exposure) * 0.03 + rng.gauss(0, 0.4)

            row.magnet = max(0.0, row.magnet + rng.gauss(0, 0.004))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
