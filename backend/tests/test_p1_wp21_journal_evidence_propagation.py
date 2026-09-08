"""P1-WP21 deterministic economic-group journal/evidence propagation contracts."""

from copy import deepcopy

import pytest

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.economic_trade_grouping import EconomicGroupingService
from app.services.economic_evidence_propagation import (
    EconomicEvidencePropagationError,
    EconomicEvidencePropagationService,
)
from app.services.trade_read_adapter import TradeReadAdapter


SOURCE_SHA = "a" * 64


def _fill(external_id: str, *, qty: str = "0.5", price: str = "100", occurred_at: str = "2026-09-08T10:00:00Z", economic_key: str | None = None):
    row = {
        "observation_type": "FILL",
        "id": external_id,
        "order_id": f"ORDER-{external_id}",
        "fill_id": external_id,
        "qty": qty,
        "price": price,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "occurred_at": occurred_at,
    }
    if economic_key is not None:
        row["economic_key"] = economic_key
    return row


def _group_report(rows, *, account_id: str = "acct-1"):
    service = EconomicGroupingService()
    records, rejected = service.normalize_observations(
        "BINANCE",
        rows,
        account_id=account_id,
        source_exchange_id="binance_futures",
        market_type="swap",
        source_kind="CSV",
        source_document_sha256=SOURCE_SHA,
    )
    assert rejected == []
    return service.group(records, position_mode="ONE_WAY")


def _snapshot(group, *, trade_id: str, pnl: float = 12.5, commission: float = 0.2, **overrides):
    trade = {
        "id": trade_id,
        "symbol": group["symbol"],
        "side": group["side"],
        "entry_price": float(group["price"]),
        "qty": float(group["quantity"]),
        "entry_time": group["occurred_at"],
        "status": "OPEN",
        "pnl": pnl,
        "commission": commission,
        "notes": "fixture",
    }
    trade.update(overrides)
    return trade


def _coverage(account_id: str = "acct-1", *, status: str = "COMPLETE", **extra):
    value = {
        "status": status,
        "events_complete": status == "COMPLETE",
        "realized_pnl_complete": status == "COMPLETE",
        "unrealized_pnl_complete": status == "COMPLETE",
        "reasons": [] if status == "COMPLETE" else [f"{status}_FIXTURE"],
        "realized_pnl": None if status != "COMPLETE" else 12.5,
        "unrealized_pnl": None,
    }
    value.update(extra)
    return {account_id: value}


def _adapter(db_path, *, account_id="acct-1", venue="BINANCE"):
    driver = SQLiteDriver(str(db_path))
    return TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
        account_id=account_id,
        venue=venue,
        projection_venues=(venue,),
    )


def test_permutation_and_replay_produce_the_same_snapshot(tmp_path):
    rows = [
        _fill("FILL-2", qty="0.25", price="101", occurred_at="2026-09-08T10:02:00Z", economic_key="ECO-2"),
        _fill("FILL-1", economic_key="ECO-1"),
    ]
    report = _group_report(rows)
    snapshots = {
        group["economic_group_id"]: _snapshot(group, trade_id=f"TRADE-{index}")
        for index, group in enumerate(report["groups"], start=1)
    }

    first_db = tmp_path / "first.sqlite"
    first = EconomicEvidencePropagationService(SQLiteDriver(str(first_db))).propagate(
        report,
        trade_snapshots=snapshots,
        account_coverage=_coverage(),
    )
    replay_report = deepcopy(report)
    replay_report["groups"] = list(reversed(replay_report["groups"]))
    second_db = tmp_path / "second.sqlite"
    second_service = EconomicEvidencePropagationService(SQLiteDriver(str(second_db)))
    second = second_service.propagate(
        replay_report,
        trade_snapshots=snapshots,
        account_coverage=_coverage(),
    )
    replay = second_service.propagate(
        replay_report,
        trade_snapshots=snapshots,
        account_coverage=_coverage(),
    )

    assert first["created_count"] == 2
    assert second["created_count"] == 2
    assert replay["created_count"] == 0
    assert first["events"] == second["events"]
    first_adapter = _adapter(first_db)
    second_adapter = _adapter(second_db)
    for trade in sorted(snapshots.values(), key=lambda item: item["id"]):
        trade_id = trade["id"]
        assert first_adapter.get_evidence_pack(trade_id) == second_adapter.get_evidence_pack(trade_id)


