"""Constructores de todas las estrategias de los capítulos 4, 5, 6 y 7.

Cada builder registra los metadatos del libro: sesgo, capítulo y las
fórmulas literales de max profit / max risk / breakeven, de modo que
Strategy.summary() muestre la métrica calculada junto a la del libro.
"""

from __future__ import annotations

from collections.abc import Callable

from visual_options.contracts import OptionLeg, StockLeg
from visual_options.strategies import STRATEGY_BUILDERS, Strategy

Builder = Callable[..., Strategy]


def _register(name: str) -> Callable[[Builder], Builder]:
    def deco(fn: Builder) -> Builder:
        STRATEGY_BUILDERS[name] = fn
        return fn
    return deco


# ------------------------------------------------------------- Cap. 4: básicas

@_register("long_call")
def long_call(strike: float, premium: float) -> Strategy:
    return Strategy(
        "Long call", "alcista", "Cap. 4",
        (OptionLeg("call", strike, premium, 1),),
        notes="Busca un movimiento alcista fuerte; favorece IV relativa baja al entrar.",
        book_max_profit="ilimitado", book_max_risk="prima pagada",
        book_breakeven="strike + prima",
    )


@_register("short_call")
def short_call(strike: float, premium: float) -> Strategy:
    return Strategy(
        "Short call (descubierta)", "bajista/neutral", "Cap. 4",
        (OptionLeg("call", strike, premium, -1),),
        notes="Riesgo ilimitado al alza; el libro la desaconseja sin cobertura.",
        book_max_profit="prima recibida", book_max_risk="ilimitado",
        book_breakeven="strike + prima",
    )


@_register("long_put")
def long_put(strike: float, premium: float) -> Strategy:
    return Strategy(
        "Long put", "bajista", "Cap. 4",
        (OptionLeg("put", strike, premium, 1),),
        notes="Ideal muy bajista antes de que caiga; la IV sube cuando el valor cae.",
        book_max_profit="strike del put - prima pagada", book_max_risk="prima pagada",
        book_breakeven="strike del put - prima pagada",
    )


@_register("short_put")
def short_put(strike: float, premium: float) -> Strategy:
    return Strategy(
        "Short put (cash-secured)", "alcista/neutral", "Cap. 4",
        (OptionLeg("put", strike, premium, -1),),
        notes="Cobra prima aceptando comprar la acción al strike.",
        book_max_profit="prima recibida", book_max_risk="strike - prima (acción a 0)",
        book_breakeven="strike - prima",
    )


@_register("covered_call")
def covered_call(stock_cost: float, call_strike: float, call_premium: float) -> Strategy:
    return Strategy(
        "Covered call / buy-write", "moderadamente alcista", "Cap. 4",
        (StockLeg(stock_cost, 100), OptionLeg("call", call_strike, call_premium, -1)),
        notes="Captura theta del call corto mientras la acción se mantiene o sube "
              "ligeramente; mejor con IV alta frente a la observada al vender.",
        book_max_profit="(strike del call + prima) - coste base de la acción",
        book_max_risk="coste base de la acción - prima del call",
        book_breakeven="coste base de la acción - prima del call",
    )


@_register("protective_put")
def protective_put(stock_cost: float, put_strike: float, put_premium: float) -> Strategy:
    return Strategy(
        "Protective put (married put)", "alcista con seguro", "Cap. 4",
        (StockLeg(stock_cost, 100), OptionLeg("put", put_strike, put_premium, 1)),
        notes="Seguro contra caídas manteniendo el potencial alcista.",
        book_max_profit="ilimitado",
        book_max_risk="coste base + prima del put - strike del put",
        book_breakeven="coste base + prima del put",
    )


@_register("collar")
def collar(stock_cost: float, put_strike: float, put_premium: float,
           call_strike: float, call_premium: float) -> Strategy:
    return Strategy(
        "Collar", "neutral/protección", "Cap. 4",
        (
            StockLeg(stock_cost, 100),
            OptionLeg("put", put_strike, put_premium, 1),
            OptionLeg("call", call_strike, call_premium, -1),
        ),
        notes="Tras un rally con beneficio, protege el rango; se comporta como "
              "una vertical alcista.",
        book_max_profit="strike del call corto - coste base neto del collar",
        book_max_risk="coste base neto del collar - strike del put",
        book_breakeven="coste base neto (acción + prima call - prima put)",
    )


# --------------------------------------------------------- Cap. 5: verticales

