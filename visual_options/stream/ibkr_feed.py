"""Feed en vivo desde IBKR para el dashboard de flujo.

Clasificación buy/sell: cada incremento de volumen se clasifica comparando
el último precio con el punto medio bid-ask del momento (regla de
Lee-Ready simplificada): last ≤ mid → vendido (al bid), last > mid →
comprado (al ask). Es una aproximación con datos de nivel 1; el dashboard
del vídeo usa la misma idea con tick data.

Requiere TWS/IB Gateway con la API activada y suscripción de datos OPRA.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

from visual_options.stream.footprint import FootprintBuilder
from visual_options.stream.state import DashboardState, SeriesPoint, StrikeRow

STRIKE_SPAN = 11
REFRESH_SECONDS = 5.0


class IBKRFeed:
    """Mantiene un DashboardState sincronizado con la cadena 0DTE de IBKR."""

    def __init__(self, symbol: str = "QQQ", host: str = "127.0.0.1", port: int = 7497,
                 client_id: int = 21) -> None:
        self.footprint = FootprintBuilder()
        self._run_task: asyncio.Task | None = None
        try:
            from ib_async import IB
        except ImportError as exc:
            raise SystemExit(
                "ib-async no está instalado; instala con: uv sync --extra ibkr"
            ) from exc
        self.IB = IB
        self.symbol = symbol.upper()
        self.host, self.port, self.client_id = host, port, client_id
        self.state = DashboardState(symbol=self.symbol, spot=0.0, source="ibkr", connected=False)
        self._classified: dict[tuple[float, str], dict[str, float]] = {}
        self._last_volume: dict[tuple[float, str], int] = {}

    async def step(self) -> None:
        """Interfaz Feed (manager.py): arranca run() en segundo plano."""
        if self._run_task is None:
            self._run_task = asyncio.create_task(self.run())
        await asyncio.sleep(2.0)

    async def close(self) -> None:
        if self._run_task is not None:
            self._run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._run_task

    async def run(self) -> None:
        from ib_async import Option, Stock
        ib = self.IB()
        await ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=15)
        self.state.connected = True
        try:
            stock = Stock(self.symbol, "SMART", "USD")
            await ib.qualifyContractsAsync(stock)
            [stock_ticker] = await ib.reqTickersAsync(stock)
            self.state.spot = stock_ticker.marketPrice()

            chains = await ib.reqSecDefOptParamsAsync(stock.symbol, "", stock.secType, stock.conId)
            chain = next(c for c in chains if c.exchange == "SMART")
            expiry = sorted(chain.expirations)[0]  # 0DTE / vencimiento más cercano
            expiry_dt = datetime.strptime(expiry, "%Y%m%d")
            self.state.expiry_days = max(0.25, (expiry_dt - datetime.now()).total_seconds() / 86400)
            base = round(self.state.spot)
            strikes = [float(k) for k in range(base - STRIKE_SPAN, base + STRIKE_SPAN + 1)
                       if k in {int(s) for s in chain.strikes}]
            self.state.strikes = [StrikeRow(strike=k) for k in strikes]

            contracts = [Option(self.symbol, expiry, k, right, "SMART", currency="USD")
                         for k in strikes for right in ("C", "P")]
            contracts = await ib.qualifyContractsAsync(*contracts)
            tickers = [ib.reqMktData(c, "", False, False) for c in contracts]
            stock_stream = ib.reqMktData(stock, "", False, False)

            while True:
                await asyncio.sleep(REFRESH_SECONDS)
                spot = stock_stream.marketPrice()
                if spot and spot > 0:
                    self.state.spot = spot
                self._ingest(tickers)
                self.state.timestamp = datetime.now().strftime("%H:%M:%S")
                self.state.append_point(SeriesPoint(
                    t=self.state.timestamp,
                    price=round(self.state.spot, 2),
                    put_sell_pct=round(self.state.put_sell_pct, 3),
                    call_sell_pct=round(self.state.call_sell_pct, 3),
                ))
        finally:
            self.state.connected = False
            ib.disconnect()

    def _ingest(self, tickers) -> None:
        rows = {row.strike: row for row in self.state.strikes}
        for t in tickers:
            contract = t.contract
            key = (contract.strike, contract.right)
            row = rows.get(contract.strike)
            if row is None or not t.volume or t.volume <= 0:
                continue
            volume = int(t.volume)
            delta = volume - self._last_volume.get(key, 0)
            self._last_volume[key] = volume

            stats = self._classified.setdefault(key, {"sold": 0.0, "total": 0.0})
            if delta > 0 and t.bid and t.ask and t.last:
                mid = (t.bid + t.ask) / 2.0
                stats["total"] += delta
                if t.last <= mid:
                    stats["sold"] += delta
            sold_pct = 100.0 * stats["sold"] / stats["total"] if stats["total"] else 50.0

            if contract.right == "C":
                row.call_volume = volume
                row.call_sold_pct = sold_pct
            else:
                row.put_volume = volume
                row.put_sold_pct = sold_pct

            greeks = t.modelGreeks
            if greeks and greeks.impliedVol:
                row.iv = float(greeks.impliedVol)
            open_interest = getattr(t, "callOpenInterest" if contract.right == "C"
                                    else "putOpenInterest", 0) or volume
            if contract.right == "C":
                row.call_oi = int(open_interest)
            else:
                row.put_oi = int(open_interest)

        # exposiciones dealer (GEX/DEX/vanna) con OI + IV recogidos
        from visual_options.stream.dealer import compute_exposures, gamma_flip_level
        compute_exposures(self.state.strikes, self.state.spot, self.state.expiry_days)
        self.state.gamma_flip = gamma_flip_level(self.state.strikes)