@pytest.mark.parametrize("coverage_status", ["PARTIAL", "UNKNOWN"])
def test_lineage_and_incomplete_account_coverage_are_preserved(tmp_path, coverage_status):
    report = _group_report([_fill("FILL-1", economic_key="ECO-1")])
    group = report["groups"][0]
    db_path = tmp_path / f"{coverage_status.lower()}.sqlite"
    driver = SQLiteDriver(str(db_path))
    service = EconomicEvidencePropagationService(driver)
    service.propagate(
        report,
        trade_snapshots={group["economic_group_id"]: _snapshot(group, trade_id="TRADE-1")},
        account_coverage=_coverage(status=coverage_status),
    )

    adapter = _adapter(db_path)
    pack = adapter.get_evidence_pack("TRADE-1")
    evidence = pack["economic_evidence"]
    assert evidence["source_lineage"] == group["source_lineage"]
    assert evidence["account_coverage"]["status"] == coverage_status
    assert pack["trade"]["pnl"] == 12.5
    assert pack["trade"]["commission"] == 0.2
    assert evidence["account_coverage"].get("realized_pnl") is None
    assert evidence["account_coverage"]["status"] != "COMPLETE"


def test_correction_is_immutable_lineage_and_idempotent(tmp_path):
    db_path = tmp_path / "correction.sqlite"
    driver = SQLiteDriver(str(db_path))
    service = EconomicEvidencePropagationService(driver)
    initial_report = _group_report([_fill("FILL-1", qty="0.5", economic_key="ECO-1")])
    initial_group = initial_report["groups"][0]
    service.propagate(
        initial_report,
        trade_snapshots={initial_group["economic_group_id"]: _snapshot(initial_group, trade_id="TRADE-1")},
        account_coverage=_coverage(),
    )

    corrected_report = _group_report([
        _fill("FILL-1", qty="0.5", economic_key="ECO-1"),
        {
            **_fill("CORR-1", qty="0.7", economic_key="ECO-1", occurred_at="2026-09-08T12:00:00Z"),
            "observation_type": "CORRECTION",
            "corrects_economic_key": "ECO-1",
            "effective_at": "2026-09-08T12:00:00Z",
        },
    ])
    corrected_group = corrected_report["groups"][0]
    assert corrected_group["correction_count"] == 1
    result = service.propagate(
        corrected_report,
        trade_snapshots={corrected_group["economic_group_id"]: _snapshot(corrected_group, trade_id="TRADE-1")},
        account_coverage=_coverage(),
    )
    replay = service.propagate(
        corrected_report,
        trade_snapshots={corrected_group["economic_group_id"]: _snapshot(corrected_group, trade_id="TRADE-1")},
        account_coverage=_coverage(),
    )

    events = list(EvidenceLedgerRepository(str(db_path)).export_events(account_id="acct-1"))
    assert [event["event_type"] for event in events] == ["FillRecorded", "TradeCorrected"]
    assert events[1]["causation_id"] == events[0]["event_id"]
    assert events[0]["normalized_payload"]["trade"]["qty"] == 0.5
    assert events[1]["normalized_payload"]["trade"]["qty"] == 0.7
    assert result["created_count"] == 1
    assert replay["created_count"] == 0
    pack = _adapter(db_path).get_evidence_pack("TRADE-1")
    assert pack["event_count"] == 2
    assert pack["economic_evidence"]["revision"]["previous_event_id"] == events[0]["event_id"]
    assert pack["economic_evidence"]["revision"]["revision_number"] == 2
    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(dry_run=False)
    assert projection.get_trade_snapshot(
        "TRADE-1", account_id="acct-1", venue="BINANCE", venues=("BINANCE",)
    )["qty"] == 0.7


