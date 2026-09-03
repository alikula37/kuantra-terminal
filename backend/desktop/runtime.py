"""
BackendRuntime: owns one asyncio loop in a daemon thread, runs the FastAPI lifespan, and
dispatches requests into the app in-process through httpx's ASGITransport. No socket.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import httpx

logger = logging.getLogger("desktop.runtime")

INTERNAL_BASE_URL = "http://kuantra.desktop"


@dataclass
class BridgeResponse:
    status: int
    headers: dict = field(default_factory=dict)
    content: bytes = b""


class BackendRuntime:
    def __init__(self, app_factory: Optional[Callable] = None):
        self._app_factory = app_factory
        self.app = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._lifespan_cm = None
        self._stopped = threading.Event()
        self._stopping = threading.Event()
        # Futures handed to caller threads; cancelled on stop() so no UI thread waits on a dead loop.
        self._inflight: "set[Future]" = set()
        self._inflight_lock = threading.Lock()

    # ---- lifecycle -----------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return (
            self._ready.is_set()
            and self._startup_error is None
            and not self._stopped.is_set()
            and not self._stopping.is_set()
        )

    def start(self, timeout: float = 60.0) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._thread_main, name="kuantra-backend-loop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            raise RuntimeError("backend runtime did not start in time")
        if self._startup_error is not None:
            raise RuntimeError(f"backend runtime failed to start: {self._startup_error!r}") from self._startup_error
        logger.info("Backend runtime started (in-process ASGI, no socket).")

    def _thread_main(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._startup())
        except BaseException as exc:  # noqa: BLE001 - surfaced to start()
            self._startup_error = exc
            self._ready.set()
            self._stopped.set()
            return
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.run_until_complete(self._shutdown())
            finally:
                self.loop.close()
                self._stopped.set()

    async def _startup(self) -> None:
        if self._app_factory is None:
            from main import create_app
            from app.services.plugin_manager import plugin_manager
            self.app = create_app()
            plugin_manager.set_app(self.app)
        else:
            self.app = self._app_factory()
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        self._client = httpx.AsyncClient(transport=transport, base_url=INTERNAL_BASE_URL, timeout=None)
        self._lifespan_cm = self.app.router.lifespan_context(self.app)
        await self._lifespan_cm.__aenter__()

    async def _shutdown(self) -> None:
        if self._lifespan_cm is not None:
            try:
                await self._lifespan_cm.__aexit__(None, None, None)
            except Exception as exc:  # noqa: BLE001
                logger.warning("lifespan shutdown error: %s", exc)
        if self._client is not None:
            await self._client.aclose()

    def stop(self, timeout: float = 15.0) -> None:
        if self.loop is None or self._stopped.is_set():
            return
        # Refuse new work first, then release anyone already waiting on the loop: a UI thread
        # parked in Future.result() on a loop that is about to stop would otherwise block for
        # its full timeout and keep the process alive.
        self._stopping.set()
        with self._inflight_lock:
            pending = list(self._inflight)
        for fut in pending:
            fut.cancel()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._stopped.wait(timeout)

    # ---- dispatch --------------------------------------------------------------------------
    def run(self, coro, timeout: Optional[float] = 30.0):
        if self.loop is None:
            raise RuntimeError("runtime not started")
        if self._stopping.is_set() or self._stopped.is_set() or self.loop.is_closed():
            coro.close()
            raise RuntimeError("backend runtime is shutting down")
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)
        with self._inflight_lock:
            self._inflight.add(fut)
        try:
            return fut.result(timeout)
        finally:
            fut.cancel()
            with self._inflight_lock:
                self._inflight.discard(fut)

    def call(
        self,
        method: str,
        path: str,
        query: str = "",
        headers: Optional[dict] = None,
        body: Optional[bytes] = None,
        files: Optional[Iterable[tuple]] = None,
        fields: Optional[Iterable[tuple]] = None,
        timeout: float = 120.0,
    ) -> BridgeResponse:
        return self.run(self._request(method, path, query, headers or {}, body, files, fields), timeout=timeout)

    async def _request(self, method, path, query, headers, body, files, fields) -> BridgeResponse:
        assert self._client is not None
        url = path if not query else f"{path}?{query}"
        kwargs = {"headers": {k: v for k, v in headers.items() if k.lower() != "content-length"}}
        if files or fields:
            kwargs["files"] = [(f[0], (f[1], f[2], f[3])) for f in (files or [])]
            kwargs["data"] = {k: v for k, v in (fields or [])}
            kwargs["headers"].pop("Content-Type", None)
            kwargs["headers"].pop("content-type", None)
        elif body is not None:
            kwargs["content"] = body
        resp = await self._client.request(method.upper(), url, **kwargs)
        return BridgeResponse(status=resp.status_code, headers=dict(resp.headers), content=resp.content)
