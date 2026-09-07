"""Aggregate persisted Binance testnet soak reports fail-closed.

The command never runs a network probe.  It verifies each input with the
single-report gate, writes invalid observations into the series, and returns
non-zero unless the requested minimum number of observations are all valid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_soak_series import (  # noqa: E402
    build_binance_depth_soak_series,
    verify_binance_depth_soak_series,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate Kuantra Binance depth testnet soak reports")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--minimum-observations", type=int, default=3)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read report {path}: {exc}") from exc


def _write_or_print(report: dict[str, Any], output: Path | None) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if output is None:
        print(encoded)
        return
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(f"[binance-depth-soak-series] report={output}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.minimum_observations <= 0 or args.minimum_observations > 1000:
            raise ValueError("minimum-observations must be between 1 and 1000")
        paths = [path.resolve() for path in args.reports]
        reports = [_load(path) for path in paths]
        report = build_binance_depth_soak_series(
            reports,
            source_labels=[str(path) for path in paths],
            expected_symbol=args.symbol,
            minimum_observations=args.minimum_observations,
        )
    except (OSError, ValueError) as exc:
        print(f"[binance-depth-soak-series] REFUSED/FAIL: {exc}", file=sys.stderr)
        return 2
    _write_or_print(report, args.output)
    ok, errors = verify_binance_depth_soak_series(report)
    if not ok:
        print(
            "[binance-depth-soak-series] INVALID: " + "; ".join(errors),
            file=sys.stderr,
        )
        return 1
    if not report["overall_ok"]:
        print(
            "[binance-depth-soak-series] INVALID_SERIES: "
            + "; ".join(report["series_errors"]),
            file=sys.stderr,
        )
        return 1
    print(
        "[binance-depth-soak-series] VALID_TESTNET_SERIES_UNVERIFIED "
        f"observations={report['valid_observation_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
