"""Run the bounded, offline Binance depth fault-injection matrix.

This command is intentionally network-free.  It exercises the production
ingestor/session/segment boundaries with explicit fixtures and exits non-zero
if any expected fail-closed decision or durability invariant changes.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_fault_matrix import (  # noqa: E402
    run_binance_depth_fault_matrix,
    verify_binance_depth_fault_matrix,
)


DEFAULT_STORAGE_ROOT = Path(tempfile.gettempdir()) / "kuantra-depth-fault-matrix"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Kuantra's offline Binance depth fault matrix")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _write_or_print(report: dict, output: Path | None) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if output is None:
        print(encoded)
        return
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(f"[binance-depth-fault-matrix] report={output}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        normalized_symbol = str(args.symbol).strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must be non-empty")
        run_root = args.storage_root.resolve() / f"run-{time.time_ns()}"
        report = run_binance_depth_fault_matrix(
            storage_root=run_root,
            symbol=normalized_symbol,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[binance-depth-fault-matrix] REFUSED/FAIL: {exc}", file=sys.stderr)
        return 2
    _write_or_print(report, args.output)
    ok, errors = verify_binance_depth_fault_matrix(report)
    if not ok:
        print(
            "[binance-depth-fault-matrix] INVALID: " + "; ".join(errors),
            file=sys.stderr,
        )
        return 1
    print(
        f"[binance-depth-fault-matrix] VALID_OFFLINE_FAULT_MATRIX cases={report['case_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
