"""H07 deterministic synthetic benchmark and resource-boundary contracts."""

import pytest

from scripts.run_h07_benchmark import (
    BenchmarkContractError,
    H07BenchmarkRunner,
    ResourceBudget,
    benchmark_snapshot_digest,
    build_benchmark_report,
    generate_trade_snapshot,
    percentile,
    validate_benchmark_report,
)
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
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
    assert run["counts"] == {"trades": 12, "ledger_events": 12, "projections": 12}
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
