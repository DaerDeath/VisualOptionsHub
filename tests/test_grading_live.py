"""Tests del checklist A-F automatizado, con tickers sintéticos controlados."""

import numpy as np
import pandas as pd
import pytest

from visual_options.stream import grading_live as gl


def make_history(n=280, start=100.0, daily_drift=0.003, vol=0.005, seed=1,
                 base_volume=1_500_000):
    rng = np.random.default_rng(seed)
    returns = rng.normal(daily_drift, vol, n)
    closes = start * np.exp(np.cumsum(returns))
    highs = closes * (1 + rng.uniform(0.001, 0.01, n))
    lows = closes * (1 - rng.uniform(0.001, 0.01, n))
    volumes = rng.normal(base_volume, base_volume * 0.1, n).clip(min=1000)
    idx = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="D")
    return pd.DataFrame({"Close": closes, "High": highs, "Low": lows, "Volume": volumes}, index=idx)


class FakeTicker:
    def __init__(self, history, options=(), iv=0.25, bid_ask_width=0.05,
                 recs=None):
        self._history = history
        self.options = options
        self._iv = iv
        self._bid_ask_width = bid_ask_width
        self.recommendations_summary = recs

    def history(self, period="1y", interval="1d"):
        return self._history

    def option_chain(self, expiry):
        spot = float(self._history["Close"].iloc[-1])
        strikes = [spot * f for f in (0.97, 0.99, 1.0, 1.01, 1.03)]
        rows = [{"strike": k, "volume": 500, "bid": 2.0, "ask": 2.0 + self._bid_ask_width,
                "impliedVolatility": self._iv} for k in strikes]
        frame = pd.DataFrame(rows)
        return type("Chain", (), {"calls": frame, "puts": frame})()


def bullish_recs():
    return pd.DataFrame([{"strongBuy": 15, "buy": 10, "hold": 2, "sell": 0, "strongSell": 0}])


def bearish_recs():
    return pd.DataFrame([{"strongBuy": 0, "buy": 1, "hold": 3, "sell": 10, "strongSell": 8}])


# ------------------------------------------------------- helpers numéricos

def test_ema_matches_pandas_reference():
    values = np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    ours = gl._ema(values, span=3)
    ref = pd.Series(values).ewm(span=3, adjust=False).mean().to_numpy()
    assert ours == pytest.approx(ref, abs=1e-9)


def test_atr_positive_and_reasonable():
    n = 40
    closes = np.linspace(100, 110, n)
    highs = closes + 1.0
    lows = closes - 1.0
    atr = gl._atr(highs, lows, closes, window=14)
    assert atr == pytest.approx(2.0, abs=0.2)


def test_atr_none_when_insufficient_history():
    assert gl._atr(np.array([1.0, 2.0]), np.array([1.0, 2.0]), np.array([1.0, 2.0])) is None


def test_macd_detects_bullish_cross():
    # caída sostenida seguida de un rebote brusco justo en las últimas barras
    down = np.linspace(100, 90, 35)
    up = np.linspace(90, 105, 3)
    closes = np.concatenate([down, up])
    crossed, detail = gl._macd_cross_within(closes, bars=3)
    assert crossed is True
    assert "alcista" in detail


def test_macd_no_cross_on_flat_series():
    closes = np.full(60, 100.0) + np.random.default_rng(0).normal(0, 0.01, 60)
    crossed, _ = gl._macd_cross_within(closes, bars=3)
    assert crossed is False


# --------------------------------------------------------------- auto_grade

