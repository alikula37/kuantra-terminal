"""P1 chart trade review: read-only plan reference and close provenance.

These tests pin the honesty rules of the single-trade chart review:
- levels come from the local tracking plan when it matches the trade, otherwise
  from the recorded trade row; nothing is invented;
- every level set is a *current-plan reference*, never a claim about what was
  valid at the replay cursor;
- the close marker is classified by recorded provenance (user report, file
  import, simulation, broker-verified only if the field literally says so);
- nothing in the review path writes to the journal, ledger or plan.
"""

from __future__ import annotations

import json

import pytest

from app.quant.trade_plan_reference import (
    classify_origin,
    close_evidence,
    close_source_class,
    plan_reference,
)
from app.replay.replay_service import ReplayService


def trade_row(**overrides):
    base = {
        "id": "TRD-1", "symbol": "BTCUSDT", "side": "BUY", "status": "CLOSED",
        "entry_price": 100.0, "exit_price": 110.0, "qty": 1.0,
        "stop_loss": 95.0, "take_profit": 110.0,
        "entry_time": "2026-08-02T09:00:00.000000Z", "exit_time": "2026-08-02T12:00:00.000000Z",
        "pnl": 9.5, "commission": 0.5,
    }
    base.update(overrides)
    return base


def tracking_state(**overrides):
    base = {
        "trade_id": "TRD-1", "basis": "LOCAL_ESTIMATE", "version": 1,
        "entry_price": "100", "stop_loss": "96", "remaining_qty": "0",
        "initial_qty": "1", "revision": 3, "reset_count": 0,
        "armed_at": "2026-08-02T08:00:00+00:00",
        "targets": [
            {"id": "T1", "price": "105", "percent": "50"},
            {"id": "T2", "price": "108", "percent": "30"},
            {"id": "T3", "price": "112", "percent": "20"},
        ],
        "closures": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Level source rules
# ---------------------------------------------------------------------------


def test_local_plan_levels_win_and_keep_their_target_weights():
    plan = plan_reference(trade_row(), tracking_state())
    assert plan["kind"] == "LOCAL_PLAN"
    assert plan["reference"] is True
    assert plan["reference_code"] == "CURRENT_PLAN_REFERENCE"
    levels = {level["kind"]: level for level in plan["levels"]}
    assert levels["ENTRY"]["price"] == 100.0
    assert levels["SL"]["price"] == 96.0
    assert levels["TP1"]["price"] == 105.0 and levels["TP1"]["weight_pct"] == 50.0
    assert levels["TP3"]["weight_pct"] == 20.0


def test_trade_row_fallback_has_no_invented_weight_on_single_tp():
    plan = plan_reference(trade_row(), None)
    assert plan["kind"] == "TRADE_ROW"
    assert plan["reference"] is True
    levels = {level["kind"]: level for level in plan["levels"]}
    assert levels["SL"]["price"] == 95.0
    assert levels["TP1"]["price"] == 110.0
    assert levels["TP1"].get("weight_pct") is None


def test_missing_levels_are_omitted_not_guessed():
    plan = plan_reference(trade_row(stop_loss=None, take_profit=None), None)
    kinds = [level["kind"] for level in plan["levels"]]
    assert kinds == ["ENTRY"]
    plan2 = plan_reference(trade_row(stop_loss=None), tracking_state(stop_loss=None, targets=[]))
    kinds2 = [level["kind"] for level in plan2["levels"]]
    assert kinds2 == ["ENTRY"]


def test_plan_created_after_entry_is_flagged_even_with_revision_one():
    later = tracking_state(revision=1, armed_at="2026-08-03T10:00:00+00:00")
    plan = plan_reference(trade_row(), later)
    assert plan["kind"] == "LOCAL_PLAN"
    assert plan["created_after_entry"] is True
    early = tracking_state(revision=5, armed_at="2026-08-02T08:00:00+00:00")
    assert plan_reference(trade_row(), early)["created_after_entry"] is False


def test_mismatched_plan_entry_falls_back_to_the_recorded_row():
    plan = plan_reference(trade_row(), tracking_state(entry_price="101.5"))
    assert plan["kind"] == "TRADE_ROW"
    assert plan.get("plan_mismatch") is True


def test_short_trade_plan_still_lists_levels_without_validation_claims():
    plan = plan_reference(trade_row(side="SELL", stop_loss=105.0, take_profit=90.0,
                                     exit_price=90.0), None)
    levels = {level["kind"]: level for level in plan["levels"]}
    assert levels["SL"]["price"] == 105.0
    assert levels["TP1"]["price"] == 90.0


# ---------------------------------------------------------------------------
# Close provenance
# ---------------------------------------------------------------------------


def test_origin_classification_uses_recorded_ledger_sources():
    assert classify_origin([{"provenance": {"source": "csv"}}]) == "IMPORTED_FILE"
    assert classify_origin([{"provenance": {"source": "journal_external"}}]) == "JOURNAL"
    assert classify_origin([{"provenance": {"source": "journal_edit"}}]) == "JOURNAL"
    assert classify_origin([]) == "UNKNOWN"


def test_close_source_labels_never_upgrade_an_import_to_broker_verification():
    assert close_source_class(trade_row(close_source="USER_REPORTED"), "JOURNAL") == "USER_REPORTED"
    assert close_source_class(trade_row(close_source=None), "IMPORTED_FILE") == "IMPORTED_FILE"
    assert close_source_class(trade_row(close_source="BROKER_IMPORT"), "IMPORTED_FILE") == "IMPORTED_FILE"
    assert close_source_class(trade_row(close_source="BROKER_VERIFIED"), "JOURNAL") == "SOURCE_DECLARED"
    assert close_source_class(trade_row(close_source=None), "UNKNOWN") == "UNKNOWN"
    assert close_source_class(trade_row(close_source="SOMETHING_NEW"), "JOURNAL") == "SOURCE_DECLARED"
    assert close_source_class(trade_row(record_mode="SIMULATION", close_source="USER_REPORTED"), "JOURNAL") == "SIMULATION"


def test_close_evidence_keeps_raw_close_source_and_is_never_broker_verified():
    evidence = close_evidence(trade_row(close_source=None), "IMPORTED_FILE")
    assert evidence["price"] == 110.0
    assert evidence["source"] == "IMPORTED_FILE"
    assert evidence["broker_verified"] is False
    assert evidence["close_source_raw"] is None
    assert evidence["time_utc"].startswith("2026-08-02T12:00:00")


# ---------------------------------------------------------------------------
# Session payload
# ---------------------------------------------------------------------------


class FakeTradeReader:
    def __init__(self, trade, events):
        self.trade, self.events = trade, events

    def get_trade(self, trade_id):
        return dict(self.trade) if self.trade else None

    def list_events_for_trade(self, trade_id, **kwargs):
        return list(self.events)


class FakeTrackingReader:
    def __init__(self, state):
        self.state = state

    def get(self, trade_id):
        return self.state


def make_service(monkeypatch, recorded_trade, recorded_candles, *, events=None, tracking=None, trade=None):
    from app.quant.candle_evidence import duckdb_driver

    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *args, **kwargs: list(recorded_candles))
    payload = dict(trade if trade is not None else recorded_trade)
    return ReplayService(
        trade_reader=FakeTradeReader(payload, events or []),
        tracking_reader=FakeTrackingReader(tracking),
    )


