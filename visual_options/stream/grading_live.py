"""Checklist A-F del Cap. 2 con datos reales: 10 de los 17 criterios se
calculan solos desde precio, volumen y opciones de Yahoo; los 7 restantes
son subjetivos por diseño del libro (conocimiento del negocio, estado
mental, etc.) y quedan como toggles manuales.

Reutiliza el motor de calificación de visual_options.grading tal cual
(misma escala A→F, misma tabla de asignación de cartera) — esto solo
rellena los `criteria: dict[str, bool]` con números de verdad en vez de
pedírselos todos al usuario.
"""

from __future__ import annotations

import math

import numpy as np

from visual_options.grading import CHECKLIST_CRITERIA, GRADE_GUIDANCE, grade_trade
from visual_options.volatility import historical_volatility, iv_hv_ratio, volatility_bias

# claves que el libro exige juicio subjetivo del propio trader — no se automatizan
MANUAL_KEYS = ("fund_knowledge", "fund_business", "fund_top20", "trade_specific",
              "timing_event", "timing_chart", "timing_mental")


def _ticker(symbol: str):
    import yfinance as yf
    symbol = symbol.upper()
    return yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)


def _sma(closes: np.ndarray, window: int) -> float | None:
    return float(closes[-window:].mean()) if len(closes) >= window else None


def _macd_cross_within(closes: np.ndarray, bars: int = 3) -> tuple[bool, str]:
    """¿Hubo un cruce MACD/señal en las últimas `bars` barras? Y en qué sentido."""
    if len(closes) < 35:
        return False, "histórico insuficiente"
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26
    signal = _ema(macd, 9)
    diff = macd - signal
    recent = diff[-(bars + 1):]
    crossed_up = any(recent[i] <= 0 < recent[i + 1] for i in range(len(recent) - 1))
    crossed_down = any(recent[i] >= 0 > recent[i + 1] for i in range(len(recent) - 1))
    if crossed_up:
        return True, "cruce alcista reciente"
    if crossed_down:
        return True, "cruce bajista reciente"
    return False, "sin cruce en la ventana"


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    alpha = 2 / (span + 1)
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, window: int = 14) -> float | None:
    if len(closes) < window + 1:
        return None
    prev_close = closes[:-1]
    tr = np.maximum.reduce([
        highs[1:] - lows[1:],
        np.abs(highs[1:] - prev_close),
        np.abs(lows[1:] - prev_close),
    ])
    return float(tr[-window:].mean())


def _option_snapshot(ticker, spot: float) -> dict:
    """Volumen total de opciones, spread medio ATM e IV media del vencimiento próximo."""
    expirations = ticker.options
    if not expirations:
        return {"volume": 0, "spread": None, "iv": None}
    chain = ticker.option_chain(expirations[0])
    volume = 0
    spreads, ivs = [], []
    for frame in (chain.calls, chain.puts):
        if frame is None or not len(frame):
            continue
        volume += int(frame["volume"].fillna(0).sum())
        near = frame[(frame["strike"] - spot).abs() <= spot * 0.03]
        for _, row in near.iterrows():
            bid, ask = row.get("bid"), row.get("ask")
            if bid and ask and ask > 0:
                spreads.append(float(ask - bid))
            iv = row.get("impliedVolatility")
            if iv and not (isinstance(iv, float) and math.isnan(iv)) and 0.01 < iv < 5:
                ivs.append(float(iv))
    return {
        "volume": volume,
        "spread": round(sum(spreads) / len(spreads), 3) if spreads else None,
        "iv": round(sum(ivs) / len(ivs), 4) if ivs else None,
    }


