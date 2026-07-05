"""Tests del módulo dealer: vanna, exposiciones y gamma flip."""

import pytest

from visual_options.greeks import bs_greeks
from visual_options.stream.dealer import bs_vanna, compute_exposures, gamma_flip_level
from visual_options.stream.state import StrikeRow


def test_vanna_matches_finite_difference_of_delta():
    # vanna = d(delta)/d(sigma)
    params = dict(spot=100.0, strike=105.0, days=30.0, rate=0.04)
    iv, bump = 0.25, 0.0005
    fd = (bs_greeks("call", params["spot"], params["strike"], params["days"], iv + bump, params["rate"]).delta
          - bs_greeks("call", params["spot"], params["strike"], params["days"], iv - bump, params["rate"]).delta) / (2 * bump)
    assert bs_vanna(params["spot"], params["strike"], params["days"], iv, params["rate"]) == pytest.approx(fd, abs=1e-4)


def test_vanna_sign_by_moneyness():
    # OTM call (strike > spot): d2 < 0 → vanna positiva; ITM: negativa
    assert bs_vanna(100.0, 110.0, 30.0, 0.25) > 0
    assert bs_vanna(100.0, 85.0, 30.0, 0.25) < 0


def test_vanna_degenerate_inputs_return_zero():
    assert bs_vanna(100.0, 100.0, 0.0, 0.25) == 0.0
    assert bs_vanna(100.0, 100.0, 30.0, 0.0) == 0.0


def test_compute_exposures_signs_and_scale():
    rows = [
        StrikeRow(strike=95.0, call_oi=1000, put_oi=5000, iv=0.22),
        StrikeRow(strike=100.0, call_oi=8000, put_oi=8000, iv=0.20),
        StrikeRow(strike=105.0, call_oi=5000, put_oi=1000, iv=0.21),
    ]
    compute_exposures(rows, spot=100.0, days=1.0)
    for row in rows:
        assert row.call_gex >= 0.0       # dealers largos de calls
        assert row.put_gex <= 0.0        # dealers cortos de puts
        assert row.net_gex == pytest.approx(row.call_gex + row.put_gex)
        assert row.net_vanna == pytest.approx(row.call_vanna + row.put_vanna)
        assert row.gamma_exposure == pytest.approx(row.net_gex)
    atm = rows[1]
    assert atm.call_gex > 0.1            # ATM 0DTE con 8000 OI: gamma relevante
    # DEX: calls delta+ dominan sobre puts delta- en el strike bajo (call ITM)
    assert rows[0].net_dex > 0


def test_compute_exposures_ignores_bad_inputs():
    rows = [StrikeRow(strike=100.0, call_oi=100, put_oi=100, iv=0.2)]
    compute_exposures(rows, spot=0.0, days=1.0)   # spot inválido: no toca nada
    assert rows[0].net_gex == 0.0
    compute_exposures(rows, spot=100.0, days=0.0)
    assert rows[0].net_gex == 0.0


def test_gamma_flip_interpolates_crossing():
    rows = [
        StrikeRow(strike=95.0, net_gex=-10.0),
        StrikeRow(strike=100.0, net_gex=4.0),   # acumulado: -10 → -6
        StrikeRow(strike=105.0, net_gex=12.0),  # acumulado: -6 → +6 (cruce)
    ]
    flip = gamma_flip_level(rows)
    assert flip == pytest.approx(100.0 + 0.5 * 5.0)  # cruza a mitad del tramo


def test_gamma_flip_none_when_no_crossing():
    rows = [StrikeRow(strike=95.0, net_gex=5.0), StrikeRow(strike=100.0, net_gex=3.0)]
    assert gamma_flip_level(rows) is None


def test_sim_populates_dealer_fields():
    from visual_options.stream.sim import SessionSimulator
    sim = SessionSimulator(seed=5)
    rows = sim.state.strikes
    assert all(r.call_oi > 0 and r.put_oi > 0 for r in rows)
    assert all(r.iv > 0.05 for r in rows)
    assert any(r.net_gex != 0 for r in rows)
    assert any(r.net_vanna != 0 for r in rows)
    # smile: la IV de los puts OTM (strikes bajos) supera a la del ATM
    low, mid = rows[0], rows[len(rows) // 2]
    assert low.iv > mid.iv
    snap = sim.state.snapshot()
    assert {"call_oi", "put_oi", "iv", "net_gex", "net_dex", "net_vanna"} <= set(snap["strikes"][0])
    assert "gamma_flip" in snap
