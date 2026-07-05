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
MAX_GEX_HISTORY = 150    # columnas del heatmap tiempo × strike
MAX_TAPE_EVENTS = 120    # operaciones destacadas retenidas


@dataclass
class StrikeRow:
    strike: float
    call_volume: int = 0
    call_sold_pct: float = 50.0   # % del volumen de calls que se VENDIÓ
    put_volume: int = 0
    put_sold_pct: float = 50.0
    gamma_exposure: float = 0.0   # Net GEX en millones de $ por 1% de movimiento
    magnet: float = 0.0           # OI de mariposas / volumen (perfil imán)
    # posicionamiento de dealers (vista CloutSeeker); ver stream/dealer.py
    call_oi: int = 0
    put_oi: int = 0
    iv: float = 0.0               # IV media del strike (fracción, p.ej. 0.22)
    call_gex: float = 0.0
    put_gex: float = 0.0
    net_gex: float = 0.0
    net_dex: float = 0.0
    call_vanna: float = 0.0
    put_vanna: float = 0.0
    net_vanna: float = 0.0


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
    source: str = "sim"           # "sim" | "tradier" | "ibkr"
    connected: bool = True
    expiry_days: float = 1.0      # días a expiración de la cadena mostrada
    gamma_flip: float | None = None  # nivel de cruce del Net GEX acumulado
    strikes: list[StrikeRow] = field(default_factory=list)
    series: list[SeriesPoint] = field(default_factory=list)
    # heatmap TRACE-like: cada entrada {t, spot, gex: [net_gex por strike]}
    gex_history: list[dict] = field(default_factory=list)
    # tape de operaciones destacadas: {t, strike, kind, side, size, premium}
    tape: list[dict] = field(default_factory=list)

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

    def snapshot_gex_column(self) -> None:
        """Guarda la foto actual del Net GEX por strike para el heatmap."""
        self.gex_history.append({
            "t": self.timestamp,
            "spot": round(self.spot, 2),
            "gex": [round(r.net_gex, 2) for r in self.strikes],
        })
        if len(self.gex_history) > MAX_GEX_HISTORY:
            del self.gex_history[: len(self.gex_history) - MAX_GEX_HISTORY]

    def append_tape(self, strike: float, kind: str, side: str, size: int,
                    premium: float) -> None:
        """Registra una operación destacada (kind: call/put; side: buy/sell)."""
        self.tape.append({
            "t": self.timestamp, "strike": strike, "kind": kind,
            "side": side, "size": size, "premium": round(premium, 0),
        })
        if len(self.tape) > MAX_TAPE_EVENTS:
            del self.tape[: len(self.tape) - MAX_TAPE_EVENTS]

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
            "expiry_days": self.expiry_days,
            "gamma_flip": self.gamma_flip,
            "strikes": [asdict(r) for r in self.strikes],
            "series": [asdict(p) for p in self.series],
            "gex_history": self.gex_history,
            "tape": self.tape,
        }
