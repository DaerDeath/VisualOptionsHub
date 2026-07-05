"""Servidor del dashboard multi-símbolo: SPA + snapshot REST + WebSocket.

Fuentes de datos (--mode):
  sim      — simulador de sesión por símbolo (por defecto)
  tradier  — API de Tradier (TRADIER_TOKEN; sandbox con ~15 min de retraso)
  ibkr     — TWS/IB Gateway en vivo (uv sync --extra ibkr)

Rutas del frontend (hash): #/  selector · #/flow/QQQ · #/footprint/SPX
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from visual_options.stream.manager import SessionManager, SimFeed

WEB_DIR = Path(__file__).parent / "web"


def make_feed_factory(mode: str, *, seed: int | None = None, ib_host: str = "127.0.0.1",
                      ib_port: int = 7497, tradier_token: str | None = None,
                      tradier_env: str = "sandbox"):
    if mode == "sim":
        return lambda symbol: SimFeed(symbol, seed=seed)
    if mode == "tradier":
        from visual_options.stream.tradier_feed import TradierFeed
        return lambda symbol: TradierFeed(symbol, token=tradier_token, env=tradier_env)
    if mode == "ibkr":
        from visual_options.stream.ibkr_feed import IBKRFeed
        return lambda symbol: IBKRFeed(symbol, host=ib_host, port=ib_port)
    raise ValueError(f"modo desconocido: {mode!r} (usa 'sim', 'tradier' o 'ibkr')")


def create_app(mode: str = "sim", **feed_kwargs) -> FastAPI:
    manager = SessionManager(make_feed_factory(mode, **feed_kwargs))

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await manager.shutdown()

    app = FastAPI(title="visual-options stream", lifespan=lifespan)
    app.state.manager = manager
    app.state.mode = mode

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/config")
    async def config() -> dict:
        return {"mode": mode}

    @app.get("/api/snapshot")
    async def snapshot(symbol: str = "QQQ") -> dict:
        session = await manager.session_for(symbol)
        return {
            "flow": session.feed.state.snapshot(),
            "footprint": session.feed.footprint.snapshot(),
        }

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket, symbol: str = "QQQ") -> None:
        await ws.accept()
        session = await manager.subscribe(symbol, ws)
        try:
            await ws.send_text(session.payload())
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
    print(f"Dashboard en http://127.0.0.1:{web_port}  (modo {mode})")
    uvicorn.run(app, host="127.0.0.1", port=web_port, log_level="warning")
