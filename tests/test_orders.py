"""Tests de órdenes de Tradier con httpx.MockTransport (sin red real)."""

import asyncio

import httpx
import pytest

from visual_options.stream import orders as ords


def profile_response() -> httpx.Response:
    return httpx.Response(200, json={"profile": {"account": {"account_number": "ACC1"}}})


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_tradier_orders_normalizes_multiple():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"orders": {"order": [
            {"id": 1, "symbol": "QQQ", "class": "option", "side": "sell_to_open",
             "quantity": 2, "type": "limit", "status": "open", "price": 1.5,
             "avg_fill_price": 0, "exec_quantity": 0, "duration": "day",
             "create_date": "2026-08-01T10:00:00Z", "option_symbol": "QQQ260904P700"},
            {"id": 2, "symbol": "AAPL", "class": "equity", "side": "buy",
             "quantity": 10, "type": "market", "status": "filled", "price": None,
             "avg_fill_price": 220.5, "exec_quantity": 10, "duration": "day",
             "create_date": "2026-07-28T09:30:00Z", "option_symbol": None},
        ]}})

    client = make_client(handler)

    async def run():
        result = await ords.tradier_orders("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["account"] == "ACC1"
    assert len(result["orders"]) == 2
    # ordenadas por fecha de creación, más reciente primero
    assert result["orders"][0]["symbol"] == "QQQ"
    assert result["orders"][0]["status"] == "open"
    assert result["orders"][1]["avg_fill_price"] == 220.5


def test_tradier_orders_single_order_not_a_list():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"orders": {"order": {
            "id": 1, "symbol": "SPY", "class": "equity", "side": "buy",
            "quantity": 1, "type": "market", "status": "filled",
            "create_date": "2026-08-01T10:00:00Z",
        }}})

    client = make_client(handler)

    async def run():
        result = await ords.tradier_orders("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result["orders"]) == 1
    assert result["orders"][0]["symbol"] == "SPY"


def test_tradier_orders_empty_account():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(200, json={"orders": None})

    client = make_client(handler)

    async def run():
        result = await ords.tradier_orders("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["orders"] == []


def test_tradier_orders_propagates_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/user/profile"):
            return profile_response()
        return httpx.Response(500)

    client = make_client(handler)

    async def run():
        try:
            await ords.tradier_orders("token", "prod", client=client)
        finally:
            await client.aclose()

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