def auto_grade(symbol: str, bias: str = "neutral", side: str = "buy",
               manual_fail: tuple[str, ...] = (), ticker=None, spy_ticker=None) -> dict:
    if bias not in ("bullish", "bearish", "neutral"):
        raise ValueError("bias debe ser 'bullish', 'bearish' o 'neutral'")
    if side not in ("buy", "sell"):
        raise ValueError("side debe ser 'buy' o 'sell'")

    ticker = ticker or _ticker(symbol)
    history = ticker.history(period="1y", interval="1d")
    if len(history) < 30:
        raise ValueError(f"{symbol}: histórico insuficiente para calificar")
    closes = history["Close"].dropna().to_numpy(dtype=float)
    volumes = history["Volume"].dropna().to_numpy(dtype=float)
    highs = history["High"].dropna().to_numpy(dtype=float)
    lows = history["Low"].dropna().to_numpy(dtype=float)
    price = float(closes[-1])

    items: list[dict] = []  # {key, label, group, value, detail}
    values: dict[str, bool] = {}

    def add(key: str, value: bool | None, detail: str) -> None:
        # numpy.bool_ no es JSON-serializable de forma nativa; siempre se
        # normaliza a bool de Python (o None) antes de guardarlo
        value = None if value is None else bool(value)
        if value is not None:
            values[key] = value
        items.append({"key": key, "label": dict(CHECKLIST_CRITERIA)[key],
                      "group": "auto", "value": value, "detail": detail})

    # 1. dirección de mercado — el libro exime a las operaciones neutrales
    if bias == "neutral":
        add("market_direction", None, "operación neutral: el libro exime este criterio")
    else:
        spy = spy_ticker or _ticker("SPY")
        spy_hist = spy.history(period="1mo", interval="1d")
        spy_closes = spy_hist["Close"].dropna().to_numpy(dtype=float)
        spy_up = len(spy_closes) >= 6 and spy_closes[-1] > spy_closes[-6]
        try:
            summary = ticker.recommendations_summary
            row = summary.iloc[0] if summary is not None and len(summary) else None
            total = sum(int(row.get(k, 0) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")) if row is not None else 0
            bullish_pct = 100 * (int(row.get("strongBuy", 0)) + int(row.get("buy", 0))) / total if total else None
        except Exception:
            bullish_pct = None
        market_up = spy_up and (bullish_pct is None or bullish_pct >= 50)
        market_down = (not spy_up) and (bullish_pct is None or bullish_pct < 50)
        aligned = market_up if bias == "bullish" else market_down
        detail = f"SPY {'alcista' if spy_up else 'bajista'} (10d)" + (
            f" · analistas {bullish_pct:.0f}% alcistas" if bullish_pct is not None else "")
        add("market_direction", aligned, detail)

    # 2b. volumen
    avg_volume = float(volumes[-60:].mean())
    add("fund_volume", avg_volume >= 750_000, f"{avg_volume / 1e6:.2f}M acciones/día de media")

    # 3a. tendencia 6 meses
    if len(closes) >= 126:
        change_6m = closes[-1] / closes[-126] - 1
        trend_up = change_6m > 0
        trend_ok = True if bias == "neutral" else (trend_up if bias == "bullish" else not trend_up)
        add("chart_trend", trend_ok, f"{change_6m:+.1%} en 6 meses")
    else:
        add("chart_trend", None, "histórico insuficiente (<6 meses)")

    # 3b. medias móviles + Bollinger
    sma20, sma50, sma200 = _sma(closes, 20), _sma(closes, 50), _sma(closes, 200)
    mean20 = _sma(closes, 20)
    std20 = float(closes[-20:].std()) if len(closes) >= 20 else None
    outside_bands = None
    if mean20 is not None and std20:
        upper, lower = mean20 + 2 * std20, mean20 - 2 * std20
        outside_bands = price > upper or price < lower
    smas_favorable = None
    if all(v is not None for v in (sma20, sma50, sma200)) and bias != "neutral":
        below_price = price > sma20 > sma50 > sma200
        above_price = price < sma20 < sma50 < sma200
        smas_favorable = below_price if bias == "bullish" else above_price
    chart_current_ok = None
    if bias == "neutral":
        chart_current_ok = not bool(outside_bands) if outside_bands is not None else None
    elif smas_favorable is not None:
        chart_current_ok = smas_favorable and not bool(outside_bands)
    detail_parts = []
    if sma20 and sma50 and sma200:
        detail_parts.append(f"SMA20 {sma20:.2f} / SMA50 {sma50:.2f} / SMA200 {sma200:.2f}")
    if outside_bands is not None:
        detail_parts.append("fuera de Bollinger" if outside_bands else "dentro de Bollinger")
    add("chart_current", chart_current_ok, "; ".join(detail_parts) or "datos insuficientes")

    # 3c. volumen a favor de la tendencia
    if len(volumes) >= 20:
        recent_vol = float(volumes[-5:].mean())
        base_vol = float(volumes[-20:-5].mean())
        rising = recent_vol > base_vol
        vol_ok = True if bias == "neutral" else rising  # más volumen reciente = convicción
        add("chart_volume", vol_ok, f"volumen 5d {recent_vol / 1e6:.2f}M vs 20d {base_vol / 1e6:.2f}M")
    else:
        add("chart_volume", None, "histórico insuficiente")

    # 3d. MACD
    crossed, macd_detail = _macd_cross_within(closes, bars=3)
    if bias == "neutral":
        add("chart_macd", True, macd_detail + " (neutral: no se exige dirección)")
    else:
        wants_up = bias == "bullish"
        aligned = crossed and (("alcista" in macd_detail) == wants_up)
        add("chart_macd", aligned if crossed else False, macd_detail)

    # 4. opciones: volumen, spreads, IV vs HV
    opt = _option_snapshot(ticker, price)
    opt_threshold = 1000 if avg_volume > 750_000 else 50
    add("opt_volume", opt["volume"] >= opt_threshold,
        f"{opt['volume']:,} contratos hoy (umbral {opt_threshold:,})")

    if opt["spread"] is not None:
        threshold = 0.30 if price < 200 else 0.50
        add("opt_spreads", opt["spread"] <= threshold, f"spread medio ATM ${opt['spread']:.2f}")
    else:
        add("opt_spreads", None, "sin cotizaciones ATM disponibles")

    if opt["iv"] is not None and len(closes) >= 31:
        hv = historical_volatility(closes, window=30)
        ratio = iv_hv_ratio(opt["iv"], hv)
        recommended_side = volatility_bias(opt["iv"], hv)
        fits = (side == "buy" and recommended_side in ("comprador", "neutral")) or \
               (side == "sell" and recommended_side in ("vendedor", "neutral"))
        add("opt_iv_fit", fits,
            f"IV {opt['iv']:.1%} vs HV {hv:.1%} (ratio {ratio:.2f}) → favorece {recommended_side}")
    else:
        add("opt_iv_fit", None, "sin IV suficiente para comparar con HV")

    # 6a. ATR de hoy
    atr = _atr(highs, lows, closes, window=14)
    if atr:
        today_move = abs(float(highs[-1] - lows[-1]))
        add("timing_atr", today_move <= atr * 1.2, f"rango de hoy {today_move:.2f} vs ATR14 {atr:.2f}")
    else:
        add("timing_atr", None, "histórico insuficiente para ATR")

    # criterios manuales — el libro pide juicio propio; se dan por buenos salvo que se marquen
    for key in MANUAL_KEYS:
        failed = key in manual_fail
        items.append({"key": key, "label": dict(CHECKLIST_CRITERIA)[key],
                      "group": "manual", "value": not failed, "detail": "criterio subjetivo (Cap. 2)"})
        values[key] = not failed

    # cualquier automático que el usuario quiera anular a mano
    for key in manual_fail:
        if key not in MANUAL_KEYS:
            values[key] = False
            for item in items:
                if item["key"] == key:
                    item["value"] = False
                    item["detail"] += " · anulado manualmente"

    result = grade_trade(values)
    return {
        "symbol": symbol.upper(), "price": round(price, 2), "bias": bias, "side": side,
        "items": items, "grade": result.grade, "allocation": list(result.allocation),
        "guidance": GRADE_GUIDANCE[result.grade], "failed": list(result.failed),
    }
