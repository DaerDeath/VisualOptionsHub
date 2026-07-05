"""Modelo de datos del dashboard de flujo.

El estado replica lo que muestra el stream del vídeo:
  - por strike: volumen y % vendido de calls y puts, gamma (GEX) y el
    perfil "magnet" (OI de mariposas / volumen)
  - agregados: Put Sell % y Call Sell % sobre todos los strikes
  - series temporales: precio, put sell % y call sell % minuto a minuto
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

MAX_SERIES_POINTS = 900  # ~ una sesión completa a un punto cada ~26 s


@dataclass
class StrikeRow:
    strike: float
    call_volume: int = 0
    call_sold_pct: float = 50.0   # % del volumen de calls que se VENDIÓ
    put_volume: int = 0
    put_sold_pct: float = 50.0
    gamma_exposure: float = 0.0   # GEX en millones de $ por 1% de movimiento
    magnet: float = 0.0           # OI de mariposas / volumen (perfil imán)


@dataclass
class SeriesPoint:
    t: str                        # HH:MM:SS
    price: float
    put_sell_pct: float
    call_sell_pct: float


@dataclass
class DashboardState:
    symbol: str
    spot: float
    timestamp: str = ""
    source: str = "sim"           # "sim" | "ibkr"
    connected: bool = True
    strikes: list[StrikeRow] = field(default_factory=list)
    series: list[SeriesPoint] = field(default_factory=list)

    @property
    def put_sell_pct(self) -> float:
        """Agregado ponderado por volumen, como el 'Put Sell %' del stream."""
        total = sum(r.put_volume for r in self.strikes)
        if total == 0:
            return 0.0
        return sum(r.put_volume * r.put_sold_pct for r in self.strikes) / total

    @property
    def call_sell_pct(self) -> float:
        total = sum(r.call_volume for r in self.strikes)
        if total == 0:
            return 0.0
        return sum(r.call_volume * r.call_sold_pct for r in self.strikes) / total

    def append_point(self, point: SeriesPoint) -> None:
        self.series.append(point)
        if len(self.series) > MAX_SERIES_POINTS:
            del self.series[: len(self.series) - MAX_SERIES_POINTS]

    def snapshot(self) -> dict:
        """Estado serializable que consume el frontend.

        Los agregados del header son los de la serie temporal (la escala que
        usa el stream: ~5-45), no la media ponderada por strike (~50-80).
        """
        last = self.series[-1] if self.series else None
        return {
            "symbol": self.symbol,
            "spot": round(self.spot, 2),
            "timestamp": self.timestamp,
            "source": self.source,
            "connected": self.connected,
            "put_sell_pct": round(last.put_sell_pct if last else self.put_sell_pct, 4),
            "call_sell_pct": round(last.call_sell_pct if last else self.call_sell_pct, 4),
            "strikes": [asdict(r) for r in self.strikes],
            "series": [asdict(p) for p in self.series],
        }
