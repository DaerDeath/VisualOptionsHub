"""Feed de datos desde la API de Tradier (gratis con cuenta developer).

Token: variable de entorno TRADIER_TOKEN (o --tradier-token en la CLI).
Entornos: sandbox (datos con ~15 min de retraso, 60 req/min) y prod.

Qué rellena cada panel:
  - cadena por strike: volumen, bid/ask/last y griegas ORATS (greeks=true)
  - % vendido: aproximado clasificando cada incremento de volumen contra
    el punto medio bid-ask actual (con retraso, es orientativo)
  - GEX: gamma ORATS × open interest × 100 × spot² × 1% (en millones)
  - magnet: concentración de open interest relativa al volumen
  - footprint: timesales del subyacente (tick si está disponible, si no
    barras de 1 min clasificadas por regla uptick/downtick)
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

import httpx

from visual_options.stream.dealer import compute_exposures, gamma_flip_level
from visual_options.stream.footprint import FootprintBuilder
from visual_options.stream.state import DashboardState, SeriesPoint, StrikeRow

BASE_URLS = {
    "sandbox": "https://sandbox.tradier.com/v1",
    "prod": "https://api.tradier.com/v1",
}
STRIKE_SPAN = 11
POLL_SECONDS = 10.0


class TradierFeed:
    """Interfaz Feed (ver manager.py) sobre la API REST de Tradier."""

    def __init__(self, symbol: str, token: str | None = None, env: str = "sandbox",
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        token = token or os.environ.get("TRADIER_TOKEN", "")
        if not token:
            raise SystemExit("Falta el token de Tradier: exporta TRADIER_TOKEN o usa --tradier-token")
        if env not in BASE_URLS:
            raise ValueError(f"entorno tradier desconocido: {env!r}")
        self.base = BASE_URLS[env]
        self.symbol = symbol.upper()
        source = "tradier" if env == "prod" else "tradier-delayed"
        self.state = DashboardState(symbol=self.symbol, spot=0.0, source=source, connected=False)
        self.footprint = FootprintBuilder()
        self._client = httpx.AsyncClient(headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }, timeout=15.0, transport=transport)
        self._expiration: str | None = None
        self._classified: dict[str, dict[str, float]] = {}
        self._last_volume: dict[str, int] = {}
        self._last_timesale: str | None = None
        self._initialized = False

    async def _get(self, path: str, **params) -> dict:
        response = await self._client.get(f"{self.base}{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def step(self) -> None:
        try:
            if not self._initialized:
                await self._initialize()
            await asyncio.sleep(POLL_SECONDS)
            await self._refresh_chain()
            await self._refresh_footprint()
            self.state.connected = True
        except httpx.HTTPError as exc:
            self.state.connected = False
            await asyncio.sleep(POLL_SECONDS)
            print(f"[tradier] error de red: {exc}")

    async def close(self) -> None:
        await self._client.aclose()

    async def _initialize(self) -> None:
        data = await self._get("/markets/quotes", symbols=self.symbol)
        quote = data["quotes"]["quote"]
        self.state.spot = float(quote["last"] or quote["prevclose"])
        expirations = await self._get("/markets/options/expirations",
                                      symbol=self.symbol, includeAllRoots="true")
        dates = expirations["expirations"]["date"]
        self._expiration = dates[0] if isinstance(dates, list) else dates
        self._initialized = True

    async def _refresh_chain(self) -> None:
        quote_data = await self._get("/markets/quotes", symbols=self.symbol)
        quote = quote_data["quotes"]["quote"]
        if quote.get("last"):
            self.state.spot = float(quote["last"])

        chain = await self._get("/markets/options/chains", symbol=self.symbol,
                                expiration=self._expiration, greeks="true")
        options = chain.get("options", {}).get("option", []) or []

        # strikes centrados en el spot
        strikes_all = sorted({float(o["strike"]) for o in options})
        if not strikes_all:
            return
        center_idx = min(range(len(strikes_all)), key=lambda i: abs(strikes_all[i] - self.state.spot))
        lo = max(0, center_idx - STRIKE_SPAN)
        selected = set(strikes_all[lo: center_idx + STRIKE_SPAN + 1])
        rows = {k: StrikeRow(strike=k) for k in sorted(selected)}

        iv_sum: dict[float, list[float]] = {}
        for opt in options:
            strike = float(opt["strike"])
            row = rows.get(strike)
            if row is None:
                continue
            volume = int(opt.get("volume") or 0)
            sold_pct = self._classify(opt, volume)
            oi = int(opt.get("open_interest") or 0)
            greeks = opt.get("greeks") or {}
            mid_iv = float(greeks.get("mid_iv") or greeks.get("smv_vol") or 0.0)
            if mid_iv > 0:
                iv_sum.setdefault(strike, []).append(mid_iv)

            if opt["option_type"] == "call":
                row.call_volume = volume
                row.call_sold_pct = sold_pct
                row.call_oi = oi
                row.magnet += oi / max(volume, 1)
            else:
                row.put_volume = volume
                row.put_sold_pct = sold_pct
                row.put_oi = oi
                row.magnet += oi / max(volume, 1)

        for strike, ivs in iv_sum.items():
            rows[strike].iv = sum(ivs) / len(ivs)

        self.state.strikes = list(rows.values())
        self.state.expiry_days = self._days_to_expiry()
        compute_exposures(self.state.strikes, self.state.spot, self.state.expiry_days)
        self.state.gamma_flip = gamma_flip_level(self.state.strikes)
        self.state.timestamp = datetime.now().strftime("%H:%M:%S")
        self.state.append_point(SeriesPoint(
            t=self.state.timestamp,
            price=round(self.state.spot, 2),
            put_sell_pct=round(self.state.put_sell_pct, 3),
            call_sell_pct=round(self.state.call_sell_pct, 3),
        ))

    def _days_to_expiry(self) -> float:
        if not self._expiration:
            return 1.0
        expiry = datetime.strptime(self._expiration, "%Y-%m-%d")
        return max(0.25, (expiry - datetime.now()).total_seconds() / 86400)

    def _classify(self, opt: dict, volume: int) -> float:
        """% vendido acumulado clasificando deltas de volumen contra el mid."""
        key = opt["symbol"]
        delta = volume - self._last_volume.get(key, 0)
        self._last_volume[key] = volume
        stats = self._classified.setdefault(key, {"sold": 0.0, "total": 0.0})
        bid, ask, last = opt.get("bid"), opt.get("ask"), opt.get("last")
        if delta > 0 and bid and ask and last:
            mid = (float(bid) + float(ask)) / 2.0
            stats["total"] += delta
            if float(last) <= mid:
                stats["sold"] += delta
        return 100.0 * stats["sold"] / stats["total"] if stats["total"] else 50.0

    async def _refresh_footprint(self) -> None:
        """Timesales del subyacente → barras footprint (uptick/downtick)."""
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            data = await self._get("/markets/timesales", symbol=self.symbol,
                                   interval="1min", start=f"{today} 09:30",
                                   session_filter="open")
        except httpx.HTTPStatusError:
            return
        series = (data.get("series") or {}).get("data") or []
        if isinstance(series, dict):
            series = [series]
        prev_close: float | None = None
        for bar in series:
            t = bar["time"][11:16]  # HH:MM
            if self._last_timesale is not None and t <= self._last_timesale:
                prev_close = float(bar["close"])
                continue
            close, volume = float(bar["close"]), int(bar.get("volume") or 0)
            is_buy = prev_close is None or close >= prev_close
            trades = [(float(bar.get("low") or close), volume // 3, not is_buy),
                      (close, volume - 2 * (volume // 3), is_buy),
                      (float(bar.get("high") or close), volume // 3, is_buy)]
            self.footprint.add_trades(t, [tr for tr in trades if tr[1] > 0], bar_key=t)
            prev_close = close
            self._last_timesale = t
