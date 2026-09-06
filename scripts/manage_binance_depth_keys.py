"""Register, revoke and audit local Binance depth attestation keys."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_attestation import (  # noqa: E402
    BinanceDepthAttestationStore,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_key_registry import (  # noqa: E402
    BinanceDepthAttestationKeyRegistry,
    DepthKeyRegistryError,
)
from app.services.market_data.binance_depth_report_archive import BinanceDepthReportArchive  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Kuantra Binance depth attestation keys")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register = subparsers.add_parser("register")
    register.add_argument("--registry", type=Path, required=True)
    register.add_argument("--key-bundle", type=Path, required=True)
    register.add_argument("--operator-label", required=True)
    register.add_argument("--recorded-at", default=None)

    revoke = subparsers.add_parser("revoke")
    revoke.add_argument("--registry", type=Path, required=True)
    revoke.add_argument("--key-id", required=True)
    revoke.add_argument("--reason", required=True)
    revoke.add_argument("--revoked-at", default=None)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--registry", type=Path, required=True)
    audit.add_argument("--archive-root", type=Path, required=True)
    audit.add_argument("--require-registered", action="store_true")
    audit.add_argument("--fail-on-revoked", action="store_true")
    audit.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        registry = BinanceDepthAttestationKeyRegistry(args.registry)
        if args.command == "register":
            bundle = json.loads(args.key_bundle.read_text(encoding="utf-8"))
            private_key = private_key_from_bundle(bundle)
            public_key_b64 = bundle["public_key_b64"]
            derived_public_key_b64 = base64.b64encode(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                )
            ).decode("ascii")
            if derived_public_key_b64 != public_key_b64:
                raise DepthKeyRegistryError("key bundle public key does not match private key")
            record = registry.register(
                public_key_b64,
                operator_label=args.operator_label,
                recorded_at=args.recorded_at,
            )
            print(json.dumps(record.as_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "revoke":
            record = registry.revoke(args.key_id, reason=args.reason, revoked_at=args.revoked_at)
            print(json.dumps(record.as_dict(), indent=2, sort_keys=True))
            return 0

        archive = BinanceDepthReportArchive(args.archive_root)
        store = BinanceDepthAttestationStore(archive)
        audits = []
        for attestation in store.attestations:
            report_record = archive.get_record(attestation.report_sha256)
            audits.append(registry.audit(report_record, attestation).as_dict())
        result = {
            "registry": registry.recovery_report(),
            "archive": archive.recovery_report(),
            "attestations": store.recovery_report(),
            "audits": audits,
        }
        if args.as_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"[binance-depth-keys] audited={len(audits)}")
            for audit_result in audits:
                print(
                    f"  report-key={audit_result['key_id']} "
                    f"status={audit_result['status']} signature_valid={audit_result['signature_valid']}"
                )
        bad_signature = any(not item["signature_valid"] for item in audits)
        unregistered = any(item["status"] == "UNREGISTERED_KEY" for item in audits)
        revoked = any(item["status"] == "REVOKED_KEY" for item in audits)
        return 1 if bad_signature or (args.require_registered and unregistered) or (args.fail_on_revoked and revoked) else 0
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, DepthKeyRegistryError) as exc:
        print(f"[binance-depth-keys] FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
