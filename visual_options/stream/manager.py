"""Gestor de sesiones: una fuente de datos viva por símbolo.

Cada sesión mantiene su DashboardState + FootprintBuilder y un bucle
productor que difunde snapshots a los WebSockets suscritos a ese símbolo.
Las sesiones se crean bajo demanda al entrar el primer cliente y se
destruyen cuando se queda sin clientes un rato.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import WebSocket

from visual_options.stream.footprint import FootprintBuilder
from visual_options.stream.sim import SessionSimulator
from visual_options.stream.state import DashboardState

SIM_TICK_REAL_SECONDS = 1.0
SIM_SESSION_SECONDS_PER_TICK = 30.0
IDLE_GRACE_SECONDS = 60.0


class Feed(Protocol):
    """Interfaz mínima de una fuente de datos."""
    state: DashboardState
    footprint: FootprintBuilder

    async def step(self) -> None: ...       # avanza/refresca los datos
    async def close(self) -> None: ...


class SimFeed:
    """Adaptador del simulador a la interfaz Feed."""

    def __init__(self, symbol: str, seed: int | None = None) -> None:
        self.sim = SessionSimulator(symbol=symbol, seed=seed)
        self.state = self.sim.state
        self.footprint = self.sim.footprint

    async def step(self) -> None:
        await asyncio.sleep(SIM_TICK_REAL_SECONDS)
        self.sim.tick(seconds=SIM_SESSION_SECONDS_PER_TICK)

    async def close(self) -> None:
        return None


@dataclass
class Session:
    symbol: str
    feed: Feed
    clients: set[WebSocket] = field(default_factory=set)
    task: asyncio.Task | None = None
    idle_since: float | None = None

    def payload(self) -> str:
        return json.dumps({
            "flow": self.feed.state.snapshot(),
            "footprint": self.feed.footprint.snapshot(),
        })


class SessionManager:
    def __init__(self, factories: dict[str, object], default_source: str = "sim") -> None:
        """factories: id de fuente ('sim', 'tradier'…) → (symbol) -> Feed."""
        if default_source not in factories:
            raise ValueError(f"fuente por defecto desconocida: {default_source!r}")
        self._factories = factories
        self.default_source = default_source
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    @property
    def sources(self) -> list[str]:
        return list(self._factories)

    def has(self, symbol: str, source: str) -> bool:
        return f"{source}:{symbol.upper().strip()}" in self._sessions

    async def session_for(self, symbol: str, source: str | None = None) -> Session:
        symbol = symbol.upper().strip() or "QQQ"
        source = source or self.default_source
        if source not in self._factories:
            raise KeyError(f"fuente desconocida: {source!r} (disponibles: {self.sources})")
        key = f"{source}:{symbol}"
        async with self._lock:
            session = self._sessions.get(key)
            if session is None:
                session = Session(symbol=key, feed=self._factories[source](symbol))
                # sin clientes desde el arranque: candidata a limpieza
                session.idle_since = asyncio.get_event_loop().time()
                session.task = asyncio.create_task(self._run(session))
                self._sessions[key] = session
            return session

    async def subscribe(self, symbol: str, ws: WebSocket, source: str | None = None) -> Session:
        session = await self.session_for(symbol, source)
        session.clients.add(ws)
        session.idle_since = None
        return session

    def unsubscribe(self, session: Session, ws: WebSocket) -> None:
        session.clients.discard(ws)
        if not session.clients:
            session.idle_since = asyncio.get_event_loop().time()

    async def _run(self, session: Session) -> None:
        try:
            while True:
                await session.feed.step()
                await self._broadcast(session)
                if session.idle_since is not None and not session.clients:
                    now = asyncio.get_event_loop().time()
                    if now - session.idle_since > IDLE_GRACE_SECONDS:
                        break
        except asyncio.CancelledError:
            raise
        finally:
            await session.feed.close()
            self._sessions.pop(session.symbol, None)

    async def _broadcast(self, session: Session) -> None:
        if not session.clients:
            return
        message = session.payload()
        dead = set()
        for ws in session.clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.unsubscribe(session, ws)

    async def shutdown(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            if session.task is not None:
                session.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await session.task
