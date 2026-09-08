import asyncio
import json
import socket
import pytest
import websockets
from desktop.runtime import BackendRuntime
from desktop.gateway import IntegrationsGateway


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


def test_gateway_serves_tv_sync_and_webhook(runtime):
    port = _free_port()
    gw = IntegrationsGateway(runtime, host="127.0.0.1", port=port)
    assert gw.start() is True
    assert gw.url == f"http://127.0.0.1:{port}"
    try:
        async def talk():
            async with websockets.connect(
                f"ws://127.0.0.1:{port}/ws/tv-sync",
                origin="http://127.0.0.1:5173",
            ) as ws:
                first = json.loads(await asyncio.wait_for(ws.recv(), 5))
                assert first["type"] == "INITIAL_STATE"
                await ws.send(json.dumps({"symbol": "solusdt", "timeframe": "1h", "exchange": "binance"}))
                await asyncio.sleep(0.2)
        asyncio.run(talk())
        from app.websocket.tv_sync import tv_sync_manager
        assert tv_sync_manager.active_symbol == "SOLUSDT"
        import httpx
        r = httpx.get(f"{gw.url}/health", timeout=5)
        assert r.status_code == 200 and r.json()["gateway"] is True
        r = httpx.post(f"{gw.url}/api/v1/webhook/tradingview", content=b"{}", timeout=5)
        assert r.status_code in (200, 400, 401, 403, 422)
        # the gateway must not expose the rest of the API
        assert httpx.get(f"{gw.url}/api/v1/portfolio/summary", timeout=5).status_code == 404
    finally:
        gw.stop()


def test_gateway_disabled_when_port_busy(runtime):
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        gw = IntegrationsGateway(runtime, host="127.0.0.1", port=port)
        assert gw.start() is False
        assert gw.enabled is False and gw.url is None
    finally:
        blocker.close()
