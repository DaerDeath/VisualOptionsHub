"""Tests de búsqueda de símbolos vía Tradier (lookup + search combinados),
con httpx.MockTransport (sin red real)."""

import asyncio

import httpx

from visual_options.stream import symbolsearch as ss


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_search_symbols_merges_lookup_and_search_deduped():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/markets/lookup"):
            return httpx.Response(200, json={"securities": {"security": [
                {"symbol": "AAPL", "description": "Apple Inc"},
            ]}})
        if request.url.path.endswith("/markets/search"):
            return httpx.Response(200, json={"securities": {"security": [
                {"symbol": "AAPL", "description": "Apple Inc"},   # duplicado, se descarta
                {"symbol": "AAPD", "description": "Direxion Daily AAPL Bear 1X"},
            ]}})
        return httpx.Response(404)

    client = make_client(handler)

    async def run():
        result = await ss.search_symbols("AAPL", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    symbols = {r["symbol"] for r in result}
    assert symbols == {"AAPL", "AAPD"}
    assert len(result) == 2


def test_search_symbols_single_result_not_a_list():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/markets/lookup"):
            return httpx.Response(200, json={"securities": {"security": {
                "symbol": "TSLA", "description": "Tesla Inc"}}})
        return httpx.Response(200, json={"securities": None})

    client = make_client(handler)

    async def run():
        result = await ss.search_symbols("TSLA", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == [{"symbol": "TSLA", "name": "Tesla Inc"}]


def test_search_symbols_empty_query_returns_empty_without_request():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"securities": None})

    client = make_client(handler)

    async def run():
        result = await ss.search_symbols("   ", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == []
    assert calls["n"] == 0


def test_search_symbols_survives_one_endpoint_failing():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/markets/lookup"):
            return httpx.Response(500)
        return httpx.Response(200, json={"securities": {"security": [
            {"symbol": "QQQ", "description": "Invesco QQQ Trust"},
        ]}})

    client = make_client(handler)

    async def run():
        result = await ss.search_symbols("QQQ", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == [{"symbol": "QQQ", "name": "Invesco QQQ Trust"}]


def test_search_symbols_limits_results():
    def handler(request: httpx.Request) -> httpx.Response:
        securities = [{"symbol": f"SYM{i}", "description": f"Company {i}"} for i in range(20)]
        return httpx.Response(200, json={"securities": {"security": securities}})

    client = make_client(handler)

    async def run():
        result = await ss.search_symbols("SYM", "token", "prod", client=client, limit=5)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result) == 5
