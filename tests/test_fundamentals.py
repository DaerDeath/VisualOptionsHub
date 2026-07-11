"""Tests de la ficha de empresa con ticker falso inyectado en yfinance."""

import sys
import types
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from visual_options.stream import fundamentals as fu


class FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.info = {
            "longName": "Fake Corp", "sector": "Technology", "industry": "Software",
            "longBusinessSummary": "Hace software falso para tests.",
            "currentPrice": 100.0, "marketCap": 5e10, "beta": 1.2,
            "trailingPE": 25.0, "forwardPE": 20.0, "trailingEps": 4.0,
            "dividendYield": 0.5, "shortRatio": 2.5, "averageVolume": 2_000_000,
            "fiftyTwoWeekLow": 60.0, "fiftyTwoWeekHigh": 140.0,
        }
        now = datetime.now(timezone.utc)
        self.earnings_dates = pd.DataFrame(
            {"EPS Estimate": [1.5, 1.2, 1.1, 1.0],
             "Reported EPS": [None, 1.3, 1.0, 1.1],
             "Surprise(%)": [None, 8.3, -9.1, 10.0]},
            index=pd.DatetimeIndex([now + timedelta(days=12), now - timedelta(days=80),
                                    now - timedelta(days=170), now - timedelta(days=260)],
                                   name="Earnings Date", tz="UTC"),
        )
        self.recommendations_summary = pd.DataFrame(
            [{"period": "0m", "strongBuy": 10, "buy": 8, "hold": 2, "sell": 0, "strongSell": 0}])
        self.analyst_price_targets = {"low": 90.0, "mean": 125.0, "median": 124.0, "high": 150.0}
        self.calendar = {"Earnings Date": [(now + timedelta(days=12)).date()],
                         "Earnings Average": 1.55, "Revenue Average": 9.9e9}
        self.news = [{"content": {
            "title": "Fake Corp lanza algo",
            "pubDate": "2026-07-06T12:00:00Z",
            "provider": {"displayName": "FakeWire"},
            "canonicalUrl": {"url": "https://example.com/n1"},
        }}]


@pytest.fixture
def fake_yf(monkeypatch):
    module = types.ModuleType("yfinance")
    module.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", module)
    fu._cache.clear()
    return module


def test_company_snapshot_full(fake_yf):
    snap = fu.company_snapshot("FAKE")
    assert snap["profile"]["name"] == "Fake Corp"
    m = snap["metrics"]
    assert m["price"] == 100.0
    assert m["pos52"] == pytest.approx((100 - 60) / (140 - 60))

    e = snap["earnings"]
    assert e["next_date"] is not None and 10.5 <= e["days_to_next"] <= 13
    assert e["next_eps_est"] == pytest.approx(1.55)
    assert e["next_revenue_est"] == pytest.approx(9.9e9)
    assert len(e["history"]) == 3
    assert e["history"][0]["surprise"] == pytest.approx(8.3)

    a = snap["analysts"]
    assert a["total"] == 20
    assert a["bullish_pct"] == pytest.approx(90.0)
    assert a["target_upside_pct"] == pytest.approx(25.0)

    assert snap["news"][0]["publisher"] == "FakeWire"
    assert snap["news"][0]["url"] == "https://example.com/n1"


def test_book_checklist_verdicts(fake_yf):
    snap = fu.company_snapshot("FAKE")
    by_name = {c["name"]: c for c in snap["book_checklist"]}
    assert by_name["Convicción de analistas ≥85% alcistas (Cap. 7)"]["verdict"] == "ok"   # 90%
    assert by_name["Objetivo de consenso ≥10% sobre el precio (Cap. 7)"]["verdict"] == "ok"  # +25%
    assert by_name["Cobertura ≥4-5 analistas (menos sorpresas inesperadas)"]["verdict"] == "ok"
    assert by_name["Volumen ≥750k acciones/día (Cap. 2)"]["verdict"] == "ok"
    surprise = by_name["Historial de sorpresas EPS positivas"]
    assert "2/3" in surprise["value"]
    assert surprise["verdict"] == "warn"  # 66% < 70%


def test_cache_hits_within_ttl(fake_yf, monkeypatch):
    fu.company_snapshot("FAKE")
    calls = {"n": 0}

    class Exploding:
        def __init__(self, symbol):
            calls["n"] += 1
            raise RuntimeError("no debería llamarse: caché")

    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", Exploding)
    snap = fu.company_snapshot("FAKE")  # servido de caché
    assert snap["profile"]["name"] == "Fake Corp"
    assert calls["n"] == 0


def test_empty_info_raises(fake_yf, monkeypatch):
    class EmptyTicker(FakeTicker):
        def __init__(self, symbol):
            self.info = {}
            self.symbol = symbol

    monkeypatch.setattr(sys.modules["yfinance"], "Ticker", EmptyTicker)
    fu._cache.clear()
    with pytest.raises(ValueError):
        fu.company_snapshot("NADA")