@_register("bull_call_spread")
def bull_call_spread(long_strike: float, long_premium: float,
                     short_strike: float, short_premium: float) -> Strategy:
    if long_strike >= short_strike:
        raise ValueError("en un bull call spread se compra el strike inferior")
    return Strategy(
        "Bull call spread (vertical de débito con calls)", "alcista", "Cap. 5",
        (OptionLeg("call", long_strike, long_premium, 1),
         OptionLeg("call", short_strike, short_premium, -1)),
        notes="Mismo vencimiento, ambos calls; se compra el strike inferior.",
        book_max_profit="distancia entre strikes - débito pagado",
        book_max_risk="débito neto pagado",
        book_breakeven="strike del call largo + débito neto",
    )


@_register("bear_call_spread")
def bear_call_spread(short_strike: float, short_premium: float,
                     long_strike: float, long_premium: float) -> Strategy:
    if short_strike >= long_strike:
        raise ValueError("en un bear call spread se vende el strike inferior")
    return Strategy(
        "Bear call spread (vertical de crédito con calls)", "bajista/neutral", "Cap. 5",
        (OptionLeg("call", short_strike, short_premium, -1),
         OptionLeg("call", long_strike, long_premium, 1)),
        notes="Objetivo: que el subyacente cierre por debajo del strike corto.",
        book_max_profit="crédito neto recibido",
        book_max_risk="distancia entre strikes - crédito recibido",
        book_breakeven="strike del call corto + crédito recibido",
    )


@_register("bull_put_spread")
def bull_put_spread(short_strike: float, short_premium: float,
                    long_strike: float, long_premium: float) -> Strategy:
    if long_strike >= short_strike:
        raise ValueError("en un bull put spread se vende el strike superior")
    return Strategy(
        "Bull put spread (vertical de crédito con puts)", "alcista/neutral", "Cap. 5",
        (OptionLeg("put", short_strike, short_premium, -1),
         OptionLeg("put", long_strike, long_premium, 1)),
        notes="Cap. 2: vende el strike corto a ≥1 desviación estándar y exige "
              "un rendimiento mínimo del 12-15% (nunca <10%).",
        book_max_profit="crédito neto recibido",
        book_max_risk="distancia entre strikes - crédito recibido",
        book_breakeven="strike del put corto - crédito recibido",
    )


@_register("bear_put_spread")
def bear_put_spread(long_strike: float, long_premium: float,
                    short_strike: float, short_premium: float) -> Strategy:
    if short_strike >= long_strike:
        raise ValueError("en un bear put spread se compra el strike superior")
    return Strategy(
        "Bear put spread (vertical de débito con puts)", "bajista", "Cap. 5",
        (OptionLeg("put", long_strike, long_premium, 1),
         OptionLeg("put", short_strike, short_premium, -1)),
        notes="Objetivo: cerrar por debajo del strike corto a vencimiento.",
        book_max_profit="distancia entre strikes - prima pagada",
        book_max_risk="prima pagada",
        book_breakeven="strike del put largo - prima pagada",
    )


# ------------------------------------------------- Cap. 7: straddle/strangle

def _straddle_legs(strike: float, call_premium: float, put_premium: float, qty: int) -> tuple[OptionLeg, ...]:
    return (OptionLeg("call", strike, call_premium, qty), OptionLeg("put", strike, put_premium, qty))


@_register("long_straddle")
def long_straddle(strike: float, call_premium: float, put_premium: float) -> Strategy:
    return Strategy(
        "Long straddle", "volátil (dirección desconocida)", "Cap. 7",
        _straddle_legs(strike, call_premium, put_premium, 1),
        notes="Compra de movimiento: gana con un desplazamiento mayor que la "
              "prima total o con un salto de IV; paga theta cada día.",
        book_max_profit="ilimitado", book_max_risk="prima total pagada",
        book_breakeven="strike ± prima total",
    )


@_register("short_straddle")
def short_straddle(strike: float, call_premium: float, put_premium: float) -> Strategy:
    return Strategy(
        "Short straddle", "neutral (rango)", "Cap. 7",
        _straddle_legs(strike, call_premium, put_premium, -1),
        notes="Vende el movimiento; el libro advierte del riesgo gamma/delta y "
              "sugiere considerar iron spreads que lo limitan.",
        book_max_profit="prima total recibida", book_max_risk="ilimitado",
        book_breakeven="strike ± prima total",
    )


@_register("long_strangle")
def long_strangle(put_strike: float, put_premium: float,
                  call_strike: float, call_premium: float) -> Strategy:
    if put_strike >= call_strike:
        raise ValueError("el strike del put debe ser inferior al del call")
    return Strategy(
        "Long strangle", "volátil (dirección desconocida)", "Cap. 7",
        (OptionLeg("put", put_strike, put_premium, 1),
         OptionLeg("call", call_strike, call_premium, 1)),
        notes="Más barato que el straddle a cambio de breakevens más lejanos.",
        book_max_profit="ilimitado", book_max_risk="prima total pagada",
        book_breakeven="call strike + prima total / put strike - prima total",
    )


