"""Regression tests for recorded-bar replay, never synthetic success."""
import json

import pytest
from fastapi.testclient import TestClient

from app.quant.candle_evidence import duckdb_driver
from app.replay.replay_service import ReplayService
from app.services.trade_read_adapter import trade_read_adapter


@pytest.fixture
def replay(monkeypatch, recorded_trade, recorded_candles):
    monkeypatch.setattr(trade_read_adapter, "get_trade", lambda trade_id: recorded_trade if trade_id == recorded_trade["id"] else None)
    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *args, **kwargs: recorded_candles)
    return ReplayService(trade_reader=trade_read_adapter)


def test_unknown_trade_is_no_data_without_session(replay):
    response = replay.create_session_for_trade("UNKNOWN")
    assert response["status"] == "NO_DATA"
    assert response["reason"] == "TRADE_NOT_FOUND"
    assert response["session_id"] is None
    assert response["trade"] is None and response["current_candle"] is None
    assert response["visible_candles"] == []
    assert replay.sessions == {}


def test_recorded_session_uses_time_indices_and_is_deterministic(replay, recorded_trade, recorded_candles):
    response = replay.create_session_for_trade(recorded_trade["id"])
    assert response["status"] == "READY"
    assert response["provenance"]["quality"] == "BAR_APPROXIMATION"
    assert response["provenance"]["source_verified"] is False
    assert response["replay_fingerprint"] == response["market_context"]["fingerprint_sha256"]
    assert response["market_context"]["bar_count"] == 6
    assert response["market_context"]["trade_bar_count"] == 3
    assert response["market_context"]["complete_trade_window"] is True
    assert response["total_bars"] == 6
    assert (response["entry_index"], response["exit_index"], response["current_index"]) == (1, 3, 1)
    assert response["visible_candles"][-1]["time"] == recorded_candles[1]["time"]
    second = replay.create_session_for_trade(recorded_trade["id"])
    assert response["session_id"] != second["session_id"]
    assert {k: v for k, v in response.items() if k != "session_id"} == {k: v for k, v in second.items() if k != "session_id"}


def test_market_context_attachment_endpoint_is_bounded_and_replay_fingerprinted(replay, recorded_trade):
    context = replay.trade_reader.get_market_context(
        recorded_trade["id"],
        lookback_bars=1,
        lookforward_bars=2,
    )
    assert context["status"] == "READY"
    assert context["market_context"]["lookback_bars"] == 1
    assert context["market_context"]["lookforward_bars"] == 2
    assert context["market_context"]["complete_trade_window"] is True
    assert context["market_context"]["source_verified"] is False


def test_seek_pre_entry_and_post_exit_freeze(replay, recorded_trade):
    response = replay.create_session_for_trade(recorded_trade["id"])
    session_id = response["session_id"]
    assert response["trade"]["phase"] == "ACTIVE"
    assert response["trade"]["unrealized_pnl"] == pytest.approx(-0.4)
    assert response["trade"]["mae_r"] == pytest.approx(-0.8)
    assert replay.step(session_id)["current_index"] == 2
    assert replay.step(session_id, -1)["current_index"] == 1
    before = replay.seek(session_id, -50)["trade"]
    assert before["phase"] == "PRE_ENTRY"
    for key in ("unrealized_pnl", "realized_pnl", "r_multiple", "mae_r", "mfe_r"):
        assert before[key] is None
    at_exit = replay.seek(session_id, 3)["trade"]
    after = replay.seek(session_id, 999)["trade"]
    assert after["phase"] == at_exit["phase"] == "CLOSED"
    assert after["unrealized_pnl"] is None
    assert after["realized_pnl"] == 5.5  # recorded net PnL, not gross price-derived 6
    assert after["current_price"] != at_exit["current_price"]
    for key in ("r_multiple", "mae_r", "mfe_r", "realized_pnl"):
        assert after[key] == at_exit[key]
    assert after["mfe_r"] == 4
    assert after["mae_r"] == pytest.approx(-0.8)
    assert after["r_multiple"] == 3  # explicitly gross price movement
    assert replay.seek(session_id, 1)["trade"]["realized_pnl"] is None


