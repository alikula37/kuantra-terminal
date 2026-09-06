"""Network-bound public Binance depth adapter.

The adapter is deliberately narrower than the execution stack: it reads a
public REST snapshot and a public websocket depth stream, then delegates all
ordering, recovery, book projection and persistence decisions to the injected
``BinanceDepthTransport``/``BinanceDepthIngestor`` boundary.  It never handles
credentials or submits orders.  Testnet is the safe default and live mode is
an explicit endpoint choice.
"""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional
from urllib.parse import urlsplit

from .binance_depth_ingestor import BinanceDepthIngestor
from .binance_depth_transport import (
    BinanceDepthTransport,
    BinanceDepthTransportConfig,
    DepthTransportResult,
)


class BinanceDepthEnvironment(str, Enum):
    TESTNET = "testnet"
    LIVE = "live"


class BinanceDepthNetworkError(RuntimeError):
    """Explicit network/source failure; never converted into fake market data."""

    def __init__(self, reason_code: str, message: str):
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {message}")


@dataclass(frozen=True)
class BinanceDepthNetworkConfig:
    """Safe endpoint, timeout and payload bounds for public depth reads."""

    symbol: str
    environment: BinanceDepthEnvironment = BinanceDepthEnvironment.TESTNET
    rest_base_url: Optional[str] = None
    websocket_base_url: Optional[str] = None
    stream_suffix: str = "@depth@100ms"
    queue_size: int = 512
    snapshot_timeout_seconds: float = 10.0
    open_timeout_seconds: float = 10.0
    recv_timeout_seconds: float = 30.0
    max_message_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        normalized_symbol = str(self.symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be non-empty")
        environment = BinanceDepthEnvironment(self.environment)
        if self.rest_base_url is None:
            rest_base_url = (
                "https://testnet.binance.vision"
                if environment is BinanceDepthEnvironment.TESTNET
                else "https://api.binance.com"
            )
        else:
            rest_base_url = str(self.rest_base_url).strip()
        if self.websocket_base_url is None:
            websocket_base_url = (
                "wss://stream.testnet.binance.vision:9443/ws"
                if environment is BinanceDepthEnvironment.TESTNET
                else "wss://stream.binance.com:9443/ws"
            )
        else:
            websocket_base_url = str(self.websocket_base_url).strip()
        self._validate_endpoint(rest_base_url, "https", "rest_base_url")
        self._validate_endpoint(websocket_base_url, "wss", "websocket_base_url")
        if isinstance(self.stream_suffix, str) is False or not self.stream_suffix.startswith("@depth"):
            raise ValueError("stream_suffix must be a Binance depth stream suffix")
        for name, value in (
            ("snapshot_timeout_seconds", self.snapshot_timeout_seconds),
            ("open_timeout_seconds", self.open_timeout_seconds),
            ("recv_timeout_seconds", self.recv_timeout_seconds),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        if isinstance(self.queue_size, bool) or not isinstance(self.queue_size, int) or self.queue_size <= 0:
            raise ValueError("queue_size must be a positive integer")
        if (
            isinstance(self.max_message_bytes, bool)
            or not isinstance(self.max_message_bytes, int)
            or self.max_message_bytes <= 0
        ):
            raise ValueError("max_message_bytes must be a positive integer")
        object.__setattr__(self, "symbol", normalized_symbol)
        object.__setattr__(self, "environment", environment)
        object.__setattr__(self, "rest_base_url", rest_base_url)
        object.__setattr__(self, "websocket_base_url", websocket_base_url)

    @staticmethod
    def _validate_endpoint(value: str, scheme: str, field: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme != scheme or not parsed.netloc:
            raise ValueError(f"{field} must use {scheme} and include a host")

    @property
    def transport_config(self) -> BinanceDepthTransportConfig:
        return BinanceDepthTransportConfig(
            symbol=self.symbol,
            rest_base_url=self.rest_base_url or "",
            websocket_base_url=self.websocket_base_url or "",
            stream_suffix=self.stream_suffix,
            queue_size=self.queue_size,
        )

    @property
    def snapshot_url(self) -> str:
        return self.transport_config.snapshot_url

    @property
    def stream_url(self) -> str:
        return self.transport_config.stream_url


HttpClientFactory = Callable[..., Any]
WebsocketConnect = Callable[..., Any]


def _default_http_client_factory(*, timeout: float) -> Any:
    import httpx

    return httpx.AsyncClient(timeout=timeout)


def _default_websocket_connect(url: str, **kwargs: Any) -> Any:
    import websockets

    return websockets.connect(url, **kwargs)


class BinanceDepthNetworkAdapter:
    """Bind public REST/WS clients to the transport-free depth boundary."""

    def __init__(
        self,
        ingestor: BinanceDepthIngestor,
        config: BinanceDepthNetworkConfig,
        *,
        http_client_factory: Optional[HttpClientFactory] = None,
        websocket_connect: Optional[WebsocketConnect] = None,
    ) -> None:
        self.config = config
        self.transport = BinanceDepthTransport(ingestor, config.transport_config)
        self._http_client_factory = http_client_factory or _default_http_client_factory
        self._websocket_connect = websocket_connect or _default_websocket_connect

    async def fetch_snapshot(self) -> Mapping[str, Any]:
        """Fetch one public snapshot; HTTP/status/JSON failures stay explicit."""

        try:
            client_context = self._http_client_factory(timeout=self.config.snapshot_timeout_seconds)
            async with client_context as client:
                response = await client.get(self.config.snapshot_url)
                response.raise_for_status()
                payload = response.json()
        except asyncio.CancelledError:
            raise
        except BinanceDepthNetworkError:
            raise
        except Exception as exc:
            raise BinanceDepthNetworkError("SNAPSHOT_REQUEST_FAILED", str(exc)) from exc
        if not isinstance(payload, Mapping):
            raise BinanceDepthNetworkError("SNAPSHOT_NOT_OBJECT", "snapshot response must be a JSON object")
        return dict(payload)

    async def event_source(self, *, stop_event: Optional[asyncio.Event] = None) -> AsyncIterator[Mapping[str, Any]]:
        """Yield validated depth updates until the public socket closes."""

        try:
            websocket_context = self._websocket_connect(
                self.config.stream_url,
                open_timeout=self.config.open_timeout_seconds,
                max_size=self.config.max_message_bytes,
            )
            async with websocket_context as websocket:
                while True:
                    raw_message = await self._recv_with_stop(websocket, stop_event)
                    if raw_message is None:
                        return
                    yield self.decode_depth_message(raw_message)
        except asyncio.CancelledError:
            raise
        except BinanceDepthNetworkError:
            raise
        except Exception as exc:
            raise BinanceDepthNetworkError("EVENT_STREAM_FAILED", str(exc)) from exc

    async def _recv_with_stop(self, websocket: Any, stop_event: Optional[asyncio.Event]) -> Any:
        """Bound one recv and let an operator stop a quiet socket promptly."""

        if stop_event is None:
            try:
                return await asyncio.wait_for(websocket.recv(), timeout=self.config.recv_timeout_seconds)
            except asyncio.TimeoutError as exc:
                raise BinanceDepthNetworkError("EVENT_RECV_TIMEOUT", "websocket receive timed out") from exc
        if stop_event.is_set():
            return None
        recv_task = asyncio.create_task(websocket.recv())
        stop_task = asyncio.create_task(stop_event.wait())
        timeout_task = asyncio.create_task(asyncio.sleep(self.config.recv_timeout_seconds))
        try:
            done, _ = await asyncio.wait(
                {recv_task, stop_task, timeout_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                return None
            if timeout_task in done:
                raise BinanceDepthNetworkError("EVENT_RECV_TIMEOUT", "websocket receive timed out")
            return recv_task.result()
        finally:
            for task in (recv_task, stop_task, timeout_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(recv_task, stop_task, timeout_task, return_exceptions=True)

    def decode_depth_message(self, raw_message: Any) -> Mapping[str, Any]:
        """Decode raw WS JSON and reject non-depth/cross-symbol messages."""

        if isinstance(raw_message, bytes):
            if len(raw_message) > self.config.max_message_bytes:
                raise BinanceDepthNetworkError("EVENT_TOO_LARGE", "websocket message exceeds configured bound")
            try:
                raw_message = raw_message.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise BinanceDepthNetworkError("EVENT_NOT_UTF8", "websocket message is not UTF-8") from exc
        elif isinstance(raw_message, str):
            if len(raw_message.encode("utf-8")) > self.config.max_message_bytes:
                raise BinanceDepthNetworkError("EVENT_TOO_LARGE", "websocket message exceeds configured bound")
        else:
            raise BinanceDepthNetworkError("EVENT_NOT_TEXT", "websocket message must be text or bytes")
        try:
            message = json.loads(raw_message)
        except (TypeError, ValueError) as exc:
            raise BinanceDepthNetworkError("EVENT_INVALID_JSON", "websocket message is not valid JSON") from exc
        if not isinstance(message, Mapping):
            raise BinanceDepthNetworkError("EVENT_NOT_OBJECT", "websocket payload must be a JSON object")
        payload = message.get("data", message)
        if not isinstance(payload, Mapping):
            raise BinanceDepthNetworkError("EVENT_DATA_NOT_OBJECT", "websocket data field must be an object")
        if payload.get("e") != "depthUpdate":
            raise BinanceDepthNetworkError("EVENT_NOT_DEPTH_UPDATE", "websocket payload is not a depth update")
        if str(payload.get("s", "")).strip().upper() != self.config.symbol:
            raise BinanceDepthNetworkError("EVENT_SYMBOL_MISMATCH", "websocket symbol does not match config")
        return dict(payload)

    async def run_once(
        self,
        *,
        stop_event: Optional[asyncio.Event] = None,
        max_source_events: Optional[int] = None,
    ) -> DepthTransportResult:
        """Run one network cycle through the existing bounded transport."""

        return await self.transport.run_once(
            event_source=self.event_source(stop_event=stop_event),
            snapshot_fetcher=self.fetch_snapshot,
            stop_event=stop_event,
            max_source_events=max_source_events,
        )


__all__ = [
    "BinanceDepthEnvironment",
    "BinanceDepthNetworkAdapter",
    "BinanceDepthNetworkConfig",
    "BinanceDepthNetworkError",
]
