import json
import pytest
from desktop.runtime import BackendRuntime, BridgeResponse


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


def test_health_roundtrip(runtime):
    resp = runtime.call("GET", "/health")
    assert isinstance(resp, BridgeResponse)
    assert resp.status == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert json.loads(resp.content)["status"] == "online"


def test_query_string_and_json_body(runtime):
    resp = runtime.call("GET", "/api/v1/market-data/candles", query="symbol=BTCUSDT&timeframe=1m&limit=1")
    assert resp.status in (200, 502, 503)  # network-dependent endpoint; must not raise
    body = json.dumps({"symbol": "BTCUSDT", "side": "BUY", "order_type": "LIMIT", "qty": 1,
                       "price": 100.0, "stop_loss": 99.0, "take_profit": 102.0,
                       "exchange": "binance_futures", "mode": "PAPER"}).encode()
    resp = runtime.call("POST", "/api/v1/execution/order",
                        headers={"Content-Type": "application/json"}, body=body)
    assert resp.status in (200, 422)
    assert json.loads(resp.content)


def test_multipart_upload(runtime):
    csv = b"symbol,side,qty,price\nBTCUSDT,BUY,1,100\n"
    resp = runtime.call("POST", "/api/v1/journal/preview-csv",
                        files=[("file", "trades.csv", csv, "text/csv")])
    assert resp.status in (200, 400, 422)
    assert json.loads(resp.content)


def test_unknown_route_is_404_not_exception(runtime):
    resp = runtime.call("GET", "/api/v1/does-not-exist")
    assert resp.status == 404


def test_run_executes_on_loop(runtime):
    import asyncio

    async def probe():
        return asyncio.get_running_loop() is runtime.loop

    assert runtime.run(probe()) is True


def test_lifespan_started_binance_client(runtime):
    from app.websocket.binance_client import binance_client
    assert binance_client.is_running is True
