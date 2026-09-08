"""H01 canonical persistence, crash recovery, and concurrency contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys

import pytest

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.trade_read_adapter import TradeReadAdapter


ROOT = Path(__file__).resolve().parents[2]


def _trade(trade_id: str, *, entry_price: float = 100.0) -> dict:
    return {
        "id": trade_id,
        "symbol": "H01USDT",
        "side": "BUY",
        "entry_price": entry_price,
        "qty": 1.0,
        "entry_time": "2026-09-08T10:00:00Z",
        "status": "OPEN",
        "pnl": 0.0,
        "commission": 0.1,
        "notes": "synthetic H01 fixture",
    }


def _record(driver: SQLiteDriver, trade_id: str, *, event_key: str | None = None) -> dict:
    return driver.record_trade_with_evidence(
        _trade(trade_id),
        event_type="IntentRecorded",
        idempotency_key=event_key or f"h01:{trade_id}:intent",
        occurred_at="2026-09-08T10:00:00Z",
        provenance={"source": "h01-test"},
    )


def _crash_child(db_path: Path, phase: str) -> subprocess.CompletedProcess[str]:
    command = f"""
import os
from app.db.sqlite_driver import SQLiteDriver

def hook(current_phase, _connection):
    if current_phase == {phase!r}:
        os._exit(70)

