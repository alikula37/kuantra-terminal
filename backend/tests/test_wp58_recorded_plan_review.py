"""Synthetic, read-only plan revision acceptance. No broker history claims."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.db.sqlite_driver import SQLiteDriver
from app.services.local_tracking import LocalTrackingService
from app.quant.trade_plan_reference import recorded_plan_context


@pytest.fixture
def tracking(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "synthetic-wp58.sqlite"))
    trade = driver.record_trade_with_evidence(
        {"id": "SYNTHETIC-WP58", "symbol": "BTCUSDT", "side": "BUY",
         "entry_price": 100, "qty": 2, "qty_unit": "BASE", "record_mode": "SIMULATION"},
        event_type="IntentRecorded", idempotency_key="synthetic-wp58")
    service = LocalTrackingService(driver)
    plan = {"enabled": True, "source_id": "binance_public", "source_symbol": "BTCUSDT",
            "stop_loss": 95, "targets": [{"price": 110, "percent": 50}, {"price": 120, "percent": 50}]}
    service.edit(trade["id"], plan, expected_revision=0)
    plan["targets"][1]["price"] = 125
    service.edit(trade["id"], plan, expected_revision=1)
    return driver, service, trade, plan


def rows(driver):
    with driver.get_connection() as conn:
        return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]
                for table in ("trades", "evidence_events", "local_tracking_projections")}


def test_history_exposes_verified_record_time_and_lineage_without_writes(tracking):
    driver, service, trade, _ = tracking
    before = rows(driver)
    history = service.history(trade["id"])
    assert history[1]["causation_id"] == history[0]["event_id"]
    assert history[0]["recorded_at_utc"]
    assert history[0]["reset_index"] == 0
    context = recorded_plan_context(trade, history, history[1]["recorded_at_utc"])
    assert context["status"] == "READY"
    assert context["plan"]["reference_code"] == "RECORDED_LOCAL_PLAN"
    assert context["plan"]["source_event_hash"] == history[1]["event_hash"]
    assert context["plan"]["levels"][-1]["price"] == 125
    assert rows(driver) == before


def test_before_first_and_same_time_use_chain_order_not_future_or_current(tracking):
    _, service, trade, _ = tracking
    history = service.history(trade["id"])
    context = recorded_plan_context(trade, history, "2000-01-01T00:00:00Z")
    assert context["status"] == "NOT_AVAILABLE" and context["plan"] is None
    assert context["available_revisions"] == []
    first_time = history[0]["recorded_at_utc"]
    assert len(recorded_plan_context(trade, history, first_time)["available_revisions"]) == 1
    same_time = deepcopy(history)
    same_time[1]["recorded_at_utc"] = first_time
    result = recorded_plan_context(trade, same_time, first_time)
    assert result["plan"]["plan_revision"] == 2
    # Offset representations must denote the same instant.
    offset = datetime.fromisoformat(first_time).astimezone(timezone.utc).isoformat()
    assert recorded_plan_context(trade, same_time, offset) == result


def test_partial_close_only_exposes_levels_not_future_closure_or_result(tracking):
    driver, service, trade, _ = tracking
    service.observe(trade["id"], {"price": 110}, manual=True, expected_revision=2)
    history = service.history(trade["id"])
    before = rows(driver)
    result = recorded_plan_context(trade, history, history[-1]["recorded_at_utc"])
    assert result["plan"]["plan_revision"] == 3
    assert "closures" not in result["plan"] and "gross_pnl" not in result["plan"]
    assert rows(driver) == before


def test_correction_reset_keeps_the_old_entry_in_its_own_revision(tracking):
    driver, service, trade, plan = tracking
    corrected = {**trade, "entry_price": 101}
    with driver.get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        service.edit_in_transaction(conn, corrected, plan, expected_revision=2, reset=True)
        conn.commit()
    history = service.history(trade["id"])
    assert history[-1]["reset_index"] == 1
    old = recorded_plan_context(corrected, history, history[1]["recorded_at_utc"])
    new = recorded_plan_context(corrected, history, history[-1]["recorded_at_utc"])
    assert old["plan"]["levels"][0]["price"] == 100
    assert new["plan"]["levels"][0]["price"] == 101
    assert new["plan"]["plan_revision"] == 1


@pytest.mark.parametrize("mutation", ["scope", "revision", "causation", "time", "hash", "reset"])
def test_invalid_history_is_unknown_not_a_current_plan_fallback(tracking, mutation):
    _, service, trade, _ = tracking
    history = deepcopy(service.history(trade["id"]))
    if mutation == "scope": history[-1]["state"]["symbol"] = "GOLD"
    if mutation == "revision": history[-1]["state"]["revision"] = 9
    if mutation == "causation": history[-1]["causation_id"] = "wrong"
    if mutation == "time": history[-1]["recorded_at_utc"] = "2026-01-01T12:00:00"
    if mutation == "hash": history[-1]["event_hash"] = ""
    if mutation == "reset": history[-1]["reset_index"] = 9
    result = recorded_plan_context(trade, history, datetime.now(timezone.utc).isoformat())
    assert result["status"] == "UNKNOWN" and result["plan"] is None
    assert result["available_revisions"] == []


@pytest.mark.parametrize("status", ["OPEN", "CLOSED"])
def test_missing_legacy_import_history_remains_not_available(tracking, status):
    _, _, trade, _ = tracking
    result = recorded_plan_context({**trade, "status": status}, [], "2026-10-03T00:00:00Z")
    assert result["status"] == "NOT_AVAILABLE" and result["plan"] is None


def test_hash_valid_but_broken_reset_link_is_rejected_by_the_history_reader(tracking):
    driver, service, trade, _ = tracking
    state = deepcopy(service.get(trade["id"]))
    state["revision"] = 1
    service.ledger.append_event(
        event_type="PositionProjectionUpdated", account_id="local-journal", venue="local-journal",
        correlation_id=trade["id"], causation_id="NOT-THE-PREVIOUS-EVENT",
        idempotency_key="synthetic-broken-reset", normalized_payload={"local_tracking": state, "action": "PLAN_RESET"},
        schema_version="1", adapter_version="local-tracking-v1",
        provenance={"source": "local_tracking", "basis": "LOCAL_ESTIMATE", "broker_execution": False})
    before = rows(driver)
    with pytest.raises(ValueError, match="reset lineage"):
        service.history(trade["id"])
    assert rows(driver) == before


def test_other_producer_cannot_claim_a_local_recording_instant(tracking):
    driver, service, trade, _ = tracking
    history = service.history(trade["id"])
    state = deepcopy(history[-1]["state"])
    state["revision"] = 3
    service.ledger.append_event(
        event_type="PositionProjectionUpdated", account_id="local-journal", venue="local-journal",
        correlation_id=trade["id"], causation_id=history[-1]["event_id"],
        idempotency_key="synthetic-other-producer", normalized_payload={"local_tracking": state, "action": "PLAN_SAVED"},
        schema_version="1", adapter_version="local-tracking-v1", provenance={"source": "some_import"})
    before = rows(driver)
    with pytest.raises(ValueError, match="producer"):
        service.history(trade["id"])
    assert rows(driver) == before


@pytest.mark.parametrize("mode", ["OPEN", "CLOSED"])
def test_session_cursor_only_releases_eligible_revisions_and_rewind_hides_them(tracking, mode):
    from types import SimpleNamespace
    from app.replay.replay_service import ReplaySession, OpenReviewSession, ReplayService
    driver, tracking_reader, trade, _ = tracking
    history = tracking_reader.history(trade["id"])
    # Fixed synthetic recording instants model an edit inside a candle.
    history[0]["recorded_at_utc"] = "2026-10-03T10:00:30+00:00"
    history[1]["recorded_at_utc"] = "2026-10-03T10:01:30+00:00"
    start = int(datetime(2026, 10, 3, 10, tzinfo=timezone.utc).timestamp())
    candles = [{"time": start + i * 60, "open": 100, "high": 101, "low": 99, "close": 100, "volume": 0} for i in range(3)]
    reviewed = {**trade, "entry_time": "2026-10-03T10:00:00Z", "exit_time": "2026-10-03T10:02:00Z",
                "exit_price": 100, "pnl": None, "risk_unit": None, "risk_reason": None,
                "stop_loss": None, "take_profit": None}
    base = dict(trade=reviewed, entry_index=0, exit_index=2,
                market_context={"fingerprint_sha256": "synthetic"})
    if mode == "CLOSED":
        session = ReplaySession("synthetic-session", SimpleNamespace(candles=candles, **base), plan_history=history)
    else:
        cache = [{**c, "timestamp": c["time"]} for c in candles]
        evidence = SimpleNamespace(candles=cache, symbol=trade["symbol"], timeframe="1m",
                                   history_status="PARTIAL", entry_bar_present=True, coverage={},
                                   freshness={}, provenance={}, **base)
        session = OpenReviewSession("synthetic-session", evidence, plan_history=history)
    service = ReplayService(trade_reader=object(), tracking_reader=tracking_reader)
    service.sessions[session.session_id] = session
    before = rows(driver)
    first = service.get_session(session.session_id)
    assert first["recorded_plans"]["available_revisions"] == []
    second = service.seek(session.session_id, 1)
    assert len(second["recorded_plans"]["available_revisions"]) == 1
    assert second["recorded_plans"]["plan"]["plan_revision"] == 1
    last = service.seek(session.session_id, 2)
    assert last["recorded_plans"]["plan"]["plan_revision"] == 2
    assert service.seek(session.session_id, 0)["recorded_plans"]["plan"] is None
    assert rows(driver) == before
