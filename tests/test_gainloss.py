"""Tests de P&L realizado (gainloss) de Tradier con httpx.MockTransport."""

import asyncio

import httpx
import pytest

from visual_options.stream import gainloss as gl


def profile_response() -> httpx.Response:
    return httpx.Response(200, json={"profile": {"account": {"account_number": "ACC1"}}})


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_tradier_gainloss_normalizes_and_summarizes():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"gainloss": {"closed_position": [
            {"symbol": "QQQ", "close_date": "2026-08-01", "open_date": "2026-07-01",
             "quantity": 1, "cost": 100.0, "proceeds": 150.0, "gain_loss": 50.0,
             "gain_loss_percent": 50.0, "term": 31},
            {"symbol": "SPY", "close_date": "2026-07-15", "open_date": "2026-06-15",
             "quantity": 1, "cost": 200.0, "proceeds": 180.0, "gain_loss": -20.0,
             "gain_loss_percent": -10.0, "term": 30},
        ]}})

    client = make_client(handler)

    async def run():
        result = await gl.tradier_gainloss("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["account"] == "ACC1"
    # más reciente primero
    assert [c["symbol"] for c in result["closed"]] == ["QQQ", "SPY"]
    summary = result["summary"]
    assert summary["n_trades"] == 2
    assert summary["wins"] == 1 and summary["losses"] == 1
    assert summary["win_rate"] == 50.0
    assert summary["total_pnl"] == pytest.approx(30.0)
    assert summary["avg_win"] == pytest.approx(50.0)
    assert summary["avg_loss"] == pytest.approx(-20.0)


def test_tradier_gainloss_single_closed_position_not_a_list():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"gainloss": {"closed_position": {
            "symbol": "TSLA", "close_date": "2026-08-01", "open_date": "2026-07-01",
            "quantity": 1, "cost": 100.0, "proceeds": 90.0, "gain_loss": -10.0,
            "gain_loss_percent": -10.0, "term": 30,
        }}})

    client = make_client(handler)

    async def run():
        result = await gl.tradier_gainloss("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result["closed"]) == 1
    assert result["summary"]["losses"] == 1


def test_tradier_gainloss_empty_history():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"gainloss": None})

    client = make_client(handler)

    async def run():
        result = await gl.tradier_gainloss("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["closed"] == []
    assert result["summary"] == {"n_trades": 0, "wins": 0, "losses": 0, "win_rate": None,
                                 "total_pnl": 0.0, "avg_win": None, "avg_loss": None}


def test_tradier_gainloss_propagates_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(401)

    client = make_client(handler)

    async def run():
        try:
            await gl.tradier_gainloss("token", "prod", client=client)
        finally:
            await client.aclose()

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