def with_close(trade, **overrides):
    merged = dict(trade)
    merged.update(overrides)
    return merged


def test_session_exposes_plan_reference_and_hides_close_before_exit(monkeypatch, recorded_trade, recorded_candles):
    service = make_service(monkeypatch, recorded_trade, recorded_candles, tracking=tracking_state())
    session = service.create_session_for_trade(recorded_trade["id"])
    assert session["status"] == "READY"
    assert session["plan"]["kind"] == "LOCAL_PLAN"
    assert session["plan"]["reference_code"] == "CURRENT_PLAN_REFERENCE"
    assert session["close_evidence"] is None  # cursor sits at the entry bar
    assert session["current_index"] < session["exit_index"]
    step = service.step(session["session_id"], direction=1)
    assert step["close_evidence"] is None  # still before the exit bar
    last = service.seek(session["session_id"], session["total_bars"] - 1)
    assert last["trade"]["phase"] == "CLOSED"
    assert last["close_evidence"]["price"] == recorded_trade["exit_price"]
    assert last["close_evidence"]["broker_verified"] is False


class LedgerRepoReader:
    """Mimics the real read adapter: no event method, only a scoped ledger repo."""

    account_id = "local-journal"
    projection_venues = ("local-journal",)

    def __init__(self, trade, events):
        self.trade = trade
        self.calls = []
        outer = self

        class _Ledger:
            def list_events_for_trade(self, trade_id, *, account_id="local-journal", venue=None, venues=None):
                outer.calls.append((trade_id, account_id, tuple(venues or ())))
                return list(events)

        self.ledger_repo = _Ledger()

    def get_trade(self, trade_id):
        return dict(self.trade)


def test_origin_lookup_uses_the_adapters_ledger_repo(monkeypatch, recorded_trade, recorded_candles):
    from app.quant.candle_evidence import duckdb_driver

    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *args, **kwargs: list(recorded_candles))
    reader = LedgerRepoReader(with_close(recorded_trade, close_source=None), [{"provenance": {"source": "csv"}}])
    service = ReplayService(trade_reader=reader, tracking_reader=FakeTrackingReader(None))
    session = service.create_session_for_trade(recorded_trade["id"])
    assert session["origin_class"] == "IMPORTED_FILE"
    assert reader.calls and reader.calls[0][0] == recorded_trade["id"]
    assert reader.calls[0][2] == ("local-journal",)


