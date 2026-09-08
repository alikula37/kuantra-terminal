"""Fail-closed validator for smoke/local-CI build provenance reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_provenance import ProvenanceError, validate_report


ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate exact Kuantra build provenance")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--release",
        action="store_true",
        help="require a clean checkout and COMPLETE release-facing provenance",
    )
    args = parser.parse_args(argv)
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        validate_report(report, release_facing=args.release)
    except (OSError, json.JSONDecodeError, ProvenanceError) as exc:
        print(f"[provenance] FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"[provenance] PASS: {report_path} ({'release' if args.release else 'local'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

