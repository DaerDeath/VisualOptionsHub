"""Tests de los conceptos del Cap. 1: moneyness, intrínseco y extrínseco."""

import pytest

from visual_options.contracts import OptionLeg, StockLeg


def test_call_intrinsic_and_extrinsic():
    call = OptionLeg("call", strike=100.0, premium=5.0)
    assert call.intrinsic_value(103.0) == 3.0
    assert call.extrinsic_value(103.0) == 2.0
    assert call.intrinsic_value(97.0) == 0.0
    assert call.extrinsic_value(97.0) == 5.0  # todo prima de tiempo


def test_put_intrinsic_value():
    put = OptionLeg("put", strike=100.0, premium=4.0)
    assert put.intrinsic_value(92.0) == 8.0
    assert put.intrinsic_value(105.0) == 0.0


def test_moneyness_classification():
    call = OptionLeg("call", strike=100.0, premium=2.0)
    assert call.moneyness(110.0) == "ITM"
    assert call.moneyness(90.0) == "OTM"
    assert call.moneyness(100.2) == "ATM"
    put = OptionLeg("put", strike=100.0, premium=2.0)
    assert put.moneyness(90.0) == "ITM"
    assert put.moneyness(110.0) == "OTM"


def test_option_leg_validation():
    with pytest.raises(ValueError):
        OptionLeg("cal", 100.0, 1.0)   # tipo inválido
    with pytest.raises(ValueError):
        OptionLeg("call", -5.0, 1.0)   # strike negativo
    with pytest.raises(ValueError):
        OptionLeg("call", 100.0, -1.0)  # prima negativa
    with pytest.raises(ValueError):
        OptionLeg("call", 100.0, 1.0, 0)  # cantidad cero


def test_stock_leg_validation_and_payoff():
    with pytest.raises(ValueError):
        StockLeg(cost_basis=0.0)
    with pytest.raises(ValueError):
        StockLeg(cost_basis=100.0, quantity=0)
    stock = StockLeg(cost_basis=100.0, quantity=100)
    assert float(stock.payoff_at_expiry(105.0)) == pytest.approx(5.0)


def test_short_leg_payoff_sign():
    short_call = OptionLeg("call", strike=100.0, premium=3.0, quantity=-1)
    assert float(short_call.payoff_at_expiry(95.0)) == pytest.approx(3.0)   # se queda la prima
    assert float(short_call.payoff_at_expiry(110.0)) == pytest.approx(-7.0)