def test_bullish_setup_computes_the_robust_criteria_correctly():
    # nota: un dato sintético con deriva pura queda "sobreextendido" (fuera de
    # Bollinger) de forma realista, así que no forzamos un grado concreto —
    # eso ya lo prueba test_volatility_grading.py sobre grade_trade() directo.
    # Aquí solo se valida que los criterios que SÍ podemos controlar salgan bien.
    history = make_history(n=280, daily_drift=0.004, vol=0.004, seed=2, base_volume=2_000_000)
    ticker = FakeTicker(history, options=("2099-01-01",), iv=0.18, recs=bullish_recs())
    spy_hist = make_history(n=30, daily_drift=0.003, vol=0.003, seed=3)
    spy = FakeTicker(spy_hist)
    result = gl.auto_grade("FAKE", bias="bullish", side="buy", ticker=ticker, spy_ticker=spy)
    assert result["symbol"] == "FAKE"
    labels = {i["key"]: i["value"] for i in result["items"]}
    assert labels["fund_volume"] is True       # 2M/día >> 750k
    assert labels["market_direction"] is True  # SPY alcista + 93% analistas alcistas
    assert labels["opt_volume"] is True        # 5000 contratos >> umbral 1000
    assert labels["opt_spreads"] is True        # spread $0.05, muy ajustado
    assert labels["chart_trend"] is True        # +58% en 6 meses, alineado con bias alcista
    assert result["grade"] in ("A", "B", "C", "D", "F")  # siempre un grado válido


def test_neutral_bias_exempts_market_direction():
    history = make_history(n=280, seed=4)
    ticker = FakeTicker(history, options=("2099-01-01",))
    result = gl.auto_grade("FAKE", bias="neutral", side="sell", ticker=ticker)
    item = next(i for i in result["items"] if i["key"] == "market_direction")
    assert item["value"] is None
    assert "exime" in item["detail"]
    # None no debe colarse como fallo: no aparece en failed por este criterio
    assert "market_direction" not in result["failed"]


def test_manual_fail_downgrades_and_is_marked():
    history = make_history(n=280, seed=5)
    ticker = FakeTicker(history, options=())
    baseline = gl.auto_grade("FAKE", bias="neutral", ticker=ticker)
    downgraded = gl.auto_grade("FAKE", bias="neutral", ticker=ticker,
                               manual_fail=("timing_mental", "fund_knowledge"))
    assert len(downgraded["failed"]) >= len(baseline["failed"]) + 2
    mental = next(i for i in downgraded["items"] if i["key"] == "timing_mental")
    assert mental["value"] is False and mental["group"] == "manual"


def test_manual_fail_can_override_automatic_criterion():
    history = make_history(n=280, daily_drift=0.004, vol=0.004, seed=2, base_volume=2_000_000)
    ticker = FakeTicker(history, options=("2099-01-01",), iv=0.18, recs=bullish_recs())
    spy = FakeTicker(make_history(n=30, seed=3))
    result = gl.auto_grade("FAKE", bias="bullish", ticker=ticker, spy_ticker=spy,
                           manual_fail=("fund_volume",))
    item = next(i for i in result["items"] if i["key"] == "fund_volume")
    assert item["value"] is False
    assert "anulado manualmente" in item["detail"]


def test_option_snapshot_thresholds_scale_with_price():
    history = make_history(n=280, start=250.0, seed=6)  # precio >200 → umbral de spread más laxo
    ticker = FakeTicker(history, options=("2099-01-01",), bid_ask_width=0.35)
    result = gl.auto_grade("FAKE", bias="neutral", ticker=ticker)
    spreads_item = next(i for i in result["items"] if i["key"] == "opt_spreads")
    assert spreads_item["value"] is True  # 0.35 pasa el umbral de 0.50 para precio>200


def test_invalid_bias_and_side_raise():
    history = make_history(n=280, seed=7)
    ticker = FakeTicker(history)
    with pytest.raises(ValueError):
        gl.auto_grade("FAKE", bias="lateral", ticker=ticker)
    with pytest.raises(ValueError):
        gl.auto_grade("FAKE", side="hold", ticker=ticker)


def test_short_history_raises():
    ticker = FakeTicker(make_history(n=10, seed=8))
    with pytest.raises(ValueError):
        gl.auto_grade("FAKE", ticker=ticker)


def test_all_seventeen_criteria_present_in_items():
    from visual_options.grading import CHECKLIST_CRITERIA
    history = make_history(n=280, seed=9)
    ticker = FakeTicker(history, options=("2099-01-01",))
    result = gl.auto_grade("FAKE", bias="bullish", ticker=ticker, spy_ticker=FakeTicker(make_history(n=30, seed=1)))
    keys = {i["key"] for i in result["items"]}
    assert keys == {k for k, _ in CHECKLIST_CRITERIA}
