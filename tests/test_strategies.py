"""Verifica cada estrategia contra las fórmulas literales del libro.

Las fórmulas de max profit / max risk / breakeven provienen de los
capítulos 4, 5 y 6 de Visual Guide to Options (Jared Levy).
"""

import math

import pytest

from visual_options.builders import (
    bear_call_spread,
    bear_put_spread,
    bull_call_spread,
    bull_put_spread,
    collar,
    covered_call,
    long_butterfly,
    long_call,
    long_condor,
    long_iron_butterfly,
    long_iron_condor,
    long_put,
    long_straddle,
    long_strangle,
    protective_put,
    short_butterfly,
    short_condor,
    short_iron_butterfly,
    short_iron_condor,
    short_put,
    short_straddle,
)


def test_long_call_book_formulas():
    s = long_call(strike=100, premium=3.0)
    assert math.isinf(s.max_profit())
    assert s.max_loss() == pytest.approx(3.0)          # prima pagada
    assert s.breakevens() == pytest.approx((103.0,))   # strike + prima


def test_long_put_book_formulas():
    s = long_put(strike=100, premium=4.0)
    assert s.max_profit() == pytest.approx(96.0)       # strike - prima
    assert s.max_loss() == pytest.approx(4.0)          # prima pagada
    assert s.breakevens() == pytest.approx((96.0,))    # strike - prima


def test_short_put_book_formulas():
    s = short_put(strike=50, premium=2.0)
    assert s.max_profit() == pytest.approx(2.0)        # prima recibida
    assert s.max_loss() == pytest.approx(48.0)         # strike - prima
    assert s.breakevens() == pytest.approx((48.0,))


def test_covered_call_book_formulas():
    # Libro: max profit = (strike + prima) - coste base; riesgo y BE = coste - prima
    s = covered_call(stock_cost=95.0, call_strike=100.0, call_premium=2.5)
    assert s.max_profit() == pytest.approx(100.0 + 2.5 - 95.0)
    assert s.max_loss() == pytest.approx(95.0 - 2.5)
    assert s.breakevens() == pytest.approx((92.5,))


def test_protective_put_book_formulas():
    s = protective_put(stock_cost=100.0, put_strike=95.0, put_premium=3.0)
    assert math.isinf(s.max_profit())
    assert s.max_loss() == pytest.approx(100.0 + 3.0 - 95.0)
    assert s.breakevens() == pytest.approx((103.0,))


def test_collar_book_formulas():
    # Libro: net cost basis = acción + prima call vendida... (compra put - vende call)
    s = collar(stock_cost=100.0, put_strike=95.0, put_premium=2.0,
               call_strike=110.0, call_premium=1.5)
    net_basis = 100.0 + 2.0 - 1.5
    assert s.max_profit() == pytest.approx(110.0 - net_basis)
    assert s.max_loss() == pytest.approx(net_basis - 95.0)
    assert s.breakevens() == pytest.approx((net_basis,))


def test_bull_call_spread_book_formulas():
    s = bull_call_spread(long_strike=180.0, long_premium=6.0,
                         short_strike=190.0, short_premium=2.05)
    debit = 6.0 - 2.05
    assert s.max_profit() == pytest.approx(10.0 - debit)
    assert s.max_loss() == pytest.approx(debit)
    assert s.breakevens() == pytest.approx((180.0 + debit,))


def test_bull_put_spread_book_formulas():
    s = bull_put_spread(short_strike=190.0, short_premium=5.0,
                        long_strike=180.0, long_premium=2.5)
    credit = 2.5
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(10.0 - credit)
    assert s.breakevens() == pytest.approx((190.0 - credit,))


def test_bear_call_spread_book_formulas():
    # Ejemplo del libro: GS julio 155/165 call spread por 2.10 de crédito
    s = bear_call_spread(short_strike=155.0, short_premium=4.0,
                         long_strike=165.0, long_premium=1.9)
    credit = 2.1
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(10.0 - credit)
    assert s.breakevens() == pytest.approx((155.0 + credit,))


def test_bear_put_spread_book_formulas():
    # Ejemplo del libro: comprar 165 put, vender 155 put por débito 7.90
    s = bear_put_spread(long_strike=165.0, long_premium=9.0,
                        short_strike=155.0, short_premium=1.1)
    debit = 7.9
    assert s.max_profit() == pytest.approx(10.0 - debit)
    assert s.max_loss() == pytest.approx(debit)
    assert s.breakevens() == pytest.approx((165.0 - debit,))


def test_long_straddle_book_formulas():
    s = long_straddle(strike=100.0, call_premium=3.0, put_premium=2.8)
    total = 5.8
    assert math.isinf(s.max_profit())
    assert s.max_loss() == pytest.approx(total)
    assert s.breakevens() == pytest.approx((100.0 - total, 100.0 + total))


def test_short_straddle_book_formulas():
    s = short_straddle(strike=100.0, call_premium=3.0, put_premium=2.8)
    assert s.max_profit() == pytest.approx(5.8)
    assert math.isinf(s.max_loss())


def test_long_strangle_book_formulas():
    s = long_strangle(put_strike=95.0, put_premium=1.5, call_strike=105.0, call_premium=1.7)
    total = 3.2
    assert s.max_loss() == pytest.approx(total)
    assert s.breakevens() == pytest.approx((95.0 - total, 105.0 + total))


