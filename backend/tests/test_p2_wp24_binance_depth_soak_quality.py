"""P2-WP24 soak-series quality/promotion gate contracts."""

from app.services.market_data.binance_depth_report import REPORT_SCHEMA_VERSION
from app.services.market_data.binance_depth_soak_quality import (
    SERIES_QUALITY_GATE_SCHEMA_VERSION,
    DepthSoakSeriesQualityPolicy,
    evaluate_binance_depth_soak_series_quality,
)
from app.services.market_data.binance_depth_soak_series import (
    build_binance_depth_soak_series,
)


def _report(
    index: int,
    *,
    events: int = 120,
    elapsed_ms: float = 300_000.0,
    gaps: int = 0,
    recovery: bool = False,
    source_failure: bool = False,
) -> dict:
    cycles = []
    if recovery or source_failure:
        cycles.append(
            {
                "decision": "RECOVERY_REQUIRED" if recovery else "SOURCE_FAILED",
                "reason_code": "fixture fault",
                "events_processed": events,
                "gap_events": gaps,
                "source_verified": False,
            }
        )
        cycles.append(
            {
                "decision": "STOPPED",
                "reason_code": "STOP_EVENT_SET",
                "events_processed": events,
                "gap_events": 0,
                "source_verified": False,
            }
        )
    else:
        cycles.append(
            {
                "decision": "STOPPED",
                "reason_code": "STOP_EVENT_SET",
                "events_processed": events,
                "gap_events": gaps,
                "source_verified": False,
            }
        )
    processed = sum(cycle["events_processed"] for cycle in cycles)
    cycle_count = len(cycles)
    reconnects = 1 if cycle_count == 2 else 0
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": "testnet",
        "environment": "testnet",
        "symbol": "BTCUSDT",
        "started_at": f"2026-09-07T10:0{index}:00Z",
        "elapsed_ms": elapsed_ms,
        "run_root": f"C:/test-only/soak-{index}",
        "session": {
            "decision": "STOPPED",
            "reason_code": "STOP_EVENT_SET",
            "attempts": cycle_count,
            "reconnects": reconnects,
            "processed_event_count": processed,
            "source_verified": False,
            "cycles": cycles,
            "continuity": {
                "cycle_count": cycle_count,
                "reconnect_count": reconnects,
                "processed_event_count": processed,
                "gap_event_count": gaps,
                "completed_cycle_count": 0,
                "stopped_cycle_count": 1,
                "source_failure_cycle_count": 1 if source_failure else 0,
                "snapshot_retry_cycle_count": 0,
                "snapshot_rejected_cycle_count": 0,
                "recovery_required_cycle_count": 1 if recovery else 0,
                "persistence_failure_cycle_count": 0,
            },
        },
        "chain": {
            "valid": True,
            "event_count": processed + 1,
            "head_hash": "0" * 64,
            "errors": [],
        },
        "persistence": {
            "valid": True,
            "event_count": processed + 1,
            "errors": [],
        },
        "source_verified": False,
        "execution_authority": False,
    }


def _series(*reports: dict, minimum: int = 3) -> dict:
    return build_binance_depth_soak_series(reports, minimum_observations=minimum)


def test_quality_gate_accepts_only_policy_compliant_series():
    series = _series(*(_report(index) for index in range(3)))

    result = evaluate_binance_depth_soak_series_quality(series)

    assert result.schema_version == SERIES_QUALITY_GATE_SCHEMA_VERSION
    assert result.decision == "ELIGIBLE_FOR_REVIEW"
    assert result.errors == ()
    assert result.source_verified is False
    assert result.execution_authority is False


def test_quality_gate_rejects_short_series_and_short_observation():
    series = _series(_report(0, events=10, elapsed_ms=1_000), minimum=1)

    result = evaluate_binance_depth_soak_series_quality(series)

    assert result.decision == "REJECTED"
    assert any("policy minimum 3" in error for error in result.errors)
    assert any("elapsed_ms" in error for error in result.errors)
    assert any("processed events" in error for error in result.errors)


def test_quality_gate_rejects_gap_recovery_and_source_failure_rates():
    series = _series(
        _report(0),
        _report(1, gaps=1),
        _report(2, recovery=True),
        _report(3, source_failure=True),
    )

    result = evaluate_binance_depth_soak_series_quality(series)

    assert result.decision == "REJECTED"
    assert any("gap_event_rate" in error for error in result.errors)
    assert any("recovery_cycle_rate" in error for error in result.errors)
    assert any("source_failure_cycle_rate" in error for error in result.errors)


def test_quality_policy_rejects_invalid_thresholds():
    try:
        DepthSoakSeriesQualityPolicy(max_gap_event_rate=1.1)
    except ValueError as exc:
        assert "between 0 and 1" in str(exc)
    else:
        raise AssertionError("invalid rate must be rejected")
