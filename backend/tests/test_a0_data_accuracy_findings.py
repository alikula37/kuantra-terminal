"""A0 — verification of the two reported data-accuracy findings.

Finding 1: broker-sourced ``FillRecorded`` events carry a ``broker_lifecycle``
payload and account-reconciliation ``TradeCorrected`` events carry an
``account_event`` payload.  Neither is a trade snapshot, so a projection
rebuild must treat them as out-of-scope lifecycle observations instead of
aborting the whole journal projection.  Unknown projectable payloads must
still fail closed.

Finding 2: the DuckDB OLAP path must preserve an unknown PnL as NULL (never a
synthetic zero) and its analytics aggregates must use known results only,
matching the portfolio service contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.db.duckdb_driver import DuckDBDriver
from app.db.duckdb_hydrator import DuckDBHydrator
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import (
    EvidenceProjectionError,
    EvidenceTradeProjectionRepository,
)
from app.db.sqlite_driver import SQLiteDriver
from app.services.account_reconciliation import AccountReconciliationService
from app.services.broker_import_service import BrokerImportService

FIXTURES = Path(__file__).parent / "fixtures" / "broker"


def _journal_trade(trade_id: str = "A0-TRD-1") -> dict:
    return {
        "id": trade_id,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "position_type": "LONG",
        "entry_price": 100.0,
        "qty": 2.0,
        "entry_time": "2026-09-10T10:00:00Z",
        "status": "OPEN",
        "pnl": None,
        "qty_unit": "BASE",
    }


def _record_journal_trade(driver: SQLiteDriver, trade_id: str = "A0-TRD-1") -> None:
    driver.record_trade_with_evidence(
        _journal_trade(trade_id),
        event_type="IntentRecorded",
        idempotency_key=f"a0:journal:{trade_id}:1",
        occurred_at="2026-09-10T10:00:00Z",
        provenance={"source": "a0_test"},
    )


def _import_broker_fixture(ledger: EvidenceLedgerRepository) -> dict:
    source_bytes = (FIXTURES / "binance_orders_fills.json").read_bytes()
    return BrokerImportService(ledger).import_json_document(
        "BINANCE",
        source_bytes,
        source_name="a0-broker-export.json",
    )


def _persist_account_events(ledger: EvidenceLedgerRepository) -> dict:
    """Persist real account observations through the production normalizer.

    ``TRADE_FEE`` maps to ``FeeAdjusted`` (not projectable) and
    ``MANUAL_CORRECTION`` maps to ``TradeCorrected`` with the ``account_event``
    payload, which is the projectable-type collision under review.
    """

    service = AccountReconciliationService(ledger)
    fee = service.normalize_event(
        "BINANCE",
        {
            "event_type": "TRADE_FEE",
            "external_event_id": "A0-FEE-1",
            "amount": "1.5",
            "currency": "USDT",
            "occurred_at": "2026-09-10T11:00:00Z",
        },
        account_id="a0-account-events",
    )
    fee_report = service.persist_records([fee])
    correction = service.normalize_event(
        "BINANCE",
        {
            "event_type": "MANUAL_CORRECTION",
            "external_event_id": "A0-CORR-1",
            "amount": "0.25",
            "currency": "USDT",
            "occurred_at": "2026-09-10T11:30:00Z",
            "effective_at": "2026-09-10T11:00:00Z",
            "corrects_event_id": fee_report["event_ids"][0],
        },
        account_id="a0-account-events",
    )
    correction_report = service.persist_records([correction])
    return {"fee": fee_report, "correction": correction_report}


def _append_raw_event(
    ledger: EvidenceLedgerRepository,
    *,
    event_type: str,
    payload: dict,
    suffix: str,
    account_id: str = "a0-raw-events",
    venue: str = "BINANCE",
) -> str:
    event_ids = ledger.append_events([{
        "event_type": event_type,
        "account_id": account_id,
        "venue": venue,
        "idempotency_key": f"a0:raw:{suffix}",
        "normalized_payload": payload,
        "occurred_at": "2026-09-10T13:00:00Z",
        "schema_version": "1",
        "adapter_version": "a0-test-v1",
        "correlation_id": f"A0-RAW-{suffix}",
        "provenance": {"source": "a0_test"},
    }])
    return event_ids[0]


# ---------------------------------------------------------------------------
# Finding 1 — broker / account lifecycle events vs. trade projection rebuild
# ---------------------------------------------------------------------------


def test_projection_rebuild_counts_non_trade_lifecycle_events(tmp_path):
    db_path = str(tmp_path / "a0-projection.sqlite")
    driver = SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)

    _record_journal_trade(driver)
    broker_report = _import_broker_fixture(ledger)
    assert broker_report["ledger_created_count"] == 4
    account_reports = _persist_account_events(ledger)
    assert account_reports["fee"]["created_count"] == 1
    assert account_reports["correction"]["created_count"] == 1

    events_before = len(list(ledger.export_events()))

    report = projection.rebuild(dry_run=False)

    assert report["ledger_valid"] is True
    assert report["projectable_events"] == 1
    # two VenueAck order observations plus the FeeAdjusted account observation
    assert report["ignored_events"] == 3
    # two broker fills plus the TradeCorrected manual account correction
    assert report["non_trade_lifecycle_events"] == 3
    assert report["projections_written"] == 1
    assert report["tombstones"] == 0

    rows = projection.list_projections()
    assert [(row["account_id"], row["trade_id"]) for row in rows] == [
        ("local-journal", "A0-TRD-1")
    ]
    assert projection.get_projection("A0-TRD-1")["trade_id"] == "A0-TRD-1"

    broker_only = projection.rebuild(account_id="local-broker-import", dry_run=False)
    assert broker_only["projections_written"] == 0

    second = projection.rebuild(dry_run=False)
    assert second["projectable_events"] == report["projectable_events"]
    assert second["ignored_events"] == report["ignored_events"]
    assert second["non_trade_lifecycle_events"] == report["non_trade_lifecycle_events"]
    assert second["projections_written"] == report["projections_written"]
    assert len(projection.list_projections()) == 1
    assert len(list(ledger.export_events())) == events_before
    assert ledger.verify_chain()["valid"] is True


def test_projection_rebuild_still_fails_closed_on_unknown_projectable_payload(tmp_path):
    db_path = str(tmp_path / "a0-fail-closed.sqlite")
    driver = SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)

    _record_journal_trade(driver)
    ledger.append_events([{
        "event_type": "FillRecorded",
        "account_id": "a0-unknown-payload",
        "venue": "a0-unknown-payload",
        "idempotency_key": "a0:unknown-payload:1",
        "normalized_payload": {"unexpected": True},
        "occurred_at": "2026-09-10T13:00:00Z",
        "schema_version": "1",
        "adapter_version": "a0-test-v1",
        "correlation_id": "A0-UNKNOWN-1",
        "provenance": {"source": "a0_test"},
    }])

    projections_before = projection.list_projections()
    with pytest.raises(EvidenceProjectionError, match="no trade snapshot"):
        projection.rebuild(account_id="a0-unknown-payload", dry_run=False)
    assert projection.list_projections() == projections_before


_VALID_BROKER_LIFECYCLE = {
    "numeric_encoding": "DECIMAL_STRING",
    "record_type": "fill",
    "venue": "BINANCE",
    "external_order_id": "A0-ORDER-1",
    "external_fill_id": "A0-FILL-1",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "status": "FILLED",
    "occurred_at": "2026-09-10T12:00:00Z",
    "source_row_number": 3,
    "source_row_sha256": "0" * 64,
}

_VALID_ACCOUNT_EVENT = {
    "account_event_kind": "MANUAL_CORRECTION",
    "account_event_status": "SUPPORTED",
    "storage_status": "PERSISTABLE",
    "account_id": "a0-raw-events",
    "venue": "BINANCE",
    "external_event_id": "A0-CORR-RAW-1",
    "occurred_at": "2026-09-10T12:00:00Z",
}

MALFORMED_LIFECYCLE_CASES = [
    ("broker_empty", "FillRecorded", {"broker_lifecycle": {}}, "broker_lifecycle"),
    ("broker_not_object", "FillRecorded", {"broker_lifecycle": "not-an-object"}, "broker_lifecycle"),
    (
        "broker_wrong_event_type",
        "TradeCorrected",
        {"broker_lifecycle": dict(_VALID_BROKER_LIFECYCLE)},
        "broker_lifecycle",
    ),
    (
        "broker_missing_order_id",
        "FillRecorded",
        {"broker_lifecycle": {**_VALID_BROKER_LIFECYCLE, "external_order_id": ""}},
        "external_order_id",
    ),
    (
        "broker_fill_missing_fill_id",
        "FillRecorded",
        {"broker_lifecycle": {**_VALID_BROKER_LIFECYCLE, "external_fill_id": None}},
        "external_fill_id",
    ),
    (
        "broker_venue_mismatch",
        "FillRecorded",
        {"broker_lifecycle": {**_VALID_BROKER_LIFECYCLE, "venue": "OKX"}},
        "venue",
    ),
    (
        "conflicting_keys",
        "FillRecorded",
        {
            "broker_lifecycle": dict(_VALID_BROKER_LIFECYCLE),
            "account_event": dict(_VALID_ACCOUNT_EVENT),
        },
        "conflicting",
    ),
    (
        "account_wrong_event_type",
        "FillRecorded",
        {"account_event": dict(_VALID_ACCOUNT_EVENT)},
        "account_event",
    ),
    (
        "account_missing_external_id",
        "TradeCorrected",
        {"account_event": {**_VALID_ACCOUNT_EVENT, "external_event_id": ""}},
        "external_event_id",
    ),
    (
        "account_account_mismatch",
        "TradeCorrected",
        {"account_event": {**_VALID_ACCOUNT_EVENT, "account_id": "other-account"}},
        "account_id",
    ),
]


@pytest.mark.parametrize("case,event_type,payload,expected", MALFORMED_LIFECYCLE_CASES)
def test_projection_classifier_rejects_malformed_lifecycle_payloads(
    tmp_path, case, event_type, payload, expected
):
    db_path = str(tmp_path / f"a0-classifier-{case}.sqlite")
    SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)
    _append_raw_event(ledger, event_type=event_type, payload=payload, suffix=case)

    projections_before = projection.list_projections()
    with pytest.raises(EvidenceProjectionError, match=expected):
        projection.rebuild(account_id="a0-raw-events", dry_run=False)
    assert projection.list_projections() == projections_before


def test_failed_rebuild_keeps_existing_projections_and_source_events(tmp_path):
    db_path = str(tmp_path / "a0-midway.sqlite")
    driver = SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)

    _record_journal_trade(driver)
    assert projection.rebuild(dry_run=False)["projections_written"] == 1
    projections_before = projection.list_projections()

    _append_raw_event(
        ledger,
        event_type="FillRecorded",
        payload={"broker_lifecycle": {}},
        suffix="midway",
    )
    hashes_before = [event["event_hash"] for event in ledger.export_events()]
    with pytest.raises(EvidenceProjectionError, match="broker_lifecycle"):
        projection.rebuild(dry_run=False)

    assert projection.list_projections() == projections_before
    assert [event["event_hash"] for event in ledger.export_events()] == hashes_before
    assert ledger.verify_chain()["valid"] is True


def test_atomic_upsert_shares_lifecycle_classification(tmp_path):
    db_path = str(tmp_path / "a0-upsert.sqlite")
    SQLiteDriver(db_path)
    ledger = EvidenceLedgerRepository(db_path)
    projection = EvidenceTradeProjectionRepository(db_path)
    _import_broker_fixture(ledger)
    fill_event = next(
        event
        for event in ledger.export_events(account_id="local-broker-import")
        if event["event_type"] == "FillRecorded"
    )

    conn = projection._connect(write=True)
    try:
        conn.execute("BEGIN IMMEDIATE")
        assert projection.upsert_event_in_transaction(conn, fill_event) is None
        malformed = dict(fill_event)
        malformed["normalized_payload_json"] = json.dumps({"broker_lifecycle": {}})
        with pytest.raises(EvidenceProjectionError, match="broker_lifecycle"):
            projection.upsert_event_in_transaction(conn, malformed)
    finally:
        conn.rollback()
        conn.close()


# ---------------------------------------------------------------------------
# Finding 2 — DuckDB unknown PnL contract
# ---------------------------------------------------------------------------


def _trade(trade_id: str, pnl, exit_time: str, *, status: str = "CLOSED") -> dict:
    return {
        "id": trade_id,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "exit_price": 110.0 if pnl is not None else None,
        "qty": 1.0,
        "stop_loss": None,
        "take_profit": None,
        "entry_time": "2026-09-01T00:00:00Z",
        "exit_time": exit_time if status == "CLOSED" else None,
        "status": status,
        "pnl": pnl,
        "r_multiple": None,
        "commission": 0.0,
    }


def test_duckdb_preserves_unknown_pnl_and_excludes_it_from_aggregates(tmp_path):
    driver = DuckDBDriver(str(tmp_path / "a0-olap.duckdb"))
    driver.sync_trade(_trade("A0-WIN", 5.0, "2026-09-02T00:00:00Z"))
    driver.sync_trade(_trade("A0-ZERO", 0.0, "2026-09-03T00:00:00Z"))
    driver.sync_trade(_trade("A0-LOSS", -3.0, "2026-09-04T00:00:00Z"))
    driver.sync_trade(_trade("A0-UNKNOWN", None, "2026-09-05T00:00:00Z"))

    conn = driver.get_connection()
    try:
        stored = conn.execute(
            "SELECT pnl FROM olap_trades WHERE id = 'A0-UNKNOWN'"
        ).fetchone()[0]
        winner_flag = conn.execute(
            "SELECT is_winner FROM olap_trades WHERE id = 'A0-UNKNOWN'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert stored is None
    assert winner_flag is None

    stats = driver.get_aggregated_stats()
    assert stats["total_trades"] == 4
    assert stats["known_pnl_trades"] == 3
    assert stats["unknown_pnl_trades"] == 1
    assert stats["win_count"] == 1
    assert stats["loss_count"] == 1
    assert stats["breakeven_count"] == 1
    assert stats["win_rate"] == 33.33
    assert stats["total_pnl"] == 2.0
    assert stats["avg_pnl"] == 0.67

    curve = driver.get_equity_curve()
    assert [row["id"] for row in curve] == ["A0-WIN", "A0-ZERO", "A0-LOSS"]

    breakdown = driver.get_symbol_breakdown()
    row = next(item for item in breakdown if item["symbol"] == "BTCUSDT")
    assert row["count"] == 4
    assert row["known_pnl_count"] == 3
    assert row["unknown_pnl_count"] == 1
    assert row["win_rate"] == 33.33
    assert row["total_pnl"] == 2.0


def test_duckdb_hydrator_preserves_unknown_pnl(tmp_path):
    class _Reader:
        def coverage(self):
            return {"ready": True}

        def list_trades(self, limit=100000):
            return [
                _trade("A0-H-WIN", 5.0, "2026-09-02T00:00:00Z"),
                _trade("A0-H-UNKNOWN", None, "2026-09-03T00:00:00Z"),
            ]

    duckdb_path = str(tmp_path / "a0-hydrated.duckdb")
    hydrator = DuckDBHydrator(
        duckdb_path=duckdb_path,
        sqlite_path=str(tmp_path / "a0-hydrated.sqlite"),
        trade_reader=_Reader(),
    )
    result = hydrator.hydrate_from_sqlite(force_rebuild=True)
    assert result["status"] == "HYDRATED"

    driver = DuckDBDriver(duckdb_path)
    conn = driver.get_connection()
    try:
        stored = conn.execute(
            "SELECT pnl FROM olap_trades WHERE id = 'A0-H-UNKNOWN'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert stored is None

    stats = driver.get_aggregated_stats()
    assert stats["unknown_pnl_trades"] == 1
    assert stats["known_pnl_trades"] == 1
    assert stats["total_pnl"] == 5.0
    assert stats["win_rate"] == 100.0


def test_duckdb_analytics_and_portfolio_share_the_unknown_pnl_contract(tmp_path, monkeypatch):
    from app.services import portfolio_service as portfolio_module

    trades = [
        _trade("A0-C-WIN", 5.0, "2026-09-02T00:00:00Z"),
        _trade("A0-C-ZERO", 0.0, "2026-09-03T00:00:00Z"),
        _trade("A0-C-LOSS", -3.0, "2026-09-04T00:00:00Z"),
        _trade("A0-C-UNKNOWN", None, "2026-09-05T00:00:00Z"),
    ]
    driver = DuckDBDriver(str(tmp_path / "a0-consistency.duckdb"))
    for trade in trades:
        driver.sync_trade(trade)

    class _Reader:
        def list_trades(self, limit=100000):
            return [dict(trade) for trade in trades]

    monkeypatch.setattr(portfolio_module, "trade_read_adapter", _Reader())
    summary = portfolio_module.PortfolioAnalyticsService(
        default_initial_balance=10000.0
    ).get_portfolio_summary()
    stats = driver.get_aggregated_stats()

    assert summary["total_closed_trades"] == stats["total_trades"]
    assert summary["unknown_pnl_trades"] == stats["unknown_pnl_trades"]
    assert summary["net_pnl"] == stats["total_pnl"]
    assert summary["win_rate"] == stats["win_rate"]
