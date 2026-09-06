import json
import sqlite3

import pytest

from app.db.evidence_schema import EVENT_TYPES, initialize_evidence_schema
from app.db.repositories.evidence_ledger_repo import (
    GENESIS_HASH,
    EvidenceIdentityConflict,
    EvidenceLedgerRepository,
    EvidenceValidationError,
)
from app.db.sqlite_driver import SQLiteDriver
from app.cli import create_parser


def _command(index: int, *, account_id: str = "acct-1"):
    return {
        "event_type": "IntentRecorded",
        "account_id": account_id,
        "venue": "paper",
        "idempotency_key": f"intent-{index}",
        "normalized_payload": {"index": index, "setup": "breakout"},
        "occurred_at": "2026-09-06T10:00:00Z",
        "adapter_version": "test-v1",
        "correlation_id": f"trade-{index}",
        "provenance": {"source": "test"},
    }


def test_schema_is_idempotent_and_alembic_reaches_head(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repository = EvidenceLedgerRepository(str(db_path))
    with sqlite3.connect(db_path) as conn:
        initialize_evidence_schema(conn)
        initialize_evidence_schema(conn)
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(evidence_events)").fetchall()
        }
        assert {"event_id", "normalized_payload_json", "prev_hash", "event_hash"} <= columns
        index_names = {
            row[1]
            for row in conn.execute("PRAGMA index_list(evidence_events)").fetchall()
        }
        assert "uq_evidence_events_identity" in index_names

    driver = SQLiteDriver(str(db_path))
    assert driver.run_migrations("head") is True
    assert driver.run_migrations("head") is True
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "002_evidence_ledger"
    assert repository.count_events() == 0


def test_10000_events_form_a_valid_chain(tmp_path):
    repository = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    results = repository.append_events(_command(index) for index in range(10_000))

    assert len(results) == 10_000
    assert results[0]["chain_sequence"] == 1
    assert results[-1]["chain_sequence"] == 10_000
    assert results[0]["prev_hash"] == GENESIS_HASH
    report = repository.verify_chain(account_id="acct-1", chain_date_utc="2026-09-06")
    assert report["valid"] is True
    assert report["checked_events"] == 10_000
    assert report["errors"] == []


def test_duplicate_identity_is_a_noop_and_conflict_is_fail_closed(tmp_path):
    repository = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    first = repository.append_event(**_command(1))
    duplicate = repository.append_event(
        **{**_command(1), "received_at": "2026-09-06T10:01:00Z", "event_id": "retry-id"}
    )
    assert duplicate["created"] is False
    assert duplicate["event_id"] == first["event_id"]
    assert repository.count_events() == 1

    with pytest.raises(EvidenceIdentityConflict):
        repository.append_event(
            **{
                **_command(1),
                "normalized_payload": {"index": 1, "setup": "different"},
            }
        )
    assert repository.count_events() == 1


