"""Servidor del dashboard: frontend estático + snapshot REST + WebSocket.

Modos:
  sim   — simulador de sesión (por defecto; no necesita nada externo)
  ibkr  — feed en vivo desde TWS/IB Gateway (uv sync --extra ibkr)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from visual_options.stream.sim import SessionSimulator

WEB_DIR = Path(__file__).parent / "web"
SIM_TICK_SECONDS = 1.0


def create_app(mode: str = "sim", symbol: str = "QQQ", host: str = "127.0.0.1",
               port: int = 7497, seed: int | None = None) -> FastAPI:
    clients: set[WebSocket] = set()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(producer())
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(title="visual-options stream", lifespan=lifespan)

    if mode == "sim":
        simulator = SessionSimulator(symbol=symbol, seed=seed)
        app.state.dashboard = simulator.state

        async def producer() -> None:
            while True:
                await asyncio.sleep(SIM_TICK_SECONDS)
                simulator.tick(seconds=30.0)  # cada segundo real ≈ 30 s de sesión
                await _broadcast(clients, simulator.state.snapshot())
    elif mode == "ibkr":
        from visual_options.stream.ibkr_feed import IBKRFeed
        feed = IBKRFeed(symbol=symbol, host=host, port=port)
        app.state.dashboard = feed.state

        async def producer() -> None:
            feed_task = asyncio.create_task(feed.run())
            try:
                while True:
                    await asyncio.sleep(2.0)
                    await _broadcast(clients, feed.state.snapshot())
            finally:
                feed_task.cancel()
    else:
        raise ValueError(f"modo desconocido: {mode!r} (usa 'sim' o 'ibkr')")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/snapshot")
    async def snapshot() -> dict:
        return app.state.dashboard.snapshot()

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        clients.add(ws)
        try:
            await ws.send_text(json.dumps(app.state.dashboard.snapshot()))
            while True:
                await ws.receive_text()  # mantiene viva la conexión
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(ws)

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


async def _broadcast(clients: set[WebSocket], payload: dict) -> None:
    if not clients:
        return
    message = json.dumps(payload)
    dead = set()
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    clients -= dead


def run_server(mode: str = "sim", symbol: str = "QQQ", web_port: int = 8000,
               ib_host: str = "127.0.0.1", ib_port: int = 7497, seed: int | None = None) -> None:
    import uvicorn
    app = create_app(mode=mode, symbol=symbol, host=ib_host, port=ib_port, seed=seed)
    print(f"Dashboard en http://127.0.0.1:{web_port}  (modo {mode}, {symbol})")
    uvicorn.run(app, host="127.0.0.1", port=web_port, log_level="warning")