def test_session_close_source_comes_from_recorded_events(monkeypatch, recorded_trade, recorded_candles):
    imported = with_close(recorded_trade, close_source=None)
    service = make_service(
        monkeypatch, recorded_trade, recorded_candles,
        trade=imported, events=[{"provenance": {"source": "csv"}}], tracking=None,
    )
    last = service.seek(
        service.create_session_for_trade(recorded_trade["id"])["session_id"], len(recorded_candles) - 1
    )
    assert last["close_evidence"]["source"] == "IMPORTED_FILE"
    assert last["origin_class"] == "IMPORTED_FILE"
    assert last["plan"]["kind"] == "TRADE_ROW"


def test_open_trade_is_reported_honestly_without_candles(monkeypatch, recorded_trade, recorded_candles):
    """Since OP-01, open trades use the open-review path: without a declared
    provider identity the chart match cannot be established (fail closed)."""

    open_trade = with_close(recorded_trade, status="OPEN", exit_price=None, exit_time=None)
    service = make_service(monkeypatch, recorded_trade, recorded_candles, trade=open_trade)
    session = service.create_session_for_trade(recorded_trade["id"])
    assert session["status"] == "NO_DATA"
    assert session["reason"] == "PROVIDER_NOT_DECLARED"
    assert session["review_mode"] == "OPEN"
    assert session["close_evidence"] is None
    assert session["visible_candles"] == []


def test_chart_review_writes_nothing(monkeypatch, tmp_path, recorded_trade):
    """The whole session lifecycle must leave the persisted state untouched."""
    from app.db.sqlite_driver import SQLiteDriver
    from app.services.local_tracking import LocalTrackingService

    driver = SQLiteDriver(str(tmp_path / "review.sqlite"))
    open_trade = dict(recorded_trade)
    open_trade.update({"id": "TRD-REVIEW", "status": "OPEN", "exit_price": None, "exit_time": None})
    driver.record_trade_with_evidence(
        open_trade,
        event_type="IntentRecorded",
        idempotency_key="review:test:1",
        occurred_at="2026-09-01T10:00:00Z",
        provenance={"source": "journal_external"},
    )

    def ledger_count():
        with driver.get_connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0]

    before = {"trades": driver.list_trades(limit=10), "events": ledger_count()}
    service = ReplayService(
        trade_reader=FakeTradeReader(open_trade, []),
        tracking_reader=LocalTrackingService(driver),
    )
    session = service.create_session_for_trade("TRD-REVIEW")
    if session.get("session_id"):
        service.step(session["session_id"], direction=1)
        service.seek(session["session_id"], 0)
    after = {"trades": driver.list_trades(limit=10), "events": ledger_count()}
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    assert session["status"] == "NO_DATA" and session["reason"] == "PROVIDER_NOT_DECLARED"
    assert session["review_mode"] == "OPEN"


# ---------------------------------------------------------------------------
# Broker-verification claim must not be openable by a raw string
# ---------------------------------------------------------------------------


def test_forged_broker_verified_close_source_is_only_a_declaration():
    """There is no broker-verification infrastructure; a raw string must not claim it."""

    for forged in ("BROKER_VERIFIED", "BROKER_CONFIRMED", "VERIFIED_BROKER", "broker_verified"):
        evidence = close_evidence(trade_row(close_source=forged), "JOURNAL")
        assert evidence["source"] == "SOURCE_DECLARED"
        assert evidence["broker_verified"] is False
        assert evidence["close_source_raw"] == forged


def test_declared_close_source_keeps_the_raw_value_for_traceability():
    evidence = close_evidence(trade_row(close_source="EXCHANGE_SETTLEMENT"), "JOURNAL")
    assert evidence["source"] == "SOURCE_DECLARED"
    assert evidence["broker_verified"] is False
    assert evidence["close_source_raw"] == "EXCHANGE_SETTLEMENT"


def test_user_report_and_import_classes_are_unchanged():
    assert close_source_class(trade_row(close_source="USER_REPORTED"), "JOURNAL") == "USER_REPORTED"
    assert close_source_class(trade_row(close_source="BROKER_IMPORT"), "IMPORTED_FILE") == "IMPORTED_FILE"
    assert close_source_class(trade_row(close_source=None), "IMPORTED_FILE") == "IMPORTED_FILE"
    assert close_source_class(trade_row(close_source=None), "UNKNOWN") == "UNKNOWN"
    assert close_source_class(trade_row(close_source=""), "UNKNOWN") == "UNKNOWN"
