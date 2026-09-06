"""Create a signed operator review record for an eligible depth observation."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_attestation import (  # noqa: E402
    BinanceDepthAttestationStore,
    private_key_from_bundle,
)
from app.services.market_data.binance_depth_attestation_gate import (  # noqa: E402
    DEFAULT_MAX_AGE_SECONDS,
    evaluate_binance_depth_attestation_gate,
)
from app.services.market_data.binance_depth_key_policy import (  # noqa: E402
    DEFAULT_MAX_ACTIVE_AGE_SECONDS,
    DEFAULT_REVOKED_RETENTION_SECONDS,
    evaluate_key_rotation_policy,
)
from app.services.market_data.binance_depth_key_registry import (  # noqa: E402
    BinanceDepthAttestationKeyRegistry,
    DepthKeyRegistryError,
    OperatorKeyStatus,
)
from app.services.market_data.binance_depth_report_archive import (  # noqa: E402
    BinanceDepthReportArchive,
)
from app.services.market_data.binance_depth_review_record import (  # noqa: E402
    BinanceDepthOperatorReviewStore,
    DepthReviewRecordError,
    create_operator_review_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a signed operator review record for an eligible Binance depth observation"
    )
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--attestation-id", default=None)
    parser.add_argument("--key-bundle", type=Path, required=True)
    parser.add_argument("--reviewer-label", required=True)
    parser.add_argument("--reviewed-at", default=None)
    parser.add_argument("--retention-until", required=True)
    parser.add_argument("--max-age-seconds", type=float, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument(
        "--max-active-key-age-seconds",
        type=float,
        default=DEFAULT_MAX_ACTIVE_AGE_SECONDS,
    )
    parser.add_argument(
        "--revoked-retention-seconds",
        type=float,
        default=DEFAULT_REVOKED_RETENTION_SECONDS,
    )
    parser.add_argument(
        "--minimum-review-retention-seconds",
        type=float,
        default=DEFAULT_REVOKED_RETENTION_SECONDS,
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reviewed_at = _parse_timestamp(args.reviewed_at) if args.reviewed_at else None
        retention_until = _parse_timestamp(args.retention_until)
        if reviewed_at is not None and retention_until <= reviewed_at:
            raise DepthReviewRecordError("retention_until must be after reviewed_at")
        retention_base = reviewed_at or datetime.now(retention_until.tzinfo)
        retention_seconds = (retention_until - retention_base).total_seconds()
        if retention_seconds < args.minimum_review_retention_seconds:
            raise DepthReviewRecordError("review retention is below the configured minimum")

        archive = BinanceDepthReportArchive(args.archive_root)
        attestations = BinanceDepthAttestationStore(archive)
        registry = BinanceDepthAttestationKeyRegistry(args.registry)
        policy = evaluate_key_rotation_policy(
            registry,
            now=reviewed_at,
            max_active_age_seconds=args.max_active_key_age_seconds,
            revoked_retention_seconds=args.revoked_retention_seconds,
        )
        if not policy.valid:
            raise DepthKeyRegistryError("key policy rejected: " + "; ".join(policy.errors))
        gate = evaluate_binance_depth_attestation_gate(
            archive,
            attestations,
            registry,
            args.report_id,
            attestation_id=args.attestation_id,
            now=reviewed_at,
            max_age_seconds=args.max_age_seconds,
        )
        if gate.decision != "ELIGIBLE_FOR_REVIEW":
            raise DepthReviewRecordError("review gate rejected: " + "; ".join(gate.errors))

        bundle = json.loads(args.key_bundle.read_text(encoding="utf-8"))
        private_key = private_key_from_bundle(bundle)
        public_key_b64 = base64.b64encode(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode("ascii")
        if public_key_b64 != bundle.get("public_key_b64"):
            raise DepthKeyRegistryError("key bundle public key does not match private key")
        key_record = registry.get(public_key_b64)
        if key_record.status != OperatorKeyStatus.ACTIVE:
            raise DepthKeyRegistryError("reviewer key is not active")
        if key_record.operator_label != args.reviewer_label.strip():
            raise DepthKeyRegistryError("reviewer label does not match registered key")

        record = create_operator_review_record(
            gate,
            private_key,
            policy_result=policy,
            reviewer_label=args.reviewer_label,
            reviewed_at=reviewed_at.isoformat().replace("+00:00", "Z") if reviewed_at else None,
            retention_until=retention_until.isoformat().replace("+00:00", "Z"),
        )
        store = BinanceDepthOperatorReviewStore(archive)
        store.append(record)
        result = {
            "policy": policy.as_dict(),
            "gate": gate.as_dict(),
            "review": record.as_dict(),
            "store": store.recovery_report(),
        }
        if args.as_json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(
                f"[binance-depth-review] recorded={record.review_id} "
                f"report={record.report_id} reviewer={record.reviewer_label}"
            )
        return 0
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        DepthKeyRegistryError,
        DepthReviewRecordError,
    ) as exc:
        print(f"[binance-depth-review] FAIL: {exc}", file=sys.stderr)
        return 1


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
