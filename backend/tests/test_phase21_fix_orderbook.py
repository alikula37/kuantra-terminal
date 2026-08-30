import pytest
from app.services.matching.order_book import LimitOrderBook, Order, PriceLevel
from app.services.fix.fix_gateway import FIXMessage, FIXSessionStateMachine
from app.services.fix.dma_router import DirectMarketAccessRouter

class TestPhase21FIXAndOrderBook:
    """Test suite for Native L2/L3 Limit Order Book, FIX Protocol Gateway, and DMA Router."""

    def test_order_book_operations(self):
        ob = LimitOrderBook(symbol="BTCUSDT")

        # 1. Add Resting Bids and Asks
        res_bid = ob.add_order("BID-001", "BUY", 65000.0, 2.0, "LIMIT")
        assert res_bid["status"] == "NEW"
        assert res_bid["filled_size"] == 0.0
        assert res_bid["remaining_size"] == 2.0

        res_ask = ob.add_order("ASK-001", "SELL", 65010.0, 3.0, "LIMIT")
        assert res_ask["status"] == "NEW"

        best_bid, best_ask = ob.get_bbo()
        assert best_bid == 65000.0
        assert best_ask == 65010.0

        # 2. Cancel Order
        cancel_res = ob.cancel_order("BID-001")
        assert cancel_res["status"] == "CANCELLED_SUCCESS"
        assert cancel_res["cancelled_size"] == 2.0
        assert ob.get_bbo()[0] is None

        # Re-add bid
        ob.add_order("BID-002", "BUY", 65000.0, 5.0, "LIMIT")

        # 3. Post-Only Rejection
        post_only_reject = ob.add_order("POST-REJECT", "BUY", 65015.0, 1.0, "POST_ONLY")
        assert post_only_reject["status"] == "REJECTED_POST_ONLY_RESTRICTED"

        # 4. Fill-Or-Kill (FOK) Insufficient Liquidity
        fok_fail = ob.add_order("FOK-001", "BUY", 65010.0, 100.0, "FOK")
        assert fok_fail["status"] == "CANCELLED_FOK_INSUFFICIENT_LIQUIDITY"

        # 5. Immediate-Or-Cancel (IOC) Partial Fill
        ioc_res = ob.add_order("IOC-001", "BUY", 65010.0, 5.0, "IOC")
        assert ioc_res["status"] == "PARTIALLY_FILLED_IOC_CANCELLED"
        assert ioc_res["filled_size"] == 3.0
        assert ioc_res["remaining_size"] == 2.0

    def test_order_book_mbp_aggregation_and_vwap(self):
        ob = LimitOrderBook(symbol="ETHUSDT")
        ob.add_order("B1", "BUY", 2700.0, 10.0, "LIMIT")
        ob.add_order("B2", "BUY", 2690.0, 20.0, "LIMIT")
        ob.add_order("A1", "SELL", 2710.0, 5.0, "LIMIT")
        ob.add_order("A2", "SELL", 2720.0, 15.0, "LIMIT")

        snap = ob.get_l2_snapshot(depth=5)
        assert snap["symbol"] == "ETHUSDT"
        assert snap["best_bid"] == 2700.0
        assert snap["best_ask"] == 2710.0
        assert snap["spread_absolute"] == 10.0
        assert snap["mid_price"] == 2705.0
        assert snap["total_bid_depth_volume"] == 30.0
        assert snap["total_ask_depth_volume"] == 20.0
        assert snap["book_imbalance_ratio"] > 0.0 # Bids > Asks

        # Test Sweep
        sweep = ob.simulate_sweep("BUY", size=10.0)
        assert sweep["filled_size"] == 10.0
        # 5 @ 2710 + 5 @ 2720 = 13550 + 13600 = 27150 / 10 = 2715.0
        assert sweep["execution_vwap"] == 2715.0
        assert sweep["slippage_bps"] > 0

    def test_fix_message_parser_and_serializer(self):
        # 1. Create and Serialize
        msg = FIXMessage(begin_string="FIX.4.4", msg_type="D")
        msg.set_tag(11, "CLORD-12345")
        msg.set_tag(55, "BTCUSDT")
        msg.set_tag(54, "1")
        msg.set_tag(38, "2.5")
        msg.set_tag(44, "65000.0")

        raw_fix = msg.serialize(delimiter="|")
        assert "8=FIX.4.4|" in raw_fix
        assert "35=D|" in raw_fix
        assert "11=CLORD-12345|" in raw_fix
        assert "10=" in raw_fix # CheckSum tag

        # 2. Parse and Validate
        parsed = FIXMessage.parse(raw_fix, delimiter="|")
        assert parsed.begin_string == "FIX.4.4"
        assert parsed.msg_type == "D"
        assert parsed.get_tag(11) == "CLORD-12345"
        assert parsed.get_tag(55) == "BTCUSDT"
        assert parsed.get_tag(38) == "2.5"

    def test_fix_session_state_machine(self):
        session = FIXSessionStateMachine(sender_comp_id="TEST_SENDER", target_comp_id="TEST_TARGET")
        assert session.state == "DISCONNECTED"

        # 1. Create Logon
        logon_raw = session.create_logon()
        assert "35=A" in logon_raw
        assert session.state == "LOGON_SENT"

        # 2. Incoming Logon Confirm
        ack_res = session.process_incoming("8=FIX.4.4|9=45|35=A|49=TEST_TARGET|56=TEST_SENDER|34=1|10=050|")
        assert ack_res["status"] == "SESSION_ACTIVE"
        assert session.state == "ACTIVE"

        # 3. Test Request
        test_req_res = session.process_incoming("8=FIX.4.4|9=50|35=1|112=TEST_REQ_999|49=TEST_TARGET|56=TEST_SENDER|34=2|10=060|")
        assert test_req_res["status"] == "TEST_REQUEST_REPLIED"
        assert "35=0" in test_req_res["response_fix"]
        assert "112=TEST_REQ_999" in test_req_res["response_fix"]

        # 4. Execution Report Processing
        exec_raw = "8=FIX.4.4|9=80|35=8|17=EXEC-001|11=CLORD-12345|39=2|14=2.5|151=0.0|6=65000.0|10=080|"
        exec_res = session.process_incoming(exec_raw)
        assert exec_res["status"] == "EXECUTION_REPORT_PROCESSED"
        assert exec_res["exec_id"] == "EXEC-001"
        assert exec_res["ord_status"] == "2" # Filled
        assert exec_res["cum_qty"] == 2.5

    def test_dma_router_and_api_endpoints(self):
        router = DirectMarketAccessRouter()

        # Submit Order
        sub = router.submit_order(
            symbol="BTCUSDT",
            side="BUY",
            price=64990.0,
            qty=1.0,
            order_type="LIMIT",
            destination="INTERNAL_MATCHING_ENGINE"
        )
        assert "CLORD-" in sub["cl_ord_id"]
        assert sub["destination"] == "INTERNAL_MATCHING_ENGINE"
        assert sub["matching_status"] in ("NEW", "FILLED", "PARTIALLY_FILLED")

        # Cancel Order
        cancel = router.cancel_order(cl_ord_id=sub["cl_ord_id"], symbol="BTCUSDT", side="BUY")
        assert cancel["orig_cl_ord_id"] == sub["cl_ord_id"]
        assert "CANC-" in cancel["cancel_cl_ord_id"]