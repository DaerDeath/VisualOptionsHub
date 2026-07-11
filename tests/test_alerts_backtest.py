"""Tests del motor de alertas server-side y del backtest de rangos."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from visual_options.stream import backtest as bt
from visual_options.stream.alerts_engine import AlertEngine
from visual_options.stream.server import create_app
from visual_options.stream.state import DashboardState, SeriesPoint


def make_state(symbol="QQQ", spot=100.0, call_sell=15.0, put_sell=12.0, flip=None):
    state = DashboardState(symbol=symbol, spot=spot, gamma_flip=flip)
    state.append_point(SeriesPoint(t="10:00:00", price=spot,
                                   put_sell_pct=put_sell, call_sell_pct=call_sell))
    return state


def engine(tmp_path) -> AlertEngine:
    e = AlertEngine(tmp_path / "a.db")
    e.notify_cmd = None  # sin notify-send en tests
    return e


def test_price_cross_fires_once(tmp_path):
    eng = engine(tmp_path)
    eng.create("QQQ", "price_above", 105.0)
    eng.check_state(make_state(spot=100.0))   # fija el previo
    eng.check_state(make_state(spot=104.0))   # no cruza
    assert len(eng.log()) == 0
    eng.check_state(make_state(spot=106.0))   # cruza ↑
    log = eng.log()
    assert len(log) == 1 and "105" in log[0]["text"]
    assert eng.active() == []                  # done
    eng.check_state(make_state(spot=110.0))   # no re-dispara
    assert len(eng.log()) == 1
    eng.close()


def test_flow_threshold_and_gamma_flip(tmp_path):
    eng = engine(tmp_path)
    eng.create("QQQ", "call_sell_below", 10.0)
    eng.create("QQQ", "gamma_flip", None)
    eng.check_state(make_state(spot=100.0, call_sell=12.0, flip=99.0))
    assert len(eng.log()) == 0
    # call sell cae bajo el umbral Y el precio cruza el flip a la vez
    eng.check_state(make_state(spot=98.0, call_sell=9.0, flip=99.0))
    texts = [entry["text"] for entry in eng.log()]
    assert any("squeeze" in t for t in texts)
    assert any("gamma flip" in t for t in texts)
    eng.close()


def test_alert_validation(tmp_path):
    eng = engine(tmp_path)
    with pytest.raises(ValueError):
        eng.create("QQQ", "tipo_raro", 1.0)
    with pytest.raises(ValueError):
        eng.create("QQQ", "price_above", None)
    eng.close()


def test_alerts_endpoints(tmp_path):
    app = create_app(mode="sim", seed=1, db_path=str(tmp_path / "s.db"))
    with TestClient(app) as client:
        created = client.post("/api/alerts", json={
            "symbol": "qqq", "type": "price_above", "value": 999}).json()
        assert created["symbol"] == "QQQ"
        listed = client.get("/api/alerts").json()
        assert len(listed["active"]) == 1
        client.delete(f"/api/alerts/{created['id']}")
        assert client.get("/api/alerts").json()["active"] == []
        assert client.post("/api/alerts", json={"type": "nope"}).status_code == 400


# ----------------------------------------------------------------- backtest

def synthetic_closes(n=600, sigma=0.01, seed=3):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, sigma, n)))


def test_backtest_shapes_and_stats():
    closes = synthetic_closes()
    result = bt.run_backtest("QQQ", otm_pct=3.0, dte=5, years=2, closes=closes)
    assert result["n"] >= 100
    assert 0 <= result["win_rate"] <= 100
    assert len(result["curve"]) == result["n"]
    assert result["max_drawdown"] >= 0
    # con sigma diaria 1%, ±3% a 5 días gana la mayoría de las veces
    assert result["win_rate"] > 60


def test_backtest_narrow_range_loses_more():
    closes = synthetic_closes()
    wide = bt.run_backtest("QQQ", otm_pct=5.0, dte=5, closes=closes)
    narrow = bt.run_backtest("QQQ", otm_pct=0.5, dte=5, closes=closes)
    assert wide["win_rate"] > narrow["win_rate"]


def test_backtest_validation():
    with pytest.raises(ValueError):
        bt.run_backtest("QQQ", otm_pct=99, closes=synthetic_closes())
    with pytest.raises(ValueError):
        bt.run_backtest("QQQ", dte=999, closes=synthetic_closes())
    with pytest.raises(ValueError):
        bt.run_backtest("QQQ", closes=synthetic_closes(n=40))
