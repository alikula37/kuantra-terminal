"""Regression coverage for the P0-WP06B no-fabricated-evidence contract."""

from fastapi.testclient import TestClient

from main import create_app
from app.plugins.plugin_fix_dma.plugin import get_fix_dma_status
from app.plugins.plugin_orderflow.plugin import get_orderflow_status
from app.services.matching.order_book import LimitOrderBook, global_order_book
from app.services.orderflow.delta_heatmap import DeltaHeatmapEngine
from app.services.orderflow.footprint_engine import FootprintEngine


def test_fresh_orderflow_engines_expose_empty_truth_states():
    footprint = FootprintEngine()
    response = footprint.get_footprint_response("BTCUSDT")
    assert footprint.get_footprint_candles("BTCUSDT") == []
    assert response["status"] == "NO_DATA"
    assert response["bars"] == []
    assert response["provenance"] == "RUNTIME_INGEST_ONLY"
    assert "feed" in response["caveat"].lower()

    heatmap = DeltaHeatmapEngine()
    cvd = heatmap.get_cvd_series("BTCUSDT")
    assert cvd["status"] == "NO_DATA"
    assert cvd["current_cvd"] is None
    assert cvd["series"] == []
    assert cvd["divergence"]["has_divergence"] is False
    assert cvd["divergence"]["type"] == "UNAVAILABLE"

    liquidity = heatmap.get_liquidity_heatmap("BTCUSDT")
    assert liquidity["status"] == "NO_DATA"
    assert liquidity["snapshots_count"] == 0
    assert liquidity["history"] == []


def test_explicit_orderflow_inputs_remain_available_but_unverified():
    footprint = FootprintEngine(tick_size=10.0)
    footprint.process_trade_tick("BTCUSDT", 65000.0, 2.0, is_buyer_maker=False, timestamp=1000.0)
    response = footprint.get_footprint_response("BTCUSDT")
    assert response["status"] == "IN_MEMORY_UNVERIFIED"
    assert len(response["bars"]) == 1

    heatmap = DeltaHeatmapEngine()
    heatmap.update_cvd_tick("BTCUSDT", delta=2.0, price=65000.0, timestamp=1000.0)
    heatmap.update_book_depth("BTCUSDT", bids=[[64990.0, 1.0]], asks=[[65010.0, 1.0]], timestamp=1000.0)
    assert heatmap.get_cvd_series("BTCUSDT")["status"] == "IN_MEMORY_UNVERIFIED"
    assert heatmap.get_liquidity_heatmap("BTCUSDT")["status"] == "IN_MEMORY_UNVERIFIED"


def test_empty_l2_book_and_sweep_cannot_imply_liquidity():
    empty_book = LimitOrderBook("BTCUSDT")
    snapshot = empty_book.get_l2_snapshot()
    assert snapshot["status"] == "NO_DATA"
    assert snapshot["bids"] == []
    assert snapshot["asks"] == []
    assert snapshot["best_bid"] is None
    assert snapshot["best_ask"] is None
    assert snapshot["book_imbalance_ratio"] is None

    sweep = empty_book.simulate_sweep("BUY", 1.0)
    assert sweep["status"] == "NO_DATA"
    assert sweep["filled_size"] == 0.0
    assert sweep["execution_vwap"] is None
    assert sweep["slippage_bps"] is None

    global_snapshot = global_order_book.get_l2_snapshot()
    assert global_snapshot["status"] == "NO_DATA"
    assert global_snapshot["bids"] == []
    assert global_snapshot["asks"] == []


def test_public_orderflow_and_fix_surfaces_do_not_report_fake_success():
    app = create_app()
    with TestClient(app) as client:
        footprint = client.get("/api/v1/orderflow/footprint?symbol=UNSEEN")
        assert footprint.status_code == 200
        assert footprint.json()["status"] == "NO_DATA"
        assert footprint.json()["bars"] == []

        cvd = client.get("/api/v1/orderflow/cvd?symbol=UNSEEN")
        assert cvd.status_code == 200
        assert cvd.json()["status"] == "NO_DATA"
        assert cvd.json()["series"] == []

        l2 = client.get("/api/v1/orderbook/l2-snapshot")
        assert l2.status_code == 200
        assert l2.json()["status"] == "NO_DATA"

        fix_status = client.get("/api/v1/fix/status")
        assert fix_status.status_code == 200
        assert fix_status.json()["status"] == "EXPERIMENTAL_DISABLED"
        assert fix_status.json()["is_logged_on"] is False
        assert fix_status.json()["round_trip_latency_us"] is None

        fix_order = client.post("/api/v1/fix/order", json={"symbol": "ESM6", "side": "BUY", "qty": 1, "price": 5600})
        assert fix_order.status_code == 503
        assert fix_order.json()["status"] == "EXPERIMENTAL_DISABLED"
        assert fix_order.json()["execution_status"] == "NOT_SUBMITTED"
        assert fix_order.json()["round_trip_latency_us"] is None

        logon = client.post("/api/v1/fix/session/logon")
        assert logon.status_code == 503
        assert logon.json()["session_state"] == "DISCONNECTED"

        submit = client.post("/api/v1/fix/order/submit", json={"symbol": "BTCUSDT", "side": "BUY", "price": 1, "qty": 1})
        assert submit.status_code == 503
        assert submit.json()["filled_size"] == 0.0
        assert submit.json()["fills"] == []

        sweep = client.post("/api/v1/orderbook/simulate-fill", json={"side": "BUY", "size": 1})
        assert sweep.status_code == 503
        assert sweep.json()["execution_vwap"] is None
        assert sweep.json()["slippage_bps"] is None


def test_plugin_statuses_report_availability_not_online_claims():
    orderflow = get_orderflow_status()
    assert orderflow["status"] == "NO_DATA"
    assert orderflow["provenance"] == "RUNTIME_INGEST_ONLY"

    fix = get_fix_dma_status()
    assert fix["status"] == "EXPERIMENTAL_DISABLED"
    assert fix["transport_connected"] is False
