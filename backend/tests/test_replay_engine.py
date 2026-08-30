import pytest
from app.replay.replay_service import ReplayService, ReplaySession

class TestTradeReplayEngine:
    """Test suite for Bar-by-Bar Trade Replay Engine."""

    def test_session_creation_and_bounds(self):
        service = ReplayService()
        session = service.create_session_for_trade("TRD-TEST-REPLAY", lookback_bars=25, lookforward_bars=15)
        
        assert session["session_id"].startswith("REP-")
        assert session["total_bars"] >= 40
        assert session["entry_index"] >= 20
        assert session["exit_index"] > session["entry_index"]
        assert session["current_index"] == session["entry_index"]
        assert len(session["visible_candles"]) == session["entry_index"] + 1

    def test_step_forward_and_backward(self):
        service = ReplayService()
        session = service.create_session_for_trade("TRD-TEST-STEP")
        s_id = session["session_id"]
        initial_idx = session["current_index"]

        # Step forward +1
        s_fwd = service.step(s_id, direction=1)
        assert s_fwd["current_index"] == initial_idx + 1

        # Step backward -1
        s_back = service.step(s_id, direction=-1)
        assert s_back["current_index"] == initial_idx

    def test_seek_and_boundary_clamping(self):
        service = ReplayService()
        session = service.create_session_for_trade("TRD-TEST-SEEK")
        s_id = session["session_id"]
        total = session["total_bars"]

        # Seek to specific frame
        res = service.seek(s_id, target_index=10)
        assert res["current_index"] == 10

        # Seek out of bounds (negative)
        res_neg = service.seek(s_id, target_index=-50)
        assert res_neg["current_index"] == 0

        # Seek out of bounds (beyond total)
        res_overflow = service.seek(s_id, target_index=total + 100)
        assert res_overflow["current_index"] == total - 1

    def test_playback_speed_and_state(self):
        service = ReplayService()
        session = service.create_session_for_trade("TRD-TEST-SPEED")
        s_id = session["session_id"]

        res_speed = service.set_speed(s_id, speed=5.0)
        assert res_speed["speed_multiplier"] == 5.0

        res_play = service.set_playing(s_id, is_playing=True)
        assert res_play["is_playing"] is True

    def test_active_trade_pnl_simulation(self):
        service = ReplayService()
        session = service.create_session_for_trade("TRD-TEST-PNL")
        trade_state = session["trade"]
        assert trade_state is not None
        assert "unrealized_pnl" in trade_state
        assert "r_multiple" in trade_state
        assert "mae_r" in trade_state
        assert "mfe_r" in trade_state