def test_verifier_detects_payload_and_previous_hash_mutation(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repository = EvidenceLedgerRepository(str(db_path))
    repository.append_events([_command(1), _command(2)])

    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TRIGGER evidence_events_no_update")
        conn.execute(
            "UPDATE evidence_events SET normalized_payload_json = ? WHERE chain_sequence = 1",
            ('{"index":999,"setup":"tampered"}',),
        )
        conn.execute(
            "UPDATE evidence_events SET prev_hash = ? WHERE chain_sequence = 2",
            ("f" * 64,),
        )
        conn.commit()

    report = repository.verify_chain()
    assert report["valid"] is False
    assert any("event hash mismatch" in error for error in report["errors"])
    assert any("prev_hash mismatch" in error for error in report["errors"])


def test_validation_and_injected_failure_leave_no_event(tmp_path):
    repository = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    with pytest.raises(EvidenceValidationError):
        repository.append_event(**{**_command(1), "event_type": "SyntheticTick"})
    with pytest.raises(EvidenceValidationError):
        repository.append_event(**{**_command(1), "normalized_payload": {"api_key": "secret"}})
    with pytest.raises(EvidenceValidationError):
        repository.append_event(
            **{**_command(1), "raw_payload": {"private_key": "secret"}}
        )

    def fail_after_insert(_connection):
        raise RuntimeError("injected transaction failure")

    failing = EvidenceLedgerRepository(
        str(tmp_path / "failing.sqlite"), failure_injector=fail_after_insert
    )
    with pytest.raises(RuntimeError, match="injected"):
        failing.append_event(**_command(1))
    assert failing.count_events() == 0


def test_append_only_guards_and_read_only_export(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repository = EvidenceLedgerRepository(str(db_path))
    repository.append_events([_command(1), _command(2)])
    exported = list(repository.export_events(account_id="acct-1"))
    assert [row["chain_sequence"] for row in exported] == [1, 2]
    exported_jsonl = repository.export_jsonl().splitlines()
    assert len(exported_jsonl) == 2
    assert all(isinstance(json.loads(line), dict) for line in exported_jsonl)
    assert all(row["event_hash"] for row in exported)

    with sqlite3.connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM evidence_events WHERE chain_sequence = 1")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE evidence_events SET venue = 'mutated' WHERE chain_sequence = 1"
            )


def test_legacy_backfill_is_dry_run_idempotent_and_does_not_mutate_source(tmp_path):
    db_path = tmp_path / "journal.sqlite"
    driver = SQLiteDriver(str(db_path))
    driver.insert_trade(
        {
            "id": "legacy-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-09-01T10:00:00Z",
            "status": "OPEN",
            "notes": "pilot",
        }
    )
    driver.insert_trade(
        {
            "id": "legacy-2",
            "symbol": "ETHUSDT",
            "side": "SELL",
            "entry_price": 200.0,
            "qty": 2.0,
            "entry_time": "2026-09-01T11:00:00Z",
            "status": "CLOSED",
            "exit_price": 190.0,
        }
    )
    before = driver.list_trades(limit=10, order_by_utc=True)
    repository = EvidenceLedgerRepository(str(db_path))

    dry_run = repository.backfill_legacy_trades(dry_run=True)
    assert dry_run["source_count"] == 2
    assert dry_run["would_append"] == 2
    assert dry_run["appended"] == 0
    assert repository.count_events() == 0

    applied = repository.backfill_legacy_trades(dry_run=False)
    assert applied["appended"] == 2
    repeated = repository.backfill_legacy_trades(dry_run=False)
    assert repeated["duplicates"] == 2
    assert repository.count_events() == 2
    assert driver.list_trades(limit=10, order_by_utc=True) == before
    assert repository.verify_chain()["valid"] is True


def test_legacy_trade_upsert_preserves_foreign_key_tags(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    trade = {
        "id": "TAGGED-TRADE",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "qty": 1.0,
        "entry_time": "2026-09-01T10:00:00Z",
        "status": "OPEN",
    }
    driver.insert_trade(trade)

    with driver.get_connection() as conn:
        conn.execute("INSERT INTO tags (name) VALUES (?)", ("breakout",))
        tag_id = conn.execute(
            "SELECT id FROM tags WHERE name = ?", ("breakout",)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO trade_tags (trade_id, tag_id) VALUES (?, ?)",
            (trade["id"], tag_id),
        )
        conn.commit()

    driver.insert_trade(
        {
            **trade,
            "entry_price": 101.0,
            "status": "CLOSED",
            "exit_price": 102.0,
        }
    )

    with driver.get_connection() as conn:
        linked_tags = conn.execute(
            "SELECT tag_id FROM trade_tags WHERE trade_id = ?",
            (trade["id"],),
        ).fetchall()

    assert [row[0] for row in linked_tags] == [tag_id]
    assert driver.get_trade(trade["id"])["entry_price"] == 101.0
    assert driver.get_trade(trade["id"])["status"] == "CLOSED"


def test_event_type_contract_is_explicit():
    assert len(EVENT_TYPES) == 14
    assert "LegacyTradeImported" in EVENT_TYPES
    assert "SyntheticTick" not in EVENT_TYPES


def test_explicit_backfill_cli_supports_dry_run_and_apply():
    parser = create_parser()
    dry_run = parser.parse_args(["evidence-ledger", "backfill", "--dry-run"])
    apply = parser.parse_args(["evidence-ledger", "backfill", "--apply"])
    assert dry_run.dry_run is True
    assert dry_run.apply is False
    assert apply.apply is True
