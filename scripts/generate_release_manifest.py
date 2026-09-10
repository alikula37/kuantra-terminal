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
import re
import sys
import time
from typing import Any, Dict, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from app.version import __version__  # noqa: E402
from release_truth import DEFAULT_MATRIX_PATH, canonical_matrix_digest, load_matrix  # noqa: E402
from run_n05_macos_distribution_preflight import N05DistributionError, validate_n05_report  # noqa: E402

PRODUCT_NAME = "Kuantra Terminal"
ARTIFACT_PREFIX = "Kuantra-Terminal-"
MACOS_ARCH_RE = re.compile(r"(?:^|[-_])(arm64|aarch64|x86_64)(?:[-_.]|$)", re.IGNORECASE)


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hex digest for a file using streaming 64KB chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def truth_matrix_metadata() -> Dict[str, str]:
    """Return immutable truth-contract identity for the shipped manifest."""
    matrix = load_matrix(DEFAULT_MATRIX_PATH)
    product = matrix.get("product", {})
    if product.get("version") != __version__:
        raise ValueError("truth matrix product version does not match app version")
    return {
        "document_id": str(matrix["document_id"]),
        "version": str(matrix["version"]),
        "sha256": canonical_matrix_digest(matrix),
    }


def classify_artifact(filename: str) -> tuple[str, str]:
    """Infers (platform, arch) from a packaged artifact filename."""
    lower_name = filename.lower()
    if lower_name.endswith((".exe", ".msi")) or "windows" in lower_name:
        return "Windows", "x64"
    if lower_name.endswith(".dmg") or "darwin" in lower_name or "macos" in lower_name:
        match = MACOS_ARCH_RE.search(lower_name)
        if not match:
            return "macOS", "unknown"
        arch = "arm64" if match.group(1).casefold() in {"arm64", "aarch64"} else "x86_64"
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


def distribution_attestation(
    report_path: str,
    *,
    dist_dir: str,
    artifacts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Bind the checked-in N05 report to the macOS artifact in MANIFEST.json."""

    try:
        with open(report_path, "r", encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid macOS N05 report: {report_path}") from exc
    report_artifact_sha = str(report.get("artifacts", {}).get("dmg_sha256") or "")
    macos = next(
        (
            artifact
            for artifact in artifacts
            if artifact["platform"] == "macOS" and artifact["sha256"] == report_artifact_sha
        ),
        None,
    )
    if macos is None:
        raise ValueError("macOS N05 report does not match a macOS artifact")
    try:
        validate_n05_report(report, artifact_sha256=macos["sha256"])
    except N05DistributionError as exc:
        raise ValueError(f"macOS N05 report is not release-ready: {exc}") from exc
    report_filename = os.path.relpath(report_path, dist_dir)
    return {
        "report_filename": report_filename,
        "report_sha256": compute_sha256(report_path),
        "artifact_filename": macos["filename"],
        "artifact_sha256": report_artifact_sha,
        "architecture": macos["arch"],
        "source_commit_sha": report["source"]["commit_sha"],
        "status": report["status"],
    }


def generate_manifest(dist_dir: str = "dist", tag: str | None = None,
                      dry_run: bool = False,
                      macos_distribution_reports: List[str] | None = None,
                      macos_distribution_report: str | None = None) -> Dict[str, Any]:
    """Builds the manifest for ``dist_dir`` and writes ``MANIFEST.json`` into it."""
    if not os.path.isabs(dist_dir):
        dist_dir = os.path.join(ROOT_DIR, dist_dir)

    release_tag = tag or f"v{__version__}"
    truth_metadata = truth_matrix_metadata()
    expected_tag = f"v{__version__}"
    if release_tag != expected_tag:
        raise ValueError(f"release tag {release_tag!r} does not match {expected_tag!r}")
    artifacts: List[Dict[str, Any]] = [] if dry_run else collect_artifacts(dist_dir)
    invalid_macos = [
        artifact["filename"]
        for artifact in artifacts
        if artifact["platform"] == "macOS" and artifact["arch"] not in {"arm64", "x86_64"}
    ]
    if invalid_macos:
        raise ValueError(f"macOS artifact architecture is missing or unsupported: {invalid_macos}")

    attestations: Dict[str, Any] = {}
    report_paths = list(macos_distribution_reports or [])
    if macos_distribution_report is not None:
        report_paths.append(macos_distribution_report)
    for report_path in report_paths:
        if not os.path.isabs(report_path):
            report_path = os.path.join(ROOT_DIR, report_path)
        attestation = distribution_attestation(
            report_path,
            dist_dir=dist_dir,
            artifacts=artifacts,
        )
        attestations[f"macOS-{attestation['architecture']}"] = attestation

    manifest_data: Dict[str, Any] = {
        "release_tag": release_tag,
        "product_name": PRODUCT_NAME,
        "version": __version__,
        "truth_matrix": truth_metadata,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_artifacts": len(artifacts),
        "artifacts": artifacts,
        "distribution_attestations": attestations,
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
    parser.add_argument(
        "--macos-distribution-report",
        action="append",
        dest="macos_distribution_reports",
        default=[],
        help="Require and bind a PASS N05 macOS distribution report (repeat per architecture)",
    )
    args = parser.parse_args(argv)

    generate_manifest(
        dist_dir=args.dist,
        tag=args.tag,
        dry_run=args.dry_run,
        macos_distribution_reports=args.macos_distribution_reports,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
