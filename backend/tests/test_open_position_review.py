"""OP-01 open position chart review: provider-matched snapshot only.

The review never presents cache rows of unknown provenance as the trade's
matched chart.  Candles come from a manual fetch against the trade's declared
free public provider and exact provider symbol; mismatches and failures fail
closed with an explicit reason, and no journal/plan/ledger record is written.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
from app.quant.open_position_evidence import (
    OpenReviewError,
    declared_provider_identity,
    load_open_position_evidence,
)
from app.services.market_data.public_fetcher import ProviderFetchError
from app.replay.replay_service import ReplayService


def open_trade(**overrides):
    base = {
        "id": "TRD-OPEN", "symbol": "XAUUSD", "side": "BUY", "status": "OPEN",
        "entry_price": 4264.0, "exit_price": None, "qty": 1.0,
        "stop_loss": 4250.0, "take_profit": 4300.0,
        "entry_time": "2026-09-01T10:00:15Z", "exit_time": None,
        "pnl": None, "commission": 0.0, "record_mode": "EXTERNAL",
        "price_source": "biquote_public", "price_source_symbol": "XAUUSD",
    }
    base.update(overrides)
    return base


ENTRY_TS = int(datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc).timestamp())
NOW = datetime(2026, 9, 1, 10, 4, 30, tzinfo=timezone.utc)


def candles_from(start_ts: int, values, step: int = 60):
    return [
        {"timestamp": start_ts + index * step, "open": o, "high": h, "low": low,
         "close": c, "volume": 10.0}
        for index, (o, h, low, c) in enumerate(values)
    ]


FOUR_BARS = candles_from(ENTRY_TS, [
    (4264.0, 4266.0, 4262.0, 4265.0),
    (4265.0, 4268.0, 4263.0, 4266.5),
    (4266.5, 4270.0, 4265.0, 4269.0),
    (4269.0, 4271.0, 4267.0, 4270.5),
])


def snapshot(candles=None, *, provider="biquote_public", provider_symbol="XAUUSD",
             interval="1m", fetched_at="2026-09-01T10:04:40Z"):
    return {
        "provider": provider, "provider_symbol": provider_symbol,
        "candles": [dict(candle) for candle in (FOUR_BARS if candles is None else candles)],
        "interval": interval, "fetched_at": fetched_at,
    }


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def tracking_state(**overrides):
    base = {
        "trade_id": "TRD-OPEN", "basis": "LOCAL_ESTIMATE", "version": 1,
        "entry_price": "4264", "stop_loss": "4250", "remaining_qty": "1",
        "initial_qty": "1", "revision": 1, "reset_count": 0,
        "armed_at": "2026-09-01T10:00:20+00:00",
        "targets": [{"id": "T1", "price": "4290", "percent": "60"},
                    {"id": "T2", "price": "4300", "percent": "40"}],
        "closures": [],
    }
    base.update(overrides)
    return base


class FakeTradeReader:
    def __init__(self, trade, events=None):
        self.trade, self.events = trade, events or []

    def get_trade(self, trade_id):
        return dict(self.trade)

    def list_events_for_trade(self, trade_id, **kwargs):
        return list(self.events)


class FakeTrackingReader:
    def __init__(self, state=None):
        self.state = state

    def get(self, trade_id):
        return self.state


def service(trade, *, snapshot_result=None, tracking=None):
    calls = []

    async def fetcher(provider, provider_symbol, **kwargs):
        calls.append((provider, provider_symbol, kwargs))
        if isinstance(snapshot_result, Exception):
            raise snapshot_result
        return snapshot_result if snapshot_result is not None else snapshot()

    replay = ReplayService(
        trade_reader=FakeTradeReader(trade),
        tracking_reader=FakeTrackingReader(tracking),
        provider_fetcher=fetcher,
    )
    return replay, calls


# ---------------------------------------------------------------------------
# Declared provider identity
# ---------------------------------------------------------------------------


def test_declared_provider_identity_requires_a_free_provider_and_symbol():
    assert declared_provider_identity(open_trade()) == {"provider": "biquote_public", "provider_symbol": "XAUUSD"}
    assert declared_provider_identity(open_trade(price_source="manual")) is None
    assert declared_provider_identity(open_trade(price_source_symbol="")) is None
    assert declared_provider_identity(open_trade(price_source="connector")) is None


def test_review_rejects_a_snapshot_from_another_provider_or_symbol():
    with pytest.raises(OpenReviewError) as wrong_provider:
        load_open_position_evidence(
            open_trade(), snapshot=snapshot(provider="yahoo_public"), now=NOW)
    assert wrong_provider.value.reason == "PROVIDER_IDENTITY_MISMATCH"
    with pytest.raises(OpenReviewError) as wrong_symbol:
        load_open_position_evidence(
            open_trade(), snapshot=snapshot(provider_symbol="GC=F"), now=NOW)
    assert wrong_symbol.value.reason == "PROVIDER_IDENTITY_MISMATCH"
    with pytest.raises(OpenReviewError) as not_declared:
        load_open_position_evidence(
            open_trade(price_source="manual"), snapshot=snapshot(), now=NOW)
    assert not_declared.value.reason == "PROVIDER_NOT_DECLARED"


# ---------------------------------------------------------------------------
# Evidence rules over the matched snapshot
# ---------------------------------------------------------------------------


def test_open_trade_without_exit_is_supported():
    evidence = load_open_position_evidence(open_trade(), snapshot=snapshot(), now=NOW)
    assert evidence.timeframe == "1m"
    assert evidence.history_status == "FULL_SINCE_ENTRY"
    assert evidence.coverage["bars"] == 4
    assert evidence.freshness["delay_indicator"] == "FRESH_DELAY"
    assert evidence.freshness["last_candle_state"] == "CLOSED"
    assert evidence.freshness["last_download_at"] == "2026-09-01T10:04:40Z"
    assert evidence.provenance["provider"] == "biquote_public"
    assert evidence.provenance["identity_verified"] is True
    assert evidence.provenance["provider_note"] == "NOT_BROKER_EXECUTION_EVIDENCE"
    in_progress = load_open_position_evidence(
        open_trade(), snapshot=snapshot(),
        now=datetime(2026, 9, 1, 10, 3, 30, tzinfo=timezone.utc))
    assert in_progress.freshness["last_candle_state"] == "OPEN"


def test_provider_millisecond_timestamps_are_normalized_to_seconds():
    """Provider payloads arrive in milliseconds; reviews compare in seconds."""

    ms_candles = [{**candle, "timestamp": candle["timestamp"] * 1000} for candle in FOUR_BARS]
    evidence = load_open_position_evidence(open_trade(), snapshot=snapshot(ms_candles), now=NOW)
    assert evidence.candles[0]["timestamp"] == FOUR_BARS[0]["timestamp"]
    assert evidence.history_status == "FULL_SINCE_ENTRY"
    assert evidence.freshness["delay_indicator"] == "FRESH_DELAY"
    assert evidence.freshness["last_candle_state"] == "CLOSED"
    assert evidence.coverage["gap_count"] == 0


def test_partial_history_is_reported_with_the_covered_range():
    evidence = load_open_position_evidence(
        open_trade(), snapshot=snapshot(FOUR_BARS[2:]), now=NOW)
    assert evidence.history_status == "PARTIAL_SINCE_ENTRY"
    assert evidence.entry_bar_present is False
    assert evidence.coverage["missing_before_entry_minutes"] == 2


def test_empty_snapshot_is_an_explicit_no_data_error():
    with pytest.raises(OpenReviewError) as excinfo:
        load_open_position_evidence(open_trade(), snapshot=snapshot([]), now=NOW)
    assert excinfo.value.reason == "PROVIDER_FETCH_FAILED"


def test_delayed_candles_are_flagged_only_as_a_delay_indicator():
    old = candles_from(ENTRY_TS, [(1, 1, 1, 1), (2, 2, 2, 2), (3, 3, 3, 3)])
    evidence = load_open_position_evidence(
        open_trade(), snapshot=snapshot(old),
        now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc))
    assert evidence.freshness["delay_indicator"] == "DELAYED"
    assert evidence.freshness["last_candle_state"] == "CLOSED"
    assert "LIVE" not in json.dumps(evidence.freshness).upper()


def test_gaps_are_reported_as_not_assessable():
    gapped = [FOUR_BARS[0], FOUR_BARS[1], FOUR_BARS[3]]
    evidence = load_open_position_evidence(open_trade(), snapshot=snapshot(gapped), now=NOW)
    assert evidence.coverage["gap_count"] == 1
    assert evidence.coverage["gap_note"] == "RANGE_NOT_ASSESSABLE"
    assert "touch" not in json.dumps(evidence.coverage).lower()


def test_bar_ceiling_truncates_explicitly_to_the_most_recent_bars(monkeypatch):
    monkeypatch.setattr("app.quant.open_position_evidence.MAX_OPEN_REVIEW_BARS", 3)
    many = candles_from(ENTRY_TS, [(1, 1, 1, 1)] * 6)
    evidence = load_open_position_evidence(open_trade(), snapshot=snapshot(many), now=NOW)
    assert len(evidence.candles) == 3
    assert evidence.coverage["bars_truncated"] is True
    assert evidence.coverage["coverage_start_utc"] == iso(many[-3]["timestamp"])


# ---------------------------------------------------------------------------
# Session integration
# ---------------------------------------------------------------------------


def test_session_without_refresh_never_fetches_and_asks_for_the_match():
    replay, calls = service(open_trade(), tracking=tracking_state())
    payload = replay.create_session_for_trade("TRD-OPEN")
    assert calls == []  # creating a session never hits the provider
    assert payload["status"] == "NO_DATA"
    assert payload["reason"] == "PROVIDER_MATCH_REQUIRED"
    assert payload["review_mode"] == "OPEN"
    assert payload["provider"] == "biquote_public"
    assert payload["provider_symbol"] == "XAUUSD"
    assert payload["visible_candles"] == []


def test_session_without_declared_provider_reports_it_explicitly():
    replay, calls = service(open_trade(price_source="manual", price_source_symbol=None))
    payload = replay.create_session_for_trade("TRD-OPEN")
    assert calls == []
    assert payload["status"] == "NO_DATA"
    assert payload["reason"] == "PROVIDER_NOT_DECLARED"


def test_manual_refresh_fetches_only_the_declared_provider_and_displays_its_rows(tmp_path, monkeypatch):
    driver = SQLiteDriver(str(tmp_path / "open-review.sqlite"))
    trade = open_trade(price_source="biquote_public", price_source_symbol="XAUUSD")
    driver.record_trade_with_evidence(
        trade, event_type="IntentRecorded", idempotency_key="open-review:1",
        occurred_at="2026-09-01T10:00:00Z", provenance={"source": "journal_external"},
    )
    # Seed the market cache with DIFFERENT prices under the same symbol bucket:
    # the review must display the fetched snapshot, never these cached rows.
    from app.db.repositories.candles_repo import candles_repo

    decoy = candles_from(ENTRY_TS, [(999.0, 999.0, 999.0, 999.0)] * 4)
    candles_repo.save_candles_batch(decoy, symbol="XAUUSD", timeframe="1m")

    def ledger_count():
        with driver.get_connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0]

    before = {"trades": driver.list_trades(limit=10), "events": ledger_count()}
    replay, calls = service(trade, tracking=tracking_state())
    payload = asyncio.run(replay.create_open_review_session("TRD-OPEN", refresh=True))
    assert calls == [("biquote_public", "XAUUSD", {"interval": "1m", "limit": 2001})]
    assert payload["status"] == "READY"
    assert payload["review_mode"] == "OPEN"
    assert payload["open_review"]["provider"] == "biquote_public"
    assert payload["open_review"]["provider_symbol"] == "XAUUSD"
    assert payload["open_review"]["last_download_at"] == "2026-09-01T10:04:40Z"
    assert payload["visible_candles"][0]["close"] == 4265.0  # not the decoy
    after = {"trades": driver.list_trades(limit=10), "events": ledger_count()}
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
    # No performance numbers and no close evidence on the open path.
    for field in ("unrealized_pnl", "realized_pnl", "r_multiple", "mae_r", "mfe_r"):
        assert payload["trade"][field] is None
    assert payload["close_evidence"] is None
    assert {level["kind"] for level in payload["plan"]["levels"]} == {"ENTRY", "SL", "TP1", "TP2"}


def test_refresh_failure_is_reported_and_never_substituted():
    failure = ProviderFetchError("PROVIDER_FETCH_FAILED", "biquote returned nothing")
    replay, _ = service(open_trade(), snapshot_result=failure)
    payload = asyncio.run(replay.create_open_review_session("TRD-OPEN", refresh=True))
    assert payload["status"] == "UNAVAILABLE"
    assert payload["reason"] == "PROVIDER_FETCH_FAILED"
    assert payload["visible_candles"] == []

    mismatch = service(open_trade(), snapshot_result=snapshot(provider_symbol="GC=F"))[0]
    payload2 = asyncio.run(mismatch.create_open_review_session("TRD-OPEN", refresh=True))
    assert payload2["status"] == "UNAVAILABLE"
    assert payload2["reason"] == "PROVIDER_IDENTITY_MISMATCH"
    assert payload2["visible_candles"] == []

    unsupported = service(open_trade(), snapshot_result=ProviderFetchError(
        "PROVIDER_INSTRUMENT_UNSUPPORTED", "declared symbol maps to a different product"))[0]
    payload3 = asyncio.run(unsupported.create_open_review_session("TRD-OPEN", refresh=True))
    assert payload3["status"] == "UNAVAILABLE"
    assert payload3["reason"] == "PROVIDER_INSTRUMENT_UNSUPPORTED"


def test_closed_replay_payload_stays_on_the_closed_contract(monkeypatch, recorded_trade, recorded_candles):
    from app.quant.candle_evidence import duckdb_driver

    monkeypatch.setattr(duckdb_driver, "get_candles_range", lambda *a, **k: list(recorded_candles))
    replay = ReplayService(
        trade_reader=FakeTradeReader(recorded_trade),
        tracking_reader=FakeTrackingReader(None),
    )
    payload = replay.create_session_for_trade(recorded_trade["id"])
    assert payload["status"] == "READY"
    assert payload["review_mode"] == "CLOSED"
    assert payload["close_evidence"] is None  # no future leak before the exit frame
    last = replay.seek(payload["session_id"], payload["total_bars"] - 1)
    assert last["close_evidence"] is not None
    assert last["trade"]["phase"] == "CLOSED"


def test_open_session_candles_use_the_chart_candle_shape():
    replay, _ = service(open_trade())
    payload = asyncio.run(replay.create_open_review_session("TRD-OPEN", refresh=True))
    candle = payload["visible_candles"][0]
    assert set(candle) == {"time", "open", "high", "low", "close", "volume"}
    assert candle["time"] == FOUR_BARS[0]["timestamp"]


def test_open_session_steps_and_seeks_over_the_fetched_snapshot():
    replay, _ = service(open_trade())
    created = asyncio.run(replay.create_open_review_session("TRD-OPEN", refresh=True))
    assert created["current_index"] == 0
    assert len(created["visible_candles"]) == 1
    stepped = replay.step(created["session_id"], direction=1)
    assert stepped["current_index"] == 1
    assert len(stepped["visible_candles"]) == 2
    last = replay.seek(created["session_id"], 99)
    assert last["current_index"] == last["total_bars"] - 1
    assert last["close_evidence"] is None


def test_refresh_writes_no_canonical_records(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "readonly.sqlite"))
    trade = open_trade(qty_unit="BASE")
    ledger = EvidenceLedgerRepository(driver.db_path)
    driver.record_trade_with_evidence(
        trade, event_type="IntentRecorded", idempotency_key="readonly:1",
        occurred_at="2026-09-01T10:00:00Z", provenance={"source": "journal_external"},
        local_tracking_plan={"enabled": True, "source_id": "biquote_public",
                             "source_symbol": "XAUUSD", "stop_loss": 4250.0,
                             "targets": [{"price": 4290.0, "percent": 100}]},
    )

    def ledger_state():
        with driver.get_connection() as connection:
            row = connection.execute("SELECT COUNT(*), MAX(event_hash) FROM evidence_events").fetchone()
            return tuple(row)

    before = {"trades": driver.list_trades(limit=10), "ledger": ledger_state()}
    replay, _ = service(trade)
    asyncio.run(replay.create_open_review_session("TRD-OPEN", refresh=True))
    after = {"trades": driver.list_trades(limit=10), "ledger": ledger_state()}
    assert json.dumps(before, sort_keys=True) == json.dumps(after, sort_keys=True)
