"""Tests del screener de verticales de crédito con tickers sintéticos
controlados (sin red, sin yfinance real) para verificar la regla del
libro: strike corto a ≥1σ y rendimiento (crédito/riesgo) ≥ mínimo."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from visual_options.pricing import bs_price, expected_move
from visual_options.stream import screener as sc

SPOT, IV, DAYS = 100.0, 0.30, 30


def _expiry_str(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def _frame(kind: str, strikes: list[float]) -> pd.DataFrame:
    rows = []
    for k in strikes:
        price = bs_price(kind, SPOT, k, DAYS, IV)
        rows.append({
            "strike": k, "bid": round(price - 0.01, 4), "ask": round(price + 0.01, 4),
            "lastPrice": round(price, 4), "impliedVolatility": IV,
            "volume": 100, "openInterest": 500,
        })
    return pd.DataFrame(rows)


class FakeTicker:
    def __init__(self, spot, expiries, put_strikes, call_strikes):
        self._spot = spot
        self.options = expiries
        self._put_strikes = put_strikes
        self._call_strikes = call_strikes

    @property
    def fast_info(self):
        return {"last_price": self._spot}

    def history(self, period="5d", interval="1d"):
        return pd.DataFrame({"Close": [self._spot]})

    def option_chain(self, expiry):
        return type("Chain", (), {
            "puts": _frame("put", self._put_strikes),
            "calls": _frame("call", self._call_strikes),
        })()


PUT_STRIKES = [85, 88, 89, 90, 91, 92, 93, 95, 97, 99, 100]
CALL_STRIKES = [100, 101, 103, 105, 107, 108, 109, 110, 111, 112, 115]


def make_ticker(days=DAYS, put_strikes=PUT_STRIKES, call_strikes=CALL_STRIKES):
    return FakeTicker(SPOT, (_expiry_str(days),), put_strikes, call_strikes)


def test_pick_expiry_prefers_within_range():
    ticker = FakeTicker(SPOT, (_expiry_str(10), _expiry_str(35), _expiry_str(60)), PUT_STRIKES, CALL_STRIKES)
    expiry, days = sc._pick_expiry(ticker, min_days=25, max_days=45)
    assert 25 <= days <= 45


def test_pick_expiry_falls_back_when_none_in_range():
    ticker = FakeTicker(SPOT, (_expiry_str(5), _expiry_str(10)), PUT_STRIKES, CALL_STRIKES)
    result = sc._pick_expiry(ticker, min_days=25, max_days=45)
    assert result is None  # ambos por debajo de min_days: se descartan, no hay fallback válido


def test_scan_symbol_finds_bull_put_meeting_book_rule():
    result = sc.scan_symbol("QQQ", ticker=make_ticker(), min_days=25, max_days=45,
                            min_return=0.12, min_sigma=1.0, sides=("put",))
    assert result["skip_reason"] is None
    assert len(result["candidates"]) == 1
    c = result["candidates"][0]
    assert c["side"] == "put"
    assert c["short_strike"] == 91.0
    assert c["long_strike"] == 90.0
    sigma_move = expected_move(SPOT, IV, DAYS)
    assert c["sigma_distance"] == pytest.approx(9.0 / sigma_move, abs=0.05)
    assert c["sigma_distance"] >= 1.0
    assert c["return_pct"] >= 0.12


def test_scan_symbol_finds_bear_call_meeting_book_rule():
    result = sc.scan_symbol("QQQ", ticker=make_ticker(), min_days=25, max_days=45,
                            min_return=0.12, min_sigma=1.0, sides=("call",))
    assert result["skip_reason"] is None
    c = result["candidates"][0]
    assert c["side"] == "call"
    assert c["short_strike"] == 109.0
    assert c["long_strike"] == 110.0
    assert c["sigma_distance"] >= 1.0
    assert c["return_pct"] >= 0.12


def test_scan_symbol_rejects_when_strikes_too_wide_for_min_return():
    wide_puts = [80, 85, 90, 95, 100]
    result = sc.scan_symbol("QQQ", ticker=make_ticker(put_strikes=wide_puts), min_days=25, max_days=45,
                            min_return=0.12, min_sigma=1.0, sides=("put",))
    assert result["candidates"] == []
    assert result["skip_reason"] is not None


def test_scan_symbol_no_spot_price():
    ticker = FakeTicker(None, (_expiry_str(DAYS),), PUT_STRIKES, CALL_STRIKES)
    result = sc.scan_symbol("GHOST", ticker=ticker)
    assert result["candidates"] == []
    assert "precio" in result["skip_reason"]


def test_scan_symbol_no_options_chain():
    ticker = FakeTicker(SPOT, (), PUT_STRIKES, CALL_STRIKES)
    result = sc.scan_symbol("NOOPT", ticker=ticker)
    assert result["candidates"] == []
    assert "cadena" in result["skip_reason"]


def test_scan_aggregates_and_sorts_by_return_desc():
    import asyncio

    def fake_scanner(symbol):
        if symbol == "LOW":
            return {"candidates": [{"symbol": "LOW", "return_pct": 0.13, "side": "put"}], "skip_reason": None}
        if symbol == "HIGH":
            return {"candidates": [{"symbol": "HIGH", "return_pct": 0.28, "side": "put"}], "skip_reason": None}
        return {"candidates": [], "skip_reason": "sin datos"}

    result = asyncio.run(sc.scan(("LOW", "HIGH", "SKIP"), scanner=fake_scanner))
    assert [c["symbol"] for c in result["candidates"]] == ["HIGH", "LOW"]
    assert result["skipped"] == [{"symbol": "SKIP", "reason": "sin datos"}]
    assert result["scanned"] == 3
