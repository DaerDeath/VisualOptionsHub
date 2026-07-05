"""Calculadora de estrategias para la web (Options Calculator).

Expone el motor del toolkit (las 23 estrategias del libro con payoff,
breakevens, prob. de beneficio y griegas) como datos serializables para
el frontend. Las primas pueden venir dadas o estimarse con BSM
(auto-precio) a partir de spot/IV/días.
"""

from __future__ import annotations

import dataclasses
import inspect
import math

import numpy as np

from visual_options import builders as _builders  # noqa: F401 (puebla el registro)
from visual_options.contracts import OptionLeg
from visual_options.pricing import bs_price
from visual_options.strategies import STRATEGY_BUILDERS, Strategy

CURVE_POINTS = 220


def strategy_catalog() -> list[dict]:
    """Lista de estrategias con sus parámetros para construir el formulario."""
    catalog = []
    for name, builder in sorted(STRATEGY_BUILDERS.items()):
        params = list(inspect.signature(builder).parameters)
        catalog.append({"id": name, "params": params})
    return catalog


def build_strategy(name: str, params: dict[str, str], *, auto_price: bool,
                   spot: float | None, iv: float | None, days: float | None,
                   rate: float = 0.04) -> Strategy:
    builder = STRATEGY_BUILDERS.get(name)
    if builder is None:
        raise ValueError(f"estrategia desconocida: {name}")
    signature = inspect.signature(builder)
    kwargs: dict[str, object] = {}
    for param in signature.parameters:
        if param in params and params[param] != "":
            kwargs[param] = params[param] if param == "kind" else float(params[param])
        elif param.endswith("premium") or (param.startswith("p") and param[1:].isdigit()):
            if not auto_price:
                raise ValueError(f"falta el parámetro {param} (o activa el auto-precio)")
            kwargs[param] = 0.0
        else:
            raise ValueError(f"falta el parámetro {param}")
    strategy = builder(**kwargs)
    if auto_price:
        if spot is None or iv is None or days is None:
            raise ValueError("el auto-precio necesita spot, IV y días")
        legs = []
        for leg in strategy.legs:
            if isinstance(leg, OptionLeg):
                premium = bs_price(leg.kind, spot, leg.strike, days, iv, rate)
                legs.append(dataclasses.replace(leg, premium=round(premium, 4)))
            else:
                legs.append(leg)
        strategy = dataclasses.replace(strategy, legs=tuple(legs))
    return strategy


def analyze(strategy: Strategy, *, spot: float | None, iv: float | None,
            days: float | None, rate: float = 0.04) -> dict:
    """Métricas + curvas de payoff (expiración y T+0) listas para canvas."""
    strikes = [leg.strike for leg in strategy.legs if isinstance(leg, OptionLeg)]
    anchors = strikes or [spot or 100.0]
    if spot:
        anchors = [*anchors, spot]
    lo, hi = min(anchors) * 0.85, max(anchors) * 1.15
    spots = np.linspace(lo, hi, CURVE_POINTS)
    payoff = np.asarray(strategy.payoff(spots)) * 100.0

    result = {
        "name": strategy.name,
        "sentiment": strategy.sentiment,
        "chapter": strategy.chapter,
        "notes": strategy.notes,
        "net_premium": round(strategy.net_premium(), 4),
        "max_profit": None if math.isinf(strategy.max_profit()) else round(strategy.max_profit() * 100, 2),
        "max_loss": None if math.isinf(strategy.max_loss()) else round(strategy.max_loss() * 100, 2),
        "breakevens": [round(b, 2) for b in strategy.breakevens()],
        "legs": [
            {"kind": leg.kind, "strike": leg.strike, "premium": leg.premium,
             "quantity": leg.quantity} if isinstance(leg, OptionLeg)
            else {"kind": "stock", "cost_basis": leg.cost_basis, "quantity": leg.quantity}
            for leg in strategy.legs
        ],
        "curve": {
            "spots": [round(float(s), 3) for s in spots],
            "payoff": [round(float(v), 2) for v in payoff],
        },
    }
    if spot is not None and iv is not None and days is not None and days > 0 and iv > 0:
        t0 = [round(strategy.value_at(float(s), days, iv, rate) * 100.0, 2) for s in spots]
        greeks = strategy.position_greeks(spot, days, iv, rate)
        result["curve"]["t0"] = t0
        result["pop"] = round(strategy.probability_of_profit(spot, iv, days, rate), 4)
        result["greeks"] = {
            "delta": round(greeks.delta, 4), "gamma": round(greeks.gamma, 5),
            "theta": round(greeks.theta, 5), "vega": round(greeks.vega, 5),
        }
    return result
