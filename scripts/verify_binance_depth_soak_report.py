"""Verify one Binance depth soak report without changing it or promoting truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_report import verify_depth_soak_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Kuantra Binance depth soak report")
    parser.add_argument("report", type=Path)
    parser.add_argument("--mode", choices=("fixture", "testnet"), default=None)
    parser.add_argument("--minimum-elapsed-ms", type=float, default=0.0)
    parser.add_argument("--allow-missing-durable", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read report: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verification = verify_depth_soak_report(
            _load(args.report),
            expected_mode=args.mode,
            minimum_elapsed_ms=args.minimum_elapsed_ms,
            require_durable=not args.allow_missing_durable,
        )
    except (OSError, ValueError) as exc:
        print(f"[binance-depth-report] FAIL: {exc}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(verification.as_dict(), indent=2, sort_keys=True))
    else:
        label = "PASS" if verification.ok else "FAIL"
        print(f"[binance-depth-report] {label}: {verification.verdict.value}")
        for error in verification.errors:
            print(f"  error: {error}")
        for warning in verification.warnings:
            print(f"  warning: {warning}")
    return 0 if verification.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
