"""H07 deterministic synthetic benchmark and resource-boundary contracts."""

import sqlite3

import pytest

from scripts.run_h07_benchmark import (
    BenchmarkContractError,
    BenchmarkResourceLimitError,
    H07BenchmarkRunner,
    ResourceBudget,
    benchmark_snapshot_digest,
    build_benchmark_report,
    generate_trade_snapshot,
    percentile,
    validate_benchmark_report,
)
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import (
    SQLiteDriver,
    SQLiteOperationCancelled,
    SQLiteOperationResourceLimit,
)
from app.services.evidence_pack_export import EvidencePackExportService
from app.services.trade_read_adapter import TradeReadAdapter
from scripts.run_h07_benchmark import _command_for_trade


def test_synthetic_trade_snapshot_is_deterministic_and_seeded():
    first = [generate_trade_snapshot(index, seed="H07-SEED") for index in range(4)]
    second = [generate_trade_snapshot(index, seed="H07-SEED") for index in range(4)]
    other = [generate_trade_snapshot(index, seed="OTHER") for index in range(4)]

    assert first == second
    assert first != other
    assert len({row["id"] for row in first}) == 4
    assert all(row["entry_time"].endswith("Z") for row in first)


def test_snapshot_digest_is_order_independent_only_after_canonical_sorting():
    rows = [generate_trade_snapshot(index, seed="H07-SEED") for index in range(5)]

    assert benchmark_snapshot_digest(rows) == benchmark_snapshot_digest(list(reversed(rows)))


def test_percentile_is_deterministic_without_numpy():
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 50) == 25.0
    assert percentile(values, 95) == 38.5
    assert percentile(values, 99) == 39.7


def test_benchmark_report_rejects_missing_measurement_provenance():
    report = build_benchmark_report(
        seed="H07-SEED",
        sizes=(1000,),
        provenance={"source_commit_sha": ""},
        runs=[{
            "size": 1000,
            "operations": {
                "query": {"sample_count": 0, "status": "UNKNOWN"},
            },
        }],
    )

    with pytest.raises(BenchmarkContractError, match="provenance"):
        validate_benchmark_report(report)


def test_benchmark_contract_rejects_oversized_dataset():
    with pytest.raises(BenchmarkContractError, match="100000"):
        build_benchmark_report(
            seed="H07-SEED",
            sizes=(100001,),
            provenance={},
            runs=[],
        )


def test_small_benchmark_exercises_import_rebuild_query_pack_export_and_cancel(tmp_path):
    report = H07BenchmarkRunner(
        seed="H07-INTEGRATION",
        batch_size=4,
        operation_repetitions=3,
    ).run((12,), work_dir=tmp_path)

    validate_benchmark_report(report)
    run = report["runs"][0]
    assert run["counts"] == {"trades": 12, "ledger_events": 15, "projections": 12}
    assert run["coverage"]["ready"] is True
    assert run["determinism"]["status"] == "COMPLETE"
    assert run["determinism"]["evidence_pack_snapshot_sha256"]
    assert run["determinism"]["evidence_artifact_sha256"]
    assert all(
        run["operations"][name]["status"] == "MEASURED"
        for name in (
            "import",
            "projection_rebuild",
            "query",
            "correction",
            "correction_replay",
            "replay",
            "evidence_pack",
            "evidence_pack_export",
            "cancel",
        )
    )


def test_explicit_resource_budget_fails_closed():
    with pytest.raises(BenchmarkContractError, match="RSS resource budget exceeded"):
        ResourceBudget(max_rss_mb=0).check(rss_mb=1, temp_disk_bytes=0)


