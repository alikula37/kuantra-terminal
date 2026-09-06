"""Evaluate one Binance depth attestation for human-review eligibility."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_attestation import (  # noqa: E402
    BinanceDepthAttestationStore,
)
from app.services.market_data.binance_depth_attestation_gate import (  # noqa: E402
    DEFAULT_MAX_AGE_SECONDS,
    evaluate_binance_depth_attestation_gate,
)
from app.services.market_data.binance_depth_key_registry import (  # noqa: E402
    BinanceDepthAttestationKeyRegistry,
)
from app.services.market_data.binance_depth_report_archive import (  # noqa: E402
    BinanceDepthReportArchive,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate one Binance depth attestation for human-review eligibility"
    )
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--attestation-id", default=None)
    parser.add_argument("--max-age-seconds", type=float, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument("--now", default=None, help="ISO-8601 UTC timestamp for deterministic evaluation")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        archive = BinanceDepthReportArchive(args.archive_root)
        attestations = BinanceDepthAttestationStore(archive)
        registry = BinanceDepthAttestationKeyRegistry(args.registry)
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
        result = evaluate_binance_depth_attestation_gate(
            archive,
            attestations,
            registry,
            args.report_id,
            attestation_id=args.attestation_id,
            now=now,
            max_age_seconds=args.max_age_seconds,
        )
        if args.as_json:
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        else:
            print(
                f"[binance-depth-attestation-gate] decision={result.decision} "
                f"report={result.report_id} key_status={result.key_status} "
                f"freshness_valid={result.freshness_valid}"
            )
            for error in result.errors:
                print(f"  error={error}", file=sys.stderr)
        return 0 if result.decision == "ELIGIBLE_FOR_REVIEW" else 1
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"[binance-depth-attestation-gate] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