def test_missing_stop_no_r_at_any_cursor(replay, recorded_trade):
    recorded_trade["stop_loss"] = None
    session_id = replay.create_session_for_trade(recorded_trade["id"])["session_id"]
    for index in range(6):
        trade = replay.seek(session_id, index)["trade"]
        assert all(trade[key] is None for key in ("risk_unit", "r_multiple", "mae_r", "mfe_r"))


def test_unknown_realized_pnl_is_not_zero(replay, recorded_trade):
    recorded_trade["pnl"] = None
    session_id = replay.create_session_for_trade(recorded_trade["id"])["session_id"]
    assert replay.seek(session_id, 3)["trade"]["realized_pnl"] is None


@pytest.mark.parametrize("history,reason", [([], "NO_CANDLE_HISTORY"), ([{"time": 60}], "NO_CANDLE_HISTORY")])
def test_missing_or_unrelated_history_no_session(replay, recorded_trade, monkeypatch, history, reason):
    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *a, **kw: history)
    response = replay.create_session_for_trade(recorded_trade["id"])
    assert response["status"] == "NO_DATA" and response["reason"] == reason
    assert response["session_id"] is None and not replay.sessions


@pytest.mark.parametrize("store,method", [(duckdb_driver, "get_candles_range"), (trade_read_adapter, "get_trade")])
def test_store_failure_is_unavailable_and_does_not_leak(replay, recorded_trade, monkeypatch, store, method):
    def fail(*a, **kw):
        raise RuntimeError("private/path/credential")
    monkeypatch.setattr(store, method, fail)
    response = replay.create_session_for_trade(recorded_trade["id"])
    assert response["status"] == "UNAVAILABLE"
    assert response["session_id"] is None and not replay.sessions
    assert "private/path" not in json.dumps(response)


def test_playback_bounds_speed_and_session_eviction(replay, recorded_trade):
    first = replay.create_session_for_trade(recorded_trade["id"])["session_id"]
    assert replay.set_speed(first, 100)["speed_multiplier"] == 20
    assert replay.set_speed(first, 0.1)["speed_multiplier"] == 0.25
    with pytest.raises(ValueError):
        replay.set_speed(first, float("nan"))
    assert replay.set_playing(first, True)["is_playing"] is True
    assert replay.seek(first, 999)["is_playing"] is False
    assert replay.set_playing(first, True)["is_playing"] is False
    for _ in range(32):
        replay.create_session_for_trade(recorded_trade["id"])
    assert len(replay.sessions) == 32 and replay.get_session(first) is None
    with pytest.raises(ValueError, match="not found"):
        replay.step(first)


def test_http_no_data_and_speed_validation(test_app, replay, recorded_trade, monkeypatch):
    from app.api import endpoints
    monkeypatch.setattr(endpoints, "replay_service", replay)
    client = TestClient(test_app)
    assert client.get("/api/v1/replay/session/MISSING").json()["session_id"] is None
    response = client.get(f"/api/v1/replay/session/{recorded_trade['id']}").json()
    session_id = response["session_id"]
    context = client.get(f"/api/v1/trades/{recorded_trade['id']}/market-context")
    assert context.status_code == 200
    assert context.json()["market_context"]["fingerprint_sha256"] == response["replay_fingerprint"]
    assert client.post(f"/api/v1/replay/{session_id}/speed", json={"speed": "NaN"}).status_code == 422
    assert client.post("/api/v1/replay/evicted/speed", json={"speed": 1}).status_code == 404
    assert client.post(f"/api/v1/replay/{session_id}/seek", json={"target_index": 5}).json()["trade"]["realized_pnl"] == 5.5


def test_websocket_failed_init_does_not_reuse_previous_session(test_app, replay, recorded_trade, monkeypatch):
    from app.api import endpoints
    monkeypatch.setattr(endpoints, "replay_service", replay)
    with TestClient(test_app).websocket_connect("/api/v1/ws/replay") as socket:
        socket.send_json({"action": "INIT", "trade_id": recorded_trade["id"]})
        assert socket.receive_json()["data"]["status"] == "READY"
        socket.send_json({"action": "INIT", "trade_id": "MISSING"})
        assert socket.receive_json()["data"]["status"] == "NO_DATA"
        socket.send_json({"action": "STEP"})
        assert socket.receive_json()["type"] == "REPLAY_ERROR"
        socket.send_text("invalid JSON")
        assert socket.receive_json()["type"] == "REPLAY_ERROR"
