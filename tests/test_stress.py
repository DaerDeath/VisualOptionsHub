"""Tests del stress test del portafolio, con book y spot_fetcher inyectados
(sin red, sin broker real) para verificar la matemática de la matriz."""

import asyncio

import pytest

from visual_options.pricing import bs_price, implied_volatility
from visual_options.stream import stress as st


def make_book(positions):
    totals = {"market_value": sum(p.get("market_value", 0) for p in positions),
             "unrealized_pnl": sum(p.get("unrealized_pnl", 0) for p in positions)}
    return {"account": "TEST123", "positions": positions, "totals": totals}


async def fetcher(values):
    async def _f(symbol):
        return values.get(symbol)
    return _f


def test_days_to_expiry_parses_both_formats():
    from datetime import datetime, timedelta
    d = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
    assert 9 <= st._days_to_expiry(d) <= 11
    d2 = (datetime.now() + timedelta(days=10)).strftime("%Y%m%d")
    assert 9 <= st._days_to_expiry(d2) <= 11
    assert st._days_to_expiry(None) is None
    assert st._days_to_expiry("no-una-fecha") is None


def test_stock_position_pnl_is_linear():
    price = 100.0
    fair_call = bs_price("call", price, 100.0, 30, 0.25)
    positions = [
        {"symbol": "AAPL", "kind": "stock", "qty": 100, "avg_cost": 90.0,
         "price": price, "market_value": 10000.0, "unrealized_pnl": 1000.0,
         "delta": None, "gamma": None, "theta": None, "vega": None},
    ]
    book = make_book(positions)

    async def run():
        return await st.stress_test("ibkr", book=book, spot_fetcher=await fetcher({"AAPL": price}))

    result = asyncio.run(run())
    # fila iv_shock=0, columna spot_shock=+0.05 → P&L = qty * spot * 0.05
    zero_iv_row = next(r for r in result["matrix"] if r["iv_shock"] == 0.0)
    idx_5pct = result["spot_shocks"].index(0.05)
    assert zero_iv_row["pnl"][idx_5pct] == pytest.approx(100 * price * 0.05)
    idx_0pct = result["spot_shocks"].index(0.0)
    assert zero_iv_row["pnl"][idx_0pct] == pytest.approx(0.0)
    assert result["modeled_linear"] == 1
    assert result["modeled_bsm"] == 0


def test_option_position_uses_bsm_with_implied_vol():
    spot = 100.0
    strike, days, true_iv = 105.0, 30, 0.22
    market_price = bs_price("call", spot, strike, days, true_iv)
    positions = [
        {"symbol": "QQQ", "kind": "call", "strike": strike, "expiry":
         __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
         "qty": 2, "avg_cost": market_price * 200, "price": market_price,
         "market_value": market_price * 200, "unrealized_pnl": 0.0,
         "delta": None, "gamma": None, "theta": None, "vega": None},
    ]
    # ajusta expiry a +días reales para que _days_to_expiry calce ~30
    from datetime import datetime, timedelta
    positions[0]["expiry"] = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    book = make_book(positions)

    async def run():
        return await st.stress_test("ibkr", book=book, spot_fetcher=await fetcher({"QQQ": spot}))

    result = asyncio.run(run())
    assert result["modeled_bsm"] == 1
    zero_row = next(r for r in result["matrix"] if r["iv_shock"] == 0.0)
    idx_0 = result["spot_shocks"].index(0.0)
    # en el escenario 0/0 el P&L debe ser ~0 (mismo precio que el de mercado)
    assert zero_row["pnl"][idx_0] == pytest.approx(0.0, abs=0.5)
    # subir el spot debe dar P&L positivo para una call larga
    idx_up = result["spot_shocks"].index(0.10)
    assert zero_row["pnl"][idx_up] > 0
    # subir la IV con spot plano también debe ser positivo (vega larga)
    up_iv_row = next(r for r in result["matrix"] if r["iv_shock"] == 0.30)
    assert up_iv_row["pnl"][idx_0] > 0


def test_delta_only_fallback_when_price_missing():
    positions = [
        {"symbol": "SPY", "kind": "put", "strike": 400.0, "expiry": "2099-01-01",
         "qty": -1, "avg_cost": 500.0, "price": None,
         "market_value": 0.0, "unrealized_pnl": 0.0,
         "delta": -0.30, "gamma": None, "theta": None, "vega": None},
    ]
    book = make_book(positions)

    async def run():
        return await st.stress_test("ibkr", book=book, spot_fetcher=await fetcher({"SPY": 400.0}))

    result = asyncio.run(run())
    assert result["modeled_linear"] == 1  # delta_only cuenta como "linear" en el resumen
    assert result["modeled_bsm"] == 0
    zero_row = next(r for r in result["matrix"] if r["iv_shock"] == 0.0)
    idx_5 = result["spot_shocks"].index(0.05)
    expected = -0.30 * 400.0 * 0.05
    assert zero_row["pnl"][idx_5] == pytest.approx(expected)


def test_missing_spot_contributes_zero_without_crashing():
    positions = [
        {"symbol": "GHOST", "kind": "stock", "qty": 10, "avg_cost": 1.0,
         "price": 1.0, "market_value": 10.0, "unrealized_pnl": 0.0,
         "delta": None, "gamma": None, "theta": None, "vega": None},
    ]
    book = make_book(positions)

    async def run():
        return await st.stress_test("ibkr", book=book, spot_fetcher=await fetcher({}))

    result = asyncio.run(run())
    assert result["unmodeled"] == 1
    assert all(v == 0.0 for row in result["matrix"] for v in row["pnl"])


def test_empty_portfolio_returns_zero_matrix():
    book = make_book([])

    async def run():
        return await st.stress_test("ibkr", book=book, spot_fetcher=await fetcher({}))

    result = asyncio.run(run())
    assert result["n_positions"] == 0
    assert all(v == 0.0 for row in result["matrix"] for v in row["pnl"])


def test_stress_test_rejects_unknown_source():
    async def run():
        return await st.stress_test("yahoo")
    with pytest.raises(ValueError):
        asyncio.run(run())


def test_stress_test_requires_tradier_token():
    async def run():
        return await st.stress_test("tradier", tradier_token=None)
    with pytest.raises(ValueError):
        asyncio.run(run())
