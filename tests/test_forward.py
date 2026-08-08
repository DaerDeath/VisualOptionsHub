"""Tests de forward_analysis contra el ejemplo trabajado de IBM del libro
(Cap. 2, pág. 66-69): spot $200, tasa 0.35%, 469 días, dividendos $2.87
→ forward esperado $198.03."""

import types

import pytest

from visual_options.stream import forward as fwd


class FakeTicker:
    def __init__(self, spot, dividend_rate, options=("2099-01-01",)):
        self._spot = spot
        self.fast_info = {"last_price": spot}
        self.info = {"dividendRate": dividend_rate}
        self.options = options


class FakeRateTicker:
    """Simula ^IRX: history()['Close'] en puntos porcentuales."""
    def __init__(self, pct):
        self._pct = pct

    def history(self, period="5d", interval="1d"):
        import pandas as pd
        return pd.DataFrame({"Close": [self._pct]})


def test_ibm_worked_example_from_the_book():
    # spot 200, tasa 0.35%, 469 días, dividendos totales 2.87 hasta expiry
    # → dividendo "anual" equivalente que al prorratear por 469/365 da 2.87
    days = 469
    total_dividends = 2.87
    annual_dividend = total_dividends / (days / 365)  # para que el prorrateo dé 2.87 exacto

    ticker = FakeTicker(spot=200.0, dividend_rate=annual_dividend)
    result = fwd.forward_analysis("IBM", days=days, rate=0.0035, ticker=ticker)

    assert result["interest_multiplier"] == pytest.approx(469 / 365, abs=1e-4)
    assert result["interest_amount"] == pytest.approx(0.90, abs=0.01)          # libro: $0.90
    assert result["dividends_to_expiry"] == pytest.approx(2.87, abs=0.01)      # libro: $2.87
    assert result["forward_simple"] == pytest.approx(198.03, abs=0.01)         # libro: $198.03
    assert result["cost_of_carry"] == pytest.approx(0.90 - 2.87, abs=0.01)
    # "los puts deberían cotizar unos $1.97 por encima de los calls"
    assert result["put_over_call_atm"] == pytest.approx(1.97, abs=0.01)
    assert "dividendos superan" in result["carry_direction"]


def test_manual_rate_skips_treasury_fetch():
    ticker = FakeTicker(spot=100.0, dividend_rate=0.0)
    result = fwd.forward_analysis("QQQ", days=30, rate=0.05, ticker=ticker)
    assert result["rate"] == 0.05
    assert result["rate_source"] == "manual"
    # sin dividendos: interés puro sube el forward por encima del spot
    assert result["forward_simple"] > result["spot"]
    assert "interés supera" in result["carry_direction"]


def test_auto_rate_uses_irx_ticker_factory():
    ticker = FakeTicker(spot=50.0, dividend_rate=0.0)
    result = fwd.forward_analysis(
        "AAPL", days=30, ticker=ticker,
        rate_ticker_factory=lambda: FakeRateTicker(4.25))
    assert result["rate"] == pytest.approx(0.0425)
    assert result["rate_source"].startswith("T-bill")


def test_days_default_to_front_month_not_nearest():
    from datetime import datetime, timedelta
    # 0DTE muy cercano + uno a ~30 días: debe elegir el de ~30, no el 0DTE
    near = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    front_month = (datetime.now() + timedelta(days=28)).strftime("%Y-%m-%d")
    far = (datetime.now() + timedelta(days=200)).strftime("%Y-%m-%d")
    ticker = FakeTicker(spot=100.0, dividend_rate=0.0, options=(near, front_month, far))
    result = fwd.forward_analysis("QQQ", rate=0.04, ticker=ticker)
    assert 26 <= result["days"] <= 30


def test_continuous_forward_reported_alongside_simple():
    ticker = FakeTicker(spot=100.0, dividend_rate=0.0)
    result = fwd.forward_analysis("QQQ", days=30, rate=0.05, ticker=ticker)
    # sin dividendos y plazo corto, ambos métodos casi coinciden
    assert result["forward_continuous"] == pytest.approx(result["forward_simple"], abs=0.05)


def test_validation_errors():
    ticker = FakeTicker(spot=100.0, dividend_rate=0.0)
    with pytest.raises(ValueError):
        fwd.forward_analysis("QQQ", days=0, rate=0.04, ticker=ticker)
    with pytest.raises(ValueError):
        fwd.forward_analysis("QQQ", days=30, rate=5.0, ticker=ticker)  # 500%, no es fracción


def test_steps_are_ordered_and_numeric():
    ticker = FakeTicker(spot=200.0, dividend_rate=2.0)
    result = fwd.forward_analysis("IBM", days=90, rate=0.04, ticker=ticker)
    labels = [s["label"] for s in result["steps"]]
    assert labels == ["Precio spot", "Multiplicador de interés", "Monto de interés",
                      "Dividendos hasta el vencimiento", "Cost of Carry", "Forward Price"]
    assert all(isinstance(s["value"], float) for s in result["steps"])
