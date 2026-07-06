"""Tests del módulo de estadísticos con series sintéticas controladas."""

import numpy as np
import pytest

from visual_options.stream import stats as st


def normal_returns(n=1000, sigma=0.002, seed=1):
    return np.random.default_rng(seed).normal(0, sigma, n)


def garch_returns(n=1500, omega=0.02, alpha=0.1, beta=0.85, seed=2):
    """Serie GARCH(1,1) sintética (en la escala interna ×1000)."""
    rng = np.random.default_rng(seed)
    r = np.empty(n)
    sigma2 = omega / (1 - alpha - beta)
    prev = 0.0
    for t in range(n):
        sigma2 = omega + alpha * prev ** 2 + beta * sigma2
        prev = np.sqrt(sigma2) * rng.standard_normal()
        r[t] = prev
    return r / st.GARCH_SCALE


def test_describe_annualizes_by_interval():
    r = normal_returns(sigma=0.001)
    daily = st.describe(r, "1d")
    intraday = st.describe(r, "15m")
    assert intraday["sigma_annual"] > daily["sigma_annual"]
    assert daily["sigma_annual"] == pytest.approx(r.std(ddof=1) * np.sqrt(252), rel=1e-9)


def test_jarque_bera_detects_normal_and_fat_tails():
    assert st.jarque_bera(normal_returns())["normal"] is True
    fat = np.random.default_rng(3).standard_t(df=3, size=2000) * 0.002
    assert st.jarque_bera(fat)["normal"] is False


def test_ljung_box_iid_vs_autocorrelated():
    assert st.ljung_box(normal_returns())["independent"] is True
    rng = np.random.default_rng(4)
    ar = np.empty(1000)
    ar[0] = 0.0
    for t in range(1, 1000):
        ar[t] = 0.6 * ar[t - 1] + rng.normal(0, 0.001)
    assert st.ljung_box(ar)["independent"] is False


def test_adf_stationary_returns_vs_random_walk():
    assert st.adf_test(normal_returns())["stationary"] is True
    walk = np.cumsum(normal_returns(seed=5))
    assert st.adf_test(walk)["stationary"] is False


def test_ar1_recovers_phi():
    rng = np.random.default_rng(6)
    y = np.empty(2000)
    y[0] = 0.0
    for t in range(1, 2000):
        y[t] = 0.4 * y[t - 1] + rng.normal(0, 0.001)
    fit = st.ar1_fit(y)
    assert fit["significant"] is True
    assert fit["phi"] == pytest.approx(0.4, abs=0.08)


def test_garch_fit_recovers_persistence():
    r = garch_returns()
    fit = st.garch11_fit(r)
    assert fit["converged"] is True
    assert fit["persistence"] == pytest.approx(0.95, abs=0.06)
    assert len(fit["std_residuals"]) == len(r)


def test_garch_detects_arch_effect_in_synthetic_series():
    r = garch_returns()
    lb2 = st.ljung_box(r ** 2)
    assert lb2["independent"] is False  # clustering presente


def test_monte_carlo_shapes_and_sanity():
    r = garch_returns(n=800)
    mc = st.monte_carlo(r, last_price=100.0, horizon=48, paths=500, seed=7)
    assert len(mc["bands"]) == 48
    assert all(len(row) == 5 for row in mc["bands"])
    final = mc["bands"][-1]
    assert final[0] < final[2] < final[4]           # P5 < P50 < P95
    assert 0.2 < mc["prob_up"] < 0.8                # sin drift: ~50%
    assert mc["expected"] == pytest.approx(100.0, rel=0.05)
    assert mc["var95"] > 0
    # el cono se ensancha con el horizonte
    early = mc["bands"][5]
    assert (final[4] - final[0]) > (early[4] - early[0])


def test_monte_carlo_reproducible_with_seed():
    r = garch_returns(n=600)
    a = st.monte_carlo(r, 100.0, horizon=24, paths=300, seed=42)
    b = st.monte_carlo(r, 100.0, horizon=24, paths=300, seed=42)
    assert a["bands"] == b["bands"]


def test_analyze_cards_with_mocked_fetch(monkeypatch):
    r = garch_returns(n=900)
    monkeypatch.setattr(st, "fetch_log_returns", lambda symbol, interval="15m": (r, 500.0))
    result = st.analyze("QQQ", "15m")
    ids = [c["id"] for c in result["cards"]]
    assert ids == ["desc", "jb", "adf", "lb", "arch", "ar1", "garch"]
    for card in result["cards"]:
        assert card["verdict"] in ("ok", "warn", "fail")
        assert card["does"] and card["result"] and card["note"]
    by_id = {c["id"]: c for c in result["cards"]}
    assert by_id["adf"]["verdict"] == "ok"     # retornos estacionarios
    assert by_id["arch"]["verdict"] == "ok"    # clustering presente → GARCH justificado
    assert by_id["garch"]["verdict"] == "ok"
