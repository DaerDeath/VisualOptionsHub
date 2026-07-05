"""Tests del feed de Tradier con la API simulada (httpx MockTransport)."""

import asyncio

import httpx
import pytest

from visual_options.stream.tradier_feed import TradierFeed


def make_feed(handler) -> TradierFeed:
    return TradierFeed("QQQ", token="test-token", env="sandbox",
                       transport=httpx.MockTransport(handler))


def option(symbol, strike, opt_type, volume, oi, bid, ask, last, mid_iv=0.20):
    return {
        "symbol": symbol, "strike": strike, "option_type": opt_type,
        "volume": volume, "open_interest": oi, "bid": bid, "ask": ask, "last": last,
        "greeks": {"gamma": 0.01, "mid_iv": mid_iv},
    }


CHAIN_CALLS = {"count": 0}


def api_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/markets/quotes"):
        return httpx.Response(200, json={"quotes": {"quote": {
            "symbol": "QQQ", "last": 720.0, "prevclose": 718.0}}})
    if path.endswith("/markets/options/expirations"):
        return httpx.Response(200, json={"expirations": {"date": ["2026-07-06", "2026-07-07"]}})
    if path.endswith("/markets/options/chains"):
        # cada refresh añade volumen para poder clasificar los incrementos
        CHAIN_CALLS["count"] += 1
        extra = (CHAIN_CALLS["count"] - 1) * 400
        return httpx.Response(200, json={"options": {"option": [
            option("QQQ260706C720", 720.0, "call", 1000 + extra, 5000, 2.0, 2.2, 2.05),
            option("QQQ260706P720", 720.0, "put", 800 + extra, 4000, 1.8, 2.0, 1.99),
            option("QQQ260706C721", 721.0, "call", 500 + extra, 2000, 1.5, 1.7, 1.68),
        ]}})
    if path.endswith("/markets/timesales"):
        return httpx.Response(200, json={"series": {"data": [
            {"time": "2026-07-06T09:30:00", "open": 719.5, "high": 720.1,
             "low": 719.3, "close": 720.0, "volume": 90000},
            {"time": "2026-07-06T09:31:00", "open": 720.0, "high": 720.4,
             "low": 719.9, "close": 719.9, "volume": 60000},
        ]}})
    return httpx.Response(404)


def test_requires_token(monkeypatch):
    monkeypatch.delenv("TRADIER_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        TradierFeed("QQQ", token=None)


def test_rejects_unknown_env():
    with pytest.raises(ValueError):
        TradierFeed("QQQ", token="x", env="staging")


def test_initialize_and_refresh_chain():
    CHAIN_CALLS["count"] = 0
    feed = make_feed(api_handler)

    async def scenario():
        await feed._initialize()
        assert feed.state.spot == 720.0
        assert feed._expiration == "2026-07-06"
        await feed._refresh_chain()   # línea base: sin clasificar
        await feed._refresh_chain()   # incrementos de volumen → clasificación
        await feed.close()

    asyncio.run(scenario())

    strikes = {r.strike: r for r in feed.state.strikes}
    assert 720.0 in strikes and 721.0 in strikes
    row = strikes[720.0]
    assert row.call_volume == 1400
    assert row.put_volume == 1200
    # incremento: call last 2.05 <= mid 2.1 → vendido
    assert row.call_sold_pct == 100.0
    # put last 1.99 > mid 1.9 → comprado
    assert row.put_sold_pct == 0.0
    # y el bloque de 400 contratos aparece en el tape
    assert len(feed.state.tape) >= 2
    assert len(feed.state.series) == 2

    # exposiciones dealer calculadas desde OI + mid_iv
    assert row.call_oi == 5000 and row.put_oi == 4000
    assert row.iv == pytest.approx(0.20)
    assert row.call_gex > 0 and row.put_gex < 0
    assert row.net_gex == pytest.approx(row.call_gex + row.put_gex)
    assert row.gamma_exposure == pytest.approx(row.net_gex)
    assert feed.state.expiry_days > 0


def test_refresh_footprint_builds_bars():
    feed = make_feed(api_handler)

    async def scenario():
        await feed._refresh_footprint()
        await feed.close()

    asyncio.run(scenario())
    assert len(feed.footprint.bars) == 2
    first, second = feed.footprint.bars
    assert first.t == "09:30" and second.t == "09:31"
    assert first.volume == 90000
    # segunda barra: cierre 719.9 < cierre previo 720.0 → downtick (delta negativo)
    assert second.delta < 0


def test_footprint_skips_already_seen_bars():
    feed = make_feed(api_handler)

    async def scenario():
        await feed._refresh_footprint()
        await feed._refresh_footprint()  # segunda pasada: mismos datos
        await feed.close()

    asyncio.run(scenario())
    assert len(feed.footprint.bars) == 2
    assert feed.footprint.bars[0].volume == 90000  # sin duplicar