def test_trade_event_lookup_uses_correlation_index_for_canonical_events(tmp_path, monkeypatch):
    db_path = tmp_path / "indexed-events.sqlite"
    driver = SQLiteDriver(str(db_path))
    trade = generate_trade_snapshot(0, seed="H07-INDEX")
    driver.record_grouped_evidence_batch([
        _command_for_trade(trade, 0, seed="H07-INDEX"),
    ])
    ledger = EvidenceLedgerRepository(str(db_path))

    def fail_if_full_ledger_scan_is_used(*_args, **_kwargs):
        raise AssertionError("canonical correlation lookup must not scan the full ledger")

    monkeypatch.setattr(ledger, "export_events", fail_if_full_ledger_scan_is_used)
    events = ledger.list_events_for_trade(
        trade["id"],
        account_id="h07-synthetic-account",
        venues=("h07-synthetic",),
    )

    assert [event["event_id"] for event in events] == ["H07-EVENT-000000"]


def test_chain_verification_uses_raw_snapshot_without_read_path_json_decode(tmp_path, monkeypatch):
    db_path = tmp_path / "raw-verification.sqlite"
    driver = SQLiteDriver(str(db_path))
    trade = generate_trade_snapshot(0, seed="H07-VERIFY")
    driver.record_grouped_evidence_batch([
        _command_for_trade(trade, 0, seed="H07-VERIFY"),
    ])
    ledger = EvidenceLedgerRepository(str(db_path))

    def fail_if_export_read_path_is_used(*_args, **_kwargs):
        raise AssertionError("verification must use its bounded raw snapshot path")

    monkeypatch.setattr(ledger, "export_events", fail_if_export_read_path_is_used)
    report = ledger.verify_chain(account_id="h07-synthetic-account")

    assert report["valid"] is True
    assert report["checked_events"] == 1


