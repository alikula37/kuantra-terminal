"""Generate an explicit local Ed25519 key bundle for soak attestations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.market_data.binance_depth_attestation import generate_operator_key_bundle  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a local Ed25519 Kuantra soak attestation key")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        print(f"[binance-depth-key] REFUSED: output exists: {output}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(generate_operator_key_bundle(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[binance-depth-key] generated: {output}")
    print("[binance-depth-key] protect the private_key_b64 value; it is not recoverable from the public key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
