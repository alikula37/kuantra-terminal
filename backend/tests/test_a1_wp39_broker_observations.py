"""A1.1 — broker observation projection, deterministic rebuild and counters.

Account-scope closure contract:

* the caller-declared local bucket (``account_id``) is not a broker-verified
  account identity; being in the same bucket or carrying the same symbol/fill id
  never proves account equality and a file hash never substitutes for it;
* while the source account scope is unverified, observations are preserved
  individually with an explicit scope state and counters - no economic merge,
  no repeat/dedup and no content conflict may be declared across documents;
* source-level idempotency (re-sending the same document) is a ledger property
  handled separately from cross-document economic dedup;
* order and fill identities stay separate; a fill identity is the source
  fill/deal id, never the order id, the ledger event id or a content hash;
* rebuild is deterministic, captures its ledger boundary and keeps the previous
  snapshot on failure while recording the failure visibly.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.db.repositories.broker_observation_repo import (
    BrokerObservationProjectionError,
    BrokerObservationProjectionRepository,
)
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.broker_import_service import BrokerImportService
from app.services.broker_observations import (
    ACCOUNT_CONTEXTS,
    ACCOUNT_ENVIRONMENTS,
    ACCOUNT_METADATA_BASIS,
    ACCOUNT_SCOPE_BASIS,
    ACCOUNT_SCOPE_REASON_NOT_PROVIDED,
    ACCOUNT_SCOPE_STATE_UNVERIFIED,
    BrokerObservation,
    BrokerObservationError,
    build_broker_observation_snapshot,
    validate_account_scope,
)
from app.services.macos_migration import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    upgrade_sqlite_schema,
)


def _manifest(source_exchange_id: str = "binance_spot", market_type: str = "spot") -> dict:
    return {
        "manifest_version": "2",
        "permission_scope": "READ_ONLY",
        "snapshot_sha256": "a" * 64,
        "complete": True,
        "source_exchange_id": source_exchange_id,
        "market_type": market_type,
        "orders_page_count": 1,
        "fills_page_count": 1,
        "order_count": 1,
        "fill_count": 1,
        "request_count": 2,
        "warnings": [],
    }


def _order(
    order_id: str = "O-1",
    *,
    status: str = "FILLED",
    orig_qty: str = "2",
    executed_qty: str = "2",
    price: str = "100",
    avg_price: str = "100",
    fee: str = "0.2",
    time: str = "2026-09-10T10:00:00Z",
) -> dict:
    return {
        "orderId": order_id,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": status,
        "origQty": orig_qty,
        "executedQty": executed_qty,
        "price": price,
        "avgPrice": avg_price,
        "fee": fee,
        "commissionAsset": "USDT",
        "updateTime": time,
    }


def _fill(
    fill_id: str,
    order_id: str = "O-1",
    *,
    qty: str = "1",
    price: str = "100",
    fee: str = "0.1",
    time: str = "2026-09-10T10:00:01Z",
) -> dict:
    return {
        "id": fill_id,
        "orderId": order_id,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "qty": qty,
        "price": price,
        "fee": fee,
        "commissionAsset": "USDT",
        "time": time,
    }


def _ledger(tmp_path: Path, name: str = "broker.sqlite") -> EvidenceLedgerRepository:
    return EvidenceLedgerRepository(str(tmp_path / name))


def _repo(tmp_path: Path, name: str = "broker.sqlite") -> BrokerObservationProjectionRepository:
    return BrokerObservationProjectionRepository(str(tmp_path / name))


def _valid_body(record_type: str = "fill", **overrides) -> dict:
    body = {
        "record_type": record_type,
        "venue": "BINANCE",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
        "occurred_at": "2026-09-10T10:00:00Z",
        "external_order_id": "O-1",
    }
    if record_type == "fill":
        body.update({
            "external_fill_id": "F-1",
            "filled_qty": "1",
            "price": "100",
            "fee": "0.1",
            "fee_currency": "USDT",
        })
    else:
        body.update({
            "order_qty": "2",
            "filled_qty": "2",
            "price": "100",
            "avg_price": "100",
            "fee": "0.2",
            "fee_currency": "USDT",
        })
    body.update(overrides)
    return body


def _raw_event(
    event_id: str,
    *,
    event_type: str = "FillRecorded",
    payload: dict | None = None,
    body: dict | None = None,
    account_id: str = "acc-1",
    venue: str = "BINANCE",
    provenance: dict | None = None,
) -> dict:
    if payload is None:
        payload = {"broker_lifecycle": body if body is not None else _valid_body()}
    provenance_body = {
        "source_exchange_id": "binance_spot",
        "market_type": "spot",
    }
    if provenance:
        provenance_body.update(provenance)
    return {
        "event_id": event_id,
        "event_hash": hashlib.sha256(f"hash:{event_id}".encode()).hexdigest(),
        "event_type": event_type,
        "account_id": account_id,
        "venue": venue,
        "occurred_at_utc": "2026-09-10T10:00:00Z",
        "received_at_utc": "2026-09-10T10:00:00Z",
        "normalized_payload_json": json.dumps(payload, sort_keys=True),
        "provenance_json": json.dumps(provenance_body, sort_keys=True),
    }


def _append_raw_event(
    ledger: EvidenceLedgerRepository,
    *,
    event_type: str,
    payload: dict,
    suffix: str,
    account_id: str = "acc-raw",
) -> None:
    ledger.append_events([{
        "event_type": event_type,
        "account_id": account_id,
        "venue": "BINANCE",
        "idempotency_key": f"a1wp39:{suffix}",
        "normalized_payload": payload,
        "occurred_at": "2026-09-10T13:00:00Z",
        "schema_version": "1",
        "adapter_version": "a1wp39-test-v1",
        "correlation_id": f"A1WP39-{suffix}",
        "provenance": {"source": "a1wp39_test"},
    }])


def _import_fill_once(
    service: BrokerImportService,
    document: bytes,
    *,
    fill_id: str = "F-1",
    price: str = "100",
    account_id: str = "local-broker-import",
) -> dict:
    return service.import_records(
        "BINANCE",
        orders=[],
        fills=[_fill(fill_id, "O-1", price=price)],
        account_id=account_id,
        source_bytes=document,
        snapshot_manifest=_manifest(),
    )


# ---------------------------------------------------------------------------
# Identity contracts
# ---------------------------------------------------------------------------


def test_order_and_fill_identities_are_separate(tmp_path):
    ledger = _ledger(tmp_path)
    report = BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1"), _fill("F-2", "O-1")],
        snapshot_manifest=_manifest(),
    )
    assert report["status"] == "RECONCILED"

    projection = _repo(tmp_path)
    rebuild = projection.rebuild(dry_run=False)
    assert rebuild["counters"]["accepted_observation_count"] == 3
    assert rebuild["counters"]["unverified_account_scope_observation_count"] == 3
    assert rebuild["counters"]["verified_account_scope_observation_count"] == 0
    assert rebuild["counters"]["unverified_duplicate_claim_count"] == 0

    rows = projection.list_observations()
    order_rows = [row for row in rows if row["record_type"] == "order"]
    fill_rows = [row for row in rows if row["record_type"] == "fill"]
    assert [row["external_identity"] for row in order_rows] == ["O-1"]
    assert sorted(row["external_identity"] for row in fill_rows) == ["F-1", "F-2"]
    assert all(row["related_order_id"] == "O-1" for row in fill_rows)
    assert all(row["account_scope_state"] == ACCOUNT_SCOPE_STATE_UNVERIFIED for row in rows)
    assert all(row["account_scope_reason"] == ACCOUNT_SCOPE_REASON_NOT_PROVIDED for row in rows)


def test_fill_without_fill_identity_is_rejected_and_never_keys_on_order(tmp_path):
    ledger = _ledger(tmp_path)
    incomplete_fill = _fill("placeholder", "O-1")
    incomplete_fill.pop("id")
    report = BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[incomplete_fill],
        snapshot_manifest=_manifest(),
    )
    assert report["rejected_row_count"] == 1

    fill_events = [
        event for event in ledger.export_events() if event["event_type"] == "FillRecorded"
    ]
    assert fill_events == []

    projection = _repo(tmp_path)
    projection.rebuild(dry_run=False)
    assert projection.list_observations(record_type="fill") == []

    with pytest.raises(BrokerObservationError, match="external_fill_id"):
        build_broker_observation_snapshot([_raw_event(
            "malformed-fill",
            body=_valid_body("fill", external_fill_id=None),
        )])


def test_missing_source_scope_stays_unresolved_and_is_not_projected(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
    )

    projection = _repo(tmp_path)
    report = projection.rebuild(dry_run=False)
    assert report["counters"]["accepted_observation_count"] == 2
    assert report["counters"]["unresolved_source_scope_observation_count"] == 2
    assert report["counters"]["unverified_account_scope_observation_count"] == 0
    assert report["counters"]["unresolved_reasons"] == {"MISSING_SOURCE_SCOPE": 2}
    assert projection.list_observations() == []

    coverage = projection.coverage()
    assert coverage["state"] == "CURRENT"
    assert coverage["last_attempt_status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# Mandatory account-scope scenarios
# ---------------------------------------------------------------------------


def test_same_bucket_same_fill_same_content_does_not_merge(tmp_path):
    """Two documents, same declared bucket, same fill id and content.

    The documents carry no proof of belonging to the same real account, so the
    observations must stay separate and must not be counted as one economic fill
    plus a repeat.
    """

    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    _import_fill_once(service, b"document-one")
    _import_fill_once(service, b"document-two")

    projection = _repo(tmp_path)
    report = projection.rebuild(dry_run=False)
    counters = report["counters"]
    assert counters["accepted_observation_count"] == 2
    assert counters["unverified_account_scope_observation_count"] == 2
    assert counters["unverified_duplicate_claim_count"] == 1
    assert counters["unverified_duplicate_identity_count"] == 1
    assert counters["verified_account_scope_observation_count"] == 0

    rows = projection.list_observations(record_type="fill")
    assert len(rows) == 2
    assert {row["external_identity"] for row in rows} == {"F-1"}
    assert len({row["source_event_id"] for row in rows}) == 2
    assert all(row["account_scope_state"] == ACCOUNT_SCOPE_STATE_UNVERIFIED for row in rows)
    assert all(row["semantics"]["price"] == "100" for row in rows)


def test_same_bucket_same_fill_different_content_is_not_an_economic_conflict(tmp_path):
    """Different prices for the same claimed fill id in two documents.

    Account equality is unproven, so shared economic identity is not established
    and no UNRESOLVED_CONFLICT variants may be declared; both observations stay
    preserved with their own lineage.
    """

    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    _import_fill_once(service, b"document-one", price="100")
    _import_fill_once(service, b"document-two", price="101")

    projection = _repo(tmp_path)
    report = projection.rebuild(dry_run=False)
    counters = report["counters"]
    assert counters["accepted_observation_count"] == 2
    assert counters["unverified_account_scope_observation_count"] == 2
    assert counters["unverified_duplicate_claim_count"] == 1
    assert counters["unverified_duplicate_identity_count"] == 1

    rows = projection.list_observations(record_type="fill")
    assert len(rows) == 2
    prices = sorted(row["semantics"]["price"] for row in rows)
    assert prices == ["100", "101"]
    assert all(row["account_scope_state"] == ACCOUNT_SCOPE_STATE_UNVERIFIED for row in rows)
    assert all(row["account_scope_reason"] == ACCOUNT_SCOPE_REASON_NOT_PROVIDED for row in rows)
    for row in rows:
        assert row["source_event_id"]
        assert row["source_event_hash"]
        assert row["lineage"]


def test_different_declared_buckets_or_sources_stay_separate(tmp_path):
    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    for account_id in ("acc-a", "acc-b"):
        service.import_records(
            "BINANCE",
            orders=[_order("O-1")],
            fills=[_fill("F-1", "O-1")],
            account_id=account_id,
            snapshot_manifest=_manifest(),
        )
    service.import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        account_id="acc-a",
        snapshot_manifest=_manifest("binance_futures", "swap"),
    )

    projection = _repo(tmp_path)
    report = projection.rebuild(dry_run=False)
    assert report["counters"]["accepted_observation_count"] == 6
    assert len(projection.list_observations(account_id="acc-a")) == 4
    assert len(projection.list_observations(account_id="acc-b")) == 2
    futures = projection.list_observations(account_id="acc-a", source_exchange_id="binance_futures")
    assert {row["market_type"] for row in futures} == {"swap"}


def test_prop_demo_and_prop_live_scope_combinations_are_valid():
    for environment in ACCOUNT_ENVIRONMENTS:
        for context in ACCOUNT_CONTEXTS:
            scope = validate_account_scope(environment, context, "USER_DECLARED")
            assert scope["environment"] == environment
            assert scope["context"] == context
            assert scope["source"] == "USER_DECLARED"
    assert validate_account_scope("DEMO", "PROP", "BROKER_VERIFIED")["context"] == "PROP"
    assert validate_account_scope("LIVE", "PROP", "USER_DECLARED")["environment"] == "LIVE"

    with pytest.raises(BrokerObservationError):
        validate_account_scope("REAL", "PERSONAL")
    with pytest.raises(BrokerObservationError):
        validate_account_scope("DEMO", "FUNDED")


def test_environment_and_context_metadata_are_not_part_of_the_identity_key():
    base = {
        "event_id": "e1",
        "event_hash": "h1",
        "account_id": "acc-1",
        "venue": "BINANCE",
        "received_at_utc": "2026-09-10T10:00:00Z",
        "record_type": "fill",
        "external_identity": "F-1",
        "related_order_id": "O-1",
        "occurred_at_utc": "2026-09-10T10:00:00Z",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
        "semantics": {"price": "100"},
        "semantic_sha256": "s",
        "source_exchange_id": "binance_spot",
        "market_type": "spot",
        "unresolved_reason": None,
        "source_document_sha256": None,
        "source_row_number": None,
    }
    unknown = BrokerObservation(environment="UNKNOWN", context="UNKNOWN", **base)
    live = BrokerObservation(environment="LIVE", context="PERSONAL", **base)
    prop_demo = BrokerObservation(environment="DEMO", context="PROP", **base)
    prop_live = BrokerObservation(environment="LIVE", context="PROP", **base)

    assert unknown.claim_key == live.claim_key
    assert unknown.claim_key == prop_demo.claim_key
    assert unknown.claim_key == prop_live.claim_key

    other_account = BrokerObservation(
        environment="LIVE", context="PERSONAL", **{**base, "account_id": "acc-2"}
    )
    other_source = BrokerObservation(
        environment="LIVE",
        context="PERSONAL",
        **{**base, "source_exchange_id": "binance_futures", "market_type": "swap"},
    )
    assert other_account.claim_key != unknown.claim_key
    assert other_source.claim_key != unknown.claim_key


def test_unverified_metadata_is_never_inferred_for_an_observation(tmp_path):
    event = _raw_event(
        "metadata-negative",
        provenance={
            "account_environment": "LIVE",
            "account_context": "PROP",
        },
    )
    snapshot = build_broker_observation_snapshot([event])
    record = snapshot["records"][0]
    assert record["account_environment"] == "UNKNOWN"
    assert record["account_context"] == "UNKNOWN"


def test_account_scope_state_and_basis_are_explicit(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    projection = _repo(tmp_path)
    projection.rebuild(dry_run=False)

    coverage = projection.coverage()
    assert ACCOUNT_SCOPE_BASIS == "CALLER_DECLARED"
    assert coverage["account_scope_basis"] == ACCOUNT_SCOPE_BASIS
    assert coverage["account_metadata_basis"] == ACCOUNT_METADATA_BASIS
    assert coverage["counters"]["verified_account_scope_observation_count"] == 0
    assert coverage["counters"]["unverified_account_scope_observation_count"] == 2

    rows = projection.list_observations()
    assert all(row["account_environment"] == "UNKNOWN" for row in rows)
    assert all(row["account_context"] == "UNKNOWN" for row in rows)


# ---------------------------------------------------------------------------
# Idempotency, counters and determinism
# ---------------------------------------------------------------------------


def test_same_document_resend_keeps_source_level_idempotency(tmp_path):
    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    document = b"same-document"
    first = _import_fill_once(service, document)
    projection = _repo(tmp_path)
    before = projection.rebuild(dry_run=False)

    second = _import_fill_once(service, document)
    assert second["ledger_duplicate_count"] == first["ledger_created_count"]
    after = projection.rebuild(dry_run=False)
    assert after["counters"] == before["counters"]
    assert len(projection.list_observations()) == 1


def test_counter_examples_are_disjoint_and_exact(tmp_path):
    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    projection = _repo(tmp_path)

    _import_fill_once(service, b"example-single", price="100")
    single = projection.rebuild(dry_run=False)["counters"]
    assert (
        single["accepted_observation_count"],
        single["unverified_account_scope_observation_count"],
        single["unresolved_source_scope_observation_count"],
        single["unverified_duplicate_claim_count"],
        single["unverified_duplicate_identity_count"],
    ) == (1, 1, 0, 0, 0)

    _import_fill_once(service, b"example-repeat", price="100")
    repeated = projection.rebuild(dry_run=False)["counters"]
    assert (
        repeated["accepted_observation_count"],
        repeated["unverified_account_scope_observation_count"],
        repeated["unverified_duplicate_claim_count"],
        repeated["unverified_duplicate_identity_count"],
    ) == (2, 2, 1, 1)

    _import_fill_once(service, b"example-variant", price="101")
    variant = projection.rebuild(dry_run=False)["counters"]
    assert (
        variant["accepted_observation_count"],
        variant["unverified_account_scope_observation_count"],
        variant["unverified_duplicate_claim_count"],
        variant["unverified_duplicate_identity_count"],
    ) == (3, 3, 2, 1)
    assert variant["accepted_observation_count"] == (
        variant["verified_account_scope_observation_count"]
        + variant["unverified_account_scope_observation_count"]
        + variant["unresolved_source_scope_observation_count"]
    )


def test_input_permutation_does_not_change_the_snapshot(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    events = list(ledger.export_events())

    ordered = build_broker_observation_snapshot(events)
    reversed_input = build_broker_observation_snapshot(list(reversed(events)))
    shuffled = build_broker_observation_snapshot([events[1], events[0]])

    assert ordered["snapshot_sha256"] == reversed_input["snapshot_sha256"]
    assert ordered["snapshot_sha256"] == shuffled["snapshot_sha256"]
    assert ordered["counters"] == reversed_input["counters"] == shuffled["counters"]


# ---------------------------------------------------------------------------
# Rebuild boundary, failure visibility and determinism
# ---------------------------------------------------------------------------


def test_malformed_event_fails_closed_and_preserves_previous_snapshot(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    projection = _repo(tmp_path)
    projection.rebuild(dry_run=False)
    rows_before = projection.list_projections()

    _append_raw_event(
        ledger,
        event_type="FillRecorded",
        payload={"broker_lifecycle": {"record_type": "fill", "venue": "BINANCE"}},
        suffix="malformed",
    )
    with pytest.raises(BrokerObservationProjectionError, match="occurred_at"):
        projection.rebuild(dry_run=False)

    assert projection.list_projections() == rows_before
    coverage = projection.coverage()
    assert coverage["last_attempt_status"] == "FAILED"
    assert coverage["last_failure_reason"]
    assert coverage["last_success_snapshot_sha256"] is not None
    assert coverage["state"] == "STALE"
    assert coverage["newer_events_pending"] is True


def test_rebuild_does_not_mix_events_appended_during_the_scan(tmp_path):
    ledger = _ledger(tmp_path)
    service = BrokerImportService(ledger)
    service.import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    projection = _repo(tmp_path)
    boundary_event = list(ledger.export_events())[-1]

    def append_during_rebuild(phase: str) -> None:
        if phase != "after_event_snapshot":
            return
        service.import_records(
            "BINANCE",
            orders=[_order("O-2")],
            fills=[_fill("F-2", "O-2")],
            source_bytes=b"during-rebuild",
            snapshot_manifest=_manifest(),
        )

    report = projection.rebuild(dry_run=False, resource_check=append_during_rebuild)
    assert report["scanned_event_count"] == 2
    assert report["processed_through"]["event_id"] == boundary_event["event_id"]
    assert {row["external_identity"] for row in projection.list_observations()} == {"O-1", "F-1"}

    coverage = projection.coverage()
    assert coverage["state"] == "STALE"
    assert coverage["newer_events_pending"] is True


def test_failure_injection_keeps_previous_snapshot_and_records_failure(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    projection = _repo(tmp_path)
    success = projection.rebuild(dry_run=False)
    rows_before = projection.list_projections()

    def fail_before_commit(phase: str) -> None:
        if phase == "before_projection_commit":
            raise OSError("synthetic broker projection failure")

    with pytest.raises(OSError, match="synthetic broker projection failure"):
        projection.rebuild(dry_run=False, resource_check=fail_before_commit)

    assert projection.list_projections() == rows_before
    coverage = projection.coverage()
    assert coverage["last_attempt_status"] == "FAILED"
    assert "synthetic broker projection failure" in coverage["last_failure_reason"]
    assert coverage["last_success_snapshot_sha256"] == success["snapshot_sha256"]
    assert coverage["state"] == "CURRENT"


def test_repeated_rebuild_is_deterministic_and_keeps_the_ledger_unchanged(tmp_path):
    ledger = _ledger(tmp_path)
    BrokerImportService(ledger).import_records(
        "BINANCE",
        orders=[_order("O-1")],
        fills=[_fill("F-1", "O-1")],
        snapshot_manifest=_manifest(),
    )
    projection = _repo(tmp_path)
    ledger_hashes = [event["event_hash"] for event in ledger.export_events()]
    export_before = ledger.export_jsonl()

    first = projection.rebuild(dry_run=False)
    rows_first = projection.list_projections()
    second = projection.rebuild(dry_run=False)
    rows_second = projection.list_projections()

    assert first["snapshot_sha256"] == second["snapshot_sha256"]
    assert first["counters"] == second["counters"]
    assert rows_first == rows_second
    assert [event["event_hash"] for event in ledger.export_events()] == ledger_hashes
    assert ledger.export_jsonl() == export_before


# ---------------------------------------------------------------------------
# Supported migration paths
# ---------------------------------------------------------------------------


def test_legacy_backfill_skips_trades_with_canonical_evidence(tmp_path):
    database = tmp_path / "backfill.sqlite3"
    driver = SQLiteDriver(str(database))
    driver.record_trade_with_evidence(
        {
            "id": "A1WP39-CANONICAL-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-10T10:00:00Z",
            "status": "OPEN",
            "qty_unit": "BASE",
        },
        event_type="IntentRecorded",
        idempotency_key="a1wp39:backfill:1",
        occurred_at="2026-09-10T10:00:00Z",
        provenance={"source": "a1wp39_test"},
    )
    driver.insert_trade(
        {
            "id": "A1WP39-LEGACY-2",
            "symbol": "ETHUSDT",
            "side": "SELL",
            "entry_price": 200.0,
            "qty": 2.0,
            "entry_time": "2026-09-10T11:00:00Z",
            "status": "OPEN",
        }
    )
    repository = EvidenceLedgerRepository(str(database))

    report = repository.backfill_legacy_trades(dry_run=False)
    assert report["source_count"] == 2
    assert report["already_evidenced"] == 1
    assert report["appended"] == 1
    assert repository.count_events() == 2

    repeated = repository.backfill_legacy_trades(dry_run=False)
    assert repeated["appended"] == 0
    assert repeated["already_evidenced"] == 1
    assert repeated["duplicates"] == 1
    assert repository.count_events() == 2
    assert repository.verify_chain()["valid"] is True


def test_supported_head_upgrade_with_canonical_evidence_does_not_duplicate(tmp_path):
    database = tmp_path / "modern-007.sqlite3"
    driver = SQLiteDriver(str(database))
    driver.record_trade_with_evidence(
        {
            "id": "A1WP39-MODERN-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-10T10:00:00Z",
            "status": "OPEN",
            "qty_unit": "BASE",
        },
        event_type="IntentRecorded",
        idempotency_key="a1wp39:modern:1",
        occurred_at="2026-09-10T10:00:00Z",
        provenance={"source": "a1wp39_test"},
    )
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS broker_observation_log")
        connection.execute("DROP TABLE IF EXISTS broker_projection_state")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        connection.execute("DELETE FROM alembic_version")
        connection.execute("INSERT INTO alembic_version VALUES ('007_trade_qty_unit')")
        connection.commit()

    upgraded = upgrade_sqlite_schema(database)
    assert upgraded["valid"] is True
    assert upgraded["status"] == "UPGRADED"
    assert upgraded["schema_before"]["version"] == 7
    assert upgraded["schema_after"]["version"] == CURRENT_SQLITE_SCHEMA_VERSION

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_trade_projections"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0] == "008_broker_observation_projection"
        assert connection.execute(
            "SELECT COUNT(*) FROM broker_observation_log"
        ).fetchone()[0] == 0

    repeated = upgrade_sqlite_schema(database)
    assert repeated["status"] == "CURRENT"
    assert repeated["changed"] is False


def test_additive_migration_preserves_existing_records(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                qty REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                pnl REAL,
                r_multiple REAL,
                mae REAL,
                mfe REAL,
                exit_efficiency REAL,
                status TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                exit_time TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('001_initial_baseline');
            INSERT INTO trades (
                id, symbol, side, entry_price, qty, status, entry_time, notes
            ) VALUES (
                'A1WP39-LEGACY-1', 'BTCUSDT', 'BUY', 100.0, 1.0, 'OPEN',
                '2026-09-10T10:00:00Z', 'legacy row'
            );
            """
        )
        connection.commit()

    upgraded = upgrade_sqlite_schema(database)
    assert upgraded["valid"] is True
    assert upgraded["status"] == "UPGRADED"
    assert upgraded["schema_after"]["version"] == CURRENT_SQLITE_SCHEMA_VERSION

    with sqlite3.connect(database) as connection:
        legacy_row = connection.execute(
            "SELECT id, symbol, status FROM trades WHERE id = 'A1WP39-LEGACY-1'"
        ).fetchone()
        assert legacy_row == ("A1WP39-LEGACY-1", "BTCUSDT", "OPEN")
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0] == "008_broker_observation_projection"
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_events"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM broker_observation_log"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM broker_projection_state"
        ).fetchone()[0] == 0
    assert SQLiteDriver(str(database)).get_trade("A1WP39-LEGACY-1")["id"] == "A1WP39-LEGACY-1"
