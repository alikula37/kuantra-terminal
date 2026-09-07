"""Create, verify and restore deterministic Binance depth evidence bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_evidence_bundle import (  # noqa: E402
    DepthEvidenceBundleError,
    create_evidence_bundle,
    restore_evidence_bundle,
    verify_evidence_bundle,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage deterministic Binance depth evidence bundles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--archive-root", type=Path, required=True)
    create.add_argument("--registry", type=Path, default=None)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--created-at", default=None)
    create.add_argument("--json", action="store_true", dest="as_json")

    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--json", action="store_true", dest="as_json")

    restore = subparsers.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--target-root", type=Path, required=True)
    restore.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_evidence_bundle(
                args.archive_root,
                args.output,
                registry_path=args.registry,
                created_at=args.created_at,
            )
            result = manifest.as_dict()
            if args.as_json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(
                    f"[binance-depth-bundle] created={args.output} "
                    f"bundle_id={manifest.bundle_id} files={manifest.file_count}"
                )
            return 0
        if args.command == "verify":
            result = verify_evidence_bundle(args.bundle)
            if args.as_json:
                print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
            else:
                print(
                    f"[binance-depth-bundle] valid={result.valid} "
                    f"bundle_id={result.bundle_id} files={result.file_count}"
                )
                for error in result.errors:
                    print(f"  error={error}", file=sys.stderr)
            return 0 if result.valid else 1

        result = restore_evidence_bundle(args.bundle, args.target_root)
        if args.as_json:
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
        else:
            print(
                f"[binance-depth-bundle] restored={args.target_root} "
                f"bundle_id={result.bundle_id} files={result.file_count}"
            )
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthEvidenceBundleError) as exc:
        print(f"[binance-depth-bundle] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