def test_chain_verification_reuses_unchanged_append_only_snapshot_until_append(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "cached-verification.sqlite"
    driver = SQLiteDriver(str(db_path))
    first_trade = generate_trade_snapshot(0, seed="H07-CACHE")
    driver.record_grouped_evidence_batch([
        _command_for_trade(first_trade, 0, seed="H07-CACHE"),
    ])
    ledger = EvidenceLedgerRepository(str(db_path))
    original_iter = ledger._iter_raw_verification_rows
    iterator_calls = 0

    def count_iterator_calls(*args, **kwargs):
        nonlocal iterator_calls
        iterator_calls += 1
        return original_iter(*args, **kwargs)

    monkeypatch.setattr(ledger, "_iter_raw_verification_rows", count_iterator_calls)

    first_report = ledger.verify_chain(account_id="h07-synthetic-account")
    second_report = ledger.verify_chain(account_id="h07-synthetic-account")

    assert first_report == second_report
    assert iterator_calls == 1

    second_trade = generate_trade_snapshot(1, seed="H07-CACHE")
    driver.record_grouped_evidence_batch([
        _command_for_trade(second_trade, 1, seed="H07-CACHE"),
    ])

    appended_report = ledger.verify_chain(account_id="h07-synthetic-account")

    assert appended_report["valid"] is True
    assert appended_report["checked_events"] == 2
    assert iterator_calls == 2


def test_projection_rebuild_reuses_ledger_verification_for_unchanged_snapshot(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "projection-verification-cache.sqlite"
    driver = SQLiteDriver(str(db_path))
    trade = generate_trade_snapshot(0, seed="H07-PROJECTION-CACHE")
    driver.record_grouped_evidence_batch([
        _command_for_trade(trade, 0, seed="H07-PROJECTION-CACHE"),
    ])
    projection = EvidenceTradeProjectionRepository(str(db_path))
    original_iter = projection._ledger_repo._iter_raw_verification_rows
    iterator_calls = 0

    def count_iterator_calls(*args, **kwargs):
        nonlocal iterator_calls
        iterator_calls += 1
        return original_iter(*args, **kwargs)

    monkeypatch.setattr(
        projection._ledger_repo,
        "_iter_raw_verification_rows",
        count_iterator_calls,
    )

    first = projection.rebuild(
        account_id="h07-synthetic-account",
        dry_run=True,
    )
    second = projection.rebuild(
        account_id="h07-synthetic-account",
        dry_run=True,
    )

    assert first == second
    assert iterator_calls == 1


def test_projection_apply_releases_verifier_connection_after_write(tmp_path):
    db_path = tmp_path / "projection-verification-connection.sqlite"
    driver = SQLiteDriver(str(db_path))
    trade = generate_trade_snapshot(0, seed="H07-PROJECTION-CONNECTION")
    driver.record_grouped_evidence_batch([
        _command_for_trade(trade, 0, seed="H07-PROJECTION-CONNECTION"),
    ])
    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(account_id="h07-synthetic-account", dry_run=True)

    assert projection._ledger_repo._integrity_cache_connection is not None

    projection.rebuild(account_id="h07-synthetic-account", dry_run=False)

    assert projection._ledger_repo._integrity_cache_connection is None


def test_grouped_batch_cancellation_rolls_back_canonical_trade_projection_and_ledger(tmp_path):
    db_path = tmp_path / "cancelled-batch.sqlite"
    driver = SQLiteDriver(str(db_path))
    commands = [
        _command_for_trade(
            generate_trade_snapshot(index, seed="H07-CANCEL"),
            index,
            seed="H07-CANCEL",
        )
        for index in range(2)
    ]
    checks = 0

    def cancel_after_first_boundary():
        nonlocal checks
        checks += 1
        return checks >= 2

    with pytest.raises(SQLiteOperationCancelled, match="cancelled"):
        driver.record_grouped_evidence_batch(
            commands,
            cancel_check=cancel_after_first_boundary,
        )

    assert checks == 2
    assert driver.list_trades(limit=10) == []
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
    with sqlite3.connect(str(db_path)) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_trade_projections"
        ).fetchone()[0] == 0


def test_grouped_batch_resource_limit_rolls_back_before_commit(tmp_path):
    db_path = tmp_path / "resource-limited-batch.sqlite"
    driver = SQLiteDriver(str(db_path))
    commands = [
        _command_for_trade(
            generate_trade_snapshot(index, seed="H07-RESOURCE"),
            index,
            seed="H07-RESOURCE",
        )
        for index in range(2)
    ]
    phases = []

    def resource_check(phase):
        phases.append(phase)
        if phase == "before_commit":
            raise SQLiteOperationResourceLimit("RSS resource budget exceeded")

    with pytest.raises(SQLiteOperationResourceLimit, match="resource budget"):
        driver.record_grouped_evidence_batch(
            commands,
            resource_check=resource_check,
        )

    assert phases[-1] == "before_commit"
    assert driver.list_trades(limit=10) == []
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0
    with sqlite3.connect(str(db_path)) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_trade_projections"
        ).fetchone()[0] == 0


def test_projection_rebuild_resource_limit_rolls_back_existing_projection(tmp_path):
    db_path = tmp_path / "resource-limited-rebuild.sqlite"
    driver = SQLiteDriver(str(db_path))
    commands = [
        _command_for_trade(
            generate_trade_snapshot(index, seed="H07-REBUILD"),
            index,
            seed="H07-REBUILD",
        )
        for index in range(3)
    ]
    driver.record_grouped_evidence_batch(commands)
    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(account_id="h07-synthetic-account", dry_run=False)
    before = projection.get_projection(
        commands[0]["trade"]["id"],
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
    )

    phases = []

    def resource_check(phase):
        phases.append(phase)
        if phase == "before_projection_commit":
            raise SQLiteOperationResourceLimit("temporary disk resource budget exceeded")

    with pytest.raises(SQLiteOperationResourceLimit, match="resource budget"):
        projection.rebuild(
            account_id="h07-synthetic-account",
            dry_run=False,
            resource_check=resource_check,
        )

    assert phases[-1] == "before_projection_commit"
    after = projection.get_projection(
        commands[0]["trade"]["id"],
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
    )
    assert after == before
    assert projection.coverage(
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
        venues=("h07-synthetic",),
    )["ready"] is True


