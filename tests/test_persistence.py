"""Tests de la grabadora de sesiones y los endpoints de replay."""

import json

import pytest
from fastapi.testclient import TestClient

from visual_options.stream.persistence import Recorder
from visual_options.stream.server import create_app


def payload(spot: float) -> str:
    return json.dumps({"flow": {"spot": spot}, "footprint": {"bars": []}})


def test_record_and_get_roundtrip(tmp_path):
    rec = Recorder(tmp_path / "s.db")
    assert rec.record("sim:QQQ:0", payload(100.0)) is True
    days = rec.days("QQQ")
    assert len(days) == 1 and days[0]["source"] == "sim" and days[0]["count"] == 1
    snap = rec.get("QQQ", days[0]["day"], "sim", 0, 0)
    assert snap["total"] == 1 and snap["payload"]["flow"]["spot"] == 100.0
    rec.close()


def test_record_throttles_within_interval(tmp_path):
    rec = Recorder(tmp_path / "s.db")
    assert rec.record("sim:QQQ:0", payload(1)) is True
    assert rec.record("sim:QQQ:0", payload(2)) is False   # < RECORD_INTERVAL
    assert rec.record("sim:SPY:0", payload(3)) is True    # otra sesión, sin throttle
    assert rec.days("QQQ")[0]["count"] == 1
    rec.close()


def test_get_clamps_index_and_missing_returns_none(tmp_path):
    rec = Recorder(tmp_path / "s.db")
    rec.record("sim:QQQ:0", payload(1))
    rec._last_write.clear()  # saltar throttle para un segundo snapshot
    rec.record("sim:QQQ:0", payload(2))
    day = rec.days("QQQ")[0]["day"]
    snap = rec.get("QQQ", day, "sim", 0, 999)
    assert snap["index"] == 1 and snap["payload"]["flow"]["spot"] == 2
    assert rec.get("QQQ", "1999-01-01", "sim", 0, 0) is None
    rec.close()


def test_replay_endpoints_after_ws_connect(tmp_path):
    app = create_app(mode="sim", seed=1, db_path=str(tmp_path / "s.db"))
    with TestClient(app) as client:
        with client.websocket_connect("/ws?symbol=QQQ") as ws:
            ws.receive_text()  # el snapshot inicial también se graba
        days = client.get("/api/replay/days", params={"symbol": "QQQ"}).json()
        assert len(days) == 1 and days[0]["count"] >= 1
        snap = client.get("/api/replay", params={
            "symbol": "QQQ", "day": days[0]["day"], "source": "sim",
            "expiry": 0, "i": 0}).json()
        assert snap["payload"]["flow"]["symbol"] == "QQQ"
        assert client.get("/api/replay", params={
            "symbol": "QQQ", "day": "1999-01-01", "source": "sim"}).status_code == 404
