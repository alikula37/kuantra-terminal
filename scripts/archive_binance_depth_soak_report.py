"""Archive one verified Binance depth soak report locally and append-only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_report_archive import (  # noqa: E402
    BinanceDepthReportArchive,
    DepthSoakArchiveError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive a verified Kuantra Binance depth soak report")
    parser.add_argument("report", type=Path)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _load(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DepthSoakArchiveError(f"cannot read report: {exc}") from exc
    if not isinstance(payload, dict):
        raise DepthSoakArchiveError("report must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        archive = BinanceDepthReportArchive(args.archive_root)
        record = archive.archive(_load(args.report))
    except (OSError, ValueError, DepthSoakArchiveError) as exc:
        print(f"[binance-depth-archive] FAIL: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(record.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"[binance-depth-archive] PASS: report_id={record.report_id} "
            f"sha256={record.report_sha256} path={record.report_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
