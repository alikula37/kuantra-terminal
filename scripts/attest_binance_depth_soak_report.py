"""Create and append an operator attestation for an archived soak report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_attestation import (  # noqa: E402
    BinanceDepthAttestationStore,
    DepthSoakAttestationError,
    attest_archive_record,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attest an archived Kuantra Binance depth soak report")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--key-bundle", type=Path, required=True)
    parser.add_argument("--operator-label", required=True)
    parser.add_argument("--attested-at", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        key_payload = json.loads(args.key_bundle.read_text(encoding="utf-8"))
        private_key = private_key_from_bundle(key_payload)
        archive = BinanceDepthReportArchive(args.archive_root)
        record = archive.get_record(args.report_id)
        attestation = attest_archive_record(
            record,
            private_key,
            operator_label=args.operator_label,
            attested_at=args.attested_at,
        )
        stored = BinanceDepthAttestationStore(archive).append(attestation)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthSoakAttestationError) as exc:
        print(f"[binance-depth-attestation] FAIL: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(stored.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            f"[binance-depth-attestation] PASS: attestation_id={stored.attestation_id} "
            f"report_id={stored.report_id} operator={stored.operator_label}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
