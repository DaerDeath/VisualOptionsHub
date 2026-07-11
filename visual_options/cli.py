"""CLI `voptions`: aplica el flujo del libro desde la terminal.

Subcomandos:
  list                estrategias disponibles (Cap. 4-6)
  analyze             métricas + gráficos de una estrategia
  price               precio BSM, griegas y prob. ITM de una opción suelta
  vol                 HV desde cierres, ratio IV/HV y movimiento esperado
  grade               sistema de calificación A-F del Cap. 2
  earnings            checklist previo a earnings del Cap. 7
  chain               cadena de opciones vía IBKR (opcional, requiere ib-async)
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import sys
from pathlib import Path

from visual_options import builders as _builders  # noqa: F401  (puebla el registro)
from visual_options import grading, pricing, volatility
from visual_options.contracts import OptionLeg
from visual_options.greeks import bs_greeks
from visual_options.strategies import STRATEGY_BUILDERS, Strategy


def _autoprice_legs(strategy: Strategy, spot: float, iv: float, days: float, rate: float) -> Strategy:
    """Sustituye las primas por precios BSM manteniendo strikes y cantidades."""
    new_legs = []
    for leg in strategy.legs:
        if isinstance(leg, OptionLeg):
            premium = pricing.bs_price(leg.kind, spot, leg.strike, days, iv, rate)
            new_legs.append(dataclasses.replace(leg, premium=round(premium, 4)))
        else:
            new_legs.append(leg)
    return dataclasses.replace(strategy, legs=tuple(new_legs))


def _build_strategy(args: argparse.Namespace) -> Strategy:
    builder = STRATEGY_BUILDERS[args.strategy]
    signature = inspect.signature(builder)
    params = list(signature.parameters)
    provided = dict(pair.split("=", 1) for pair in args.param)
    unknown = set(provided) - set(params)
    if unknown:
        raise SystemExit(f"parámetros desconocidos {sorted(unknown)}; esperados: {params}")

    kwargs: dict[str, object] = {}
    for name in params:
        if name in provided:
            raw = provided[name]
            kwargs[name] = raw if name == "kind" else float(raw)
        elif name.endswith("premium") or name.startswith("p") and name[1:].isdigit():
            if not args.auto_price:
                raise SystemExit(f"falta {name}=...; usa --auto-price con --spot/--iv/--days para estimarla")
            kwargs[name] = 0.0
        else:
            raise SystemExit(f"falta el parámetro obligatorio {name}=...")

    strategy = builder(**kwargs)
    if args.auto_price:
        if args.spot is None or args.iv is None or args.days is None:
            raise SystemExit("--auto-price requiere --spot, --iv y --days")
        strategy = _autoprice_legs(strategy, args.spot, args.iv, args.days, args.rate)
    return strategy


def cmd_list(_: argparse.Namespace) -> None:
    print("Estrategias del libro (Cap. 4-7) y sus parámetros:\n")
    for key, builder in sorted(STRATEGY_BUILDERS.items()):
        params = inspect.signature(builder).parameters
        print(f"{key:24} — {', '.join(params)}")


def cmd_analyze(args: argparse.Namespace) -> None:
    strategy = _build_strategy(args)
    print(strategy.summary(spot=args.spot, iv=args.iv, days=args.days))
    if args.plot:
        from visual_options.plotting import plot_payoff
        out = plot_payoff(strategy, args.plot, spot=args.spot, iv=args.iv, days=args.days)
        print(f"Gráfico P/L guardado en {out}")
    if args.greeks_plot:
        if args.spot is None or args.iv is None or args.days is None:
            raise SystemExit("--greeks-plot requiere --spot, --iv y --days")
        from visual_options.plotting import plot_greeks
        out = plot_greeks(strategy, args.greeks_plot, args.spot, args.iv, args.days, args.rate)
        print(f"Gráfico de griegas guardado en {out}")


def cmd_price(args: argparse.Namespace) -> None:
    price = pricing.bs_price(args.kind, args.spot, args.strike, args.days, args.iv, args.rate)
    greeks = bs_greeks(args.kind, args.spot, args.strike, args.days, args.iv, args.rate)
    prob = pricing.probability_itm(args.kind, args.spot, args.strike, args.days, args.iv, args.rate)
    move = pricing.expected_move(args.spot, args.iv, args.days)
    print(f"Precio BSM      : {price:.4f}")
    print(f"Delta {greeks.delta:+.4f}  Gamma {greeks.gamma:+.5f}  Theta {greeks.theta:+.5f}/día  "
          f"Vega {greeks.vega:+.5f}/1%  Rho {greeks.rho:+.5f}/1%")
    print(f"Prob. ITM       : {prob:.1%}")
    print(f"Mov. esperado 1σ: ±{move:.2f} ({move / args.spot:.1%})  [libro: 1σ ≈ 68-70%]")


def cmd_vol(args: argparse.Namespace) -> None:
    closes = [float(line.strip()) for line in Path(args.closes).read_text().splitlines()
              if line.strip() and not line.startswith("#")]
    hv = volatility.historical_volatility(closes, window=args.window)
    print(f"HV ({args.window or len(closes) - 1} sesiones): {hv:.1%}")
    if args.iv is not None:
        ratio = volatility.iv_hv_ratio(args.iv, hv)
        bias = volatility.volatility_bias(args.iv, hv)
        print(f"IV {args.iv:.1%} → ratio IV/HV {ratio:.2f} → sesgo del libro: {bias} de prima")
        if args.days:
            move = pricing.expected_move(closes[-1], args.iv, args.days)
            print(f"Movimiento esperado 1σ a {args.days:.0f} días: ±{move:.2f}")


def cmd_grade(args: argparse.Namespace) -> None:
    if args.show_criteria:
        for key, label in grading.CHECKLIST_CRITERIA:
            print(f"{key:18} {label}")
        return
    failed_keys = [k.strip() for k in (args.fail or "").split(",") if k.strip()]
    criteria = {key: key not in failed_keys for key, _ in grading.CHECKLIST_CRITERIA}
    result = grading.grade_trade(criteria)
    print(result.summary())
    if args.account:
        lo, hi = result.allocation
        print(f"Con una cuenta de ${args.account:,.0f}: arriesga entre ${args.account * lo:,.0f} y ${args.account * hi:,.0f}")


def cmd_earnings(args: argparse.Namespace) -> None:
    print("Checklist previo a earnings (Cap. 7):")
    for i, item in enumerate(grading.EARNINGS_CHECKLIST, 1):
        print(f" {i:2}. {item}")
    if args.spot and args.avg_move:
        target = grading.earnings_breakeven_target(args.spot, args.avg_move, bullish=not args.bearish)
        side = "≤" if not args.bearish else "≥"
        print(f"\nRegla de breakeven: con spot {args.spot:.2f} y movimiento medio {args.avg_move:.0%}, "
              f"sitúa tu breakeven {side} {target:.2f}")


def cmd_chain(args: argparse.Namespace) -> None:
    from visual_options.data.ibkr import fetch_chain_summary
    fetch_chain_summary(args.symbol, host=args.host, port=args.port, expiries=args.expiries)


def cmd_stream(args: argparse.Namespace) -> None:
    from visual_options.stream.server import run_server
    run_server(mode=args.mode, web_port=args.web_port,
               ib_host=args.host, ib_port=args.port, seed=args.seed,
               tradier_token=args.tradier_token, tradier_env=args.tradier_env)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="voptions",
                                     description="Toolkit basado en Visual Guide to Options (Jared Levy)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="lista las estrategias del libro")
    p_list.set_defaults(func=cmd_list)

    p_an = sub.add_parser("analyze", help="analiza una estrategia")
    p_an.add_argument("strategy", choices=sorted(STRATEGY_BUILDERS))
    p_an.add_argument("param", nargs="*", help="parámetros nombre=valor (ver `voptions list`)")
    p_an.add_argument("--spot", type=float)
    p_an.add_argument("--iv", type=float, help="volatilidad implícita, p.ej. 0.30")
    p_an.add_argument("--days", type=float, help="días a expiración")
    p_an.add_argument("--rate", type=float, default=0.04)
    p_an.add_argument("--auto-price", action="store_true",
                      help="estima las primas con BSM (requiere --spot/--iv/--days)")
    p_an.add_argument("--plot", help="ruta PNG para el diagrama P/L")
    p_an.add_argument("--greeks-plot", help="ruta PNG para los perfiles de griegas")
    p_an.set_defaults(func=cmd_analyze)

    p_pr = sub.add_parser("price", help="precio BSM y griegas de una opción")
    p_pr.add_argument("kind", choices=["call", "put"])
    p_pr.add_argument("--spot", type=float, required=True)
    p_pr.add_argument("--strike", type=float, required=True)
    p_pr.add_argument("--days", type=float, required=True)
    p_pr.add_argument("--iv", type=float, required=True)
    p_pr.add_argument("--rate", type=float, default=0.04)
    p_pr.set_defaults(func=cmd_price)

    p_vol = sub.add_parser("vol", help="HV desde un fichero de cierres (uno por línea)")
    p_vol.add_argument("closes", help="fichero de precios de cierre")
    p_vol.add_argument("--window", type=int, help="sesiones a usar (p.ej. 30)")
    p_vol.add_argument("--iv", type=float, help="IV actual para comparar")
    p_vol.add_argument("--days", type=float, help="días para el movimiento esperado")
    p_vol.set_defaults(func=cmd_vol)

    p_gr = sub.add_parser("grade", help="sistema de calificación A-F del Cap. 2")
    p_gr.add_argument("--fail", help="criterios NO cumplidos, separados por comas")
    p_gr.add_argument("--show-criteria", action="store_true", help="muestra las claves de criterios")
    p_gr.add_argument("--account", type=float, help="tamaño de cuenta para dimensionar el riesgo")
    p_gr.set_defaults(func=cmd_grade)

    p_ea = sub.add_parser("earnings", help="checklist de earnings del Cap. 7")
    p_ea.add_argument("--spot", type=float)
    p_ea.add_argument("--avg-move", type=float, help="movimiento medio histórico en earnings, p.ej. 0.10")
    p_ea.add_argument("--bearish", action="store_true")
    p_ea.set_defaults(func=cmd_earnings)

    p_ch = sub.add_parser("chain", help="cadena de opciones desde IBKR (pip install .[ibkr])")
    p_ch.add_argument("symbol")
    p_ch.add_argument("--host", default="127.0.0.1")
    p_ch.add_argument("--port", type=int, default=7496, help="7496 real TWS (por defecto), 7497 paper, 4001/4002 Gateway")
    p_ch.add_argument("--expiries", type=int, default=2, help="número de vencimientos a mostrar")
    p_ch.set_defaults(func=cmd_chain)

    p_st = sub.add_parser("stream", help="dashboard web multi-vista (flujo de opciones, footprint…)")
    p_st.add_argument("--mode", choices=["sim", "yfinance", "tradier", "tradier-delayed", "ibkr"], default="sim",
                      help="fuente POR DEFECTO (todas quedan disponibles y se cambian desde la web)")
    p_st.add_argument("--web-port", type=int, default=8000)
    p_st.add_argument("--host", default="127.0.0.1", help="host de TWS/Gateway (modo ibkr)")
    p_st.add_argument("--port", type=int, default=7496,
                      help="puerto de TWS/Gateway: 7496 real (por defecto), 7497 paper")
    p_st.add_argument("--seed", type=int, help="semilla del simulador (reproducible)")
    p_st.add_argument("--tradier-token", help="token de Tradier (por defecto: env TRADIER_TOKEN)")
    p_st.add_argument("--tradier-env", choices=["sandbox", "prod"], default="sandbox",
                      help="sandbox = gratis con ~15 min de retraso; prod = cuenta de broker")
    p_st.set_defaults(func=cmd_stream)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
