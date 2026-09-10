"""Prepare a fail-closed, hash-verified macOS pilot package.

The package is deliberately smaller than a production release.  It accepts only
the exact native arm64 and x86_64 DMGs together with their final mounted-DMG
smoke and N05 reports.  An ad-hoc N05 result is allowed for the trusted pilot
path, but it is recorded as non-production and never promoted to a release claim.

This command does not build, sign, notarize, publish, tag, access Keychain, or
read application data.  It only validates and copies already-produced evidence
into a new output directory, then writes a standalone manifest and checksum file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BACKEND = ROOT / "backend"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.version import __version__  # noqa: E402
from build_provenance import ProvenanceError, validate_report  # noqa: E402
from release_truth import DEFAULT_MATRIX_PATH, canonical_matrix_digest, load_matrix  # noqa: E402
from run_n05_macos_distribution_preflight import (  # noqa: E402
    N05DistributionError,
    validate_n05_report,
)


ARCHITECTURES = ("arm64", "x86_64")
SMOKE_REPORT_NAMES = {arch: f"final-smoke-{arch}.json" for arch in ARCHITECTURES}
N05_REPORT_NAMES = {arch: f"n05-macos-distribution-{arch}.json" for arch in ARCHITECTURES}
MANIFEST_NAME = "PILOT-MANIFEST.json"
CHECKSUMS_NAME = "SHA256SUMS"
INSTRUCTIONS_NAME = "PILOT-INSTRUCTIONS.md"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class PilotPackageError(ValueError):
    """Raised for malformed or mismatched pilot evidence."""


class MissingPilotEvidence(PilotPackageError):
    """Raised when an external build/host result is not available yet."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PilotPackageError(message)


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise PilotPackageError(f"missing or symlinked pilot input: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PilotPackageError(f"could not hash pilot input: {path}") from exc
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotPackageError(f"{label} is missing or invalid: {path}") from exc
    if not isinstance(value, dict):
        raise PilotPackageError(f"{label} must be a JSON object: {path}")
    return value


def _source_identity(report: Mapping[str, Any], *, architecture: str, dmg: Path) -> dict[str, Any]:
    """Validate one final mounted-DMG smoke report against its exact DMG."""

    try:
        provenance = validate_report(report, release_facing=True)
    except ProvenanceError as exc:
        raise PilotPackageError(f"{architecture} smoke provenance is incomplete: {exc}") from exc

    expected_digest = canonical_matrix_digest(load_matrix(DEFAULT_MATRIX_PATH))
    _require(report.get("platform") == "darwin", f"{architecture} smoke is not a macOS report")
    _require(report.get("version") == __version__, f"{architecture} smoke version is not {__version__}")
    _require(report.get("version_expected") == __version__, f"{architecture} smoke expected version mismatch")
    _require(report.get("ok") is True, f"{architecture} final desktop smoke is not PASS")
    _require(report.get("architecture") == architecture, f"{architecture} smoke architecture mismatch")
    _require(report.get("architecture_verified") is True, f"{architecture} smoke architecture is not verified")
    _require(report.get("renderer_actual") == "wkwebview", f"{architecture} smoke did not use WKWebView")
    _require(report.get("renderer_controller_ready") is True, f"{architecture} WKWebView controller is not ready")
    _require(provenance.get("os") == "darwin", f"{architecture} provenance is not macOS")
    _require(provenance.get("architecture") == architecture, f"{architecture} provenance architecture mismatch")
    _require(provenance.get("build_host_architecture") == architecture,
             f"{architecture} provenance was not collected on the matching host process")
    _require(provenance.get("build_host_translation") == "native",
             f"{architecture} provenance does not prove a native, non-Rosetta host")

    truth = report.get("truth_matrix")
    _require(isinstance(truth, Mapping), f"{architecture} truth-matrix identity is missing")
    _require(truth.get("document_id") == "KTR-001", f"{architecture} truth-matrix document mismatch")
    _require(truth.get("version") == "1.0.0", f"{architecture} truth-matrix version mismatch")
    _require(truth.get("product_version") == __version__, f"{architecture} truth-matrix product mismatch")
    _require(truth.get("sha256") == expected_digest, f"{architecture} truth-matrix digest mismatch")

    dmg_sha256 = _sha256_file(dmg)
    _require(report.get("artifact_sha256") == dmg_sha256,
             f"{architecture} smoke artifact SHA does not match the exact DMG")
    _require(provenance.get("artifact_sha256") == dmg_sha256,
             f"{architecture} provenance artifact SHA does not match the exact DMG")

    mounted = report.get("macos_dmg_smoke")
    _require(isinstance(mounted, Mapping), f"{architecture} mounted-DMG smoke evidence is missing")
    for key, expected in (
        ("status", "PASS"),
        ("mount_mode", "readonly"),
        ("renderer", "wkwebview"),
        ("architecture", architecture),
        ("artifact_sha256", dmg_sha256),
    ):
        _require(mounted.get(key) == expected, f"{architecture} mounted-DMG smoke {key} is not {expected!r}")
    _require(mounted.get("executable_from_mount") is True,
             f"{architecture} smoke did not execute the app selected from the DMG mount")
    _require(mounted.get("mount_detached") is True,
             f"{architecture} DMG mount detach was not confirmed")
    _require(SHA256_RE.fullmatch(str(mounted.get("executable_sha256") or "")) is not None,
             f"{architecture} mounted executable SHA is missing")
    _require(mounted.get("executable_sha256") == report.get("executable_sha256"),
             f"{architecture} mounted executable SHA does not match final smoke")

    source_commit = str(provenance.get("source_commit_sha") or "").lower()
    _require(COMMIT_RE.fullmatch(source_commit) is not None, f"{architecture} source commit is invalid")
    return {
        "architecture": architecture,
        "source_commit_sha": source_commit,
        "tracked_source_tree_sha256": provenance.get("tracked_source_tree_sha256"),
        "lock_hashes": dict(provenance.get("lock_hashes") or {}),
        "toolchain": dict(provenance.get("toolchain") or {}),
        "os_version": provenance.get("os_version"),
        "build_host_architecture": provenance.get("build_host_architecture"),
        "build_host_translation": provenance.get("build_host_translation"),
        "executable_sha256": report.get("executable_sha256"),
        "artifact_sha256": dmg_sha256,
        "truth_matrix_sha256": truth.get("sha256"),
    }


def _validate_blocked_n05(
    report: Mapping[str, Any],
    *,
    architecture: str,
    dmg_sha256: str,
    executable_sha256: str,
    source_commit_sha: str,
) -> str:
    """Validate an N05 report for either a trusted ad-hoc pilot or PASS artifact."""

    status = report.get("status")
    _require(status in {"BLOCKED", "PASS"}, f"{architecture} N05 status is unsupported: {status!r}")
    if status == "PASS":
        try:
            validate_n05_report(
                report,
                artifact_sha256=dmg_sha256,
                source_commit_sha=source_commit_sha,
            )
        except N05DistributionError as exc:
            raise PilotPackageError(f"{architecture} N05 PASS report is invalid: {exc}") from exc
        platform_info = report.get("platform")
        _require(isinstance(platform_info, Mapping) and platform_info.get("architecture") == architecture,
                 f"{architecture} N05 platform architecture mismatch")
        artifacts_info = report.get("artifacts")
        _require(isinstance(artifacts_info, Mapping) and artifacts_info.get("executable_sha256") == executable_sha256,
                 f"{architecture} N05 executable SHA does not match final smoke")
        return "N05_PASS"

    _require(report.get("acceptance_status") == "OWNER_REVIEW_REQUIRED",
             f"{architecture} blocked N05 report has an unexpected acceptance status")
    platform_info = report.get("platform")
    source = report.get("source")
    artifacts = report.get("artifacts")
    signing = report.get("signing")
    notarization = report.get("notarization")
    mount = report.get("mount")
    commands = report.get("commands")
    claims = report.get("claims")
    contract = report.get("contract")
    for value, label in (
        (platform_info, "platform"),
        (source, "source"),
        (artifacts, "artifacts"),
        (signing, "signing"),
        (notarization, "notarization"),
        (mount, "mount"),
        (commands, "commands"),
        (claims, "claims"),
        (contract, "contract"),
    ):
        _require(isinstance(value, Mapping), f"{architecture} blocked N05 {label} evidence is missing")

    _require(platform_info.get("os") == "darwin", f"{architecture} blocked N05 is not macOS evidence")
    _require(platform_info.get("architecture") == architecture, f"{architecture} blocked N05 architecture mismatch")
    _require(source.get("commit_sha") == source_commit_sha, f"{architecture} blocked N05 source commit mismatch")
    _require(source.get("tracked_tree_status") == "clean", f"{architecture} blocked N05 source tree is not clean")
    _require(source.get("provenance_status") == "COMPLETE", f"{architecture} blocked N05 provenance is incomplete")
    _require(artifacts.get("dmg_sha256") == dmg_sha256, f"{architecture} blocked N05 DMG SHA mismatch")
    _require(artifacts.get("executable_sha256") == executable_sha256,
             f"{architecture} blocked N05 executable SHA mismatch")
    _require(SHA256_RE.fullmatch(str(artifacts.get("app_tree_sha256") or "")) is not None,
             f"{architecture} blocked N05 app tree SHA is missing")
    _require(signing.get("codesign_verify") == "PASS", f"{architecture} blocked N05 codesign verification failed")
    _require(signing.get("identity_type") == "AD_HOC",
             f"{architecture} blocked pilot artifact must be explicitly ad-hoc")
    _require(notarization.get("release_gate_pass") is False,
             f"{architecture} blocked N05 must not claim a release gate pass")
    _require(mount.get("mode") == "readonly" and mount.get("attached") is True and mount.get("detached") is True,
             f"{architecture} blocked N05 mount lifecycle is incomplete")
    _require(commands.get("raw_output_recorded") is False,
             f"{architecture} blocked N05 contains raw signing output")
    _require(claims.get("production_ready") is False and claims.get("commercial_support") is False
             and claims.get("live_execution") is False,
             f"{architecture} blocked N05 contains an unsupported product claim")
    _require(all(contract.get(key) is False for key in (
        "user_data_read", "credentials_read", "signing_secret_read", "application_network_used", "live_execution"
    )), f"{architecture} blocked N05 contains an unsafe contract claim")
    return "AD_HOC_BLOCKED"


def _validate_common_source(identities: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    baseline = identities[ARCHITECTURES[0]]
    for architecture in ARCHITECTURES[1:]:
        candidate = identities[architecture]
        for key in ("source_commit_sha", "tracked_source_tree_sha256", "lock_hashes", "truth_matrix_sha256"):
            _require(candidate.get(key) == baseline.get(key),
                     f"architecture evidence is not from one exact source for {key}")
    _require(baseline.get("truth_matrix_sha256") == canonical_matrix_digest(load_matrix(DEFAULT_MATRIX_PATH)),
             "pilot truth-matrix digest does not match the canonical matrix")
    return {
        "commit_sha": baseline["source_commit_sha"],
        "tracked_source_tree_sha256": baseline["tracked_source_tree_sha256"],
        "lock_hashes": baseline["lock_hashes"],
        "truth_matrix_sha256": baseline["truth_matrix_sha256"],
    }


def _copy_input(source: Path, destination: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise PilotPackageError(f"pilot input is missing or symlinked: {source}")
    shutil.copy2(source, destination)


def prepare_pilot_package(
    *,
    output: Path,
    artifacts: Mapping[str, Mapping[str, Path]],
    instructions: Path,
) -> dict[str, Any]:
    """Validate two exact architecture chains and write a pilot package."""

    if set(artifacts) != set(ARCHITECTURES):
        missing = sorted(set(ARCHITECTURES) - set(artifacts))
        if missing:
            raise MissingPilotEvidence(f"missing native pilot evidence: {', '.join(missing)}")
        raise PilotPackageError("pilot package must contain exactly arm64 and x86_64 evidence")

    identities: dict[str, dict[str, Any]] = {}
    n05_states: dict[str, str] = {}
    for architecture in ARCHITECTURES:
        values = artifacts[architecture]
        dmg = Path(values["dmg"]).resolve()
        smoke_path = Path(values["smoke_report"]).resolve()
        n05_path = Path(values["n05_report"]).resolve()
        expected_name = f"Kuantra-Terminal-{__version__}-{architecture}.dmg"
        _require(dmg.name == expected_name,
                 f"{architecture} DMG must be named {expected_name}, got {dmg.name}")
        for path, label in ((dmg, "DMG"), (smoke_path, "smoke report"), (n05_path, "N05 report")):
            if path.is_symlink() or not path.is_file():
                raise MissingPilotEvidence(f"missing {architecture} {label}: {path}")
        smoke = _read_json(smoke_path, f"{architecture} smoke report")
        identities[architecture] = _source_identity(smoke, architecture=architecture, dmg=dmg)
        n05 = _read_json(n05_path, f"{architecture} N05 report")
        n05_states[architecture] = _validate_blocked_n05(
            n05,
            architecture=architecture,
            dmg_sha256=identities[architecture]["artifact_sha256"],
            executable_sha256=identities[architecture]["executable_sha256"],
            source_commit_sha=identities[architecture]["source_commit_sha"],
        )

    common = _validate_common_source(identities)
    instructions = instructions.resolve()
    if instructions.is_symlink() or not instructions.is_file():
        raise PilotPackageError(f"pilot instructions are missing or symlinked: {instructions}")

    output = output.resolve()
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise PilotPackageError(f"pilot output must be a new empty directory: {output}")
    else:
        output.mkdir(parents=True, exist_ok=False)

    artifact_entries: list[dict[str, Any]] = []
    evidence_entries: list[dict[str, Any]] = []
    for architecture in ARCHITECTURES:
        values = artifacts[architecture]
        source_dmg = Path(values["dmg"]).resolve()
        source_smoke = Path(values["smoke_report"]).resolve()
        source_n05 = Path(values["n05_report"]).resolve()
        dmg_name = source_dmg.name
        smoke_name = SMOKE_REPORT_NAMES[architecture]
        n05_name = N05_REPORT_NAMES[architecture]
        _copy_input(source_dmg, output / dmg_name)
        _copy_input(source_smoke, output / smoke_name)
        _copy_input(source_n05, output / n05_name)
        artifact_entries.append({
            "filename": dmg_name,
            "architecture": architecture,
            "platform": "macOS",
            "minimum_os": "macOS 12 Monterey or later",
            "size_bytes": source_dmg.stat().st_size,
            "sha256": identities[architecture]["artifact_sha256"],
            "final_smoke_report": smoke_name,
            "final_smoke_report_sha256": _sha256_file(source_smoke),
            "n05_report": n05_name,
            "n05_report_sha256": _sha256_file(source_n05),
            "distribution_evidence": n05_states[architecture],
        })
        evidence_entries.extend([
            {"filename": smoke_name, "sha256": _sha256_file(source_smoke)},
            {"filename": n05_name, "sha256": _sha256_file(source_n05)},
        ])

    blocked = any(state == "AD_HOC_BLOCKED" for state in n05_states.values())
    manifest: dict[str, Any] = {
        "schema_version": "Kuantra.pilot-package.v1",
        "package_type": "TRUSTED_MACOS_PILOT",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "product": {
            "name": "Kuantra Terminal",
            "version": __version__,
            "release_tag": f"v{__version__}",
            "positioning": "Local-first Execution Intelligence & Trade Forensics Workstation",
        },
        "source": common,
        "truth_matrix": {
            "path": "docs/release/truth-matrix.v1.0.0.json",
            "document_id": "KTR-001",
            "version": "1.0.0",
            "sha256": common["truth_matrix_sha256"],
        },
        "distribution": {
            "transport": "private GitHub Release",
            "repository_read_access_required": True,
            "apple_developer_id": False,
            "artifact_status": "AD_HOC_TRUSTED_PILOT_ONLY" if blocked else "N05_VERIFIED_PILOT",
            "production_ready": False,
            "commercial_support": False,
            "live_execution": False,
            "notarized": not blocked,
            "github_release_replaces_apple_notarization": False,
        },
        "access_boundary": {
            "supported_os": "macOS 12 Monterey or later",
            "architectures": list(ARCHITECTURES),
            "private_release_users_must_be_signed_in": True,
            "manual_gatekeeper_approval_required_for_ad_hoc": blocked,
            "no_public_download_claim": True,
        },
        "artifacts": artifact_entries,
        "evidence": evidence_entries,
        "included_files": [
            *[entry["filename"] for entry in artifact_entries],
            *[entry["filename"] for entry in evidence_entries],
            MANIFEST_NAME,
            CHECKSUMS_NAME,
            INSTRUCTIONS_NAME,
        ],
        "claims": {
            "production_ready": False,
            "commercial_support": False,
            "real_user_outcome": False,
            "live_broker_execution": False,
            "ai_order_authority": False,
        },
    }

    _copy_input(instructions, output / INSTRUCTIONS_NAME)
    manifest_path = output / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checksum_targets = [
        *(output / entry["filename"] for entry in artifact_entries),
        *(output / entry["filename"] for entry in evidence_entries),
        manifest_path,
        output / INSTRUCTIONS_NAME,
    ]
    checksum_lines = [f"{_sha256_file(path)}  {path.name}" for path in checksum_targets]
    (output / CHECKSUMS_NAME).write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return manifest


def _arg_path(value: str | None, default: Path) -> Path:
    return Path(value) if value else default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare a hash-verified Kuantra macOS pilot package")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instructions", type=Path, default=ROOT / "docs" / "release" / "PILOT-INSTRUCTIONS.md")
    for architecture in ARCHITECTURES:
        parser.add_argument(f"--{architecture}-dmg", dest=f"{architecture}_dmg", type=Path)
        parser.add_argument(f"--{architecture}-smoke-report", dest=f"{architecture}_smoke", type=Path)
        parser.add_argument(f"--{architecture}-n05-report", dest=f"{architecture}_n05", type=Path)
    args = parser.parse_args(argv)
    dist = args.dist.resolve()
    artifacts: dict[str, dict[str, Path]] = {}
    for architecture in ARCHITECTURES:
        artifacts[architecture] = {
            "dmg": _arg_path(
                getattr(args, f"{architecture}_dmg"),
                dist / f"Kuantra-Terminal-{__version__}-{architecture}.dmg",
            ),
            "smoke_report": _arg_path(
                getattr(args, f"{architecture}_smoke"),
                dist / SMOKE_REPORT_NAMES[architecture],
            ),
            "n05_report": _arg_path(
                getattr(args, f"{architecture}_n05"),
                dist / N05_REPORT_NAMES[architecture],
            ),
        }
    try:
        manifest = prepare_pilot_package(
            output=args.output,
            artifacts=artifacts,
            instructions=args.instructions,
        )
    except MissingPilotEvidence as exc:
        print(f"[pilot-package] BLOCKED: {exc}", file=sys.stderr)
        return 2
    except PilotPackageError as exc:
        print(f"[pilot-package] FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"[pilot-package] PASS: {manifest['distribution']['artifact_status']} "
        f"source={manifest['source']['commit_sha']} output={Path(args.output).resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
