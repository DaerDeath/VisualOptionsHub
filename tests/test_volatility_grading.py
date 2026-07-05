"""Tests de volatilidad (Cap. 2/7) y del sistema de calificación A-F."""

import math

import numpy as np
import pytest

from visual_options import grading, volatility


def test_historical_volatility_of_constant_prices_is_zero():
    assert volatility.historical_volatility([100.0] * 30) == pytest.approx(0.0)


def test_historical_volatility_matches_manual_calculation():
    rng = np.random.default_rng(7)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, 100)))
    hv = volatility.historical_volatility(closes)
    manual = np.std(np.diff(np.log(closes)), ddof=1) * math.sqrt(252)
    assert hv == pytest.approx(manual)


def test_volatility_bias_thresholds():
    assert volatility.volatility_bias(iv=0.60, hv=0.40) == "vendedor"
    assert volatility.volatility_bias(iv=0.20, hv=0.40) == "comprador"
    assert volatility.volatility_bias(iv=0.40, hv=0.40) == "neutral"


def test_iv_rank_and_percentile():
    history = [0.20, 0.30, 0.40, 0.50, 0.60]
    assert volatility.iv_rank(0.40, history) == pytest.approx(50.0)
    assert volatility.iv_percentile(0.45, history) == pytest.approx(60.0)


def test_grade_starts_at_a_and_drops_per_failure():
    assert grading.grade_trade({}).grade == "A"
    one_fail = grading.grade_trade({"market_direction": False})
    assert one_fail.grade == "B"
    two_fails = grading.grade_trade({"market_direction": False, "chart_macd": False})
    assert two_fails.grade == "C"


def test_grade_floors_at_f():
    all_failed = {key: False for key, _ in grading.CHECKLIST_CRITERIA}
    result = grading.grade_trade(all_failed)
    assert result.grade == "F"
    assert result.allocation == (0.0, 0.0)


def test_grade_rejects_unknown_criteria():
    with pytest.raises(ValueError):
        grading.grade_trade({"criterio_inventado": False})


def test_allocation_bands_match_book():
    # Cap. 2: A hasta 10%, B 5-9%, C 2-5%, D <2%, F no operar
    assert grading.ALLOCATION_BY_GRADE["A"][1] == 0.10
    assert grading.ALLOCATION_BY_GRADE["B"] == (0.05, 0.09)
    assert grading.ALLOCATION_BY_GRADE["C"] == (0.02, 0.05)
    assert grading.ALLOCATION_BY_GRADE["D"][1] == 0.02
    assert grading.ALLOCATION_BY_GRADE["F"] == (0.0, 0.0)


def test_earnings_breakeven_target_book_example():
    # Libro: acción a $100 con movimiento medio del 10% → BE ≤ 95 (alcista) o ≥ 105 (bajista)
    assert grading.earnings_breakeven_target(100.0, 0.10, bullish=True) == pytest.approx(95.0)
    assert grading.earnings_breakeven_target(100.0, 0.10, bullish=False) == pytest.approx(105.0)
