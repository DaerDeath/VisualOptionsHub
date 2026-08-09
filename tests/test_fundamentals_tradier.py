"""Tests del perfil de empresa vía la API beta de fundamentals de
Tradier, con httpx.MockTransport (sin red real). La forma exacta del
JSON de la beta no está tan documentada como el resto de la API, así
que estos tests fijan la mejor forma conocida (results[].tables.*) y
verifican que la extracción defensiva la encuentra igual."""

import asyncio

import httpx

from visual_options.stream import fundamentals_tradier as ft


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_company_profile_extracts_from_typical_beta_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "request": "AAPL", "type": "Symbols",
            "results": [{
                "type": "Company",
                "tables": {
                    "company_profile": {
                        "long_business_summary": "Apple diseña, fabrica y vende...",
                        "total_employee_number": 164000,
                    },
                    "asset_classification": {
                        "sector": "Technology", "industry": "Consumer Electronics",
                    },
                },
            }],
        }])

    client = make_client(handler)

    async def run():
        result = await ft.company_profile("AAPL", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["sector"] == "Technology"
    assert result["industry"] == "Consumer Electronics"
    assert result["employees"] == 164000
    assert result["summary"].startswith("Apple diseña")


def test_company_profile_returns_empty_dict_when_plan_lacks_access():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = make_client(handler)

    async def run():
        result = await ft.company_profile("AAPL", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) == {}


def test_company_profile_returns_empty_dict_on_unexpected_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape", "no_useful_keys": True})

    client = make_client(handler)

    async def run():
        result = await ft.company_profile("AAPL", "token", "prod", client=client)
        await client.aclose()
        return result

    assert asyncio.run(run()) == {}


def test_deep_find_scans_nested_lists_and_dicts():
    payload = {"a": [{"b": {"sector": "Energy"}}, {"c": [{"industry": "Oil & Gas"}]}]}
    found = ft._deep_find(payload, ("sector", "industry"))
    assert found == {"sector": "Energy", "industry": "Oil & Gas"}


def test_company_profile_truncates_long_summary():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"results": [{"tables": {
            "company_profile": {"description": "x" * 1000},
        }}]}])

    client = make_client(handler)

    async def run():
        result = await ft.company_profile("QQQ", "token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result["summary"]) == 420
