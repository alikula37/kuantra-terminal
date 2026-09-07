"""P2-WP22 deterministic Binance depth fault-injection matrix."""

from copy import deepcopy

from app.services.market_data.binance_depth_fault_matrix import (
    FAULT_MATRIX_SCHEMA_VERSION,
    build_binance_depth_fault_matrix,
    run_binance_depth_fault_matrix,
    verify_binance_depth_fault_matrix,
)


def test_fault_matrix_definitions_are_named_and_bounded():
    scenarios = build_binance_depth_fault_matrix()

    assert len(scenarios) == 7
    assert [scenario.scenario_id for scenario in scenarios] == [
        "clean_cycle",
        "disconnect_reconnect",
        "gap_terminal_without_retry",
        "gap_recovered_with_opt_in",
        "malformed_event_terminal",
        "snapshot_rejected",
        "reconnect_budget_exhausted",
    ]
    assert all(scenario.policy.max_reconnects <= 1 for scenario in scenarios)


def test_fault_matrix_runs_against_real_ingestor_and_durable_sink(tmp_path):
    report = run_binance_depth_fault_matrix(storage_root=tmp_path / "matrix")

    assert report["schema_version"] == FAULT_MATRIX_SCHEMA_VERSION
    assert report["mode"] == "fixture"
    assert report["environment"] == "offline"
    assert report["case_count"] == 7
    assert report["overall_ok"] is True
    assert report["source_verified"] is False
    assert report["execution_authority"] is False
    assert all(case["ok"] is True for case in report["cases"])
    assert verify_binance_depth_fault_matrix(report) == (True, ())

    by_id = {case["scenario_id"]: case for case in report["cases"]}
    assert by_id["gap_terminal_without_retry"]["observed"]["decision"] == "RECOVERY_REQUIRED"
    assert by_id["gap_terminal_without_retry"]["observed"]["persistence"]["event_count"] == 2
    assert by_id["gap_recovered_with_opt_in"]["observed"]["decision"] == "COMPLETED"
    assert by_id["gap_recovered_with_opt_in"]["observed"]["continuity"]["gap_event_count"] == 1
    assert by_id["snapshot_rejected"]["observed"]["persistence"]["event_count"] == 0


def test_fault_matrix_verifier_rejects_tampered_observation(tmp_path):
    report = run_binance_depth_fault_matrix(storage_root=tmp_path / "matrix")
    tampered = deepcopy(report)
    tampered["cases"][1]["observed"]["persistence"]["event_count"] = 999

    ok, errors = verify_binance_depth_fault_matrix(tampered)

    assert ok is False
    assert any("persistence event_count mismatch" in error for error in errors)
