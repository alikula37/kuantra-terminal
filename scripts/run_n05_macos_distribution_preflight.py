"""Verify the signed/notarized identity of an exact macOS distribution artifact.

This command is intentionally a verifier, not a signing or notarization client.  It
mounts one explicit DMG read-only, inspects the app inside that mount, and binds the
observations to the exact final smoke/provenance report.  It never reads a user data
directory, Keychain item, signing key, or credential and never changes the DMG/app.

Exit codes:
  0 - the exact DMG satisfies the N05 distribution gate;
  2 - the artifact is structurally/provenance-valid but remains blocked by the
      Developer ID, hardened-runtime, Gatekeeper, or notarization-ticket gate;
  1 - the evidence is malformed, mismatched, or the read-only audit failed.

Only command names, parsed public signing metadata, statuses, and hashes are written
to the report.  Raw codesign/spctl/stapler output is deliberately not persisted so
that signing logs remain secretless.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_provenance import ProvenanceError, _sha256_path, validate_report  # noqa: E402


SCHEMA_VERSION = "N05.macos-distribution.v1"
DEVELOPER_ID_AUTHORITY = "Developer ID Application:"
DEFAULT_ALLOWED_ENTITLEMENTS = frozenset(
    {
        "com.apple.security.network.client",
        "com.apple.security.cs.allow-jit",
        "com.apple.security.cs.disable-library-validation",
    }
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class N05DistributionError(ValueError):
    """Raised when exact N05 evidence cannot be established safely."""


class CommandResult:
    """Small command result used by the real runner and deterministic tests."""

    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


CommandRunner = Callable[[Sequence[str]], CommandResult]


def _run(command: Sequence[str]) -> CommandResult:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return CommandResult(127)
    return CommandResult(result.returncode, result.stdout, result.stderr)


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise N05DistributionError(f"missing DMG for hash: {path}")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise N05DistributionError("could not hash the exact DMG") from exc
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise N05DistributionError(f"{label} is missing or invalid") from exc
    if not isinstance(value, dict):
        raise N05DistributionError(f"{label} must be a JSON object")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _command_status(result: CommandResult) -> str:
    return "PASS" if result.returncode == 0 else "FAIL"


def _combined_output(result: CommandResult) -> str:
    return "\n".join(value for value in (result.stdout, result.stderr) if value)


def _parse_codesign_info(result: CommandResult) -> dict[str, Any]:
    """Extract only public, non-secret fields from ``codesign -dv`` output."""

    output = _combined_output(result)
    if result.returncode != 0:
        raise N05DistributionError("codesign identity inspection failed")

    def first(pattern: str) -> str | None:
        match = re.search(pattern, output, re.MULTILINE)
        return match.group(1).strip() if match else None

    authorities = [match.strip() for match in re.findall(r"^Authority=(.+)$", output, re.MULTILINE)]
    code_directory = first(r"^CodeDirectory\s+(.+)$")
    flags = code_directory or ""
    signature = first(r"^Signature=(.+)$")
    team_identifier = first(r"^TeamIdentifier=(.+)$")
    identifier = first(r"^Identifier=(.+)$")
    format_value = first(r"^Format=(.+)$")
    executable_architecture = None
    if format_value:
        architecture_match = re.search(r"\b(arm64|x86_64)\b", format_value)
        executable_architecture = architecture_match.group(1) if architecture_match else None

    if not identifier or not format_value or not signature:
        raise N05DistributionError("codesign identity metadata is incomplete")

    is_developer_id = any(authority.startswith(DEVELOPER_ID_AUTHORITY) for authority in authorities)
    is_ad_hoc = signature.casefold() == "adhoc" or (
        not authorities and (team_identifier or "").casefold() == "not set"
    )
    if is_developer_id:
        identity_type = "DEVELOPER_ID_APPLICATION"
    elif is_ad_hoc:
        identity_type = "AD_HOC"
    else:
        identity_type = "OTHER"

    return {
        "identifier": identifier,
        "format": format_value,
        "architecture": executable_architecture,
        "signature": signature,
        "team_identifier": team_identifier,
        "authorities": authorities,
        "identity_type": identity_type,
        "hardened_runtime": bool(re.search(r"flags=[^\n]*\bruntime\b", flags, re.IGNORECASE)),
    }


def _parse_entitlements(result: CommandResult) -> dict[str, Any]:
    """Parse entitlements without retaining command output in evidence."""

    if result.returncode != 0:
        output = _combined_output(result).casefold()
        if "no entitlements" in output or "does not contain entitlements" in output:
            return {}
        raise N05DistributionError("codesign entitlement inspection failed")

    candidates: list[bytes] = []
    for value in (result.stdout, result.stderr):
        encoded = value.encode("utf-8", errors="ignore")
        xml_start = encoded.find(b"<?xml")
        xml_end = encoded.find(b"</plist>", xml_start)
        if xml_start >= 0 and xml_end >= 0:
            candidates.append(encoded[xml_start : xml_end + len(b"</plist>")])
        candidates.append(encoded)

    for candidate in candidates:
        try:
            parsed = plistlib.loads(candidate)
        except (plistlib.InvalidFileException, ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _validate_smoke_binding(
    report: Mapping[str, Any],
    *,
    dmg: Path,
    dmg_sha256: str,
) -> Mapping[str, Any]:
    try:
        provenance = validate_report(report, release_facing=True)
    except ProvenanceError as exc:
        raise N05DistributionError(f"release provenance is incomplete: {exc}") from exc

    if report.get("platform") != "darwin":
        raise N05DistributionError("final smoke report is not a macOS report")
    if report.get("ok") is not True:
        raise N05DistributionError("final macOS smoke report is not PASS")
    if report.get("renderer_actual") != "wkwebview":
        raise N05DistributionError("final macOS smoke did not use WKWebView")
    if report.get("renderer_controller_ready") is not True:
        raise N05DistributionError("final macOS WKWebView controller is not ready")
    dmg = dmg.resolve()
    reported_artifact = Path(str(report.get("artifact_path") or "")).resolve()
    if reported_artifact != dmg:
        raise N05DistributionError("smoke report artifact path does not match the exact DMG")
    nested_artifact = Path(str(provenance.get("artifact_path") or "")).resolve()
    if nested_artifact != dmg:
        raise N05DistributionError("build provenance artifact path does not match the exact DMG")
    if report.get("artifact_sha256") != dmg_sha256 or provenance.get("artifact_sha256") != dmg_sha256:
        raise N05DistributionError("smoke/provenance artifact SHA does not match the exact DMG")
    smoke_dmg = report.get("macos_dmg_smoke")
    if not isinstance(smoke_dmg, Mapping) or smoke_dmg.get("status") != "PASS":
        raise N05DistributionError("exact mounted-DMG smoke evidence is missing")
    if smoke_dmg.get("dmg_image_integrity") != "PASS":
        raise N05DistributionError("DMG image integrity verification is missing")
    if smoke_dmg.get("mount_mode") != "readonly" or smoke_dmg.get("executable_from_mount") is not True:
        raise N05DistributionError("smoke report does not prove a read-only mounted executable")
    return provenance


def validate_n05_report(
    report: Mapping[str, Any],
    *,
    artifact_sha256: str | None = None,
    source_commit_sha: str | None = None,
) -> Mapping[str, Any]:
    """Validate a serialized N05 PASS before it enters a release dossier.

    This validator is platform-independent.  The macOS command performs the live
    read-only observations; release/audit jobs use this function to ensure the
    resulting evidence cannot be detached from the exact Mac artifact.
    """

    if not isinstance(report, Mapping) or report.get("schema_version") != SCHEMA_VERSION:
        raise N05DistributionError("N05 report schema is missing or unsupported")
    if report.get("status") != "PASS" or report.get("acceptance_status") != "N05_COMPLETE":
        raise N05DistributionError("N05 report is not a PASS")
    platform_info = report.get("platform")
    if not isinstance(platform_info, Mapping) or platform_info.get("os") != "darwin":
        raise N05DistributionError("N05 report is not a macOS report")
    source = report.get("source")
    if not isinstance(source, Mapping):
        raise N05DistributionError("N05 source provenance is missing")
    commit_sha = str(source.get("commit_sha") or "")
    if not COMMIT_RE.fullmatch(commit_sha):
        raise N05DistributionError("N05 source commit SHA is missing or invalid")
    if source_commit_sha is not None and commit_sha != source_commit_sha:
        raise N05DistributionError("N05 source commit does not match final smoke")
    if source.get("tracked_tree_status") != "clean" or source.get("provenance_status") != "COMPLETE":
        raise N05DistributionError("N05 source provenance is not complete")

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise N05DistributionError("N05 artifact hashes are missing")
    for key in ("dmg_sha256", "app_tree_sha256", "executable_sha256"):
        if not SHA256_RE.fullmatch(str(artifacts.get(key) or "")):
            raise N05DistributionError(f"N05 {key} is missing or invalid")
    if artifact_sha256 is not None and artifacts.get("dmg_sha256") != artifact_sha256:
        raise N05DistributionError("N05 DMG SHA does not match release artifact")
    if not isinstance(artifacts.get("dmg_size_bytes"), int) or artifacts["dmg_size_bytes"] <= 0:
        raise N05DistributionError("N05 DMG size is missing or invalid")

    signing = report.get("signing")
    if not isinstance(signing, Mapping):
        raise N05DistributionError("N05 signing evidence is missing")
    if signing.get("codesign_verify") != "PASS":
        raise N05DistributionError("N05 codesign verification is not PASS")
    if signing.get("identity_type") != "DEVELOPER_ID_APPLICATION":
        raise N05DistributionError("N05 Developer ID Application identity is missing")
    if signing.get("hardened_runtime") is not True:
        raise N05DistributionError("N05 hardened runtime is missing")
    if signing.get("unapproved_entitlement_keys") != []:
        raise N05DistributionError("N05 contains unapproved entitlements")

    notarization = report.get("notarization")
    if not isinstance(notarization, Mapping) or any(
        notarization.get(key) != "PASS"
        for key in ("gatekeeper_assessment", "dmg_ticket_validation")
    ) or notarization.get("release_gate_pass") is not True:
        raise N05DistributionError("N05 notarization/Gatekeeper evidence is incomplete")

    mount = report.get("mount")
    if not isinstance(mount, Mapping) or mount.get("mode") != "readonly" or mount.get("attached") is not True or mount.get("detached") is not True:
        raise N05DistributionError("N05 does not prove a safe read-only mount lifecycle")
    commands = report.get("commands")
    if not isinstance(commands, Mapping) or commands.get("raw_output_recorded") is not False:
        raise N05DistributionError("N05 signing evidence is not secretless")
    claims = report.get("claims")
    if not isinstance(claims, Mapping) or any(
        claims.get(key) is not False for key in ("production_ready", "commercial_support", "live_execution")
    ):
        raise N05DistributionError("N05 report made an unsupported product claim")
    contract = report.get("contract")
    if not isinstance(contract, Mapping) or any(
        contract.get(key) is not False
        for key in ("user_data_read", "credentials_read", "signing_secret_read", "application_network_used", "live_execution")
    ):
        raise N05DistributionError("N05 report made an unsafe execution/data claim")
    return report


def verify_mounted_distribution(
    app: Path,
    dmg: Path,
    smoke_report: Mapping[str, Any],
    *,
    runner: CommandRunner = _run,
    mounted_root: Path | None = None,
    allowed_entitlements: frozenset[str] = DEFAULT_ALLOWED_ENTITLEMENTS,
) -> dict[str, Any]:
    """Verify an app already selected from the exact DMG mount.

    The function is separated from hdiutil lifecycle management so the contract can
    be tested deterministically without a macOS GUI, signing identity, or network.
    """

    app = Path(app).resolve()
    dmg = Path(dmg).resolve()
    if app.name != "Kuantra Terminal.app" or app.suffix != ".app" or not app.is_dir():
        raise N05DistributionError("selected artifact is not the expected Kuantra app bundle")
    if mounted_root is not None and not app.is_relative_to(Path(mounted_root).resolve()):
        raise N05DistributionError("selected app escapes the read-only DMG mount")
    executable = app / "Contents" / "MacOS" / "Kuantra Terminal"
    if not executable.is_file():
        raise N05DistributionError("selected app executable is missing")
    if not dmg.is_file():
        raise N05DistributionError("exact DMG is missing")

    dmg_sha256 = _sha256_file(dmg)
    provenance = _validate_smoke_binding(smoke_report, dmg=dmg, dmg_sha256=dmg_sha256)
    executable_sha256 = _sha256_path(executable)
    app_tree_sha256 = _sha256_path(app)
    if not executable_sha256 or not app_tree_sha256:
        raise N05DistributionError("could not hash the mounted app")
    if provenance.get("executable_sha256") != executable_sha256:
        raise N05DistributionError("mounted executable SHA does not match smoke provenance")

    info_result = runner(("codesign", "-dv", "--verbose=4", str(app)))
    signing_info = _parse_codesign_info(info_result)
    verify_result = runner(("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)))
    entitlements_result = runner(("codesign", "-d", "--entitlements", ":-", str(app)))
    entitlements = _parse_entitlements(entitlements_result)
    entitlement_keys = sorted(str(key) for key in entitlements)
    unknown_entitlements = sorted(set(entitlement_keys) - allowed_entitlements)
    gatekeeper_result = runner(("spctl", "--assess", "--type", "execute", "--verbose=4", str(app)))
    ticket_result = runner(("xcrun", "stapler", "validate", str(dmg)))

    architecture = provenance.get("architecture")
    issues: list[str] = []
    if signing_info["identifier"] != "com.kuantra.terminal":
        issues.append("bundle_identifier_mismatch")
    if signing_info["identity_type"] != "DEVELOPER_ID_APPLICATION":
        issues.append("developer_id_application_signature_required")
    if not signing_info["hardened_runtime"]:
        issues.append("hardened_runtime_required")
    if signing_info["architecture"] and architecture and signing_info["architecture"] != architecture:
        issues.append("executable_architecture_mismatch")
    if verify_result.returncode != 0:
        issues.append("codesign_verification_failed")
    if unknown_entitlements:
        issues.append("unapproved_entitlements")
    if gatekeeper_result.returncode != 0:
        issues.append("gatekeeper_assessment_failed")
    if ticket_result.returncode != 0:
        issues.append("dmg_notarization_ticket_missing_or_invalid")

    signing_pass = not any(
        issue in issues
        for issue in (
            "developer_id_application_signature_required",
            "hardened_runtime_required",
            "codesign_verification_failed",
            "unapproved_entitlements",
        )
    )
    notarization_pass = ticket_result.returncode == 0 and gatekeeper_result.returncode == 0
    status = "PASS" if not issues else "BLOCKED"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "acceptance_status": "N05_COMPLETE" if status == "PASS" else "OWNER_REVIEW_REQUIRED",
        "recorded_at_utc": _utc_now(),
        "platform": {
            "os": provenance.get("os"),
            "os_version": provenance.get("os_version"),
            "architecture": architecture,
        },
        "source": {
            "commit_sha": provenance.get("source_commit_sha"),
            "tracked_tree_status": provenance.get("tracked_source_tree_status"),
            "provenance_status": provenance.get("provenance_status"),
        },
        "artifacts": {
            "dmg_sha256": dmg_sha256,
            "dmg_size_bytes": dmg.stat().st_size,
            "app_tree_sha256": app_tree_sha256,
            "executable_sha256": executable_sha256,
            "mounted_app_relative_path": "Kuantra Terminal.app",
            "executable_relative_path": "Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal",
        },
        "signing": {
            "codesign_verify": _command_status(verify_result),
            "identity_type": signing_info["identity_type"],
            "identifier": signing_info["identifier"],
            "team_identifier": signing_info["team_identifier"],
            "authorities": signing_info["authorities"],
            "signature": signing_info["signature"],
            "hardened_runtime": signing_info["hardened_runtime"],
            "entitlement_keys": entitlement_keys,
            "unapproved_entitlement_keys": unknown_entitlements,
        },
        "notarization": {
            "gatekeeper_assessment": _command_status(gatekeeper_result),
            "dmg_ticket_validation": _command_status(ticket_result),
            "release_gate_pass": notarization_pass and signing_pass,
        },
        "commands": {
            "raw_output_recorded": False,
            "codesign_identity": "codesign -dv --verbose=4",
            "codesign_verify": "codesign --verify --deep --strict --verbose=2",
            "entitlements": "codesign -d --entitlements :-",
            "gatekeeper": "spctl --assess --type execute --verbose=4",
            "ticket": "xcrun stapler validate",
        },
        "issues": issues,
        "claims": {
            "production_ready": False,
            "commercial_support": False,
            "signing": signing_pass,
            "notarized": notarization_pass,
            "live_execution": False,
        },
        "contract": {
            "user_data_read": False,
            "credentials_read": False,
            "signing_secret_read": False,
            "application_network_used": False,
            "live_execution": False,
        },
    }


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_preflight(dmg: Path, smoke_report_path: Path, output: Path) -> int:
    """Mount, verify, detach, and write one exact N05 report."""

    if sys.platform != "darwin":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "acceptance_status": "HOST_REQUIRED",
            "recorded_at_utc": _utc_now(),
            "issues": ["macOS_host_required"],
            "contract": {"user_data_read": False, "credentials_read": False, "live_execution": False},
        }
        _write_report(output, payload)
        print("[n05] FAIL: exact macOS distribution preflight requires macOS", file=sys.stderr)
        return 1

    dmg = Path(dmg).resolve()
    smoke_report_path = Path(smoke_report_path).resolve()
    output = Path(output).resolve()
    if not dmg.is_file():
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "acceptance_status": "EVIDENCE_INVALID",
            "recorded_at_utc": _utc_now(),
            "issues": ["exact_dmg_missing"],
        }
        _write_report(output, payload)
        print(f"[n05] FAIL: missing DMG: {dmg}", file=sys.stderr)
        return 1

    smoke_report = _read_json(smoke_report_path, "final smoke report")
    mountpoint = Path(tempfile.mkdtemp(prefix="kuantra-n05-mount-"))
    attached = False
    payload: dict[str, Any] | None = None
    error: Exception | None = None
    detached = False
    try:
        attached_result = _run(("hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mountpoint), str(dmg)))
        if attached_result.returncode != 0:
            raise N05DistributionError("read-only DMG attach failed")
        attached = True
        app = mountpoint / "Kuantra Terminal.app"
        payload = verify_mounted_distribution(app, dmg, smoke_report, mounted_root=mountpoint)
    except Exception as exc:  # noqa: BLE001 - one fail-closed report boundary
        error = exc
    finally:
        if attached:
            detached_result = _run(("hdiutil", "detach", str(mountpoint), "-force"))
            detached = detached_result.returncode == 0
        shutil.rmtree(mountpoint, ignore_errors=True)

    if payload is None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "acceptance_status": "EVIDENCE_INVALID",
            "recorded_at_utc": _utc_now(),
            "issues": ["preflight_failed"],
        }
    payload.setdefault("mount", {})
    payload["mount"].update({"mode": "readonly", "attached": attached, "detached": detached})
    if error is not None:
        payload["status"] = "FAIL"
        payload["acceptance_status"] = "EVIDENCE_INVALID"
        payload["issues"] = list(payload.get("issues") or []) + [str(error)]
    elif not detached:
        payload["status"] = "FAIL"
        payload["acceptance_status"] = "EVIDENCE_INVALID"
        payload["issues"] = list(payload.get("issues") or []) + ["mount_detach_not_confirmed"]
    _write_report(output, payload)

    if error is not None or not detached:
        print(f"[n05] FAIL: {output}", file=sys.stderr)
        return 1
    if payload.get("status") == "BLOCKED":
        print(f"[n05] BLOCKED: Developer ID/notarization gate is not complete ({output})", file=sys.stderr)
        return 2
    print(f"[n05] PASS: {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify exact macOS signing/notarization evidence without signing secrets")
    parser.add_argument("--dmg", type=Path, required=True, help="exact final DMG to mount read-only")
    parser.add_argument("--smoke-report", type=Path, required=True, help="exact mounted-DMG smoke report for this DMG")
    parser.add_argument("--output", type=Path, required=True, help="N05 JSON evidence output")
    args = parser.parse_args(argv)
    return run_preflight(args.dmg, args.smoke_report, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