@_register("short_strangle")
def short_strangle(put_strike: float, put_premium: float,
                   call_strike: float, call_premium: float) -> Strategy:
    if put_strike >= call_strike:
        raise ValueError("el strike del put debe ser inferior al del call")
    return Strategy(
        "Short strangle", "neutral (rango)", "Cap. 7",
        (OptionLeg("put", put_strike, put_premium, -1),
         OptionLeg("call", call_strike, call_premium, -1)),
        notes="Menos gamma/delta que el short straddle, sigue con riesgo ilimitado.",
        book_max_profit="prima total recibida", book_max_risk="ilimitado",
        book_breakeven="call strike + prima total / put strike - prima total",
    )


# ------------------------------------------- Cap. 6: mariposas, cóndores, iron

def _fly_legs(kind: str, lower: tuple[float, float], center: tuple[float, float],
              upper: tuple[float, float], sign: int) -> tuple[OptionLeg, ...]:
    return (
        OptionLeg(kind, lower[0], lower[1], sign),
        OptionLeg(kind, center[0], center[1], -2 * sign),
        OptionLeg(kind, upper[0], upper[1], sign),
    )


def _check_fly(lower: float, center: float, upper: float) -> None:
    if not (lower < center < upper):
        raise ValueError("los strikes deben cumplir inferior < central < superior")


@_register("long_butterfly")
def long_butterfly(kind: str, lower_strike: float, lower_premium: float,
                   center_strike: float, center_premium: float,
                   upper_strike: float, upper_premium: float) -> Strategy:
    _check_fly(lower_strike, center_strike, upper_strike)
    return Strategy(
        "Long butterfly (1-2-1)", "neutral (clavada en el strike central)", "Cap. 6",
        _fly_legs(kind, (lower_strike, lower_premium), (center_strike, center_premium),
                  (upper_strike, upper_premium), 1),
        notes="Máximo beneficio con la acción en el strike central a vencimiento; "
              "alas anchas = más caras pero con zona de beneficio más amplia.",
        book_max_profit="distancia entre strikes - prima pagada",
        book_max_risk="prima pagada",
        book_breakeven="strike inferior + prima / strike superior - prima",
    )


@_register("short_butterfly")
def short_butterfly(kind: str, lower_strike: float, lower_premium: float,
                    center_strike: float, center_premium: float,
                    upper_strike: float, upper_premium: float) -> Strategy:
    _check_fly(lower_strike, center_strike, upper_strike)
    return Strategy(
        "Short butterfly (1-2-1)", "volátil (huir del strike central)", "Cap. 6",
        _fly_legs(kind, (lower_strike, lower_premium), (center_strike, center_premium),
                  (upper_strike, upper_premium), -1),
        notes="Gana si la acción escapa de las alas; pierde clavada en el centro.",
        book_max_profit="crédito recibido",
        book_max_risk="distancia entre strikes - crédito recibido",
        book_breakeven="strike inferior + crédito / strike superior - crédito",
    )


def _condor_legs(kind: str, strikes_premiums: tuple[tuple[float, float], ...], signs: tuple[int, ...]) -> tuple[OptionLeg, ...]:
    return tuple(OptionLeg(kind, s, p, q) for (s, p), q in zip(strikes_premiums, signs))


def _check_condor(s1: float, s2: float, s3: float, s4: float) -> None:
    if not (s1 < s2 < s3 < s4):
        raise ValueError("los cuatro strikes deben ser estrictamente crecientes")


@_register("long_condor")
def long_condor(kind: str, s1: float, p1: float, s2: float, p2: float,
                s3: float, p3: float, s4: float, p4: float) -> Strategy:
    _check_condor(s1, s2, s3, s4)
    return Strategy(
        "Long condor (1-1-1-1)", "neutral (entre strikes interiores)", "Cap. 6",
        _condor_legs(kind, ((s1, p1), (s2, p2), (s3, p3), (s4, p4)), (1, -1, -1, 1)),
        notes="Como la mariposa larga pero con meseta de beneficio entre los "
              "strikes interiores.",
        book_max_profit="envergadura del ala - prima pagada",
        book_max_risk="prima pagada",
        book_breakeven="ala inferior + prima / ala superior - prima",
    )


@_register("short_condor")
def short_condor(kind: str, s1: float, p1: float, s2: float, p2: float,
                 s3: float, p3: float, s4: float, p4: float) -> Strategy:
    _check_condor(s1, s2, s3, s4)
    return Strategy(
        "Short condor (1-1-1-1)", "volátil (fuera de strikes exteriores)", "Cap. 6",
        _condor_legs(kind, ((s1, p1), (s2, p2), (s3, p3), (s4, p4)), (-1, 1, 1, -1)),
        notes="Gana si la acción termina fuera de las alas a vencimiento.",
        book_max_profit="crédito recibido",
        book_max_risk="envergadura del ala - crédito recibido",
        book_breakeven="strike interior inferior - crédito / superior + crédito",
    )


