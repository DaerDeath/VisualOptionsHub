"""Tests de las features SpotGamma-like: heatmap, tape, calculadora y scanner."""

import pytest
from fastapi.testclient import TestClient

from visual_options.stream.server import create_app
from visual_options.stream.sim import SessionSimulator
from visual_options.stream.state import MAX_GEX_HISTORY, MAX_TAPE_EVENTS, DashboardState, StrikeRow


# ------------------------------------------------------- estado: historia

def test_gex_history_column_matches_strikes():
    sim = SessionSimulator(seed=9)
    history = sim.state.gex_history
    assert len(history) == 40  # una columna por tick de arranque
    assert len(history[-1]["gex"]) == len(sim.state.strikes)
    assert "t" in history[-1] and "spot" in history[-1]


def test_gex_history_rolls():
    state = DashboardState(symbol="X", spot=100.0,
                           strikes=[StrikeRow(strike=100.0, net_gex=1.0)])
    for i in range(MAX_GEX_HISTORY + 30):
        state.timestamp = f"{i}"
        state.snapshot_gex_column()
    assert len(state.gex_history) == MAX_GEX_HISTORY
    assert state.gex_history[0]["t"] == "30"


def test_tape_rolls_and_serializes():
    state = DashboardState(symbol="X", spot=100.0)
    for i in range(MAX_TAPE_EVENTS + 10):
        state.append_tape(100.0, "call", "buy", 500, 12345.6)
    assert len(state.tape) == MAX_TAPE_EVENTS
    snap = state.snapshot()
    assert "tape" in snap and "gex_history" in snap
    event = snap["tape"][-1]
    assert {"t", "strike", "kind", "side", "size", "premium"} <= set(event)


def test_sim_emits_tape_events():
    sim = SessionSimulator(seed=3)
    assert len(sim.state.tape) > 0
    kinds = {ev["kind"] for ev in sim.state.tape}
    assert kinds <= {"call", "put"}
    assert all(ev["size"] >= 400 for ev in sim.state.tape)


# ---------------------------------------------------------- calculadora

def test_calculator_catalog_lists_book_strategies():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        catalog = client.get("/api/calculator/strategies").json()
        ids = {s["id"] for s in catalog}
        assert {"long_call", "bull_put_spread", "short_iron_condor", "collar"} <= ids
        entry = next(s for s in catalog if s["id"] == "bull_put_spread")
        assert entry["params"] == ["short_strike", "short_premium", "long_strike", "long_premium"]


def test_calculator_analyzes_with_premiums():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        result = client.get("/api/calculator", params={
            "strategy": "bull_put_spread",
            "params": "short_strike=190,short_premium=5,long_strike=180,long_premium=2.5",
            "spot": 195, "iv": 0.28, "days": 30,
        }).json()
        assert result["max_profit"] == pytest.approx(250.0)   # 2.50 × 100
        assert result["max_loss"] == pytest.approx(750.0)
        assert result["breakevens"] == [187.5]
        assert 0.5 < result["pop"] < 1.0
        assert len(result["curve"]["spots"]) == len(result["curve"]["payoff"])
        assert "t0" in result["curve"]


def test_calculator_auto_price():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        result = client.get("/api/calculator", params={
            "strategy": "long_straddle", "params": "strike=100",
            "auto_price": "true", "spot": 100, "iv": 0.35, "days": 21,
        }).json()
        assert result["max_profit"] is None      # ilimitado
        assert result["net_premium"] > 0         # débito
        assert len(result["breakevens"]) == 2


def test_calculator_rejects_bad_input():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        assert client.get("/api/calculator", params={
            "strategy": "no_existe", "params": "strike=1"}).status_code == 400
        assert client.get("/api/calculator", params={
            "strategy": "long_call", "params": "strike=100"}).status_code == 400  # falta prima


# --------------------------------------------------------------- scanner

def test_scan_returns_signals_per_symbol():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        rows = client.get("/api/scan", params={"symbols": "qqq,spy"}).json()
        assert [r["symbol"] for r in rows] == ["QQQ", "SPY"]
        for row in rows:
            assert {"spot", "direction_score", "total_gex", "regime",
                    "gamma_flip", "atm_iv", "connected"} <= set(row)
            assert row["regime"] in ("amortiguador", "acelerador")


def test_scan_limits_symbol_count():
    app = create_app(mode="sim", seed=1)
    with TestClient(app) as client:
        many = ",".join(f"S{i}" for i in range(30))
        rows = client.get("/api/scan", params={"symbols": many}).json()
        assert len(rows) == 16
