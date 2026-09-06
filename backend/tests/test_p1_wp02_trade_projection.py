import pytest

from app.cli import create_parser
from app.api.endpoints import delete_trade, get_trade_evidence
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import (
    EvidenceProjectionError,
    EvidenceTradeProjectionRepository,
)
from app.db.sqlite_driver import SQLiteDriver
from app.db.sync_pipeline import SyncPipeline
from app.services.trade_read_adapter import TradeReadAdapter


def _trade(**overrides):
    value = {
        "id": "PROJECTION-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "qty": 1.0,
        "entry_time": "2026-09-06T10:00:00Z",
        "status": "OPEN",
        "notes": "projection fixture",
    }
    value.update(overrides)
    return value


def _use_driver(monkeypatch, driver):
    monkeypatch.setattr("app.db.sync_pipeline.sqlite_driver", driver)
    monkeypatch.setattr(
        "app.db.sync_pipeline.duckdb_driver",
        type("DuckDBDisabled", (), {"is_available": False})(),
    )


def test_projection_rebuild_replays_fill_and_tombstone(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)

    SyncPipeline.record_and_sync_trade(_trade(), source="manual")
    SyncPipeline.record_and_sync_trade(
        _trade(
            status="CLOSED",
            exit_price=105.0,
            exit_time="2026-09-06T10:05:00Z",
            pnl=5.0,
        ),
        source="manual",
    )
    SyncPipeline.record_and_sync_trade(
        {"id": "PROJECTION-1", "status": "CANCELED"},
        source="journal_delete",
        source_ref="api",
    )

    repository = EvidenceTradeProjectionRepository(str(db_path))
    dry_run = repository.rebuild(dry_run=True)
    assert dry_run["events_seen"] == 3
    assert dry_run["projectable_events"] == 3
    assert dry_run["tombstones"] == 1
    # Production journal writes keep the typed read model current.  The dry run
    # must not clear or mutate that already-available projection.
    assert repository.get_projection("PROJECTION-1")["status"] == "CANCELED"

    applied = repository.rebuild(dry_run=False)
    projection = repository.get_projection("PROJECTION-1")
    assert applied["projections_written"] == 1
    assert projection["status"] == "CANCELED"
    assert projection["is_tombstone"] == 1
    assert projection["source_event_type"] == "TradeCorrected"
    assert projection["snapshot"]["status"] == "CANCELED"


