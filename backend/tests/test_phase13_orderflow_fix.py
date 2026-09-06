import time
import pytest
from app.services.orderflow.footprint_engine import footprint_engine, FootprintEngine
from app.services.orderflow.delta_heatmap import delta_heatmap_engine, DeltaHeatmapEngine
from app.services.execution.fix_bridge import quickfix_dma_client, QuickFixDmaClient, SOH
from app.services.biometrics.watch_bridge import biometric_watch_bridge

class TestPhase13OrderflowAndFixDma:
    """Test suite for Order Flow Footprints, CVD Liquidity Heatmaps, and CME QuickFIX DMA Client."""

    def test_footprint_tick_bucketing_and_imbalances(self):
        engine = FootprintEngine(tick_size=10.0, imbalance_ratio=3.0)
        # Add buyer aggressors (Ask volume)
        engine.process_trade_tick("BTCUSDT", 64800.0, 1.0, is_buyer_maker=False)
        engine.process_trade_tick("BTCUSDT", 64810.0, 10.0, is_buyer_maker=False)
        # Add seller aggressors (Bid volume)
        engine.process_trade_tick("BTCUSDT", 64800.0, 1.5, is_buyer_maker=True)

        bars = engine.get_footprint_candles("BTCUSDT", limit=1)
        assert len(bars) == 1
        bar = bars[0]
        assert bar["total_volume"] == 12.5
        assert bar["delta"] == 9.5
        assert bar["poc_price"] == 64810.0
        assert bar["poc_volume"] == 10.0

    def test_stacked_imbalances_detection(self):
        engine = FootprintEngine(tick_size=10.0, imbalance_ratio=3.0)
        # 3 contiguous prices
        imb_prices = [64800.0, 64810.0, 64820.0]
        assert engine._detect_stacked(imb_prices) is True

        # Non-contiguous prices
        assert engine._detect_stacked([64800.0, 64830.0, 64860.0]) is False
        assert engine._detect_stacked([64800.0, 64810.0]) is False

    def test_cumulative_volume_delta_and_divergence(self):
        engine = DeltaHeatmapEngine()
        engine.update_cvd_tick("BTCUSDT", delta=10.0, price=64800.0)
        engine.update_cvd_tick("BTCUSDT", delta=15.0, price=64820.0)
        engine.update_cvd_tick("BTCUSDT", delta=-5.0, price=64810.0)

        cvd_res = engine.get_cvd_series("BTCUSDT", limit=10)
        assert cvd_res["current_cvd"] == 20.0
        assert len(cvd_res["series"]) == 3

        # Test LOB depth
        engine.update_book_depth(
            "BTCUSDT",
            bids=[[64800.0, 12.0]],
            asks=[[64810.0, 9.0]]
        )
        hm = engine.get_liquidity_heatmap("BTCUSDT")
        assert hm["snapshots_count"] == 1

    def test_quickfix_message_encoding_decoding_and_checksum(self):
        client = QuickFixDmaClient(sender_comp_id="TEST_SENDER", target_comp_id="CME_TEST")
        raw = client.encode_fix_message("D", {11: "ORD-999", 55: "ESM6", 54: "1", 38: 5, 44: 5610.5})

        assert raw.startswith("8=FIX.4.4\x019=")
        assert "\x0135=D\x01" in raw
        assert "\x0111=ORD-999\x01" in raw
        assert "\x0110=" in raw

        # Checksum calculation correctness
        checksum = QuickFixDmaClient.calculate_checksum("8=FIX.4.4\x0135=0\x01")
        assert len(checksum) == 3
        assert checksum.isdigit()

        # Decoding
        decoded = QuickFixDmaClient.decode_fix_message(raw)
        assert decoded[35] == "D"
        assert decoded[11] == "ORD-999"
        assert decoded[55] == "ESM6"
        assert decoded[38] == "5"

    def test_quickfix_dma_order_is_disabled_without_transport(self, monkeypatch):
        client = QuickFixDmaClient(sender_comp_id="TEST_SENDER", target_comp_id="CME_TEST")

        monkeypatch.setattr(
            "app.services.execution.fix_bridge.risk_interceptor.evaluate_order",
            lambda _order: pytest.fail("Unavailable FIX transport must not evaluate an order"),
        )

        res = client.send_new_order_single(symbol="ESM6", side="BUY", qty=1.0, price=5600.0)
        assert res["status"] == "EXPERIMENTAL_DISABLED"
        assert res["execution_status"] == "NOT_SUBMITTED"
        assert res["transport_connected"] is False
        assert res["round_trip_latency_us"] is None
        assert "FILLED" not in res.values()
        assert "raw_fix_wire" not in res

        session = client.get_session_status()
        assert session["status"] == "EXPERIMENTAL_DISABLED"
        assert session["is_logged_on"] is False
        assert session["round_trip_latency_us"] is None

        biometric_watch_bridge.update_telemetry(bpm=140.0, hrv=15.0)
        blocked = client.send_new_order_single(symbol="ESM6", side="BUY", qty=1.0, price=5600.0)
        assert blocked["status"] == "EXPERIMENTAL_DISABLED"
        assert blocked["execution_status"] == "NOT_SUBMITTED"
        assert blocked["round_trip_latency_us"] is None
        biometric_watch_bridge.update_telemetry(bpm=58.0, hrv=85.0)
