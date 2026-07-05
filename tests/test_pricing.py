"""Tests de pricing: valores BSM conocidos, IV inversa y paridad put-call."""

import math

import pytest

from visual_options import pricing


# Caso canónico: S=100, K=100, T=1 año, r=5%, sigma=20% → call ≈ 10.4506
CANONICAL = dict(spot=100.0, strike=100.0, days=365.0, iv=0.20, rate=0.05)


def test_bs_call_canonical_value():
    price = pricing.bs_price("call", **CANONICAL)
    assert price == pytest.approx(10.4506, abs=1e-3)


def test_bs_put_canonical_value():
    price = pricing.bs_price("put", **CANONICAL)
    assert price == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity_holds():
    call = pricing.bs_price("call", **CANONICAL)
    put = pricing.bs_price("put", **CANONICAL)
    parity_put = pricing.put_call_parity_put(call, 100.0, 100.0, 365.0, rate=0.05)
    assert put == pytest.approx(parity_put, abs=1e-9)


def test_implied_volatility_roundtrip():
    price = pricing.bs_price("call", 150.0, 155.0, 45.0, 0.35, 0.04)
    iv = pricing.implied_volatility("call", price, 150.0, 155.0, 45.0, 0.04)
    assert iv == pytest.approx(0.35, abs=1e-6)


def test_expired_option_returns_intrinsic():
    assert pricing.bs_price("call", 110.0, 100.0, 0.0, 0.3) == 10.0
    assert pricing.bs_price("put", 110.0, 100.0, 0.0, 0.3) == 0.0


def test_probability_itm_bounds_and_symmetry():
    p_call = pricing.probability_itm("call", 100.0, 100.0, 30.0, 0.25, rate=0.0)
    p_put = pricing.probability_itm("put", 100.0, 100.0, 30.0, 0.25, rate=0.0)
    assert 0.0 < p_call < 1.0
    assert p_call + p_put == pytest.approx(1.0, abs=1e-9)


def test_expected_move_scales_with_sqrt_time():
    one_month = pricing.expected_move(100.0, 0.30, 30.0)
    four_months = pricing.expected_move(100.0, 0.30, 120.0)
    assert four_months == pytest.approx(one_month * 2.0, rel=1e-9)


def test_deep_itm_call_approaches_forward_intrinsic():
    price = pricing.bs_price("call", 200.0, 50.0, 30.0, 0.20, 0.04)
    t = 30.0 / 365.0
    assert price == pytest.approx(200.0 - 50.0 * math.exp(-0.04 * t), abs=1e-6)