def test_batch_failure_rolls_back_compatibility_ledger_and_projection(tmp_path, monkeypatch):
    db_path = tmp_path / "rollback.sqlite"
    driver = SQLiteDriver(str(db_path))
    report = _group_report([
        _fill("FILL-1", economic_key="ECO-1"),
        _fill("FILL-2", qty="0.25", price="101", occurred_at="2026-09-08T10:02:00Z", economic_key="ECO-2"),
    ])
    snapshots = {
        group["economic_group_id"]: _snapshot(group, trade_id=f"TRADE-{index}")
        for index, group in enumerate(report["groups"], start=1)
    }
    calls = {"count": 0}
    original = EvidenceTradeProjectionRepository.upsert_event_in_transaction

    def fail_on_second(self, conn, event):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("injected projection failure")
        return original(self, conn, event)

    monkeypatch.setattr(EvidenceTradeProjectionRepository, "upsert_event_in_transaction", fail_on_second)
    with pytest.raises(RuntimeError, match="injected projection failure"):
        EconomicEvidencePropagationService(driver).propagate(
            report,
            trade_snapshots=snapshots,
            account_coverage=_coverage(),
        )

    assert driver.list_trades(limit=100) == []
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
    assert EvidenceTradeProjectionRepository(str(db_path)).list_projections() == []


def test_invalid_chain_malformed_group_missing_account_support_and_unknown_financials_fail_closed(tmp_path, monkeypatch):
    db_path = tmp_path / "negative.sqlite"
    driver = SQLiteDriver(str(db_path))
    service = EconomicEvidencePropagationService(driver)
    report = _group_report([_fill("FILL-1", economic_key="ECO-1")])
    group = report["groups"][0]
    base_snapshots = {group["economic_group_id"]: _snapshot(group, trade_id="TRADE-1")}

    malformed = deepcopy(report)
    malformed["groups"][0]["quantity"] = None
    with pytest.raises(EconomicEvidencePropagationError, match="quantity"):
        service.propagate(malformed, trade_snapshots=base_snapshots, account_coverage=_coverage())

    missing_pnl = deepcopy(base_snapshots)
    missing_pnl[group["economic_group_id"]] = _snapshot(group, trade_id="TRADE-1")
    del missing_pnl[group["economic_group_id"]]["pnl"]
    with pytest.raises(EconomicEvidencePropagationError, match="pnl"):
        service.propagate(report, trade_snapshots=missing_pnl, account_coverage=_coverage())

    unsupported = _coverage(
        status="PARTIAL",
        reasons=["EVENT_STORAGE_SCHEMA_PENDING"],
        unsupported_event_count=1,
    )
    with pytest.raises(EconomicEvidencePropagationError, match="unsupported"):
        service.propagate(report, trade_snapshots=base_snapshots, account_coverage=unsupported)

    service.propagate(report, trade_snapshots=base_snapshots, account_coverage=_coverage())
    monkeypatch.setattr(
        service.ledger_repo,
        "verify_chain",
        lambda **_: {"valid": False, "checked_events": 1, "errors": ["tampered fixture"]},
    )
    next_report = _group_report([_fill("FILL-2", economic_key="ECO-2", occurred_at="2026-09-08T10:02:00Z")])
    next_group = next_report["groups"][0]
    with pytest.raises(EconomicEvidencePropagationError, match="ledger"):
        service.propagate(
            next_report,
            trade_snapshots={next_group["economic_group_id"]: _snapshot(next_group, trade_id="TRADE-2")},
            account_coverage=_coverage(),
        )
