"""Feed de datos reales desde Yahoo Finance (yfinance) — sin token.

Gratis y sin registro: precio del subyacente, cadenas de opciones con
volumen, open interest e IV, y velas 1m para el footprint. Las cadenas
de Yahoo van con ~15 min de retraso y se actualizan lentas; el % vendido
se aproxima clasificando los deltas de volumen contra el mid actual,
igual que en los feeds de Tradier e IBKR.

yfinance es síncrono: cada refresco corre en un hilo (asyncio.to_thread).
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime

from visual_options.stream.dealer import compute_exposures, gamma_flip_level
from visual_options.stream.footprint import FootprintBuilder
from visual_options.stream.state import DashboardState, SeriesPoint, StrikeRow

STRIKE_SPAN = 11
POLL_SECONDS = 20.0
TAPE_THRESHOLD = 300


def _num(value, default: float = 0.0) -> float:
    """Convierte a float tratando None/NaN/strings raras como `default`.

    Yahoo devuelve NaN en volumen, OI, bid/ask… de contratos sin operar,
    y NaN es truthy: `int(nan or 0)` revienta.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else value


class YFinanceFeed:
    """Interfaz Feed (ver manager.py) sobre yfinance."""

    def __init__(self, symbol: str, ticker_factory=None, expiry_index: int = 0) -> None:
        self.symbol = symbol.upper()
        self.expiry_index = max(0, expiry_index)
        self.state = DashboardState(symbol=self.symbol, spot=0.0,
                                    source="yfinance", connected=False)
        self.footprint = FootprintBuilder()
        self._ticker_factory = ticker_factory or self._default_factory
        self._ticker = None
        self._expiration: str | None = None
        self._classified: dict[str, dict[str, float]] = {}
        self._last_volume: dict[str, int] = {}
        self._last_bar: str | None = None
        self._first_pass = True

    @staticmethod
    def _default_factory(symbol: str):
        import yfinance as yf
        # los índices en Yahoo llevan ^ delante (SPX → ^SPX)
        return yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)

    async def step(self) -> None:
        try:
            await asyncio.to_thread(self._refresh)
            self.state.connected = True
        except Exception as exc:  # red, rate limit, símbolo sin opciones…
            self.state.connected = False
            print(f"[yfinance] {type(exc).__name__}: {exc}")
        await asyncio.sleep(POLL_SECONDS)

    async def close(self) -> None:
        return None

    # ------------------------------------------------------------ sincrónico

    def _refresh(self) -> None:
        if self._ticker is None:
            self._ticker = self._ticker_factory(self.symbol)
        spot = self._fetch_spot()
        if spot and spot > 0:
            self.state.spot = float(spot)
        if self._expiration is None:
            expirations = self._ticker.options
            if not expirations:
                raise RuntimeError(f"{self.symbol} no tiene cadena de opciones en Yahoo")
            self._expiration = expirations[min(self.expiry_index, len(expirations) - 1)]

        self._refresh_chain()
        self._refresh_footprint()
        self._first_pass = False

        self.state.timestamp = datetime.now().strftime("%H:%M:%S")
        self.state.append_point(SeriesPoint(
            t=self.state.timestamp,
            price=round(self.state.spot, 2),
            put_sell_pct=round(self.state.put_sell_pct, 3),
            call_sell_pct=round(self.state.call_sell_pct, 3),
        ))

    def _fetch_spot(self) -> float | None:
        info = getattr(self._ticker, "fast_info", None)
        for key in ("last_price", "lastPrice"):
            try:
                value = _num(info[key] if info is not None else None)
            except (KeyError, TypeError):
                value = 0.0
            if value > 0:
                return value
        history = self._ticker.history(period="1d", interval="1m")
        if len(history):
            closes = history["Close"].dropna()
            if len(closes):
                value = _num(closes.iloc[-1])
                return value if value > 0 else None
        return None

    def _refresh_chain(self) -> None:
        chain = self._ticker.option_chain(self._expiration)
        spot = self.state.spot
        strikes_all = sorted(set(chain.calls["strike"]) | set(chain.puts["strike"]))
        if not strikes_all or not spot:
            return
        center = min(range(len(strikes_all)), key=lambda i: abs(strikes_all[i] - spot))
        lo = max(0, center - STRIKE_SPAN)
        selected = set(strikes_all[lo: center + STRIKE_SPAN + 1])
        rows = {k: StrikeRow(strike=float(k)) for k in sorted(selected)}

        for kind, frame in (("call", chain.calls), ("put", chain.puts)):
            for record in frame.to_dict("records"):
                strike = float(record["strike"])
                row = rows.get(strike)
                if row is None:
                    continue
                volume = int(_num(record.get("volume")))
                oi = int(_num(record.get("openInterest")))
                iv = _num(record.get("impliedVolatility"))
                sold_pct = self._classify(record, kind, volume)
                if kind == "call":
                    row.call_volume, row.call_sold_pct, row.call_oi = volume, sold_pct, oi
                else:
                    row.put_volume, row.put_sold_pct, row.put_oi = volume, sold_pct, oi
                if 0.01 < iv < 5.0:
                    row.iv = (row.iv + iv) / 2 if row.iv > 0 else iv
                row.magnet += oi / max(volume, 1)

        self.state.strikes = list(rows.values())
        self.state.expiry_days = self._days_to_expiry()
        compute_exposures(self.state.strikes, spot, self.state.expiry_days)
        self.state.gamma_flip = gamma_flip_level(self.state.strikes)
        self.state.snapshot_gex_column()

    def _classify(self, record: dict, kind: str, volume: int) -> float:
        key = record.get("contractSymbol") or f"{kind}{record['strike']}"
        is_baseline = key not in self._last_volume
        delta = volume - self._last_volume.get(key, 0)
        self._last_volume[key] = volume
        stats = self._classified.setdefault(key, {"sold": 0.0, "total": 0.0})
        if is_baseline:
            # la primera foto trae el acumulado del día: solo sirve de línea base
            return 50.0
        bid = _num(record.get("bid"))
        ask = _num(record.get("ask"))
        last = _num(record.get("lastPrice"))
        if delta > 0 and bid > 0 and ask > 0 and last > 0:
            mid = (bid + ask) / 2.0
            is_sell = last <= mid
            stats["total"] += delta
            if is_sell:
                stats["sold"] += delta
            if delta >= TAPE_THRESHOLD:
                self.state.append_tape(float(record["strike"]), kind,
                                       "sell" if is_sell else "buy", delta,
                                       delta * last * 100)
        return 100.0 * stats["sold"] / stats["total"] if stats["total"] else 50.0

    def _refresh_footprint(self) -> None:
        history = self._ticker.history(period="1d", interval="1m")
        if not len(history):
            return
        prev_close: float | None = None
        for timestamp, bar in history.iterrows():
            label = timestamp.strftime("%H:%M")
            close = _num(bar.get("Close"))
            volume = int(_num(bar.get("Volume")))
            if close <= 0:
                continue
            if self._last_bar is not None and label <= self._last_bar:
                prev_close = close
                continue
            if volume <= 0:
                prev_close = close
                continue
            is_buy = prev_close is None or close >= prev_close
            third = volume // 3
            trades = [(_num(bar.get("Low"), close), third, not is_buy),
                      (close, volume - 2 * third, is_buy),
                      (_num(bar.get("High"), close), third, is_buy)]
            self.footprint.add_trades(label, [t for t in trades if t[1] > 0], bar_key=label)
            prev_close = close
            self._last_bar = label

    def _days_to_expiry(self) -> float:
        if not self._expiration:
            return 1.0
        expiry = datetime.strptime(self._expiration, "%Y-%m-%d")
        return max(0.25, (expiry - datetime.now()).total_seconds() / 86400)
