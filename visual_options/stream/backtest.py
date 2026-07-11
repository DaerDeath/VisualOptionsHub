"""Backtest de venta de rangos (short strangle) con históricos de Yahoo.

Aproximación honesta y declarada: las primas se estiman con Black-Scholes
usando la volatilidad realizada de las 21 sesiones previas a cada entrada
(no hay históricos de opciones gratis). Sin comisiones ni slippage. Sirve
para comparar parámetros (ancho OTM, DTE) y ver la forma de la equity,
no para prometer rentabilidades.
"""

from __future__ import annotations

import math

import numpy as np

from visual_options.pricing import bs_price

LOOKBACK = 21           # sesiones para la vol realizada de entrada
TRADING_DAYS = 252


def fetch_daily_closes(symbol: str, years: int) -> tuple[list[str], np.ndarray]:
    import yfinance as yf
    ticker = yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)
    history = ticker.history(period=f"{max(1, min(years, 10))}y", interval="1d")
    closes = history["Close"].dropna()
    dates = [ts.strftime("%Y-%m-%d") for ts in closes.index]
    return dates, closes.to_numpy(dtype=float)


def run_backtest(symbol: str, otm_pct: float = 3.0, dte: int = 5, years: int = 2,
                 closes: np.ndarray | None = None,
                 dates: list[str] | None = None) -> dict:
    """Vende un strangle ±otm_pct% cada `dte` sesiones y lo lleva a expiración."""
    if not 0.2 <= otm_pct <= 25:
        raise ValueError("otm_pct debe estar entre 0.2 y 25")
    if not 1 <= dte <= 63:
        raise ValueError("dte debe estar entre 1 y 63 sesiones")
    if closes is None:
        dates, closes = fetch_daily_closes(symbol, years)
    dates = dates or [str(i) for i in range(len(closes))]
    log_returns = np.diff(np.log(closes))
    otm = otm_pct / 100.0

    trades = []
    equity = 0.0
    curve = []
    peak = 0.0
    max_drawdown = 0.0
    calendar_days = dte * 365.0 / TRADING_DAYS

    for i in range(LOOKBACK, len(closes) - dte, dte):
        entry = float(closes[i])
        exit_price = float(closes[i + dte])
        window = log_returns[i - LOOKBACK:i]
        vol = float(np.std(window, ddof=1) * math.sqrt(TRADING_DAYS))
        if not (0.01 < vol < 3.0):
            continue
        premium = (bs_price("call", entry, entry * (1 + otm), calendar_days, vol)
                   + bs_price("put", entry, entry * (1 - otm), calendar_days, vol))
        premium_pct = premium / entry * 100
        move_pct = (exit_price / entry - 1) * 100
        loss_pct = max(0.0, abs(move_pct) - otm_pct)
        pnl_pct = premium_pct - loss_pct

        equity += pnl_pct
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        trades.append({
            "date": dates[i], "entry": round(entry, 2),
            "move_pct": round(move_pct, 2), "premium_pct": round(premium_pct, 3),
            "pnl_pct": round(pnl_pct, 3), "vol": round(vol, 4),
        })
        curve.append({"date": dates[i + dte], "equity": round(equity, 3)})

    if len(trades) < 10:
        raise ValueError(f"solo {len(trades)} operaciones; amplía años o reduce DTE")

    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return {
        "symbol": symbol, "otm_pct": otm_pct, "dte": dte, "years": years,
        "n": len(trades),
        "win_rate": round(100 * len(wins) / len(trades), 1),
        "total_pct": round(equity, 2),
        "avg_win": round(float(np.mean(wins)), 3) if wins else 0.0,
        "avg_loss": round(float(np.mean(losses)), 3) if losses else 0.0,
        "worst": round(min(pnls), 2),
        "max_drawdown": round(max_drawdown, 2),
        "curve": curve,
        "trades": trades[-12:],
        "note": ("primas BSM con vol realizada 21d; sin comisiones ni slippage; "
                 "P&L en % del subyacente por strangle vendido"),
    }
