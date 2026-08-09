"""Tests de watchlists de Tradier con httpx.MockTransport (sin red real),
cubriendo el caso típico de la API (XML→JSON): un único elemento llega
como objeto suelto en vez de lista."""

import asyncio

import httpx
import pytest

from visual_options.stream import watchlists as wl


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_list_watchlists_normalizes_multiple():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"watchlists": {"watchlist": [
            {"id": "1", "name": "Core", "items": {"item": [
                {"symbol": "QQQ"}, {"symbol": "SPY"}]}},
            {"id": "2", "name": "Earnings", "items": {"item": [
                {"symbol": "AAPL"}]}},
        ]}})

    client = make_client(handler)

    async def run():
        result = await wl.list_watchlists("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result) == 2
    assert result[0] == {"id": "1", "name": "Core", "symbols": ["QQQ", "SPY"]}
    assert result[1] == {"id": "2", "name": "Earnings", "symbols": ["AAPL"]}


def test_list_watchlists_normalizes_single_watchlist_single_symbol():
    """El caso trampa de Tradier: con un solo elemento, llega como dict, no lista."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"watchlists": {"watchlist": {
            "id": "1", "name": "Solo", "items": {"item": {"symbol": "TSLA"}},
        }}})

    client = make_client(handler)

    async def run():
        result = await wl.list_watchlists("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == [{"id": "1", "name": "Solo", "symbols": ["TSLA"]}]


def test_list_watchlists_empty_account():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"watchlists": None})

    client = make_client(handler)

    async def run():
        result = await wl.list_watchlists("token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) == []


def test_list_watchlists_rejects_unknown_env():
    async def run():
        return await wl.list_watchlists("token", "staging")
    with pytest.raises(ValueError):
        asyncio.run(run())


def test_list_watchlists_propagates_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"fault": "no autorizado"})

    client = make_client(handler)

    async def run():
        try:
            await wl.list_watchlists("bad-token", "prod", client=client)
        finally:
            await client.aclose()

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