def test_long_butterfly_book_formulas():
    # Libro: max profit = distancia entre strikes - prima; riesgo = prima;
    # zona de beneficio entre (inferior + prima) y (superior - prima)
    s = long_butterfly("call", 95.0, 7.0, 100.0, 4.0, 105.0, 2.0)
    debit = 7.0 - 2 * 4.0 + 2.0
    assert s.max_loss() == pytest.approx(debit)
    assert s.max_profit() == pytest.approx(5.0 - debit)
    assert s.breakevens() == pytest.approx((95.0 + debit, 105.0 - debit))
    # el pico está en el strike central
    assert float(s.payoff(100.0)) == pytest.approx(5.0 - debit)


def test_short_butterfly_book_formulas():
    s = short_butterfly("call", 95.0, 7.0, 100.0, 4.0, 105.0, 2.0)
    credit = 7.0 - 2 * 4.0 + 2.0
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(5.0 - credit)
    # pérdida máxima clavada en el centro
    assert float(s.payoff(100.0)) == pytest.approx(-(5.0 - credit))


def test_long_condor_book_formulas():
    s = long_condor("call", 90.0, 12.0, 95.0, 8.0, 105.0, 3.0, 110.0, 1.5)
    debit = 12.0 - 8.0 - 3.0 + 1.5
    wingspan = 5.0
    assert s.max_loss() == pytest.approx(debit)
    assert s.max_profit() == pytest.approx(wingspan - debit)
    assert s.breakevens() == pytest.approx((90.0 + debit, 110.0 - debit))
    # meseta entre strikes interiores
    assert float(s.payoff(100.0)) == pytest.approx(wingspan - debit)


def test_short_condor_book_formulas():
    s = short_condor("call", 90.0, 12.0, 95.0, 8.0, 105.0, 3.0, 110.0, 1.5)
    credit = 12.0 - 8.0 - 3.0 + 1.5
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(5.0 - credit)


def test_short_iron_butterfly_book_formulas():
    # Libro: profit zone = strike central ± crédito; riesgo = distancia - crédito
    s = short_iron_butterfly(center_strike=200.0, short_call_premium=6.0, short_put_premium=5.5,
                             wing_put_strike=190.0, wing_put_premium=2.0,
                             wing_call_strike=210.0, wing_call_premium=2.5)
    credit = 6.0 + 5.5 - 2.0 - 2.5
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(10.0 - credit)
    assert s.breakevens() == pytest.approx((200.0 - credit, 200.0 + credit))
    assert float(s.payoff(200.0)) == pytest.approx(credit)


def test_long_iron_butterfly_book_formulas():
    s = long_iron_butterfly(center_strike=200.0, long_call_premium=6.0, long_put_premium=5.5,
                            wing_put_strike=190.0, wing_put_premium=2.0,
                            wing_call_strike=210.0, wing_call_premium=2.5)
    debit = 6.0 + 5.5 - 2.0 - 2.5
    assert s.max_loss() == pytest.approx(debit)
    assert s.max_profit() == pytest.approx(10.0 - debit)
    # pérdida máxima clavada en el strike central
    assert float(s.payoff(200.0)) == pytest.approx(-debit)


def test_short_iron_condor_book_formulas():
    s = short_iron_condor(put_wing_strike=85.0, put_wing_premium=0.8,
                          short_put_strike=90.0, short_put_premium=2.0,
                          short_call_strike=110.0, short_call_premium=2.2,
                          call_wing_strike=115.0, call_wing_premium=0.9)
    credit = 2.0 + 2.2 - 0.8 - 0.9
    assert s.max_profit() == pytest.approx(credit)
    assert s.max_loss() == pytest.approx(5.0 - credit)
    assert s.breakevens() == pytest.approx((90.0 - credit, 110.0 + credit))
    # beneficio máximo entre los strikes cortos
    assert float(s.payoff(100.0)) == pytest.approx(credit)


def test_long_iron_condor_book_formulas():
    s = long_iron_condor(put_wing_strike=85.0, put_wing_premium=0.8,
                         long_put_strike=90.0, long_put_premium=2.0,
                         long_call_strike=110.0, long_call_premium=2.2,
                         call_wing_strike=115.0, call_wing_premium=0.9)
    debit = 2.0 + 2.2 - 0.8 - 0.9
    assert s.max_loss() == pytest.approx(debit)
    assert s.max_profit() == pytest.approx(5.0 - debit)


def test_probability_of_profit_is_sane():
    s = bull_put_spread(short_strike=95.0, short_premium=2.0,
                        long_strike=90.0, long_premium=1.0)
    pop = s.probability_of_profit(spot=100.0, iv=0.30, days=30.0)
    assert 0.5 < pop < 1.0  # spread OTM vendido: probabilidad a favor


def test_strike_ordering_validation():
    with pytest.raises(ValueError):
        bull_call_spread(long_strike=110.0, long_premium=1.0,
                         short_strike=100.0, short_premium=3.0)
    with pytest.raises(ValueError):
        long_butterfly("call", 100.0, 4.0, 95.0, 7.0, 105.0, 2.0)
