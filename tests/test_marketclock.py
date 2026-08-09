"""Tests del estado del mercado: heurística local (sin token) y el
endpoint real de Tradier (con httpx.MockTransport, sin red)."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from visual_options.stream import marketclock as mc

NY = ZoneInfo("America/New_York")


def test_heuristic_open_on_weekday_during_session():
    now = datetime(2026, 8, 10, 11, 0, tzinfo=NY)  # lunes 11:00 NY
    result = mc._heuristic_clock(now)
    assert result["state"] == "open"
    assert result["source"] == "heuristic"


def test_heuristic_closed_before_open():
    now = datetime(2026, 8, 10, 6, 0, tzinfo=NY)  # lunes 06:00 NY
    assert mc._heuristic_clock(now)["state"] == "closed"


def test_heuristic_closed_on_weekend():
    now = datetime(2026, 8, 8, 11, 0, tzinfo=NY)  # sábado
    assert mc._heuristic_clock(now)["state"] == "closed"


def test_market_clock_without_token_uses_heuristic():
    now = datetime(2026, 8, 10, 11, 0, tzinfo=NY)

    async def run():
        return await mc.market_clock(None, now=now)

    result = asyncio.run(run())
    assert result["source"] == "heuristic"
    assert result["state"] == "open"


def test_market_clock_with_token_uses_tradier():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"clock": {
            "state": "open", "description": "Market is open",
            "next_change": "16:00", "next_state": "close",
        }})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run():
        result = await mc.market_clock("token", "prod", client=client)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == {
        "state": "open", "description": "Market is open",
        "next_change": "16:00", "next_state": "close", "source": "tradier",
    }


def test_market_clock_falls_back_to_heuristic_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    now = datetime(2026, 8, 10, 11, 0, tzinfo=NY)

    async def run():
        result = await mc.market_clock("token", "prod", client=client, now=now)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result["source"] == "heuristic"
    assert result["state"] == "open"


def test_market_clock_rejects_unknown_env():
    async def run():
        return await mc.market_clock("token", "staging")
    with pytest.raises(ValueError):
        asyncio.run(run())