def test_legacy_trade_query_resource_limit_aborts_mid_stream_without_partial_result(tmp_path):
    db_path = tmp_path / "resource-limited-legacy-query.sqlite"
    driver = SQLiteDriver(str(db_path))
    for index in range(4):
        driver.insert_trade(generate_trade_snapshot(index, seed="H07-QUERY-LEGACY"))

    phases = []
    rows_attempted = 0

    def resource_check(phase):
        nonlocal rows_attempted
        phases.append(phase)
        if phase == "before_trade_row":
            rows_attempted += 1
            if rows_attempted == 3:
                raise SQLiteOperationResourceLimit("RSS resource budget exceeded")

    with pytest.raises(SQLiteOperationResourceLimit, match="resource budget"):
        driver.list_trades(limit=4, resource_check=resource_check)

    assert phases[0] == "before_trade_query"
    assert rows_attempted == 3
    assert "after_trade_query" not in phases
    assert len(driver.list_trades(limit=4)) == 4


def test_projection_trade_query_resource_limit_aborts_mid_stream_without_partial_result(tmp_path):
    db_path = tmp_path / "resource-limited-projection-query.sqlite"
    driver = SQLiteDriver(str(db_path))
    commands = [
        _command_for_trade(
            generate_trade_snapshot(index, seed="H07-QUERY-PROJECTION"),
            index,
            seed="H07-QUERY-PROJECTION",
        )
        for index in range(4)
    ]
    driver.record_grouped_evidence_batch(commands)
    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(account_id="h07-synthetic-account", dry_run=False)
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=projection,
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
        projection_venues=("h07-synthetic",),
    )

    phases = []
    rows_attempted = 0

    def resource_check(phase):
        nonlocal rows_attempted
        phases.append(phase)
        if phase == "before_trade_row":
            rows_attempted += 1
            if rows_attempted == 3:
                raise SQLiteOperationResourceLimit("temporary disk resource budget exceeded")

    with pytest.raises(SQLiteOperationResourceLimit, match="resource budget"):
        adapter.list_trades(limit=4, order_by_utc=True, resource_check=resource_check)

    assert phases[0] == "before_trade_query"
    assert rows_attempted == 3
    assert "after_trade_query" not in phases
    assert len(adapter.list_trades(limit=4, order_by_utc=True)) == 4


def test_benchmark_resource_budget_aborts_import_before_commit(tmp_path):
    db_path = tmp_path / "resource-limited-run.sqlite"
    runner = H07BenchmarkRunner(
        seed="H07-BUDGET",
        batch_size=4,
        operation_repetitions=3,
        budget=ResourceBudget(max_temp_disk_bytes=0),
    )

    with pytest.raises(BenchmarkResourceLimitError, match="temporary disk"):
        runner.run((4,), work_dir=tmp_path)

    driver = SQLiteDriver(str(db_path))
    assert driver.list_trades(limit=10) == []
    assert EvidenceLedgerRepository(str(db_path)).count_events() == 0


def test_evidence_pack_resource_limit_is_explicit_and_read_only(tmp_path):
    db_path = tmp_path / "resource-limited-pack.sqlite"
    driver = SQLiteDriver(str(db_path))
    trade = generate_trade_snapshot(0, seed="H07-PACK")
    driver.record_grouped_evidence_batch([
        _command_for_trade(trade, 0, seed="H07-PACK"),
    ])
    projection = EvidenceTradeProjectionRepository(str(db_path))
    projection.rebuild(account_id="h07-synthetic-account", dry_run=False)
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=projection,
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
        projection_venues=("h07-synthetic",),
    )
    exporter = EvidencePackExportService(adapter)

    def resource_check(phase):
        if phase == "after_ledger_integrity":
            raise SQLiteOperationResourceLimit("RSS resource budget exceeded")

    with pytest.raises(SQLiteOperationResourceLimit, match="resource budget"):
        exporter.export(
            trade["id"],
            "json",
            resource_check=resource_check,
        )

    assert adapter.get_trade(trade["id"])["id"] == trade["id"]
