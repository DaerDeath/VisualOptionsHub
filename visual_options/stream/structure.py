"""Tres pantallas de Bloomberg que faltaban en la app, con datos de Yahoo.

TRMS — estructura de plazos de IV (ATM implied vol across maturities):
  para cada vencimiento, la IV del strike más cercano al spot.

VC — cono de volatilidad (volatility cone): volatilidad realizada anualizada
  en ventanas móviles (10/20/30/60/90 sesiones) sobre ~2 años de histórico,
  con min/p25/mediana/p75/max y el valor actual — el mismo gráfico "cono"
  que usa Bloomberg para saber si la vol actual está cara o barata en
  contexto histórico.

CORR — sensibilidad de mercado: correlación de los retornos diarios del
  símbolo con una cesta de índices/sectores/factores durante N sesiones.
"""

from __future__ import annotations

import math

import numpy as np

WINDOWS = (10, 20, 30, 60, 90)
TRADING_DAYS = 252
DEFAULT_PEERS = ("SPY", "QQQ", "IWM", "DIA", "XLF", "XLK", "XLE", "XLV", "GLD", "TLT")


def _ticker(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    return yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)


def term_structure(symbol: str, max_expiries: int = 8) -> dict:
    ticker = _ticker(symbol)
    spot = _spot(ticker)
    expirations = ticker.options
    if not expirations:
        raise ValueError(f"{symbol} no tiene cadena de opciones en Yahoo")

    from datetime import datetime
    points = []
    for expiry in expirations[:max_expiries]:
        try:
            chain = ticker.option_chain(expiry)
        except Exception:
            continue
        iv = _atm_iv(chain, spot)
        if iv is None:
            continue
        days = max(1, (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days)
        points.append({"expiry": expiry, "days": days, "iv": round(iv, 4)})

    if len(points) < 2:
        raise ValueError(f"{symbol}: no hay suficientes vencimientos con IV válida")
    contango = points[-1]["iv"] - points[0]["iv"]
    return {
        "symbol": symbol.upper(), "spot": spot, "points": points,
        "contango": round(contango, 4),
        "shape": "contango" if contango > 0.005 else "backwardation" if contango < -0.005 else "plana",
    }


def _atm_iv(chain, spot: float) -> float | None:
    ivs = []
    for frame in (chain.calls, chain.puts):
        if frame is None or not len(frame):
            continue
        idx = (frame["strike"] - spot).abs().idxmin()
        iv = frame.loc[idx, "impliedVolatility"]
        if iv is not None and not (isinstance(iv, float) and math.isnan(iv)) and 0.01 < iv < 5:
            ivs.append(float(iv))
    return sum(ivs) / len(ivs) if ivs else None


def _spot(ticker) -> float:
    info = getattr(ticker, "fast_info", None)
    for key in ("last_price", "lastPrice"):
        try:
            value = float(info[key]) if info is not None else None
        except (KeyError, TypeError, ValueError):
            value = None
        if value and not math.isnan(value):
            return value
    history = ticker.history(period="5d", interval="1d")
    return float(history["Close"].dropna().iloc[-1])


def vol_cone(symbol: str, years: int = 2) -> dict:
    import yfinance as yf
    ticker = _ticker(symbol)
    history = ticker.history(period=f"{max(1, min(years, 10))}y", interval="1d")
    closes = history["Close"].dropna().to_numpy(dtype=float)
    if len(closes) < max(WINDOWS) + 20:
        raise ValueError(f"{symbol}: histórico insuficiente para el cono de volatilidad")
    log_returns = np.diff(np.log(closes))

    cones = []
    for window in WINDOWS:
        if len(log_returns) < window + 5:
            continue
        rolling = np.array([
            np.std(log_returns[i - window:i], ddof=1) * math.sqrt(TRADING_DAYS)
            for i in range(window, len(log_returns) + 1)
        ])
        current = float(rolling[-1])
        percentile = float(100 * np.mean(rolling < current))
        cones.append({
            "window": window, "current": round(current, 4),
            "min": round(float(rolling.min()), 4), "p25": round(float(np.percentile(rolling, 25)), 4),
            "median": round(float(np.median(rolling)), 4), "p75": round(float(np.percentile(rolling, 75)), 4),
            "max": round(float(rolling.max()), 4), "percentile": round(percentile, 1),
        })
    if not cones:
        raise ValueError(f"{symbol}: sin ventanas suficientes para el cono")
    return {"symbol": symbol.upper(), "years": years, "cones": cones}


def correlation(symbol: str, peers: tuple[str, ...] = DEFAULT_PEERS, days: int = 90) -> dict:
    import yfinance as yf
    symbol = symbol.upper()
    tickers = [symbol, *[p for p in peers if p.upper() != symbol]]
    data = yf.download(tickers, period=f"{max(days + 30, 120)}d", interval="1d",
                       progress=False, auto_adjust=True)["Close"]
    if hasattr(data, "columns"):
        data = data.dropna(how="all")
    else:
        raise ValueError("descarga de peers falló")
    if symbol not in data.columns:
        raise ValueError(f"{symbol}: sin datos suficientes para correlacionar")

    returns = np.log(data / data.shift(1)).dropna(how="all").tail(days)
    base = returns[symbol].dropna()
    rows = []
    for peer in tickers[1:]:
        if peer not in returns.columns:
            continue
        aligned = returns[[symbol, peer]].dropna()
        if len(aligned) < 20:
            continue
        corr = float(np.corrcoef(aligned[symbol], aligned[peer])[0, 1])
        rows.append({"peer": peer, "correlation": round(corr, 3)})
    rows.sort(key=lambda r: abs(r["correlation"]), reverse=True)
    if not rows:
        raise ValueError(f"{symbol}: no se pudo correlacionar con ningún peer")
    return {"symbol": symbol, "days": len(base), "rows": rows}
