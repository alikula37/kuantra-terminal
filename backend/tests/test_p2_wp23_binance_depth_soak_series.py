"""P2-WP23 repeated soak observation series contracts."""

from copy import deepcopy

import pytest

from app.services.market_data.binance_depth_report import REPORT_SCHEMA_VERSION
from app.services.market_data.binance_depth_soak_series import (
    INVALID_SERIES_VERDICT,
    SOAK_SERIES_SCHEMA_VERSION,
    VALID_SERIES_VERDICT,
    build_binance_depth_soak_series,
    verify_binance_depth_soak_series,
)


def _valid_testnet_report(
    *,
    started_at: str,
    events: int = 10,
    gaps: int = 0,
    recovery_cycles: int = 0,
    reconnects: int = 0,
) -> dict:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "testnet",
        "environment": "testnet",
        "symbol": "BTCUSDT",
        "started_at": started_at,
        "elapsed_ms": 1_000.0,
        "run_root": "C:/test-only/soak",
        "session": {
            "decision": "STOPPED",
            "reason_code": "STOP_EVENT_SET",
            "attempts": max(1, reconnects + 1),
            "reconnects": reconnects,
            "processed_event_count": events,
            "source_verified": False,
            "cycles": [
                {
                    "decision": "STOPPED",
                    "reason_code": "STOP_EVENT_SET",
                    "events_processed": events,
                    "gap_events": gaps,
                    "source_verified": False,
                }
            ],
            "continuity": {
                "cycle_count": 1,
                "reconnect_count": reconnects,
                "processed_event_count": events,
                "gap_event_count": gaps,
                "completed_cycle_count": 0,
                "stopped_cycle_count": 1,
                "source_failure_cycle_count": 0,
                "snapshot_retry_cycle_count": 0,
                "snapshot_rejected_cycle_count": 0,
                "recovery_required_cycle_count": recovery_cycles,
                "persistence_failure_cycle_count": 0,
            },
        },
        "chain": {
            "valid": True,
            "event_count": events + 1,
            "head_hash": "0" * 64,
            "errors": [],
        },
        "persistence": {
            "valid": True,
            "event_count": events + 1,
            "errors": [],
        },
        "source_verified": False,
        "execution_authority": False,
    }


def test_series_aggregates_only_valid_testnet_observations():
    reports = [
        _valid_testnet_report(started_at=f"2026-09-07T10:0{index}:00Z", events=10 + index, gaps=index)
        for index in range(3)
    ]

    series = build_binance_depth_soak_series(
        reports,
        source_labels=["one", "two", "three"],
        minimum_observations=3,
    )

    assert series["schema_version"] == SOAK_SERIES_SCHEMA_VERSION
    assert series["valid_observation_count"] == 3
    assert series["invalid_observation_count"] == 0
    assert series["series_verdict"] == VALID_SERIES_VERDICT
    assert series["overall_ok"] is True
    assert series["aggregate"]["total_processed_event_count"] == 33
    assert series["aggregate"]["total_gap_event_count"] == 3
    assert series["aggregate"]["gap_event_rate"] == pytest.approx(3 / 33, abs=1e-12)
    assert verify_binance_depth_soak_series(series) == (True, ())


def test_invalid_observation_remains_visible_and_blocks_series():
    valid = _valid_testnet_report(started_at="2026-09-07T10:00:00Z")
    invalid = deepcopy(valid)
    invalid["session"]["cycles"][0]["decision"] = "RECOVERY_REQUIRED"

    series = build_binance_depth_soak_series(
        [valid, invalid],
        minimum_observations=1,
    )

    assert series["valid_observation_count"] == 1
    assert series["invalid_observation_count"] == 1
    assert series["observations"][1]["included"] is False
    assert series["series_verdict"] == INVALID_SERIES_VERDICT
    assert series["overall_ok"] is False
    assert verify_binance_depth_soak_series(series) == (True, ())


def test_series_verifier_rejects_tampered_aggregate():
    reports = [_valid_testnet_report(started_at="2026-09-07T10:00:00Z")]
    series = build_binance_depth_soak_series(reports, minimum_observations=1)
    series["aggregate"]["total_gap_event_count"] = 99

    ok, errors = verify_binance_depth_soak_series(series)

    assert ok is False
    assert "aggregate.total_gap_event_count mismatch" in errors
