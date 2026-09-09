"""Run the N03 macOS clean-profile/install-lifecycle audit.

The launcher is deliberately conservative.  It requires a host-owner clean
profile attestation, copies an explicit app (or a read-only mounted DMG) into a
disposable install root, and runs the packaged N03 worker across a process
boundary.  No existing user data directory is inspected or modified.  A PASS
is a bounded host/profile observation, never a signing, notarization, or
production-release claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_provenance import ProvenanceError, validate_report  # noqa: E402
from run_g0_g2_packaged_audit import SYNTHETIC_CSV  # noqa: E402


class N03HostRequired(RuntimeError):
    """Raised when the clean-profile/install boundary is not explicitly proven."""


class N03AuditError(ValueError):
    """Raised when a bounded N03 report is malformed or inconsistent."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_path(path: Path) -> str:
    candidate = Path(path)
    if candidate.is_file():
        return _sha256_file(candidate)
    if not candidate.is_dir() or candidate.is_symlink():
        raise N03AuditError(f"artifact must be a regular file or directory: {candidate}")
    digest = hashlib.sha256()
    for child in sorted(candidate.rglob("*"), key=lambda item: item.relative_to(candidate).as_posix()):
        relative = child.relative_to(candidate).as_posix().encode("utf-8")
        if child.is_symlink():
            digest.update(b"symlink\0" + relative + b"\0")
            digest.update(os.readlink(child).encode("utf-8"))
            digest.update(b"\0")
        elif child.is_file():
            digest.update(b"file\0" + relative + b"\0")
            with child.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def _require_existing(path: Path, *, label: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.exists():
        raise N03AuditError(f"{label} must be an existing non-symlink path")
    if not (candidate.is_file() or candidate.is_dir()):
        raise N03AuditError(f"{label} must be a regular file or directory")
    return candidate.resolve()


def validate_profile_attestation(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Require a host-owner assertion without requesting personal credentials."""

    if not isinstance(payload, Mapping):
        raise N03HostRequired("profile attestation must be a JSON object")
    if payload.get("schema_version") != "N03.profile.v1":
        raise N03HostRequired("profile attestation schema_version is missing or stale")
    for key in (
        "clean_profile",
        "previous_kuantra_data_present",
        "developer_cache_present",
        "credentials_present",
    ):
        if not isinstance(payload.get(key), bool):
            raise N03HostRequired(f"profile attestation field {key} must be boolean")
    if payload["clean_profile"] is not True:
        raise N03HostRequired("profile attestation clean_profile is not explicitly true")
    for key in ("previous_kuantra_data_present", "developer_cache_present", "credentials_present"):
        if payload[key] is not False:
            raise N03HostRequired(f"profile attestation reports {key}")
    role = payload.get("attested_by_role")
    if not isinstance(role, str) or not role.strip():
        raise N03HostRequired("profile attestation requires attested_by_role")
    timestamp = payload.get("attested_at_utc")
    if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
        raise N03HostRequired("profile attestation requires an RFC3339 UTC timestamp")
    return dict(payload)


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise N03AuditError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise N03AuditError(f"{label} must be a JSON object")
    return payload


def _validate_provenance_report(report_path: Path, *, artifact_sha256: str, executable_sha256: str) -> dict[str, Any]:
    report = _load_json(report_path, label="provenance report")
    try:
        provenance = dict(validate_report(report, release_facing=False))
    except ProvenanceError as exc:
        raise N03AuditError(f"provenance report is incomplete: {exc}") from exc
    if provenance.get("provenance_status") != "COMPLETE":
        raise N03AuditError("provenance report is not COMPLETE")
    if report.get("artifact_sha256") != artifact_sha256:
        raise N03AuditError("provenance artifact hash does not match selected source artifact")
    if report.get("executable_sha256") != executable_sha256:
        raise N03AuditError("provenance executable hash does not match installed executable")
    return {
        "report_path": str(report_path),
        "source_commit_sha": provenance.get("source_commit_sha"),
        "checkout_commit_sha": provenance.get("checkout_commit_sha"),
        "provenance_status": provenance.get("provenance_status"),
        "tracked_source_tree_status": provenance.get("tracked_source_tree_status"),
        "tracked_source_tree_sha256": provenance.get("tracked_source_tree_sha256"),
        "lock_hashes": provenance.get("lock_hashes"),
        "toolchain": provenance.get("toolchain"),
        "os": provenance.get("os"),
        "architecture": provenance.get("architecture"),
        "executable_sha256": executable_sha256,
        "artifact_sha256": artifact_sha256,
    }


def _observe_command(command: list[str], *, timeout: float = 30.0) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"status": "UNAVAILABLE", "command": command[0]}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "command": command[0]}
    return {
        "status": "OBSERVED",
        "command": command[0],
        "returncode": result.returncode,
        "assessment": "PASS" if result.returncode == 0 else "REJECTED",
        "stdout_tail": (result.stdout or "").strip()[-1000:],
        "stderr_tail": (result.stderr or "").strip()[-1000:],
    }


def _observe_security(app_path: Path) -> dict[str, Any]:
    quarantine = _observe_command(["xattr", "-p", "com.apple.quarantine", str(app_path)])
    if quarantine["status"] == "OBSERVED" and quarantine.get("returncode") != 0:
        quarantine["status"] = "NOT_PRESENT"
    gatekeeper = _observe_command(["spctl", "--assess", "--type", "execute", "--verbose=4", str(app_path)])
    return {"quarantine": quarantine, "gatekeeper": gatekeeper}


def _materialize_app(source: Path, install_root: Path) -> tuple[Path, dict[str, Any], Path | None]:
    """Copy an explicit .app, or a read-only mounted DMG, into a new temp root."""

    install_root.mkdir(parents=True, exist_ok=False)
    if any(install_root.iterdir()):
        raise N03AuditError("temporary install root was not empty")
    mountpoint: Path | None = None
    attached = False
    source_kind = "APP"
    source_app = source
    mount_mode = "not_applicable"
    if source.suffix.lower() == ".dmg":
        source_kind = "DMG"
        mount_mode = "readonly"
        mountpoint = Path(tempfile.mkdtemp(prefix="kuantra-n03-mount-"))
        attached_result = subprocess.run(
            ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mountpoint), str(source)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if attached_result.returncode != 0:
            shutil.rmtree(mountpoint, ignore_errors=True)
            raise N03AuditError("read-only DMG attach failed")
        attached = True
        source_app = mountpoint / "Kuantra Terminal.app"
    try:
        source_app = _require_existing(source_app, label="source app")
        if not source_app.name.endswith(".app") or not source_app.is_dir():
            raise N03AuditError("source app must be a .app directory")
        installed_app = install_root / source_app.name
        shutil.copytree(source_app, installed_app, symlinks=True)
        return installed_app, {
            "source_kind": source_kind,
            "mount_mode": mount_mode,
            "mount_attached": attached,
            "source_app": str(source_app),
        }, mountpoint
    except Exception:
        if attached and mountpoint is not None:
            subprocess.run(
                ["hdiutil", "detach", str(mountpoint), "-force"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        if mountpoint is not None:
            shutil.rmtree(mountpoint, ignore_errors=True)
        raise


def _detach_mount(mountpoint: Path | None) -> bool:
    if mountpoint is None:
        return True
    result = subprocess.run(
        ["hdiutil", "detach", str(mountpoint), "-force"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    shutil.rmtree(mountpoint, ignore_errors=True)
    return result.returncode == 0


def _run_worker(
    executable: Path,
    *,
    phase: str,
    fixture: Path,
    data_dir: Path,
    output: Path,
    timeout: float,
    env: Mapping[str, str],
) -> dict[str, Any]:
    command = [
        str(executable),
        "--n03-audit",
        "--phase",
        phase,
        "--fixture",
        str(fixture),
        "--data-dir",
        str(data_dir),
        "--output",
        str(output),
    ]
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise N03AuditError(
            f"packaged N03 {phase} failed with exit code {result.returncode}; "
            f"stderr={(result.stderr or '').strip()[-2000:]!r}"
        )
    report = _load_json(output, label=f"N03 {phase} worker report")
    execution = report.get("execution")
    if not isinstance(execution, Mapping) or execution.get("executable_sha256") != _sha256_file(executable):
        raise N03AuditError(f"packaged N03 {phase} executable hash does not match the selected executable")
    return report


def _validate_worker_phase(report: Mapping[str, Any], *, phase: str) -> dict[str, Any]:
    if report.get("status") != "PASS" or report.get("phase") != phase.upper():
        raise N03AuditError(f"N03 worker {phase} did not return PASS")
    contract = report.get("contract")
    if not isinstance(contract, Mapping) or any(contract.get(key) is not False for key in (
        "real_data", "credentials", "network", "live_execution", "production_claim"
    )):
        raise N03AuditError("N03 worker crossed the real-data/network/production boundary")
    scope = report.get("scope_guard")
    if (
        not isinstance(scope, Mapping)
        or scope.get("forbidden_event_types")
        or scope.get("forbidden_schema_objects")
        or scope.get("forbidden_modules_loaded")
        or scope.get("funding_transfer_schema_added") is not False
        or scope.get("market_data_enabled") is not False
        or scope.get("gateway_enabled") is not False
    ):
        raise N03AuditError("N03 worker scope guard is not clean")
    review = report.get("weekly_review")
    evidence = report.get("evidence_pack")
    if not isinstance(review, Mapping) or review.get("is_pass") is not False:
        raise N03AuditError("N03 worker weekly review produced false success")
    if not isinstance(evidence, Mapping) or evidence.get("replay_equal") is not True:
        raise N03AuditError("N03 worker Evidence Pack replay is not deterministic")
    execution = report.get("execution")
    if (
        not isinstance(execution, Mapping)
        or execution.get("mode") != "PACKAGED_PROCESS"
        or execution.get("artifact_executed") is not True
    ):
        raise N03AuditError("N03 worker did not execute from the selected packaged artifact")
    return {
        "phase": report.get("phase"),
        "status": report.get("status"),
        "data": report.get("data"),
        "trade": report.get("trade"),
        "evidence_pack": evidence,
        "weekly_review": review,
        "scope_guard": scope,
        "fixture": report.get("fixture"),
        "execution": execution,
    }


def _run_smoke(
    executable: Path,
    *,
    artifact: Path,
    data_dir: Path,
    report_path: Path,
    timeout: float,
    env: Mapping[str, str],
) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "smoke_desktop.py"),
            "--executable",
            str(executable),
            "--artifact",
            str(artifact),
            "--report",
            str(report_path),
            "--data-dir",
            str(data_dir),
            "--timeout",
            str(timeout),
        ],
        cwd=str(ROOT),
        env=dict(env),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout + 90,
    )
    payload = _load_json(report_path, label="desktop smoke report")
    if result.returncode != 0 or payload.get("ok") is not True:
        raise N03AuditError("installed app smoke did not PASS")
    if payload.get("renderer_actual") != "wkwebview" or payload.get("renderer_controller_ready") is not True:
        raise N03AuditError("installed app did not report native WKWebView readiness")
    expected_executable_sha256 = _sha256_file(executable)
    expected_artifact_sha256 = _sha256_path(artifact)
    if payload.get("executable_sha256") != expected_executable_sha256:
        raise N03AuditError("installed smoke executable hash does not match the selected executable")
    if payload.get("artifact_sha256") != expected_artifact_sha256:
        raise N03AuditError("installed smoke artifact hash does not match the selected app")
    if payload.get("provenance_status") != "COMPLETE":
        raise N03AuditError("installed app smoke provenance is not COMPLETE")
    return {
        "status": "PASS",
        "renderer_actual": payload.get("renderer_actual"),
        "renderer_controller_ready": payload.get("renderer_controller_ready"),
        "checks": payload.get("checks"),
        "report_sha256": _sha256_file(report_path),
        "build_commit": payload.get("build_commit"),
        "provenance_status": payload.get("provenance_status"),
    }


def validate_n03_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the final launcher contract without reusing application formulas."""

    if not isinstance(report, Mapping):
        raise N03AuditError("N03 report must be an object")
    if report.get("schema_version") != "N03.launcher.v1" or report.get("status") != "PASS":
        raise N03AuditError("N03 report is not PASS")
    validate_profile_attestation(report.get("profile_attestation") or {})
    installation = report.get("installation")
    launches = report.get("launches")
    value_chain = report.get("value_chain")
    if not isinstance(installation, Mapping) or not isinstance(launches, Mapping) or not isinstance(value_chain, Mapping):
        raise N03AuditError("N03 report is missing installation, launches or value_chain")
    if installation.get("source_kind") not in {"APP", "DMG"}:
        raise N03AuditError("N03 installation source_kind is missing or unsupported")
    for key in (
        "installed_app",
        "executable",
        "source_artifact_sha256",
        "installed_app_sha256",
        "executable_sha256",
    ):
        value = installation.get(key)
        if not isinstance(value, str) or not value.strip():
            raise N03AuditError(f"N03 installation is missing {key}")
    security = installation.get("quarantine")
    gatekeeper = installation.get("gatekeeper")
    if not isinstance(security, Mapping) or not isinstance(gatekeeper, Mapping):
        raise N03AuditError("N03 quarantine/Gatekeeper observations are missing")
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping) or provenance.get("provenance_status") != "COMPLETE":
        raise N03AuditError("N03 exact build provenance is not COMPLETE")
    if provenance.get("artifact_sha256") != installation.get("source_artifact_sha256"):
        raise N03AuditError("N03 provenance artifact hash is not bound to the selected artifact")
    if provenance.get("executable_sha256") != installation.get("executable_sha256"):
        raise N03AuditError("N03 provenance executable hash is not bound to the selected executable")
    for key in ("first_smoke", "reopen_smoke"):
        if not isinstance(launches.get(key), Mapping) or launches[key].get("status") != "PASS":
            raise N03AuditError(f"N03 {key} is not PASS")
    if not isinstance(value_chain.get("seed"), Mapping) or value_chain["seed"].get("status") != "PASS":
        raise N03AuditError("N03 seed chain is not PASS")
    reopen = value_chain.get("reopen")
    if not isinstance(reopen, Mapping) or reopen.get("status") != "PASS" or reopen.get("identity_preserved") is not True:
        raise N03AuditError("N03 reopen identity is not preserved")
    seed = value_chain["seed"]
    seed_evidence = seed.get("evidence_pack")
    reopen_evidence = reopen.get("evidence_pack")
    seed_review = seed.get("weekly_review")
    reopen_review = reopen.get("weekly_review")
    if not all(isinstance(value, Mapping) for value in (seed_evidence, reopen_evidence, seed_review, reopen_review)):
        raise N03AuditError("N03 value-chain evidence or review details are missing")
    if seed_evidence.get("snapshot_sha256") != reopen_evidence.get("snapshot_sha256"):
        raise N03AuditError("N03 Evidence Pack snapshot changed across reopen")
    if seed_review.get("review_id") != reopen_review.get("review_id"):
        raise N03AuditError("N03 review identity changed across reopen")
    if seed_review.get("snapshot_sha256") != reopen_review.get("snapshot_sha256"):
        raise N03AuditError("N03 review snapshot changed across reopen")
    if (reopen_review.get("completion") or {}).get("decision") != "REOPENED":
        raise N03AuditError("N03 reopen completion lineage is missing")
    contract = report.get("contract")
    if not isinstance(contract, Mapping) or any(
        contract.get(key) is not False
        for key in ("real_data", "credentials", "network", "live_execution")
    ):
        raise N03AuditError("N03 report crossed the real-data/network boundary")
    claims = report.get("claims")
    if not isinstance(claims, Mapping):
        raise N03AuditError("N03 claims are missing")
    for key in ("production_ready", "commercial_support", "signing", "notarized"):
        if claims.get(key) is not False:
            raise N03AuditError(f"N03 report made an unsupported {key} claim")
    if installation.get("mount_attached") is True and installation.get("mount_detached") is not True:
        raise N03AuditError("N03 DMG mount was not detached")
    return report


def run_audit(
    *,
    source: Path,
    provenance_report: Path,
    attestation: Path,
    output: Path,
    timeout: float,
) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise N03HostRequired("N03 install-lifecycle audit requires macOS")
    source = _require_existing(source, label="source artifact")
    if source.suffix.lower() != ".dmg" and not source.name.endswith(".app"):
        raise N03AuditError("source artifact must be a .app or .dmg")
    profile_attestation = validate_profile_attestation(_load_json(attestation, label="profile attestation"))
    artifact_sha256 = _sha256_path(source)

    with tempfile.TemporaryDirectory(prefix="kuantra-n03-audit-") as temporary_name:
        temporary = Path(temporary_name)
        install_root = temporary / "install"
        data_dir = temporary / "data"
        data_dir.mkdir(mode=0o700)
        fixture = temporary / "n03-synthetic.csv"
        fixture.write_bytes(SYNTHETIC_CSV)
        installed_app, installation, mountpoint = _materialize_app(source, install_root)
        executable = installed_app / "Contents" / "MacOS" / "Kuantra Terminal"
        executable = _require_existing(executable, label="installed executable")
        if executable.is_dir():
            raise N03AuditError("installed executable must be a regular file")
        executable_sha256 = _sha256_file(executable)
        installed_app_sha256 = _sha256_path(installed_app)
        installation.update(
            {
                "installed_app": str(installed_app),
                "executable": str(executable),
                "source_artifact_sha256": artifact_sha256,
                "installed_app_sha256": installed_app_sha256,
                "executable_sha256": executable_sha256,
            }
        )
        installation.update(_observe_security(installed_app))

        provenance = _validate_provenance_report(
            _require_existing(provenance_report, label="provenance report"),
            artifact_sha256=artifact_sha256,
            executable_sha256=executable_sha256,
        )
        env = os.environ.copy()
        env.update(
            {
                "KUANTRA_DATA_DIR": str(data_dir),
                "KUANTRA_MARKET_DATA_ENABLED": "false",
                "KUANTRA_GATEWAY_ENABLED": "false",
                "PYTHONUNBUFFERED": "1",
            }
        )
        seed_report_path = temporary / "n03-seed.json"
        reopen_report_path = temporary / "n03-reopen.json"
        first_smoke_report_path = temporary / "first-smoke.json"
        reopen_smoke_report_path = temporary / "reopen-smoke.json"
        try:
            seed = _validate_worker_phase(
                _run_worker(
                    executable,
                    phase="seed",
                    fixture=fixture,
                    data_dir=data_dir,
                    output=seed_report_path,
                    timeout=timeout,
                    env=env,
                ),
                phase="seed",
            )
            first_smoke = _run_smoke(
                executable,
                artifact=installed_app,
                data_dir=data_dir,
                report_path=first_smoke_report_path,
                timeout=timeout,
                env=env,
            )
            reopen = _validate_worker_phase(
                _run_worker(
                    executable,
                    phase="reopen",
                    fixture=fixture,
                    data_dir=data_dir,
                    output=reopen_report_path,
                    timeout=timeout,
                    env=env,
                ),
                phase="reopen",
            )
            reopen_smoke = _run_smoke(
                executable,
                artifact=installed_app,
                data_dir=data_dir,
                report_path=reopen_smoke_report_path,
                timeout=timeout,
                env=env,
            )
            seed_evidence = seed["evidence_pack"]
            reopen_evidence = reopen["evidence_pack"]
            seed_review = seed["weekly_review"]
            reopen_review = reopen["weekly_review"]
            fixture_sha256 = _sha256_file(fixture)
            if seed.get("fixture", {}).get("sha256") != fixture_sha256 or reopen.get("fixture", {}).get("sha256") != fixture_sha256:
                raise N03AuditError("N03 worker fixture provenance does not match the selected fixture")
            identity_preserved = (
                seed["trade"]["id"] == reopen["trade"]["id"]
                and seed_evidence["snapshot_sha256"] == reopen_evidence["snapshot_sha256"]
                and seed_review["review_id"] == reopen_review["review_id"]
                and seed_review["snapshot_sha256"] == reopen_review["snapshot_sha256"]
                and seed.get("data", {}).get("database_sha256") == reopen.get("data", {}).get("database_sha256")
                and reopen_review["completion"].get("decision") == "REOPENED"
            )
            if not identity_preserved:
                raise N03AuditError("N03 synthetic data/review identity changed across reopen")
            installation["mount_detached"] = _detach_mount(mountpoint)
            mountpoint = None
            if installation.get("mount_attached") is True and installation.get("mount_detached") is not True:
                raise N03AuditError("N03 DMG mount detach was not confirmed")
            report = {
                "schema_version": "N03.launcher.v1",
                "status": "PASS",
                "platform": {
                    "os": platform.system(),
                    "os_version": platform.platform(),
                    "architecture": platform.machine(),
                    "python": platform.python_version(),
                },
                "profile_attestation": profile_attestation,
                "installation": installation,
                "provenance": provenance,
                "launches": {"first_smoke": first_smoke, "reopen_smoke": reopen_smoke},
                "value_chain": {
                    "fixture_sha256": fixture_sha256,
                    "seed": seed,
                    "reopen": {**reopen, "identity_preserved": identity_preserved},
                },
                "claims": {
                    "production_ready": False,
                    "commercial_support": False,
                    "signing": False,
                    "notarized": False,
                },
                "contract": {
                    "real_data": False,
                    "credentials": False,
                    "network": False,
                    "live_execution": False,
                },
            }
            validate_n03_report(report)
            return report
        finally:
            if mountpoint is not None:
                _detach_mount(mountpoint)


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise N03AuditError("output must be a new file in an existing directory")
    with path.open("x", encoding="utf-8") as output_handle:
        json.dump(payload, output_handle, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the N03 macOS clean-profile/install-lifecycle audit")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--app", type=Path, help="explicit packaged .app to copy into a disposable install root")
    source_group.add_argument("--dmg", type=Path, help="explicit DMG to mount read-only and copy the .app")
    parser.add_argument("--provenance-report", type=Path, required=True)
    parser.add_argument("--profile-attestation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    paths = [args.app or args.dmg, args.provenance_report, args.profile_attestation, args.output]
    if any(not Path(path).is_absolute() for path in paths):
        parser.error("app/dmg, provenance-report, profile-attestation and output must be absolute paths")
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    try:
        report = run_audit(
            source=args.app or args.dmg,
            provenance_report=args.provenance_report,
            attestation=args.profile_attestation,
            output=args.output,
            timeout=args.timeout,
        )
        _write_new_json(args.output, report)
    except (N03HostRequired, N03AuditError, OSError, subprocess.SubprocessError) as exc:
        print(f"N03_AUDIT_BLOCKED {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, N03HostRequired) else 1
    print(f"N03_AUDIT_OK {args.output}")
    return 0


__all__ = [
    "N03AuditError",
    "N03HostRequired",
    "main",
    "run_audit",
    "validate_n03_report",
    "validate_profile_attestation",
]


if __name__ == "__main__":
    raise SystemExit(main())