driver = SQLiteDriver({str(db_path)!r}, transaction_hook=hook)
driver.record_trade_with_evidence(
    {json.dumps(_trade("CRASH-1"))},
    event_type="IntentRecorded",
    idempotency_key="h01:CRASH-1:intent",
    occurred_at="2026-09-08T10:00:00Z",
    provenance={{"source": "h01-test"}},
)
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "backend"), environment.get("PYTHONPATH", "")]
    )
    environment["KUANTRA_DATA_DIR"] = str(db_path.parent / "child-data")
    return subprocess.run(
        [sys.executable, "-c", command],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_process_crash_before_commit_rolls_back_and_retry_is_idempotent(tmp_path):
    for phase in ("after_canonical_event", "after_projection_update"):
        db_path = tmp_path / f"{phase}.sqlite"
        child = _crash_child(db_path, phase)
        assert child.returncode == 70, child.stderr

        reopened = SQLiteDriver(str(db_path))
        assert reopened.get_trade("CRASH-1") is None
        assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
        assert EvidenceTradeProjectionRepository(str(db_path)).list_projections() == []

        _record(reopened, "CRASH-1")
        assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
        assert EvidenceLedgerRepository(str(db_path)).verify_chain()["valid"] is True


def test_process_crash_after_commit_replay_does_not_duplicate_ack_state(tmp_path):
    db_path = tmp_path / "after-commit.sqlite"
    child = _crash_child(db_path, "after_commit_before_ack")
    assert child.returncode == 70, child.stderr

    reopened = SQLiteDriver(str(db_path))
    assert reopened.get_trade("CRASH-1") is not None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
    assert len(EvidenceTradeProjectionRepository(str(db_path)).list_projections()) == 1

    _record(reopened, "CRASH-1")
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
    assert len(EvidenceTradeProjectionRepository(str(db_path)).list_projections()) == 1


def test_concurrent_duplicate_and_distinct_imports_are_serialized_and_deterministic(tmp_path):
    db_path = tmp_path / "concurrent.sqlite"
    SQLiteDriver(str(db_path))

    def write(trade_id: str):
        return _record(SQLiteDriver(str(db_path)), trade_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        duplicate_results = list(executor.map(lambda _: write("DUPLICATE-1"), range(4)))

    assert len(duplicate_results) == 4
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
    assert len(EvidenceTradeProjectionRepository(str(db_path)).list_projections()) == 1

    with ThreadPoolExecutor(max_workers=4) as executor:
        distinct_results = list(
            executor.map(lambda index: write(f"DISTINCT-{index}"), range(4))
        )

    assert len(distinct_results) == 4
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 5
    assert len(EvidenceTradeProjectionRepository(str(db_path)).list_projections()) == 5
    assert EvidenceLedgerRepository(str(db_path)).verify_chain()["valid"] is True


def test_restart_and_projection_rebuild_preserve_evidence_pack(tmp_path):
    db_path = tmp_path / "rebuild.sqlite"
    driver = SQLiteDriver(str(db_path))
    _record(driver, "REBUILD-1")

    before = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
    ).get_evidence_pack("REBUILD-1")

    reopened = SQLiteDriver(str(db_path))
    projection = EvidenceTradeProjectionRepository(str(db_path))
    assert EvidenceLedgerRepository(str(db_path)).verify_chain()["valid"] is True
    assert projection.rebuild(dry_run=True)["ledger_valid"] is True
    projection.rebuild(dry_run=False)

    after = TradeReadAdapter(
        legacy_driver=reopened,
        projection_repo=EvidenceTradeProjectionRepository(str(db_path)),
    ).get_evidence_pack("REBUILD-1")
    assert after == before


def test_read_only_database_fails_closed_without_mutation(tmp_path, monkeypatch):
    db_path = tmp_path / "read-only.sqlite"
    driver = SQLiteDriver(str(db_path))
    _record(driver, "READONLY-1")
    original_get_connection = driver.get_connection

    def read_only_connection():
        connection = original_get_connection()
        connection.execute("PRAGMA query_only=ON")
        return connection

    monkeypatch.setattr(driver, "get_connection", read_only_connection)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        _record(driver, "READONLY-2")

    assert driver.get_trade("READONLY-1") is not None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
    assert len(EvidenceTradeProjectionRepository(str(db_path)).list_projections()) == 1


def test_read_only_directory_fails_closed_without_mutation(tmp_path):
    if os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0:
        pytest.skip("filesystem permission semantics are not reliable for this host")

    db_path = tmp_path / "read-only-directory.sqlite"
    driver = SQLiteDriver(str(db_path))
    _record(driver, "READONLY-DIR-1")
    original_db_mode = stat.S_IMODE(db_path.stat().st_mode)
    original_dir_mode = stat.S_IMODE(tmp_path.stat().st_mode)
    os.chmod(db_path, 0o444)
    os.chmod(tmp_path, 0o555)
    try:
        with pytest.raises((PermissionError, sqlite3.OperationalError)):
            SQLiteDriver(str(db_path)).record_trade_with_evidence(
                _trade("READONLY-DIR-2"),
                event_type="IntentRecorded",
                idempotency_key="h01:READONLY-DIR-2:intent",
                occurred_at="2026-09-08T10:00:00Z",
                provenance={"source": "h01-test"},
            )
    finally:
        os.chmod(tmp_path, original_dir_mode)
        os.chmod(db_path, original_db_mode)

    reopened = SQLiteDriver(str(db_path))
    assert reopened.get_trade("READONLY-DIR-1") is not None
    assert reopened.get_trade("READONLY-DIR-2") is None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1


def test_sqlite_busy_writer_fails_closed_without_half_import(tmp_path):
    db_path = tmp_path / "busy.sqlite"
    driver = SQLiteDriver(str(db_path))
    blocker = sqlite3.connect(str(db_path), isolation_level=None, timeout=0.1)
    blocker.execute("PRAGMA journal_mode=WAL")
    blocker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            _record(driver, "BUSY-1")
    finally:
        if blocker.in_transaction:
            blocker.rollback()
        blocker.close()

    assert driver.get_trade("BUSY-1") is None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
    assert EvidenceTradeProjectionRepository(str(db_path)).list_projections() == []


@pytest.mark.parametrize("message", ["database or disk is full", "database is locked"])
def test_storage_failure_is_fail_closed_and_retryable(tmp_path, message):
    db_path = tmp_path / f"{message.replace(' ', '-')}.sqlite"

    def fail_before_commit(phase, _connection):
        if phase == "before_commit":
            raise sqlite3.OperationalError(message)

    failing = SQLiteDriver(str(db_path), transaction_hook=fail_before_commit)
    with pytest.raises(sqlite3.OperationalError, match=message):
        _record(failing, "FAILURE-1")

    assert failing.get_trade("FAILURE-1") is None
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
    assert EvidenceTradeProjectionRepository(str(db_path)).list_projections() == []

    _record(SQLiteDriver(str(db_path)), "FAILURE-1")
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 1
    assert EvidenceLedgerRepository(str(db_path)).verify_chain()["valid"] is True
