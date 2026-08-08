"""Tests del portafolio real (solo lectura). ibkr_portfolio necesita TWS
en vivo y está marcado pragma: no cover, igual que ibkr_feed.py."""

import httpx
import pytest
from fastapi.testclient import TestClient

from visual_options.stream import portfolio as pf
from visual_options.stream.server import create_app


def test_empty_totals_and_accumulate():
    totals = pf.empty_totals()
    assert totals == {"market_value": 0.0, "unrealized_pnl": 0.0,
                      "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    pf._accumulate(totals, {"market_value": 100.0, "unrealized_pnl": -5.0, "delta": 2.0})
    pf._accumulate(totals, {"market_value": 50.0, "unrealized_pnl": 3.0, "gamma": 0.1})
    assert totals["market_value"] == 150.0
    assert totals["unrealized_pnl"] == -2.0
    assert totals["delta"] == 2.0
    assert totals["theta"] == 0.0  # ausente en ambas → se queda en 0


def test_shape_tradier_position_stock():
    item = {"symbol": "AAPL", "quantity": 10, "cost_basis": 2000.0}
    quote = {"last": 210.0}
    pos = pf._shape_tradier_position(item, quote)
    assert pos["kind"] == "stock"
    assert pos["symbol"] == "AAPL"
    assert pos["market_value"] == pytest.approx(2100.0)
    assert pos["unrealized_pnl"] == pytest.approx(100.0)
    assert pos["delta"] is None  # sin greeks para acciones


def test_shape_tradier_position_option_with_greeks():
    item = {"symbol": "AAPL260117C00220000", "quantity": 2, "cost_basis": 900.0}
    quote = {
        "last": 5.5, "option_type": "call", "strike": 220.0,
        "expiration_date": "2026-01-17", "underlying": "AAPL",
        "greeks": {"delta": 0.42, "gamma": 0.015, "theta": -0.08, "vega": 0.12},
    }
    pos = pf._shape_tradier_position(item, quote)
    assert pos["kind"] == "call"
    assert pos["symbol"] == "AAPL"
    assert pos["strike"] == 220.0
    assert pos["market_value"] == pytest.approx(5.5 * 2 * 100)
    assert pos["unrealized_pnl"] == pytest.approx(5.5 * 2 * 100 - 900.0)
    assert pos["delta"] == pytest.approx(0.42 * 2 * 100, abs=0.01)
    assert pos["gamma"] == pytest.approx(0.015 * 2 * 100, abs=0.001)
    assert pos["theta"] == pytest.approx(-0.08 * 2, abs=0.001)


def test_shape_tradier_position_zero_qty_no_division_error():
    item = {"symbol": "AAPL", "quantity": 0, "cost_basis": 0.0}
    pos = pf._shape_tradier_position(item, {"last": 100.0})
    assert pos["avg_cost"] == 0.0
    assert pos["unrealized_pnl_pct"] is None


def tradier_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/user/profile"):
        return httpx.Response(200, json={"profile": {"account": {"account_number": "VA123"}}})
    if path.endswith("/accounts/VA123/balances"):
        return httpx.Response(200, json={"balances": {
            "total_equity": 50000.0, "total_cash": 20000.0,
            "margin": {"stock_buying_power": 40000.0}}})
    if path.endswith("/accounts/VA123/positions"):
        return httpx.Response(200, json={"positions": {"position": [
            {"symbol": "AAPL", "quantity": 10, "cost_basis": 2000.0},
            {"symbol": "QQQ260117C00700000", "quantity": 1, "cost_basis": 450.0},
        ]}})
    if path.endswith("/markets/quotes"):
        return httpx.Response(200, json={"quotes": {"quote": [
            {"symbol": "AAPL", "last": 215.0},
            {"symbol": "QQQ260117C00700000", "last": 5.0, "option_type": "call",
             "strike": 700.0, "expiration_date": "2026-01-17", "underlying": "QQQ",
             "greeks": {"delta": 0.5, "gamma": 0.01, "theta": -0.05, "vega": 0.2}},
        ]}})
    return httpx.Response(404)


def test_tradier_portfolio_full_shape():
    client = httpx.AsyncClient(transport=httpx.MockTransport(tradier_handler), base_url="")
    import asyncio
    result = asyncio.run(pf.tradier_portfolio("tok", "prod", client=client))
    assert result["source"] == "tradier"
    assert result["account"] == "VA123"
    assert result["net_liquidation"] == 50000.0
    assert result["buying_power"] == 40000.0
    assert len(result["positions"]) == 2
    stock, option = result["positions"]
    assert stock["symbol"] == "AAPL" and stock["kind"] == "stock"
    assert option["symbol"] == "QQQ" and option["kind"] == "call"
    assert result["totals"]["market_value"] == pytest.approx(2150.0 + 500.0)


def test_tradier_portfolio_no_account_raises():
    def handler(request):
        if request.url.path.endswith("/user/profile"):
            return httpx.Response(200, json={"profile": {}})
        return httpx.Response(404)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="")
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(pf.tradier_portfolio("tok", "prod", client=client))


def test_portfolio_endpoint_rejects_unknown_source():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        response = client.get("/api/portfolio", params={"source": "yahoo"})
        assert response.status_code == 400


def test_portfolio_endpoint_requires_ibkr_installed_or_token():
    app = create_app(mode="sim", seed=1)  # sin token de Tradier
    with TestClient(app) as client:
        response = client.get("/api/portfolio", params={"source": "tradier"})
        assert response.status_code == 400
        assert "TRADIER_TOKEN" in response.json()["detail"]
