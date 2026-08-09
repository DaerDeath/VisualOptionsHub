"""Portafolio real: posiciones, P&L y griegas agregadas — SOLO LECTURA.

No coloca ni modifica ninguna orden; solo lee lo que ya tienes abierto en
tu cuenta. Dos fuentes con cuenta real: IBKR (vía ib_async, P&L calculado
por el propio TWS) y Tradier (vía REST, con griegas ORATS por posición).
"""

from __future__ import annotations

import asyncio
import math

TRADIER_URLS = {"sandbox": "https://sandbox.tradier.com/v1", "prod": "https://api.tradier.com/v1"}


def _num(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else value


def empty_totals() -> dict:
    return {"market_value": 0.0, "unrealized_pnl": 0.0,
            "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}


def _accumulate(totals: dict, position: dict) -> None:
    totals["market_value"] += position.get("market_value") or 0.0
    totals["unrealized_pnl"] += position.get("unrealized_pnl") or 0.0
    for greek in ("delta", "gamma", "theta", "vega"):
        totals[greek] += position.get(greek) or 0.0


# ------------------------------------------------------------------ IBKR

async def ibkr_portfolio(host: str = "127.0.0.1", port: int = 7496,
                         client_id: int = 77) -> dict:  # pragma: no cover — necesita TWS en vivo
    """P&L calculado por el propio TWS (PortfolioItem); no se reinventa."""
    from ib_async import IB

    ib = IB()
    await ib.connectAsync(host, port, clientId=client_id, timeout=15)
    account = ""
    try:
        accounts = ib.managedAccounts()
        account = accounts[0] if accounts else ""
        ib.reqAccountUpdates(True, account)
        await asyncio.sleep(1.5)  # deja llegar los eventos de account/portfolio

        summary = {av.tag: av.value for av in ib.accountValues(account)
                  if av.currency in ("USD", "BASE")}
        items = ib.portfolio(account) if account else ib.portfolio()

        positions = [_shape_ibkr_item(item) for item in items]
        option_positions = [(p, item) for p, item in zip(positions, items)
                            if item.contract.secType == "OPT"]
        if option_positions:
            tickers = [(p, ib.reqMktData(item.contract, "106", False, False))
                      for p, item in option_positions]
            await asyncio.sleep(2.0)
            for p, ticker in tickers:
                _apply_greeks(p, ticker.modelGreeks)
                ib.cancelMktData(ticker.contract)

        totals = empty_totals()
        for p in positions:
            _accumulate(totals, p)

        return {
            "source": "ibkr", "account": account,
            "net_liquidation": _num(summary.get("NetLiquidation")),
            "buying_power": _num(summary.get("BuyingPower")),
            "total_cash": _num(summary.get("TotalCashValue")),
            "positions": positions,
            "totals": {k: round(v, 4) for k, v in totals.items()},
        }
    finally:
        try:
            ib.reqAccountUpdates(False, account)
        except Exception:
            pass
        ib.disconnect()


def _shape_ibkr_item(item) -> dict:  # pragma: no cover — depende del tipo Contract de ib_async
    c = item.contract
    right = getattr(c, "right", "") or ""
    kind = "stock" if c.secType == "STK" else ("call" if right == "C" else "put" if right == "P" else c.secType.lower())
    avg_cost = _num(item.averageCost) or 0.0
    qty = _num(item.position) or 0.0
    cost_basis = abs(avg_cost * qty)
    return {
        "symbol": c.symbol, "kind": kind,
        "strike": _num(getattr(c, "strike", None)),
        "expiry": getattr(c, "lastTradeDateOrContractMonth", "") or None,
        "qty": qty, "avg_cost": round(avg_cost, 4),
        "price": round(_num(item.marketPrice) or 0.0, 4),
        "market_value": round(_num(item.marketValue) or 0.0, 2),
        "unrealized_pnl": round(_num(item.unrealizedPNL) or 0.0, 2),
        "unrealized_pnl_pct": round((_num(item.unrealizedPNL) or 0.0) / cost_basis * 100, 2) if cost_basis else None,
        "delta": None, "gamma": None, "theta": None, "vega": None,
    }


def _apply_greeks(position: dict, model_greeks) -> None:  # pragma: no cover
    if not model_greeks:
        return
    mult = 100 * position["qty"]
    position["delta"] = round((model_greeks.delta or 0.0) * mult, 3)
    position["gamma"] = round((model_greeks.gamma or 0.0) * mult, 4)
    position["theta"] = round((model_greeks.theta or 0.0) * position["qty"], 3)
    position["vega"] = round((model_greeks.vega or 0.0) * mult / 100, 3)


# --------------------------------------------------------------- Tradier

async def resolve_tradier_account(client, base: str) -> str:
    """Primer account_number del perfil — compartido por posiciones,
    órdenes y gainloss (todas necesitan el mismo id de cuenta)."""
    profile = (await client.get(f"{base}/user/profile")).json()
    accounts = profile.get("profile", {}).get("account") or []
    if isinstance(accounts, dict):
        accounts = [accounts]
    if not accounts:
        raise ValueError("la cuenta de Tradier no tiene accounts en el perfil")
    return accounts[0]["account_number"]


async def tradier_portfolio(token: str, env: str = "prod", client=None) -> dict:
    """`client` inyectable (httpx.AsyncClient) para tests."""
    import httpx
    base = TRADIER_URLS.get(env, TRADIER_URLS["prod"])
    owns_client = client is None
    client = client or httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=15.0)
    try:
        account_id = await resolve_tradier_account(client, base)

        balances = (await client.get(f"{base}/accounts/{account_id}/balances")).json()
        balances = balances.get("balances", {})

        raw = (await client.get(f"{base}/accounts/{account_id}/positions")).json()
        items = (raw.get("positions") or {}).get("position") or []
        if isinstance(items, dict):
            items = [items]

        quotes = {}
        if items:
            symbols = ",".join(item["symbol"] for item in items)
            data = (await client.get(f"{base}/markets/quotes",
                                     params={"symbols": symbols, "greeks": "true"})).json()
            quote_list = data.get("quotes", {}).get("quote") or []
            if isinstance(quote_list, dict):
                quote_list = [quote_list]
            quotes = {q["symbol"]: q for q in quote_list}

        positions = [_shape_tradier_position(item, quotes.get(item["symbol"], {})) for item in items]
        totals = empty_totals()
        for p in positions:
            _accumulate(totals, p)

        return {
            "source": "tradier", "account": account_id,
            "net_liquidation": _num(balances.get("total_equity")),
            "buying_power": _num((balances.get("margin") or {}).get("stock_buying_power")
                                 or (balances.get("cash") or {}).get("cash_available")),
            "total_cash": _num(balances.get("total_cash")),
            "positions": positions,
            "totals": {k: round(v, 4) for k, v in totals.items()},
        }
    finally:
        if owns_client:
            await client.aclose()


def _shape_tradier_position(item: dict, quote: dict) -> dict:
    qty = _num(item.get("quantity")) or 0.0
    cost_basis = _num(item.get("cost_basis")) or 0.0
    is_option = quote.get("option_type") is not None or quote.get("type") == "option"
    multiplier = 100.0 if is_option else 1.0
    price = _num(quote.get("last")) or _num(quote.get("close")) or 0.0
    market_value = round(price * qty * multiplier, 2)
    unrealized = round(market_value - cost_basis, 2)
    greeks = quote.get("greeks") or {}

    position = {
        "symbol": quote.get("underlying") or item.get("symbol", "").rstrip("0123456789CP")[:6].strip()
                 if is_option else item.get("symbol"),
        "kind": "call" if quote.get("option_type") == "call" else
                "put" if quote.get("option_type") == "put" else "stock",
        "strike": _num(quote.get("strike")),
        "expiry": quote.get("expiration_date"),
        "qty": qty, "avg_cost": round(cost_basis / qty, 4) if qty else 0.0,
        "price": round(price, 4), "market_value": market_value,
        "unrealized_pnl": unrealized,
        "unrealized_pnl_pct": round(unrealized / abs(cost_basis) * 100, 2) if cost_basis else None,
        "delta": None, "gamma": None, "theta": None, "vega": None,
    }
    if is_option and greeks:
        mult = 100 * qty
        delta = _num(greeks.get("delta"))
        gamma = _num(greeks.get("gamma"))
        theta = _num(greeks.get("theta"))
        vega = _num(greeks.get("vega"))
        if delta is not None:
            position["delta"] = round(delta * mult, 3)
        if gamma is not None:
            position["gamma"] = round(gamma * mult, 4)
        if theta is not None:
            position["theta"] = round(theta * qty, 3)
        if vega is not None:
            position["vega"] = round(vega * mult / 100, 3)
    return position
