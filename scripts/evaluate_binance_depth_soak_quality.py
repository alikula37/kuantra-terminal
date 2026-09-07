"""Evaluate the explicit quality policy for one Binance soak series."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_soak_quality import (  # noqa: E402
    DepthSoakSeriesQualityPolicy,
    evaluate_binance_depth_soak_series_quality,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Kuantra Binance depth soak quality gate")
    parser.add_argument("series", type=Path)
    parser.add_argument("--minimum-observations", type=int, default=3)
    parser.add_argument("--minimum-elapsed-seconds", type=float, default=300.0)
    parser.add_argument("--minimum-processed-events", type=int, default=100)
    parser.add_argument("--max-gap-event-rate", type=float, default=0.0)
    parser.add_argument("--max-recovery-cycle-rate", type=float, default=0.0)
    parser.add_argument("--max-source-failure-cycle-rate", type=float, default=0.0)
    parser.add_argument("--max-invalid-observation-rate", type=float, default=0.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _load(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read series report: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("series report must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.minimum_elapsed_seconds < 0:
            raise ValueError("minimum-elapsed-seconds must be non-negative")
        policy = DepthSoakSeriesQualityPolicy(
            minimum_observations=args.minimum_observations,
            minimum_elapsed_ms_per_observation=args.minimum_elapsed_seconds * 1000,
            minimum_processed_events_per_observation=args.minimum_processed_events,
            max_gap_event_rate=args.max_gap_event_rate,
            max_recovery_cycle_rate=args.max_recovery_cycle_rate,
            max_source_failure_cycle_rate=args.max_source_failure_cycle_rate,
            max_invalid_observation_rate=args.max_invalid_observation_rate,
        )
        result = evaluate_binance_depth_soak_series_quality(
            _load(args.series),
            policy=policy,
        )
    except (OSError, ValueError) as exc:
        print(f"[binance-depth-soak-quality] REFUSED/FAIL: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"[binance-depth-soak-quality] {result.decision}")
        for error in result.errors:
            print(f"  error: {error}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
    return 0 if result.decision == "ELIGIBLE_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
