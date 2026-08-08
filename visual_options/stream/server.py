"""Servidor del dashboard multi-símbolo y multi-fuente: SPA + REST + WebSocket.

Todas las fuentes disponibles se registran al arrancar y el usuario elige
en la propia web con qué proveedor alimentar cada vista:

  sim              simulador de sesión (siempre disponible)
  tradier          API de Tradier en tiempo real (cuenta de broker, env prod)
  tradier-delayed  API de Tradier sandbox (~15 min de retraso, gratis)
  ibkr             TWS/IB Gateway en vivo (uv sync --extra ibkr)

Las fuentes de Tradier requieren token (TRADIER_TOKEN o --tradier-token).
`--mode` fija solo la fuente por defecto.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from visual_options.stream.manager import SessionManager, SimFeed

WEB_DIR = Path(__file__).parent / "web"

SOURCE_LABELS = {
    "sim": "Simulación",
    "yfinance": "Yahoo",
    "tradier": "Tradier",
    "tradier-delayed": "Tradier 15m",
    "ibkr": "IBKR",
}


def build_sources(*, seed: int | None = None, ib_host: str = "127.0.0.1", ib_port: int = 7496,
                  tradier_token: str | None = None) -> tuple[dict, list[dict]]:
    """Devuelve (factories disponibles, catálogo para /api/config)."""
    token = tradier_token or os.environ.get("TRADIER_TOKEN", "")
    has_ib = importlib.util.find_spec("ib_async") is not None

    factories: dict[str, object] = {
        "sim": lambda symbol, expiry=0: SimFeed(symbol, seed=seed, expiry_index=expiry)}
    catalog: list[dict] = [
        {"id": "sim", "label": SOURCE_LABELS["sim"], "available": True, "reason": ""}]

    if importlib.util.find_spec("yfinance") is not None:
        from visual_options.stream.yfinance_feed import YFinanceFeed
        factories["yfinance"] = lambda symbol, expiry=0: YFinanceFeed(symbol, expiry_index=expiry)
        catalog.append({"id": "yfinance", "label": SOURCE_LABELS["yfinance"], "available": True,
                        "reason": "datos reales de Yahoo Finance (~15 min de retraso, sin token)"})
    else:
        catalog.append({"id": "yfinance", "label": SOURCE_LABELS["yfinance"], "available": False,
                        "reason": "instala yfinance (uv sync)"})

    for source, env in (("tradier", "prod"), ("tradier-delayed", "sandbox")):
        if token:
            from visual_options.stream.tradier_feed import TradierFeed
            factories[source] = (lambda environment: lambda symbol, expiry=0: TradierFeed(
                symbol, token=token, env=environment, expiry_index=expiry))(env)
            catalog.append({"id": source, "label": SOURCE_LABELS[source],
                            "available": True, "reason": ""})
        else:
            catalog.append({"id": source, "label": SOURCE_LABELS[source], "available": False,
                            "reason": "falta TRADIER_TOKEN (o --tradier-token)"})

    if has_ib:
        from visual_options.stream.ibkr_feed import IBKRFeed
        factories["ibkr"] = lambda symbol, expiry=0: IBKRFeed(
            symbol, host=ib_host, port=ib_port, expiry_index=expiry)
        catalog.append({"id": "ibkr", "label": SOURCE_LABELS["ibkr"], "available": True,
                        "reason": "requiere TWS/IB Gateway corriendo"})
    else:
        catalog.append({"id": "ibkr", "label": SOURCE_LABELS["ibkr"], "available": False,
                        "reason": "instala con: uv sync --extra ibkr"})

    return factories, catalog


def create_app(mode: str = "sim", *, seed: int | None = None, ib_host: str = "127.0.0.1",
               ib_port: int = 7496, tradier_token: str | None = None,
               tradier_env: str = "sandbox", db_path: str | None = None) -> FastAPI:
    if mode == "tradier" and tradier_env == "sandbox":
        mode = "tradier-delayed"
    factories, catalog = build_sources(seed=seed, ib_host=ib_host, ib_port=ib_port,
                                       tradier_token=tradier_token)
    if mode not in SOURCE_LABELS:
        raise ValueError(f"modo desconocido: {mode!r} (usa {list(SOURCE_LABELS)})")
    if mode not in factories:
        reason = next(s["reason"] for s in catalog if s["id"] == mode)
        raise SystemExit(f"la fuente por defecto {mode!r} no está disponible: {reason}")
    from visual_options.stream.alerts_engine import AlertEngine
    from visual_options.stream.persistence import Recorder
    recorder = Recorder(db_path)
    alert_engine = AlertEngine(db_path)
    manager = SessionManager(factories, default_source=mode, recorder=recorder,
                             alert_engine=alert_engine)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await manager.shutdown()
        recorder.close()
        alert_engine.close()

    app = FastAPI(title="visual-options stream", lifespan=lifespan)
    app.state.manager = manager

    def resolve_source(source: str | None) -> str:
        source = source or manager.default_source
        if source not in factories:
            raise HTTPException(status_code=400, detail=f"fuente no disponible: {source}")
        return source

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/config")
    async def config() -> dict:
        return {"default": manager.default_source, "sources": catalog}

    @app.get("/api/snapshot")
    async def snapshot(symbol: str = "QQQ", source: str | None = None,
                       expiry: int = 0) -> dict:
        session = await manager.session_for(symbol, resolve_source(source), expiry)
        return {
            "flow": session.feed.state.snapshot(),
            "footprint": session.feed.footprint.snapshot(),
        }

    @app.get("/api/backtest")
    async def backtest_endpoint(symbol: str = "QQQ", otm_pct: float = 3.0,
                                dte: int = 5, years: int = 2) -> dict:
        import asyncio as _asyncio

        from visual_options.stream import backtest as bt
        try:
            return await _asyncio.to_thread(bt.run_backtest, symbol.upper(),
                                            otm_pct, dte, years)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga falló: {exc}")

    @app.get("/api/alerts")
    async def alerts_list() -> dict:
        return {"active": alert_engine.active(), "log": alert_engine.log(),
                "desktop": alert_engine.notify_cmd is not None}

    @app.post("/api/alerts")
    async def alerts_create(body: dict) -> dict:
        try:
            return alert_engine.create(body.get("symbol", "QQQ"), body.get("type", ""),
                                       body.get("value"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.delete("/api/alerts/{alert_id}")
    async def alerts_delete(alert_id: int) -> dict:
        alert_engine.delete(alert_id)
        return {"ok": True}

    @app.delete("/api/alerts/log")
    async def alerts_clear_log() -> dict:
        alert_engine.clear_log()
        return {"ok": True}

    @app.get("/api/replay/days")
    async def replay_days(symbol: str = "QQQ") -> list[dict]:
        return recorder.days(symbol)

    @app.get("/api/replay")
    async def replay_get(symbol: str, day: str, source: str = "sim",
                         expiry: int = 0, i: int = 0) -> dict:
        snapshot = recorder.get(symbol, day, source, expiry, i)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="sesión no grabada")
        return snapshot

    @app.get("/api/expirations")
    async def expirations(symbol: str = "QQQ", source: str | None = None) -> list[dict]:
        """Vencimientos elegibles para el dropdown. Con fuentes reales usa el
        calendario de Yahoo (coincide con el de OCC); en sim, etiquetas fijas."""
        resolved = resolve_source(source)
        if resolved == "sim":
            from visual_options.stream.sim import SessionSimulator
            return [{"index": i, "label": f"~{int(d)}d"}
                    for i, d in enumerate(SessionSimulator.EXPIRY_DAYS_BY_INDEX[:6])]
        import asyncio as _asyncio

        def fetch() -> list[dict]:
            import yfinance as yf
            ticker = yf.Ticker(f"^{symbol.upper()}" if symbol.upper() in ("SPX", "VIX", "NDX", "RUT")
                               else symbol.upper())
            return [{"index": i, "label": date} for i, date in enumerate(ticker.options[:9])]

        try:
            return await _asyncio.to_thread(fetch)
        except Exception:
            return [{"index": i, "label": f"vencimiento #{i + 1}"} for i in range(4)]

    @app.get("/api/calculator/strategies")
    async def calculator_strategies() -> list[dict]:
        from visual_options.stream.calculator import strategy_catalog
        return strategy_catalog()

    @app.get("/api/calculator")
    async def calculator(strategy: str, params: str = "", auto_price: bool = False,
                         spot: float | None = None, iv: float | None = None,
                         days: float | None = None, rate: float = 0.04) -> dict:
        """params: pares nombre=valor separados por comas."""
        from visual_options.stream.calculator import analyze, build_strategy
        parsed = dict(pair.split("=", 1) for pair in params.split(",") if "=" in pair)
        try:
            built = build_strategy(strategy, parsed, auto_price=auto_price,
                                   spot=spot, iv=iv, days=days, rate=rate)
            return analyze(built, spot=spot, iv=iv, days=days, rate=rate)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/stats")
    async def stats_endpoint(symbol: str = "QQQ", interval: str = "15m") -> dict:
        import asyncio as _asyncio

        from visual_options.stream import stats as stats_mod
        if interval not in stats_mod.PERIOD_FOR_INTERVAL:
            raise HTTPException(status_code=400, detail=f"intervalo no soportado: {interval}")
        try:
            return await _asyncio.to_thread(stats_mod.analyze, symbol.upper(), interval)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga de datos falló: {exc}")

    @app.get("/api/stats/montecarlo")
    async def montecarlo_endpoint(symbol: str = "QQQ", interval: str = "15m",
                                  horizon: int = 96, paths: int = 2000,
                                  bootstrap: bool = True) -> dict:
        import asyncio as _asyncio

        from visual_options.stream import stats as stats_mod

        def run() -> dict:
            returns, last_price = stats_mod.fetch_log_returns(symbol.upper(), interval)
            return stats_mod.monte_carlo(returns, last_price,
                                         horizon=min(max(horizon, 8), 500),
                                         paths=min(max(paths, 200), 10000),
                                         bootstrap=bootstrap)

        try:
            return await _asyncio.to_thread(run)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga de datos falló: {exc}")

    @app.get("/api/company")
    async def company_endpoint(symbol: str = "QQQ") -> dict:
        import asyncio as _asyncio

        from visual_options.stream import fundamentals
        try:
            return await _asyncio.to_thread(fundamentals.company_snapshot, symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga de ficha falló: {exc}")

    @app.get("/api/term-structure")
    async def term_structure_endpoint(symbol: str = "QQQ") -> dict:
        import asyncio as _asyncio

        from visual_options.stream import structure
        try:
            return await _asyncio.to_thread(structure.term_structure, symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga falló: {exc}")

    @app.get("/api/vol-cone")
    async def vol_cone_endpoint(symbol: str = "QQQ", years: int = 2) -> dict:
        import asyncio as _asyncio

        from visual_options.stream import structure
        try:
            return await _asyncio.to_thread(structure.vol_cone, symbol, years)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga falló: {exc}")

    @app.get("/api/correlation")
    async def correlation_endpoint(symbol: str = "QQQ", peers: str | None = None,
                                   days: int = 90) -> dict:
        import asyncio as _asyncio

        from visual_options.stream import structure
        peer_tuple = tuple(p.strip().upper() for p in peers.split(",") if p.strip()) \
            if peers else structure.DEFAULT_PEERS
        try:
            return await _asyncio.to_thread(structure.correlation, symbol, peer_tuple, days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga falló: {exc}")

    @app.get("/api/notebooks")
    async def notebooks_endpoint(symbol: str = "ES=F", variant: str = "daily") -> dict:
        import asyncio as _asyncio

        from visual_options.stream import notebooks as nb_mod
        try:
            return await _asyncio.to_thread(nb_mod.original_projection, symbol.upper(), variant)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"descarga o ajuste falló: {exc}")

    @app.get("/api/scan")
    async def scan(symbols: str = "QQQ,SPY,SPX,IWM,NVDA,TSLA,AAPL,MSFT",
                   source: str | None = None) -> list[dict]:
        """Señales por símbolo (Compass-like) desde las sesiones vivas."""
        resolved = resolve_source(source)
        results = []
        # yfinance castiga las ráfagas: menos símbolos y creación escalonada
        max_symbols = 8 if resolved == "yfinance" else 16
        wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()][:max_symbols]
        for symbol in wanted:
            if resolved == "yfinance" and not manager.has(symbol, resolved):
                await asyncio.sleep(0.6)
            session = await manager.session_for(symbol, resolved)
            state = session.feed.state
            snap = state.snapshot()
            total_gex = sum(r.net_gex for r in state.strikes)
            atm = min(state.strikes, key=lambda r: abs(r.strike - state.spot)) if state.strikes else None
            direction = snap["put_sell_pct"] - snap["call_sell_pct"]
            results.append({
                "symbol": symbol,
                "spot": snap["spot"],
                "put_sell_pct": snap["put_sell_pct"],
                "call_sell_pct": snap["call_sell_pct"],
                "direction_score": round(direction, 2),
                "total_gex": round(total_gex, 1),
                "regime": "amortiguador" if total_gex >= 0 else "acelerador",
                "gamma_flip": snap["gamma_flip"],
                "flip_distance_pct": round((state.spot - snap["gamma_flip"]) / state.spot * 100, 2)
                                     if snap["gamma_flip"] and state.spot else None,
                "atm_iv": round(atm.iv, 4) if atm else None,
                "connected": snap["connected"],
            })
        return results

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket, symbol: str = "QQQ",
                                 source: str | None = None, expiry: int = 0) -> None:
        if (source or manager.default_source) not in factories:
            await ws.close(code=4400, reason="fuente no disponible")
            return
        await ws.accept()
        session = await manager.subscribe(symbol, ws, source, expiry)
        try:
            initial = session.payload()
            recorder.record(session.symbol, initial)  # garantiza ≥1 snapshot
            await ws.send_text(initial)
            while True:
                await ws.receive_text()  # mantiene viva la conexión
        except WebSocketDisconnect:
            pass
        finally:
            manager.unsubscribe(session, ws)

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


def run_server(mode: str = "sim", web_port: int = 8000, **feed_kwargs) -> None:
    import uvicorn
    app = create_app(mode=mode, **feed_kwargs)
    print(f"Dashboard en http://127.0.0.1:{web_port}  (fuente por defecto: {mode})")
    uvicorn.run(app, host="127.0.0.1", port=web_port, log_level="warning")
