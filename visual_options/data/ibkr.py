"""Feed opcional de datos desde Interactive Brokers (TWS API vía ib-async).

Requiere `pip install visual-options[ibkr]` y TWS o IB Gateway corriendo
con la API activada. IBKR calcula y envía las griegas y la IV en los ticks
OptionComputation, así que no hay que calcularlas localmente.
"""

from __future__ import annotations


def _require_ib():
    try:
        from ib_async import IB, Index, Option, Stock  # noqa: F401
        return IB, Stock, Option
    except ImportError as exc:
        raise SystemExit(
            "ib-async no está instalado; instala con: pip install 'visual-options[ibkr]'"
        ) from exc


def fetch_chain_summary(symbol: str, host: str = "127.0.0.1", port: int = 7496,
                        client_id: int = 17, expiries: int = 2, strikes_around: int = 6) -> None:
    """Imprime un resumen de la cadena: strikes ATM ± N para los próximos vencimientos."""
    IB, Stock, Option = _require_ib()
    ib = IB()
    ib.connect(host, port, clientId=client_id, timeout=10)
    try:
        stock = Stock(symbol.upper(), "SMART", "USD")
        ib.qualifyContracts(stock)
        ticker = ib.reqTickers(stock)[0]
        spot = ticker.marketPrice()
        print(f"{symbol.upper()} spot: {spot:.2f}")

        chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
        chain = next(c for c in chains if c.exchange == "SMART")
        expirations = sorted(chain.expirations)[:expiries]
        all_strikes = sorted(chain.strikes)
        atm_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - spot))
        lo = max(0, atm_idx - strikes_around)
        strikes = all_strikes[lo: atm_idx + strikes_around + 1]

        for expiry in expirations:
            print(f"\nVencimiento {expiry}:")
            contracts = [Option(symbol.upper(), expiry, k, right, "SMART", currency="USD")
                         for k in strikes for right in ("C", "P")]
            contracts = ib.qualifyContracts(*contracts)
            tickers = ib.reqTickers(*contracts)
            print(f"{'strike':>8} {'tipo':>4} {'bid':>8} {'ask':>8} {'IV':>7} {'delta':>7}")
            for t in sorted(tickers, key=lambda t: (t.contract.strike, t.contract.right)):
                greeks = t.modelGreeks
                iv = f"{greeks.impliedVol:.1%}" if greeks and greeks.impliedVol else "—"
                delta = f"{greeks.delta:+.3f}" if greeks and greeks.delta is not None else "—"
                print(f"{t.contract.strike:8.2f} {t.contract.right:>4} "
                      f"{t.bid if t.bid > 0 else float('nan'):8.2f} "
                      f"{t.ask if t.ask > 0 else float('nan'):8.2f} {iv:>7} {delta:>7}")
    finally:
        ib.disconnect()
