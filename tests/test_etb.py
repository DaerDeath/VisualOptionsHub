"""Tests de la lista Easy-To-Borrow de Tradier, con httpx.MockTransport
(sin red real)."""

import asyncio

import httpx

from visual_options.stream import etb


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_is_easy_to_borrow_true_when_symbol_in_list():
    etb._cache.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"securities": {"security": [
            {"symbol": "AAPL"}, {"symbol": "QQQ"},
        ]}})

    client = make_client(handler)

    async def run():
        result = await etb.is_easy_to_borrow("aapl", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) is True


def test_is_easy_to_borrow_false_when_symbol_missing():
    etb._cache.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"securities": {"security": [{"symbol": "AAPL"}]}})

    client = make_client(handler)

    async def run():
        result = await etb.is_easy_to_borrow("GME", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) is False


def test_is_easy_to_borrow_handles_plain_string_securities():
    """Por si Tradier devuelve strings sueltos en vez de {"symbol": ...}."""
    etb._cache.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"securities": {"security": ["TSLA", "NVDA"]}})

    client = make_client(handler)

    async def run():
        result = await etb.is_easy_to_borrow("tsla", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) is True


def test_etb_list_is_cached_within_ttl():
    etb._cache.clear()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"securities": {"security": [{"symbol": "AAPL"}]}})

    client = make_client(handler)

    async def run():
        await etb.is_easy_to_borrow("AAPL", "token", "prod", client=client)
        await etb.is_easy_to_borrow("QQQ", "token", "prod", client=client)
        await client.aclose()

    asyncio.run(run())
    assert calls["n"] == 1


def test_is_easy_to_borrow_empty_list():
    etb._cache.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"securities": None})

    client = make_client(handler)

    async def run():
        result = await etb.is_easy_to_borrow("AAPL", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) is False
