"""
IntegrationsGateway: the one socket the desktop app opens. It serves only what *other*
programs need to reach: the TradingView Chrome extension WebSocket and TradingView alert
webhooks. The UI never talks to it. Bound to loopback; disabled (not fatal) if the port is busy.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
from typing import Optional

import uvicorn
from fastapi import FastAPI

from app.api.webhook_tv import WEBHOOK_SECRET_CONFIGURED, WEBHOOK_SECRET_KEY, webhook_ingest_router
from app.api.tv_sync_ws import tv_sync_websocket
from app.core.config import settings
from app.version import __version__

logger = logging.getLogger("desktop.gateway")

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
ALLOW_NON_LOOPBACK_ENV = "KUANTRA_ALLOW_NON_LOOPBACK_GATEWAY"


def build_gateway_app() -> FastAPI:
    app = FastAPI(title="Kuantra Integrations Gateway", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    # Only the HMAC-gated ingest route is exposed here; the observation
    # list/confirm routes stay on the UI-side app.
    app.include_router(webhook_ingest_router, prefix="/api/v1")
    app.add_api_websocket_route("/ws/tv-sync", tv_sync_websocket)

    @app.get("/health")
    async def health():
        return {"status": "online", "gateway": True, "version": __version__}

    return app


class IntegrationsGateway:
    def __init__(self, runtime, host: Optional[str] = None, port: Optional[int] = None):
        self._runtime = runtime
        self.host = host or settings.gateway_host
        self.port = port or settings.gateway_port
        self.enabled = False
        self.url: Optional[str] = None
        self._server: Optional[uvicorn.Server] = None
        self._task = None
        self._sock: Optional[socket.socket] = None

    def _warn_on_missing_webhook_secret(self) -> None:
        """The webhook route is the one thing here reachable by any other program on the machine."""
        if not WEBHOOK_SECRET_CONFIGURED:
            logger.warning(
                "TradingView webhook secret is process-random and not configured; set KUANTRA_WEBHOOK_SECRET "
                "so that any local process cannot post alerts to %s:%s/api/v1/webhook/tradingview",
                self.host, self.port,
            )

    def start(self) -> bool:
        if self.host not in _LOOPBACK_HOSTS and os.environ.get(ALLOW_NON_LOOPBACK_ENV) != "1":
            logger.error(
                "Integrations gateway refused to bind non-loopback host '%s'. "
                "Set %s=1 only for an explicitly reviewed deployment.",
                self.host, ALLOW_NON_LOOPBACK_ENV,
            )
            self.enabled = False
            self.url = None
            return False
        self._warn_on_missing_webhook_secret()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform.startswith("win"):
            # On Windows SO_REUSEADDR lets a second process steal a port another one is already
            # listening on; SO_EXCLUSIVEADDRUSE is the flag that actually means "fail if taken",
            # which is what the busy-port fallback below relies on.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((self.host, self.port))
            sock.listen(128)
            sock.setblocking(False)
        except OSError as exc:
            sock.close()
            logger.warning("Integrations gateway disabled: cannot bind %s:%s (%s)", self.host, self.port, exc)
            self.enabled = False
            self.url = None
            return False
        self._sock = sock
        config = uvicorn.Config(build_gateway_app(), host=self.host, port=self.port, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(config)
        # serve() would otherwise try to install signal handlers off the main thread.
        self._server.install_signal_handlers = lambda: None

        async def _launch():
            self._task = asyncio.get_running_loop().create_task(self._server.serve(sockets=[sock]))
            for _ in range(100):
                if self._server.started:
                    return True
                if self._task.done():
                    return False
                await asyncio.sleep(0.05)
            return False

        ok = self._runtime.run(_launch(), timeout=10)
        self.enabled = bool(ok)
        self.url = f"http://{self.host}:{self.port}" if ok else None
        if ok:
            logger.info("Integrations gateway listening on %s (extension WS + TradingView webhook)", self.url)
        else:
            self._sock.close()
        return self.enabled

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is None:
            return
        self._server.should_exit = True

        async def _wait():
            if self._task is not None:
                try:
                    await asyncio.wait_for(self._task, timeout)
                except Exception:  # noqa: BLE001
                    pass

        try:
            self._runtime.run(_wait(), timeout=timeout + 1)
        except Exception:  # noqa: BLE001
            pass
        if self._sock is not None:
            self._sock.close()
        self.enabled = False
        self.url = None
