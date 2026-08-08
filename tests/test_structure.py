"""Tests de estructura de plazos, cono de volatilidad y correlación."""

import sys
import types
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from visual_options.stream import structure as st


class FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = {"last_price": 100.0}
        self._today = datetime.now()
        self.options = tuple(
            (self._today + timedelta(days=d)).strftime("%Y-%m-%d")
            for d in (7, 14, 30, 60, 90)
        )

    def option_chain(self, expiration):
        # IV creciente con el plazo → contango claro y comprobable
        idx = self.options.index(expiration)
        iv = 0.15 + idx * 0.01
        calls = pd.DataFrame([{"strike": 100.0, "impliedVolatility": iv}])
        puts = pd.DataFrame([{"strike": 100.0, "impliedVolatility": iv + 0.002}])
        return type("Chain", (), {"calls": calls, "puts": puts})()

    def history(self, period="1d", interval="1d"):
        rng = np.random.default_rng(7)
        n = 700
        closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        idx = pd.date_range(end=self._today, periods=n, freq="D")
        return pd.DataFrame({"Close": closes}, index=idx)


@pytest.fixture
def fake_yf(monkeypatch):
    module = types.ModuleType("yfinance")
    module.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", module)
    return module


def test_term_structure_detects_contango(fake_yf):
    result = st.term_structure("FAKE")
    assert result["symbol"] == "FAKE"
    assert len(result["points"]) == 5
    ivs = [p["iv"] for p in result["points"]]
    assert ivs == sorted(ivs)               # IV creciente por construcción
    assert result["shape"] == "contango"
    assert result["contango"] > 0


def test_term_structure_needs_at_least_two_points(fake_yf, monkeypatch):
    class OneExpiry(FakeTicker):
        def __init__(self, symbol):
            super().__init__(symbol)
            self.options = self.options[:1]

    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", OneExpiry)
    with pytest.raises(ValueError):
        st.term_structure("FAKE")


def test_vol_cone_shape_and_percentile(fake_yf):
    result = st.vol_cone("FAKE", years=2)
    assert result["symbol"] == "FAKE"
    windows = [c["window"] for c in result["cones"]]
    assert windows == list(st.WINDOWS)
    for cone in result["cones"]:
        assert cone["min"] <= cone["p25"] <= cone["median"] <= cone["p75"] <= cone["max"]
        assert 0 <= cone["percentile"] <= 100
        assert cone["min"] <= cone["current"] <= cone["max"] + 1e-6


def test_vol_cone_insufficient_history(fake_yf, monkeypatch):
    class ShortHistory(FakeTicker):
        def history(self, period="1d", interval="1d"):
            idx = pd.date_range(end=self._today, periods=30, freq="D")
            return pd.DataFrame({"Close": np.linspace(100, 101, 30)}, index=idx)

    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", ShortHistory)
    with pytest.raises(ValueError):
        st.vol_cone("FAKE")


def test_correlation_ranks_by_absolute_strength(monkeypatch):
    rng = np.random.default_rng(3)
    n = 150
    base = rng.normal(0, 0.01, n)
    idx = pd.date_range(end=datetime.now(), periods=n, freq="D")
    # SPY: casi idéntico a FAKE (correlación alta); GLD: independiente
    frame = pd.DataFrame({
        "FAKE": 100 * np.exp(np.cumsum(base)),
        "SPY": 400 * np.exp(np.cumsum(base * 0.98 + rng.normal(0, 0.0005, n))),
        "GLD": 180 * np.exp(np.cumsum(rng.normal(0, 0.01, n))),
    }, index=idx)

    module = types.ModuleType("yfinance")

    def fake_download(tickers, **kwargs):
        cols = pd.MultiIndex.from_product([["Close"], frame.columns])
        wide = pd.DataFrame(frame.values, index=frame.index, columns=cols)
        return wide

    module.download = fake_download
    monkeypatch.setitem(sys.modules, "yfinance", module)

    result = st.correlation("FAKE", peers=("SPY", "GLD"), days=90)
    assert result["symbol"] == "FAKE"
    peers = {r["peer"]: r["correlation"] for r in result["rows"]}
    assert peers["SPY"] > 0.9
    assert abs(peers["GLD"]) < peers["SPY"]
    assert result["rows"][0]["peer"] == "SPY"  # ordenado por |correlación|
