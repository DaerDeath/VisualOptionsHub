"""Tests de la CLI (todos los subcomandos offline) y de la generación de gráficos."""

import pytest

from visual_options.builders import covered_call, long_straddle
from visual_options.cli import main
from visual_options.plotting import plot_greeks, plot_payoff


def test_cli_list_shows_all_strategies(capsys):
    main(["list"])
    out = capsys.readouterr().out
    for name in ("long_call", "bull_put_spread", "short_iron_condor", "long_butterfly"):
        assert name in out


def test_cli_analyze_with_premiums(capsys):
    main(["analyze", "bull_put_spread",
          "short_strike=190", "short_premium=5", "long_strike=180", "long_premium=2.5",
          "--spot", "195", "--iv", "0.28", "--days", "30"])
    out = capsys.readouterr().out
    assert "Max profit : 2.50" in out
    assert "187.50" in out
    assert "Prob. beneficio" in out


def test_cli_analyze_auto_price(capsys):
    main(["analyze", "long_straddle", "strike=100",
          "--auto-price", "--spot", "100", "--iv", "0.35", "--days", "21"])
    out = capsys.readouterr().out
    assert "débito pagado" in out
    assert "ilimitado" in out


def test_cli_analyze_missing_premium_without_autoprice():
    with pytest.raises(SystemExit):
        main(["analyze", "long_call", "strike=100"])


def test_cli_analyze_rejects_unknown_param():
    with pytest.raises(SystemExit):
        main(["analyze", "long_call", "strike=100", "premium=3", "foo=1"])


def test_cli_analyze_saves_plots(tmp_path, capsys):
    payoff_png = tmp_path / "p.png"
    greeks_png = tmp_path / "g.png"
    main(["analyze", "long_call", "strike=100", "premium=3",
          "--spot", "100", "--iv", "0.3", "--days", "30",
          "--plot", str(payoff_png), "--greeks-plot", str(greeks_png)])
    assert payoff_png.exists() and payoff_png.stat().st_size > 10_000
    assert greeks_png.exists() and greeks_png.stat().st_size > 10_000


def test_cli_price(capsys):
    main(["price", "call", "--spot", "150", "--strike", "155", "--days", "45", "--iv", "0.30"])
    out = capsys.readouterr().out
    assert "Precio BSM" in out
    assert "Prob. ITM" in out


def test_cli_vol(tmp_path, capsys):
    closes = tmp_path / "closes.txt"
    closes.write_text("\n".join(str(100 + i * (-1) ** i) for i in range(20)))
    main(["vol", str(closes), "--iv", "0.45", "--days", "30"])
    out = capsys.readouterr().out
    assert "HV" in out
    assert "ratio IV/HV" in out


def test_cli_grade_show_criteria(capsys):
    main(["grade", "--show-criteria"])
    out = capsys.readouterr().out
    assert "market_direction" in out
    assert "timing_mental" in out


def test_cli_grade_with_failures_and_account(capsys):
    main(["grade", "--fail", "chart_macd,opt_spreads", "--account", "25000"])
    out = capsys.readouterr().out
    assert "Grado: C" in out
    assert "$500" in out and "$1,250" in out


def test_cli_earnings_with_breakeven_rule(capsys):
    main(["earnings", "--spot", "100", "--avg-move", "0.10"])
    out = capsys.readouterr().out
    assert "Checklist previo a earnings" in out
    assert "95.00" in out


def test_cli_earnings_bearish(capsys):
    main(["earnings", "--spot", "100", "--avg-move", "0.10", "--bearish"])
    assert "105.00" in capsys.readouterr().out


def test_plot_payoff_without_market_context(tmp_path):
    s = covered_call(stock_cost=95.0, call_strike=100.0, call_premium=2.5)
    out = plot_payoff(s, tmp_path / "cc.png")
    assert out.exists()


def test_plot_greeks_straddle(tmp_path):
    s = long_straddle(strike=100.0, call_premium=3.0, put_premium=2.8)
    out = plot_greeks(s, tmp_path / "greeks.png", spot=100.0, iv=0.30, days=21.0)
    assert out.exists()


def test_summary_shows_book_formulas():
    s = covered_call(stock_cost=95.0, call_strike=100.0, call_premium=2.5)
    text = s.summary()
    assert "coste base de la acción - prima del call" in text
    assert "Cap. 4" in text
