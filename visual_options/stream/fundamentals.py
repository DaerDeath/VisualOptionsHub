"""Ficha de empresa estilo Bloomberg (DES/ERN/ANR/N) con datos de Yahoo.

Gratis vía yfinance: perfil y métricas, calendario e historial de earnings
con sorpresas EPS, recomendaciones de analistas con price targets y
noticias. Además se evalúa automáticamente el checklist del Cap. 2 de
Visual Guide to Options (convicción de analistas, distancia del objetivo).

Cada sección se construye con try/except propio: si Yahoo no da un bloque
(índices y ETFs no tienen earnings, por ejemplo), el resto sigue saliendo.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta, timezone

CACHE_TTL = 600.0  # 10 min: estos datos cambian despacio y Yahoo limita
_cache: dict[str, tuple[float, dict]] = {}


def _num(value, default=None):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(value) else value


def _profile(info: dict) -> dict:
    return {
        "name": info.get("longName") or info.get("shortName") or "",
        "sector": info.get("sector") or "",
        "industry": info.get("industry") or "",
        "summary": (info.get("longBusinessSummary") or "")[:420],
        "website": info.get("website") or "",
        "employees": info.get("fullTimeEmployees"),
    }


def _short_interest(info: dict) -> dict:
    """SIA — interés en corto: % del float, ratio (días para cubrir) y tendencia."""
    shares_short = _num(info.get("sharesShort"))
    prior = _num(info.get("sharesShortPriorMonth"))
    pct_float = _num(info.get("shortPercentOfFloat"))
    trend_pct = None
    if shares_short is not None and prior:
        trend_pct = round((shares_short - prior) / prior * 100, 1)
    return {
        "shares_short": shares_short,
        "pct_float": round(pct_float * 100, 2) if pct_float is not None else None,
        "days_to_cover": _num(info.get("shortRatio")),
        "prior_month": prior,
        "trend_pct": trend_pct,
    }


def _metrics(info: dict) -> dict:
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    low52 = _num(info.get("fiftyTwoWeekLow"))
    high52 = _num(info.get("fiftyTwoWeekHigh"))
    pos52 = None
    if price and low52 and high52 and high52 > low52:
        pos52 = (price - low52) / (high52 - low52)
    return {
        "price": price,
        "market_cap": _num(info.get("marketCap")),
        "beta": _num(info.get("beta")),
        "trailing_pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")),
        "eps_ttm": _num(info.get("trailingEps")),
        "dividend_yield": _num(info.get("dividendYield")),
        "short_ratio": _num(info.get("shortRatio")),
        "avg_volume": _num(info.get("averageVolume")),
        "low52": low52, "high52": high52, "pos52": pos52,
    }


def _earnings(ticker) -> dict:
    result: dict = {"next_date": None, "days_to_next": None, "history": [],
                    "next_eps_est": None, "next_revenue_est": None}
    # calendar: próxima fecha + estimaciones (funciona sin lxml)
    try:
        calendar = ticker.calendar or {}
        dates = calendar.get("Earnings Date") or []
        if dates:
            when = min(dates)
            when_dt = datetime(when.year, when.month, when.day, tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if when_dt >= now - timedelta(days=1):
                result["next_date"] = when_dt.isoformat()
                result["days_to_next"] = round((when_dt - now).total_seconds() / 86400, 1)
        result["next_eps_est"] = _num(calendar.get("Earnings Average"))
        result["next_revenue_est"] = _num(calendar.get("Revenue Average"))
    except Exception:
        pass
    try:
        frame = ticker.earnings_dates
        if frame is not None and len(frame):
            frame = frame.reset_index()
            date_col = frame.columns[0]
            now = datetime.now(timezone.utc)
            for record in frame.to_dict("records"):
                when = record[date_col]
                if when is None:
                    continue
                when_utc = when.tz_convert("UTC") if when.tzinfo else when.tz_localize("UTC")
                estimate = _num(record.get("EPS Estimate"))
                reported = _num(record.get("Reported EPS"))
                surprise = _num(record.get("Surprise(%)"))
                if when_utc > now:
                    # la más cercana en el futuro
                    if result["next_date"] is None or when_utc < datetime.fromisoformat(result["next_date"]):
                        result["next_date"] = when_utc.isoformat()
                        result["days_to_next"] = round((when_utc - now).total_seconds() / 86400, 1)
                elif reported is not None:
                    result["history"].append({
                        "date": when_utc.strftime("%Y-%m-%d"),
                        "estimate": estimate, "reported": reported, "surprise": surprise,
                    })
            result["history"] = result["history"][:8]
    except Exception:
        pass
    return result


def _analysts(ticker, price: float | None) -> dict:
    result: dict = {"counts": None, "total": 0, "bullish_pct": None,
                    "targets": None, "target_upside_pct": None}
    try:
        summary = ticker.recommendations_summary
        if summary is not None and len(summary):
            row = summary.iloc[0]  # periodo actual (0m)
            counts = {key: int(row.get(key, 0) or 0)
                      for key in ("strongBuy", "buy", "hold", "sell", "strongSell")}
            total = sum(counts.values())
            if total:
                result["counts"] = counts
                result["total"] = total
                result["bullish_pct"] = round(100 * (counts["strongBuy"] + counts["buy"]) / total, 1)
    except Exception:
        pass
    try:
        targets = ticker.analyst_price_targets
        if targets:
            clean = {key: _num(targets.get(key)) for key in ("low", "mean", "median", "high")}
            if clean.get("mean"):
                result["targets"] = clean
                if price:
                    result["target_upside_pct"] = round((clean["mean"] - price) / price * 100, 2)
    except Exception:
        pass
    return result


def _news(ticker) -> list[dict]:
    items = []
    try:
        for raw in (ticker.news or [])[:10]:
            content = raw.get("content") or raw  # formato nuevo y viejo de yfinance
            title = content.get("title")
            if not title:
                continue
            provider = content.get("provider") or {}
            when = content.get("pubDate") or content.get("providerPublishTime") or ""
            if isinstance(when, (int, float)):
                when = datetime.fromtimestamp(when, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            elif isinstance(when, str) and len(when) >= 16:
                when = when[:16].replace("T", " ")
            link = content.get("canonicalUrl") or {}
            items.append({
                "title": title,
                "publisher": (provider.get("displayName") if isinstance(provider, dict)
                              else str(provider)) or raw.get("publisher", ""),
                "when": when,
                "url": (link.get("url") if isinstance(link, dict) else None) or raw.get("link", ""),
            })
    except Exception:
        pass
    return items


def _book_checklist(analysts: dict, earnings: dict, metrics: dict) -> list[dict]:
    """Criterios del Cap. 2/7 evaluables automáticamente con estos datos."""
    checks = []

    bullish = analysts.get("bullish_pct")
    checks.append({
        "name": "Convicción de analistas ≥85% alcistas (Cap. 7)",
        "value": f"{bullish:.0f}% buy/strongBuy de {analysts.get('total', 0)}" if bullish is not None else "sin datos",
        "verdict": "ok" if (bullish or 0) >= 85 else "warn" if (bullish or 0) >= 60 else "fail" if bullish is not None else "warn",
    })

    upside = analysts.get("target_upside_pct")
    checks.append({
        "name": "Objetivo de consenso ≥10% sobre el precio (Cap. 7)",
        "value": f"{upside:+.1f}% al objetivo medio" if upside is not None else "sin datos",
        "verdict": "ok" if (upside or -99) >= 10 else "warn" if (upside or -99) >= 0 else "fail" if upside is not None else "warn",
    })

    total = analysts.get("total", 0)
    checks.append({
        "name": "Cobertura ≥4-5 analistas (menos sorpresas inesperadas)",
        "value": f"{total} analistas",
        "verdict": "ok" if total >= 5 else "warn" if total >= 1 else "fail",
    })

    surprises = [h["surprise"] for h in earnings.get("history", []) if h.get("surprise") is not None]
    if surprises:
        beats = sum(1 for s in surprises if s > 0)
        checks.append({
            "name": "Historial de sorpresas EPS positivas",
            "value": f"batió {beats}/{len(surprises)} últimos trimestres",
            "verdict": "ok" if beats >= len(surprises) * 0.7 else "warn" if beats >= len(surprises) * 0.4 else "fail",
        })

    volume = metrics.get("avg_volume")
    if volume:
        checks.append({
            "name": "Volumen ≥750k acciones/día (Cap. 2)",
            "value": f"{volume / 1e6:.1f}M de media",
            "verdict": "ok" if volume >= 750_000 else "fail",
        })
    return checks


def company_snapshot(symbol: str) -> dict:
    symbol = symbol.upper()
    cached = _cache.get(symbol)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    import yfinance as yf
    ticker = yf.Ticker(f"^{symbol}" if symbol in ("SPX", "VIX", "NDX", "RUT") else symbol)
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    if not info.get("longName") and not info.get("shortName") and not info.get("regularMarketPrice"):
        raise ValueError(f"Yahoo no tiene ficha para {symbol}")

    metrics = _metrics(info)
    earnings = _earnings(ticker)
    analysts = _analysts(ticker, metrics.get("price"))
    snapshot = {
        "symbol": symbol,
        "profile": _profile(info),
        "metrics": metrics,
        "earnings": earnings,
        "analysts": analysts,
        "short_interest": _short_interest(info),
        "news": _news(ticker),
        "book_checklist": _book_checklist(analysts, earnings, metrics),
        "as_of": datetime.now(timezone.utc).strftime("%H:%M UTC"),
    }
    _cache[symbol] = (time.time(), snapshot)
    return snapshot
