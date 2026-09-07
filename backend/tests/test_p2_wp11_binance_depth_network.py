"""P2-WP11 public Binance network adapter contracts without live network."""

import asyncio
import json

import pytest

from app.services.market_data.binance_depth_ingestor import BinanceDepthIngestor
from app.services.market_data.binance_depth_network import (
    BinanceDepthEnvironment,
    BinanceDepthNetworkAdapter,
    BinanceDepthNetworkConfig,
    BinanceDepthNetworkError,
)
from app.services.market_data.binance_depth_transport import DepthTransportDecision


def _snapshot(last_id: int = 101):
    return {"lastUpdateId": last_id, "bids": [["65000", "2"]], "asks": [["65010", "3"]]}


def _event(first: int = 101, final: int = 102):
    return {"e": "depthUpdate", "s": "BTCUSDT", "U": first, "u": final, "b": [["65000", "1"]], "a": []}


class _FakeResponse:
    def __init__(self, payload, *, status_error: Exception | None = None):
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.requested_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        self.requested_url = url
        return self.response


class _FakeWebsocket:
    def __init__(self, messages):
        self.messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def recv(self):
        if not self.messages:
            await asyncio.sleep(0)
            raise ConnectionError("fixture socket exhausted")
        return self.messages.pop(0)


class _DisconnectableWebsocket:
    def __init__(self):
        self.closed = asyncio.Event()
        self.close_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def recv(self):
        await self.closed.wait()
        raise ConnectionError("operator closed fixture socket")

    async def close(self):
        self.close_calls += 1
        self.closed.set()


def _adapter(http_response, websocket_messages):
    config = BinanceDepthNetworkConfig("BTCUSDT")

    def http_factory(*, timeout):
        assert timeout == config.snapshot_timeout_seconds
        return _FakeHttpClient(http_response)

    def websocket_connect(url, **kwargs):
        assert url == config.stream_url
        assert kwargs["open_timeout"] == config.open_timeout_seconds
        assert kwargs["max_size"] == config.max_message_bytes
        return _FakeWebsocket(websocket_messages)

    return BinanceDepthNetworkAdapter(
        BinanceDepthIngestor("BTCUSDT"),
        config,
        http_client_factory=http_factory,
        websocket_connect=websocket_connect,
    )


@pytest.mark.asyncio
async def test_testnet_adapter_runs_injected_clients_through_ingestor():
    adapter = _adapter(_FakeResponse(_snapshot()), [json.dumps({"stream": "x", "data": _event()})])

    result = await adapter.run_once(max_source_events=1)

    assert result.decision is DepthTransportDecision.COMPLETED
    assert result.source_verified is False
    assert result.snapshot is not None
    assert result.processed_event_count == 1
    assert adapter.config.environment is BinanceDepthEnvironment.TESTNET
    assert adapter.config.rest_base_url == "https://testnet.binance.vision"
    assert adapter.config.websocket_base_url == "wss://stream.testnet.binance.vision:9443/ws"


def test_decoder_accepts_combined_payload_and_rejects_cross_symbol_or_wrong_event():
    adapter = _adapter(_FakeResponse(_snapshot()), [])

    decoded = adapter.decode_depth_message(json.dumps({"stream": "x", "data": _event()}))
    assert decoded["u"] == 102

    with pytest.raises(BinanceDepthNetworkError, match="symbol"):
        adapter.decode_depth_message(json.dumps({**_event(), "s": "ETHUSDT"}))
    with pytest.raises(BinanceDepthNetworkError, match="depth update"):
        adapter.decode_depth_message(json.dumps({"e": "trade", "s": "BTCUSDT"}))


def test_decoder_enforces_utf8_json_and_size_bounds():
    config = BinanceDepthNetworkConfig("BTCUSDT", max_message_bytes=8)
    adapter = BinanceDepthNetworkAdapter(BinanceDepthIngestor("BTCUSDT"), config)

    with pytest.raises(BinanceDepthNetworkError, match="EVENT_TOO_LARGE"):
        adapter.decode_depth_message(b"{}" * 8)
    with pytest.raises(BinanceDepthNetworkError, match="UTF-8"):
        adapter.decode_depth_message(b"\xff")


@pytest.mark.asyncio
async def test_http_failure_is_explicit_and_never_promoted_to_transport_success():
    adapter = _adapter(_FakeResponse({}, status_error=OSError("HTTP 503")), [])

    result = await adapter.run_once(max_source_events=1)

    assert result.decision is DepthTransportDecision.SOURCE_FAILED
    assert result.reason_code == "SNAPSHOT_FETCH_FAILED"
    assert "SNAPSHOT_REQUEST_FAILED" in (result.source_error or "")


@pytest.mark.asyncio
async def test_explicit_disconnect_after_closes_socket_and_surfaces_source_failure():
    config = BinanceDepthNetworkConfig("BTCUSDT")
    socket = _DisconnectableWebsocket()

    def http_factory(*, timeout):
        return _FakeHttpClient(_FakeResponse(_snapshot()))

    def websocket_connect(url, **kwargs):
        return socket

    adapter = BinanceDepthNetworkAdapter(
        BinanceDepthIngestor("BTCUSDT"),
        config,
        http_client_factory=http_factory,
        websocket_connect=websocket_connect,
        disconnect_after_seconds=0.01,
    )

    result = await adapter.run_once()

    assert result.decision is DepthTransportDecision.SOURCE_FAILED
    assert "OPERATOR_DISCONNECT_INJECTED" in (result.source_error or "")
    assert socket.close_calls == 1
    assert adapter.disconnect_injected is True


def test_config_rejects_non_tls_custom_endpoints_and_invalid_bounds():
    with pytest.raises(ValueError, match="https"):
        BinanceDepthNetworkConfig("BTCUSDT", rest_base_url="http://example.test")
    with pytest.raises(ValueError, match="wss"):
        BinanceDepthNetworkConfig("BTCUSDT", websocket_base_url="ws://example.test")
    with pytest.raises(ValueError, match="positive finite"):
        BinanceDepthNetworkConfig("BTCUSDT", recv_timeout_seconds=0)

    with pytest.raises(ValueError, match="disconnect_after_seconds"):
        BinanceDepthNetworkAdapter(
            BinanceDepthIngestor("BTCUSDT"),
            BinanceDepthNetworkConfig("BTCUSDT"),
            disconnect_after_seconds=0,
        )
