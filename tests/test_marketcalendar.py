"""Tests del calendario mensual de Tradier (feriados y medios días),
con httpx.MockTransport (sin red real)."""

import asyncio
from datetime import datetime

import httpx
import pytest

from visual_options.stream import marketcalendar as mcal


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_market_calendar_flags_half_days_and_holidays():
    mcal._cache.clear()
    today = datetime.now().strftime("%Y-%m-%d")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"calendar": {"days": {"day": [
            {"date": "2026-11-26", "status": "open", "description": "Market is Open",
             "open": {"start": "09:30", "end": "16:00"}},
            {"date": "2026-11-27", "status": "closed", "description": "Thanksgiving"},
            {"date": "2026-11-28", "status": "open", "description": "Market is Open (Early Close)",
             "open": {"start": "09:30", "end": "13:00"}},
        ]}}})

    client = make_client(handler)

    async def run():
        result = await mcal.market_calendar("token", "prod", month=11, year=2026, client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result["days"]) == 3
    assert [d["date"] for d in result["half_days"]] == ["2026-11-28"]
    assert [d["date"] for d in result["holidays"]] == ["2026-11-27"]
    normal_day = next(d for d in result["days"] if d["date"] == "2026-11-26")
    assert normal_day["half_day"] is False


def test_market_calendar_caches_within_ttl():
    mcal._cache.clear()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"calendar": {"days": {"day": [
            {"date": "2026-11-26", "status": "open", "description": "Market is Open",
             "open": {"start": "09:30", "end": "16:00"}},
        ]}}})

    client = make_client(handler)

    async def run():
        await mcal.market_calendar("token", "prod", month=11, year=2026, client=client)
        await mcal.market_calendar("token", "prod", month=11, year=2026, client=client)
        await client.aclose()

    asyncio.run(run())
    assert calls["n"] == 1  # la segunda llamada usó la caché, no pidió de nuevo


def test_market_calendar_single_day_not_a_list():
    mcal._cache.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"calendar": {"days": {"day": {
            "date": "2026-12-25", "status": "closed", "description": "Christmas"}}}})

    client = make_client(handler)

    async def run():
        result = await mcal.market_calendar("token", "prod", month=12, year=2026, client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert len(result["days"]) == 1
    assert result["holidays"][0]["date"] == "2026-12-25"


def test_today_entry_finds_todays_date():
    mcal._cache.clear()
    today = datetime.now().strftime("%Y-%m-%d")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"calendar": {"days": {"day": [
            {"date": today, "status": "open", "description": "Market is Open",
             "open": {"start": "09:30", "end": "13:00"}},
        ]}}})

    client = make_client(handler)

    async def run():
        entry = await mcal.today_entry("token", "prod", client=client)
        await client.aclose()
        return entry

    entry = asyncio.run(run())
    assert entry["half_day"] is True


def test_market_calendar_rejects_unknown_env():
    async def run():
        return await mcal.market_calendar("token", "staging")
    with pytest.raises(ValueError):
        asyncio.run(run())
