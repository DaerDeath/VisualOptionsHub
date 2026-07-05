"""Tests del dashboard de flujo: estado, simulador y servidor."""

import json

import pytest
from fastapi.testclient import TestClient

from visual_options.stream.server import create_app
from visual_options.stream.sim import SessionSimulator
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


def test_simulator_produces_coherent_session():
    sim = SessionSimulator(seed=7)
    assert len(sim.state.strikes) == 23
    assert len(sim.state.series) == 40  # historia de arranque
    volumes_before = [(r.call_volume, r.put_volume) for r in sim.state.strikes]
    sim.tick(seconds=60)
    for (cb, pb), row in zip(volumes_before, sim.state.strikes):
        assert row.call_volume >= cb and row.put_volume >= pb  # el volumen solo crece
    for row in sim.state.strikes:
        assert 10 <= row.call_sold_pct <= 95
        assert 5 <= row.put_sold_pct <= 90
    point = sim.state.series[-1]
    assert 3 <= point.put_sell_pct <= 45
    assert 5 <= point.call_sell_pct <= 45


def test_simulator_is_reproducible_with_seed():
    a, b = SessionSimulator(seed=42), SessionSimulator(seed=42)
    assert a.state.snapshot()["strikes"] == b.state.snapshot()["strikes"]


def test_server_serves_frontend_and_snapshot():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "profileCanvas" in index.text

        snap = client.get("/api/snapshot").json()
        assert snap["symbol"] == "QQQ"
        assert snap["source"] == "sim"
        assert len(snap["strikes"]) == 23
        assert {"strike", "call_volume", "call_sold_pct", "put_volume",
                "put_sold_pct", "gamma_exposure", "magnet"} <= set(snap["strikes"][0])

        assert client.get("/static/app.js").status_code == 200
        assert client.get("/static/style.css").status_code == 200


def test_server_websocket_sends_initial_snapshot():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            payload = json.loads(ws.receive_text())
            assert payload["symbol"] == "QQQ"
            assert len(payload["series"]) >= 1


def test_server_rejects_unknown_mode():
    with pytest.raises(ValueError):
        create_app(mode="nope")
