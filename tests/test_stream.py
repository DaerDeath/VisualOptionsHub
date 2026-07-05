"""Tests del dashboard multi-vista: estado, simulador, footprint y servidor."""

import json

import pytest
from fastapi.testclient import TestClient

from visual_options.stream.footprint import FootprintBuilder, tick_size_for
from visual_options.stream.server import create_app
from visual_options.stream.sim import SessionSimulator, base_price_for, strike_step_for
from visual_options.stream.state import MAX_SERIES_POINTS, DashboardState, SeriesPoint, StrikeRow


def test_state_aggregates_are_volume_weighted():
    state = DashboardState(symbol="QQQ", spot=100.0, strikes=[
        StrikeRow(strike=99.0, call_volume=100, call_sold_pct=80.0, put_volume=0),
        StrikeRow(strike=101.0, call_volume=300, call_sold_pct=40.0, put_volume=0),
    ])
    assert state.call_sell_pct == pytest.approx((100 * 80 + 300 * 40) / 400)
    assert state.put_sell_pct == 0.0


def test_snapshot_header_uses_series_scale():
    state = DashboardState(symbol="QQQ", spot=100.0, strikes=[
        StrikeRow(strike=100.0, call_volume=10, call_sold_pct=75.0),
    ])
    state.append_point(SeriesPoint(t="07:00:00", price=100.0, put_sell_pct=11.7, call_sell_pct=30.9))
    snap = state.snapshot()
    assert snap["put_sell_pct"] == pytest.approx(11.7)
    assert snap["call_sell_pct"] == pytest.approx(30.9)


def test_series_buffer_rolls():
    state = DashboardState(symbol="QQQ", spot=100.0)
    for i in range(MAX_SERIES_POINTS + 50):
        state.append_point(SeriesPoint(t=f"{i}", price=100.0, put_sell_pct=10.0, call_sell_pct=15.0))
    assert len(state.series) == MAX_SERIES_POINTS
    assert state.series[0].t == "50"


# ------------------------------------------------------------- simulador

def test_simulator_produces_coherent_session():
    sim = SessionSimulator(seed=7)
    assert len(sim.state.strikes) == 23
    assert len(sim.state.series) == 40
    volumes_before = [(r.call_volume, r.put_volume) for r in sim.state.strikes]
    sim.tick(seconds=60)
    for (cb, pb), row in zip(volumes_before, sim.state.strikes):
        assert row.call_volume >= cb and row.put_volume >= pb
    point = sim.state.series[-1]
    assert 3 <= point.put_sell_pct <= 45
    assert 5 <= point.call_sell_pct <= 45


def test_simulator_symbol_scaling():
    spx = SessionSimulator(symbol="SPX", seed=3)
    assert spx.state.spot == pytest.approx(base_price_for("SPX"), rel=0.05)
    strikes = [r.strike for r in spx.state.strikes]
    assert strikes[1] - strikes[0] == strike_step_for(spx.state.spot) == 10.0
    unknown = SessionSimulator(symbol="XXXX", seed=3)
    assert unknown.state.spot == pytest.approx(100.0, rel=0.05)


def test_simulator_feeds_footprint():
    sim = SessionSimulator(seed=11)
    assert len(sim.footprint.bars) > 3
    bar = sim.footprint.bars[-1]
    assert bar.volume > 0
    assert bar.low <= bar.close <= bar.high


# ------------------------------------------------------------- footprint

def test_tick_size_scales_with_price():
    assert tick_size_for(6300.0) == 2.5
    assert tick_size_for(720.0) == 0.5
    assert tick_size_for(150.0) == 0.25
    assert tick_size_for(40.0) == 0.1


def test_footprint_builder_aggregates_cells():
    fp = FootprintBuilder()
    fp.add_trades("09:30:15", [(100.10, 5, True), (100.12, 3, False), (100.35, 2, True)], bar_key="09:30")
    fp.add_trades("09:30:45", [(100.10, 4, False)], bar_key="09:30")
    assert len(fp.bars) == 1
    bar = fp.bars[0]
    assert bar.volume == 14
    assert bar.delta == (5 + 2) - (3 + 4)
    cell = bar.cells[100.0]  # 100.10/100.12 → nivel 100.0 con tick 0.25
    assert cell == [5, 7]
    assert bar.poc() == 100.0


def test_footprint_new_bar_on_new_key():
    fp = FootprintBuilder()
    fp.add_trades("09:30:00", [(50.0, 1, True)], bar_key="09:30")
    fp.add_trades("09:35:00", [(50.2, 2, False)], bar_key="09:35")
    assert [b.t for b in fp.bars] == ["09:30", "09:35"]
    snap = fp.snapshot()
    assert snap["bars"][-1]["delta"] == -2
    assert snap["tick"] == tick_size_for(50.2)


# --------------------------------------------------------------- servidor

def test_server_serves_spa_and_snapshot():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        for asset in ("shared.js", "home.js", "flow.js", "footprint.js", "app.js"):
            assert asset in index.text
            assert client.get(f"/static/{asset}").status_code == 200

        assert client.get("/api/config").json() == {"mode": "sim"}

        snap = client.get("/api/snapshot", params={"symbol": "spy"}).json()
        assert snap["flow"]["symbol"] == "SPY"
        assert len(snap["flow"]["strikes"]) == 23
        assert len(snap["footprint"]["bars"]) > 0
        assert {"price", "buy", "sell"} <= set(snap["footprint"]["bars"][-1]["cells"][0])


def test_server_websocket_per_symbol():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        with client.websocket_connect("/ws?symbol=nvda") as ws:
            payload = json.loads(ws.receive_text())
            assert payload["flow"]["symbol"] == "NVDA"
            assert "footprint" in payload


def test_server_rejects_unknown_mode():
    with pytest.raises(ValueError):
        create_app(mode="nope")
