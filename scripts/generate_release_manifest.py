"""
Release manifest & SHA-256 checksum generator for Kuantra Terminal.

Scans a distribution directory for packaged artifacts (``Kuantra-Terminal-*``),
computes their sizes and SHA-256 digests, and writes ``MANIFEST.json`` next to them.
The product version is taken from ``backend/app/version.py`` (single source of truth).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from app.version import __version__  # noqa: E402

PRODUCT_NAME = "Kuantra Terminal"
ARTIFACT_PREFIX = "Kuantra-Terminal-"


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hex digest for a file using streaming 64KB chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def classify_artifact(filename: str) -> tuple[str, str]:
    """Infers (platform, arch) from a packaged artifact filename."""
    lower_name = filename.lower()
    if lower_name.endswith((".exe", ".msi")) or "windows" in lower_name:
        return "Windows", "x64"
    if lower_name.endswith(".dmg") or "darwin" in lower_name or "macos" in lower_name:
        arch = "arm64" if ("aarch64" in lower_name or "arm64" in lower_name) else "x64"
        return "macOS", arch
    if lower_name.endswith((".appimage", ".deb", ".rpm", ".tar.gz")) or "linux" in lower_name:
        return "Linux", "x64"
    return "Multiplatform", "Universal"


def collect_artifacts(dist_dir: str) -> List[Dict[str, Any]]:
    """Collects manifest entries for every ``Kuantra-Terminal-*`` file in ``dist_dir``."""
    if not os.path.isdir(dist_dir):
        return []

    artifacts: List[Dict[str, Any]] = []
    for filename in sorted(os.listdir(dist_dir)):
        if not filename.startswith(ARTIFACT_PREFIX):
            continue
        filepath = os.path.join(dist_dir, filename)
        if not os.path.isfile(filepath):
            continue

        platform, arch = classify_artifact(filename)
        artifacts.append({
            "filename": filename,
            "platform": platform,
            "arch": arch,
            "size_bytes": os.path.getsize(filepath),
            "sha256": compute_sha256(filepath),
        })
    return artifacts


def generate_manifest(dist_dir: str = "dist", tag: str | None = None,
                      dry_run: bool = False) -> Dict[str, Any]:
    """Builds the manifest for ``dist_dir`` and writes ``MANIFEST.json`` into it."""
    if not os.path.isabs(dist_dir):
        dist_dir = os.path.join(ROOT_DIR, dist_dir)

    release_tag = tag or f"v{__version__}"
    artifacts: List[Dict[str, Any]] = [] if dry_run else collect_artifacts(dist_dir)

    manifest_data: Dict[str, Any] = {
        "release_tag": release_tag,
        "product_name": PRODUCT_NAME,
        "version": __version__,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_artifacts": len(artifacts),
        "artifacts": artifacts,
    }

    os.makedirs(dist_dir, exist_ok=True)
    manifest_path = os.path.join(dist_dir, "MANIFEST.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print("=" * 98)
    print(f"  {PRODUCT_NAME} {release_tag} RELEASE MANIFEST")
    print("=" * 98)
    print(f"Dist dir: {dist_dir} | Generated: {manifest_data['generated_at']}")
    print("-" * 98)
    if artifacts:
        print(f"{'Platform':<14} | {'Arch':<9} | {'Size (Bytes)':<13} | {'Filename':<44} | SHA-256")
        print("-" * 145)
        for a in artifacts:
            print(f"{a['platform']:<14} | {a['arch']:<9} | {a['size_bytes']:<13} | "
                  f"{a['filename']:<44} | {a['sha256']}")
    else:
        print("(no artifacts found)" if not dry_run else "(dry run: no artifacts recorded)")
    print("=" * 98)
    print(f"[+] Successfully exported release manifest to: {manifest_path}")

    return manifest_data


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Kuantra Terminal release manifest and SHA-256 checksums"
    )
    parser.add_argument("--dist", default="dist",
                        help="Directory containing the packaged artifacts (default: dist)")
    parser.add_argument("--tag", default=None,
                        help="Release tag to record (default: v<version>)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Write a manifest with zero artifacts without scanning the dist dir")
    args = parser.parse_args(argv)

    generate_manifest(dist_dir=args.dist, tag=args.tag, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