@_register("short_iron_butterfly")
def short_iron_butterfly(center_strike: float, short_call_premium: float, short_put_premium: float,
                         wing_put_strike: float, wing_put_premium: float,
                         wing_call_strike: float, wing_call_premium: float) -> Strategy:
    if not (wing_put_strike < center_strike < wing_call_strike):
        raise ValueError("las alas deben rodear al strike central")
    return Strategy(
        "Short iron butterfly", "neutral (clavada en el strike central)", "Cap. 6",
        (
            OptionLeg("call", center_strike, short_call_premium, -1),
            OptionLeg("put", center_strike, short_put_premium, -1),
            OptionLeg("put", wing_put_strike, wing_put_premium, 1),
            OptionLeg("call", wing_call_strike, wing_call_premium, 1),
        ),
        notes="Bear-call vertical + bull-put vertical con strike central común; "
              "cobras crédito (short iron = cobrar, según el libro).",
        book_max_profit="crédito cobrado",
        book_max_risk="distancia entre strikes - crédito cobrado",
        book_breakeven="strike central ± crédito recibido",
    )


@_register("long_iron_butterfly")
def long_iron_butterfly(center_strike: float, long_call_premium: float, long_put_premium: float,
                        wing_put_strike: float, wing_put_premium: float,
                        wing_call_strike: float, wing_call_premium: float) -> Strategy:
    if not (wing_put_strike < center_strike < wing_call_strike):
        raise ValueError("las alas deben rodear al strike central")
    return Strategy(
        "Long iron butterfly", "volátil (huir del strike central)", "Cap. 6",
        (
            OptionLeg("call", center_strike, long_call_premium, 1),
            OptionLeg("put", center_strike, long_put_premium, 1),
            OptionLeg("put", wing_put_strike, wing_put_premium, -1),
            OptionLeg("call", wing_call_strike, wing_call_premium, -1),
        ),
        notes="Bull-call + bear-put con strike central común; para earnings u "
              "otro evento volátil con breakevens dentro del rango realista.",
        book_max_profit="distancia entre strikes - prima pagada",
        book_max_risk="prima pagada",
        book_breakeven="strike central ± prima pagada",
    )


@_register("short_iron_condor")
def short_iron_condor(put_wing_strike: float, put_wing_premium: float,
                      short_put_strike: float, short_put_premium: float,
                      short_call_strike: float, short_call_premium: float,
                      call_wing_strike: float, call_wing_premium: float) -> Strategy:
    _check_condor(put_wing_strike, short_put_strike, short_call_strike, call_wing_strike)
    return Strategy(
        "Short iron condor", "neutral (rango entre strikes cortos)", "Cap. 6",
        (
            OptionLeg("put", put_wing_strike, put_wing_premium, 1),
            OptionLeg("put", short_put_strike, short_put_premium, -1),
            OptionLeg("call", short_call_strike, short_call_premium, -1),
            OptionLeg("call", call_wing_strike, call_wing_premium, 1),
        ),
        notes="El libro: separa los spreads fuera de soportes/resistencias o a "
              "niveles de baja probabilidad estadística; la alta probabilidad "
              "justifica el ratio beneficio/riesgo invertido.",
        book_max_profit="crédito recibido",
        book_max_risk="envergadura del ala - crédito cobrado",
        book_breakeven="strike corto inferior - crédito / superior + crédito",
    )


@_register("long_iron_condor")
def long_iron_condor(put_wing_strike: float, put_wing_premium: float,
                     long_put_strike: float, long_put_premium: float,
                     long_call_strike: float, long_call_premium: float,
                     call_wing_strike: float, call_wing_premium: float) -> Strategy:
    _check_condor(put_wing_strike, long_put_strike, long_call_strike, call_wing_strike)
    return Strategy(
        "Long iron condor", "volátil (fuera de strikes exteriores)", "Cap. 6",
        (
            OptionLeg("put", put_wing_strike, put_wing_premium, -1),
            OptionLeg("put", long_put_strike, long_put_premium, 1),
            OptionLeg("call", long_call_strike, long_call_premium, 1),
            OptionLeg("call", call_wing_strike, call_wing_premium, -1),
        ),
        notes="Compra un call spread y un put spread alejados; cuanto más "
              "separados, más baratos pero menos probables.",
        book_max_profit="envergadura del ala - débito pagado",
        book_max_risk="débito pagado",
        book_breakeven="strike interior inferior - débito / superior + débito",
    )
