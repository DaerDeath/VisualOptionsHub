"""Tests de griegas: coherencia con diferencias finitas sobre el precio BSM."""

import pytest

from visual_options.greeks import bs_greeks, stock_greeks
from visual_options.pricing import bs_price

PARAMS = dict(spot=100.0, strike=105.0, days=60.0, iv=0.30, rate=0.04)


def _fd(kind: str, param: str, bump: float) -> float:
    up = dict(PARAMS)
    down = dict(PARAMS)
    up[param] += bump
    down[param] -= bump
    return (bs_price(kind, **up) - bs_price(kind, **down)) / (2 * bump)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_delta_matches_finite_difference(kind):
    greeks = bs_greeks(kind, **PARAMS)
    assert greeks.delta == pytest.approx(_fd(kind, "spot", 0.01), abs=1e-5)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_gamma_matches_finite_difference(kind):
    greeks = bs_greeks(kind, **PARAMS)
    fd_gamma = (bs_greeks(kind, PARAMS["spot"] + 0.01, PARAMS["strike"], PARAMS["days"],
                          PARAMS["iv"], PARAMS["rate"]).delta
                - bs_greeks(kind, PARAMS["spot"] - 0.01, PARAMS["strike"], PARAMS["days"],
                            PARAMS["iv"], PARAMS["rate"]).delta) / 0.02
    assert greeks.gamma == pytest.approx(fd_gamma, abs=1e-5)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_vega_matches_finite_difference(kind):
    greeks = bs_greeks(kind, **PARAMS)
    # vega está expresada por 1% de IV
    assert greeks.vega == pytest.approx(_fd(kind, "iv", 0.0001) / 100.0, abs=1e-5)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_theta_matches_finite_difference(kind):
    greeks = bs_greeks(kind, **PARAMS)
    # theta por día = -dV/d(días)
    assert greeks.theta == pytest.approx(-_fd(kind, "days", 0.01), abs=1e-5)


def test_put_call_delta_relationship():
    call = bs_greeks("call", **PARAMS)
    put = bs_greeks("put", **PARAMS)
    assert call.delta - put.delta == pytest.approx(1.0, abs=1e-9)
    assert call.gamma == pytest.approx(put.gamma, abs=1e-12)
    assert call.vega == pytest.approx(put.vega, abs=1e-12)


def test_stock_greeks_normalized_to_contract():
    greeks = stock_greeks(100)
    assert greeks.delta == 1.0
    assert greeks.gamma == greeks.theta == greeks.vega == greeks.rho == 0.0
