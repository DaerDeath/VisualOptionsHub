"""Tests del feed de yfinance con un ticker falso (DataFrames de pandas)."""

import pandas as pd
import pytest

from visual_options.stream.yfinance_feed import YFinanceFeed


class FakeTicker:
    """Imita la superficie de yfinance.Ticker que usa el feed."""

    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {"last_price": 720.0}
        self.options = ("2026-07-06", "2026-07-08")
        self.chain_calls = 0

    def option_chain(self, expiration):
        assert expiration == "2026-07-06"
        extra = self.chain_calls * 500
        self.chain_calls += 1
        calls = pd.DataFrame([
            {"contractSymbol": "QQQ0706C719", "strike": 719.0, "lastPrice": 2.6,
             "bid": 2.5, "ask": 2.7, "volume": 1200 + extra, "openInterest": 4000,
             "impliedVolatility": 0.19},
            {"contractSymbol": "QQQ0706C720", "strike": 720.0, "lastPrice": 2.05,
             "bid": 2.0, "ask": 2.2, "volume": 1000 + extra, "openInterest": 5000,
             "impliedVolatility": 0.18},
        ])
        puts = pd.DataFrame([
            {"contractSymbol": "QQQ0706P720", "strike": 720.0, "lastPrice": 1.99,
             "bid": 1.8, "ask": 2.0, "volume": 800 + extra, "openInterest": 4500,
             "impliedVolatility": 0.20},
        ])
        return type("Chain", (), {"calls": calls, "puts": puts})()

    def history(self, period="1d", interval="1m"):
        idx = pd.to_datetime(["2026-07-02 09:30", "2026-07-02 09:31"])
        return pd.DataFrame({
            "Open": [719.5, 720.0], "High": [720.1, 720.4],
            "Low": [719.3, 719.9], "Close": [720.0, 719.9],
            "Volume": [90000, 60000],
        }, index=idx)


def make_feed() -> YFinanceFeed:
    return YFinanceFeed("QQQ", ticker_factory=lambda s: FakeTicker(s))


def test_refresh_builds_chain_and_exposures():
    feed = make_feed()
    feed._refresh()
    assert feed.state.spot == 720.0
    assert feed._expiration == "2026-07-06"
    strikes = {r.strike: r for r in feed.state.strikes}
    assert {719.0, 720.0} <= set(strikes)
    row = strikes[720.0]
    assert row.call_volume == 1000 and row.put_volume == 800
    assert row.call_oi == 5000 and row.put_oi == 4500
    assert row.iv > 0
    # primera foto = línea base: sin clasificar
    assert row.call_sold_pct == 50.0 and row.put_sold_pct == 50.0
    assert row.call_gex > 0 and row.put_gex < 0
    assert len(feed.state.series) == 1
    assert len(feed.state.gex_history) == 1


def test_second_refresh_classifies_volume_deltas():
    feed = make_feed()
    feed._refresh()
    feed._refresh()  # +500 de volumen por contrato
    row = {r.strike: r for r in feed.state.strikes}[720.0]
    # call last 2.05 <= mid 2.1 → vendido; put last 1.99 > mid 1.9 → comprado
    assert row.call_sold_pct == 100.0
    assert row.put_sold_pct == 0.0
    # bloques de 500 ≥ umbral → tape
    assert len(feed.state.tape) >= 2


def test_footprint_from_1m_bars_without_duplicates():
    feed = make_feed()
    feed._refresh()
    feed._refresh()  # segunda pasada con las mismas velas
    assert len(feed.footprint.bars) == 2
    assert feed.footprint.bars[0].volume == 90000
    assert feed.footprint.bars[1].delta < 0  # 719.9 < 720.0 → downtick


def test_expiry_days_positive():
    feed = make_feed()
    feed._refresh()
    assert feed.state.expiry_days > 0


def test_index_symbols_get_caret_prefix():
    seen = []

    class Recorder(FakeTicker):
        def __init__(self, symbol):
            seen.append(symbol)
            super().__init__(symbol)

    import visual_options.stream.yfinance_feed as mod
    original = mod.YFinanceFeed._default_factory
    try:
        import sys
        import types
        fake_yf = types.ModuleType("yfinance")
        fake_yf.Ticker = Recorder
        sys.modules["yfinance"] = fake_yf
        YFinanceFeed._default_factory("SPX")
        YFinanceFeed._default_factory("QQQ")
        assert seen == ["^SPX", "QQQ"]
    finally:
        sys.modules.pop("yfinance", None)
        mod.YFinanceFeed._default_factory = original
