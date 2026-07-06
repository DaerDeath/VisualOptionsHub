"""Tests del port fiel de los notebooks (closes sintéticos inyectados)."""

import numpy as np
import pytest

from visual_options.stream import notebooks as nb


def synthetic_closes(n=600, seed=9):
    rng = np.random.default_rng(seed)
    return 5000 * np.exp(np.cumsum(rng.normal(0, 0.0015, n)))


def test_daily_variant_matches_notebook_shape():
    closes = synthetic_closes()
    result = nb.original_projection("ES=F", "daily", closes=closes)
    assert result["label"].startswith("Proyección ARIMA(1,0,1)")
    assert len(result["projection"]) == nb.HORIZON
    assert "arima" in result["params"] and "garch" in result["params"]
    assert "upper" not in result  # la variante daily no lleva bandas
    # la trayectoria arranca cerca del último precio
    assert result["projection"][0] == pytest.approx(result["last_price"], rel=0.02)


def test_daily_variant_is_deterministic_seed42():
    closes = synthetic_closes()
    a = nb.original_projection("ES=F", "daily", closes=closes)
    b = nb.original_projection("ES=F", "daily", closes=closes)
    assert a["projection"] == b["projection"]  # np.random.seed(42), como el .ipynb


def test_meanzero_variant_has_ordered_bands():
    closes = synthetic_closes(seed=11)
    result = nb.original_projection("NQ=F", "meanzero", closes=closes)
    assert result["label"].startswith("Proyección GARCH(1,1) mean='Constant'")
    assert len(result["projection"]) == len(result["upper"]) == len(result["lower"]) == nb.HORIZON
    for low, mid, high in zip(result["lower"], result["projection"], result["upper"]):
        assert low <= mid <= high
    # las bandas se ensanchan con el horizonte
    assert (result["upper"][-1] - result["lower"][-1]) > (result["upper"][0] - result["lower"][0])


def test_rejects_unknown_variant_and_short_series():
    with pytest.raises(ValueError):
        nb.original_projection("ES=F", "weekly", closes=synthetic_closes())
    with pytest.raises(ValueError):
        nb.original_projection("ES=F", "daily", closes=synthetic_closes(n=20))