def test_delete_endpoint_records_tombstone_instead_of_physical_delete(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)
    monkeypatch.setattr("app.api.endpoints.sqlite_driver", driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")

    result = delete_trade("PROJECTION-1")

    assert result["status"] == "canceled"
    assert result["trade"]["status"] == "CANCELED"
    assert driver.get_trade("PROJECTION-1")["status"] == "CANCELED"
    assert driver.get_trade("PROJECTION-1") is not None


def test_projection_rebuild_is_deterministic_and_can_hide_tombstones(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")
    SyncPipeline.record_and_sync_trade(
        {"id": "PROJECTION-1", "status": "CANCELED"},
        source="journal_delete",
    )

    repository = EvidenceTradeProjectionRepository(str(db_path))
    repository.rebuild(dry_run=False)
    first = repository.get_projection("PROJECTION-1")
    repository.rebuild(dry_run=False)
    second = repository.get_projection("PROJECTION-1")

    assert first["source_event_id"] == second["source_event_id"]
    assert first["source_event_hash"] == second["source_event_hash"]
    assert first["snapshot"] == second["snapshot"]
    assert repository.list_projections(include_tombstones=False) == []


def test_invalid_projectable_event_fails_closed_without_clearing_projection(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")
    repository = EvidenceTradeProjectionRepository(str(db_path))
    repository.rebuild(dry_run=False)

    EvidenceLedgerRepository(str(db_path)).append_event(
        event_type="IntentRecorded",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key="invalid-projection-event",
        normalized_payload={"not_trade": True},
        occurred_at="2026-09-06T11:00:00Z",
        provenance={"source": "test"},
    )

    with pytest.raises(EvidenceProjectionError, match="no trade snapshot"):
        repository.rebuild(dry_run=False)
    assert repository.get_projection("PROJECTION-1") is not None


def test_projection_rebuild_cli_parser_is_explicit_and_safe_by_default():
    parser = create_parser()
    dry_run = parser.parse_args(["evidence-ledger", "projection-rebuild", "--dry-run"])
    apply = parser.parse_args(["evidence-ledger", "projection-rebuild", "--apply"])
    assert dry_run.apply is False
    assert apply.apply is True


def test_pipeline_write_updates_projection_without_explicit_rebuild(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)

    SyncPipeline.record_and_sync_trade(_trade(), source="manual")

    repository = EvidenceTradeProjectionRepository(str(db_path))
    projection = repository.get_projection("PROJECTION-1")
    assert projection is not None
    assert projection["status"] == "OPEN"
    assert repository.coverage()["ready"] is True


def test_projection_failure_rolls_back_trade_and_ledger(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    monkeypatch.setattr(
        "app.db.repositories.evidence_projection_repo.EvidenceTradeProjectionRepository.upsert_event_in_transaction",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("projection failure")),
    )

    with pytest.raises(RuntimeError, match="projection failure"):
        driver.record_trade_with_evidence(
            _trade(),
            event_type="IntentRecorded",
            idempotency_key="projection-rollback",
            occurred_at="2026-09-06T10:00:00Z",
            provenance={"source": "test"},
        )

    assert driver.get_trade("PROJECTION-1") is None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0


def test_read_adapter_falls_back_until_projection_coverage_is_complete(tmp_path):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    projection = EvidenceTradeProjectionRepository(str(db_path))
    adapter = TradeReadAdapter(legacy_driver=driver, projection_repo=projection)

    # Compatibility-only rows from older versions remain visible while the
    # explicit ledger backfill has not covered them.
    driver.insert_trade(_trade())
    assert adapter.coverage()["ready"] is False
    assert adapter.get_trade("PROJECTION-1")["id"] == "PROJECTION-1"

    EvidenceLedgerRepository(str(db_path)).append_event(
        event_type="LegacyTradeImported",
        account_id="local-journal",
        venue="legacy",
        idempotency_key="legacy-projection-1",
        normalized_payload={"trade": _trade()},
        occurred_at="2026-09-06T10:00:00Z",
        provenance={"source": "test"},
    )
    projection.rebuild(dry_run=False)
    assert adapter.coverage()["ready"] is True
    assert adapter.get_trade("PROJECTION-1")["id"] == "PROJECTION-1"


def test_read_adapter_rejects_duplicate_trade_ids_across_migration_venues(tmp_path):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    driver.insert_trade(_trade())
    ledger = EvidenceLedgerRepository(str(db_path))
    for venue in ("local-journal", "legacy"):
        ledger.append_event(
            event_type="LegacyTradeImported",
            account_id="local-journal",
            venue=venue,
            idempotency_key=f"duplicate-{venue}",
            normalized_payload={"trade": _trade()},
            occurred_at="2026-09-06T10:00:00Z",
            provenance={"source": "test"},
        )

    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(dry_run=False)
    coverage = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=projection,
    ).coverage()
    assert coverage["duplicate_count"] == 1
    assert coverage["ready"] is False


def test_full_duckdb_sync_blocks_unverified_compatibility_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    driver.insert_trade(_trade())
    monkeypatch.setattr("app.db.sync_pipeline.sqlite_driver", driver)

    class UnexpectedDuckDB:
        is_available = True

        @staticmethod
        def sync_all_trades(_trades):
            raise AssertionError("blocked full sync must not reach DuckDB")

    monkeypatch.setattr("app.db.sync_pipeline.duckdb_driver", UnexpectedDuckDB())
    assert SyncPipeline.full_sync() == 0


def test_full_duckdb_sync_uses_evidence_projection_when_ready(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")

    synced = []

    class RecordingDuckDB:
        is_available = True

        @staticmethod
        def sync_all_trades(trades):
            synced.extend(trades)
            return len(trades)

    monkeypatch.setattr("app.db.sync_pipeline.duckdb_driver", RecordingDuckDB())
    assert SyncPipeline.full_sync() == 1
    assert synced[0]["id"] == "PROJECTION-1"


def test_trade_evidence_pack_is_source_linked_and_raw_payload_free(tmp_path, monkeypatch):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    _use_driver(monkeypatch, driver)
    SyncPipeline.record_and_sync_trade(_trade(), source="manual")
    SyncPipeline.record_and_sync_trade(
        _trade(
            status="CLOSED",
            exit_price=105.0,
            exit_time="2026-09-06T10:05:00Z",
            pnl=5.0,
        ),
        source="manual",
    )
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
    )

    pack = adapter.get_evidence_pack("PROJECTION-1")
    assert pack["read_source"] == "typed_projection"
    assert pack["coverage"]["ready"] is True
    assert pack["ledger_integrity"]["valid"] is True
    assert [event["event_type"] for event in pack["events"]] == [
        "IntentRecorded",
        "FillRecorded",
    ]
    assert all("raw_payload" not in event for event in pack["events"])

    monkeypatch.setattr("app.api.endpoints.trade_read_adapter", adapter)
    endpoint_pack = get_trade_evidence("PROJECTION-1")
    assert endpoint_pack["event_count"] == 2
