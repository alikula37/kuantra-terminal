"""Audit the macOS manual update/uninstall data-preservation boundary.

This is an isolated filesystem transaction harness, not an automatic updater.
It requires two explicit, different packaged ``.app`` artifacts and matching
provenance reports.  All writes happen below a disposable audit sandbox; the
user's application-support directory, credentials and migration data are never
read or changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_provenance import ProvenanceError, validate_report  # noqa: E402


SANDBOX_MARKER = ".n04-audit-sandbox"
SANDBOX_MARKER_CONTENT = "N04_SANDBOX_V1\n"
FAILURE_PHASES = ("after_stage", "after_backup", "after_promotion")


class N04AuditError(ValueError):
    """Raised when the N04 audit input or report is unsafe/inconsistent."""


class N04InjectedFailure(RuntimeError):
    """Raised by the bounded interruption tests."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_path(path: Path) -> str:
    candidate = Path(path)
    if candidate.is_symlink():
        raise N04AuditError(f"audit path must not be a symlink: {candidate}")
    if candidate.is_file():
        return _sha256_file(candidate)
    if not candidate.is_dir():
        raise N04AuditError(f"audit path is missing or not a file/directory: {candidate}")

    digest = hashlib.sha256()
    try:
        children = sorted(candidate.rglob("*"), key=lambda item: item.relative_to(candidate).as_posix())
        for child in children:
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
    except OSError as exc:
        raise N04AuditError(f"could not hash audit path: {candidate}") from exc
    return digest.hexdigest()


def _require_existing(path: Path, *, label: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.exists():
        raise N04AuditError(f"{label} must be an existing non-symlink path")
    if not (candidate.is_file() or candidate.is_dir()):
        raise N04AuditError(f"{label} must be a regular file or directory")
    return candidate.resolve()


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise N04AuditError(f"{label} is missing or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise N04AuditError(f"{label} must be a JSON object")
    return payload


def _app_executable(app_path: Path) -> Path:
    if not app_path.name.endswith(".app") or not app_path.is_dir() or app_path.is_symlink():
        raise N04AuditError("previous/current artifact must be a non-symlink .app directory")
    executable = app_path / "Contents" / "MacOS" / app_path.stem
    if not executable.is_file() or executable.is_symlink():
        raise N04AuditError(f"app executable is missing or unsafe: {executable}")
    return executable


def _validate_provenance_report(report_path: Path, *, app_path: Path) -> dict[str, Any]:
    report_path = _require_existing(report_path, label="provenance report")
    if not report_path.is_file():
        raise N04AuditError("provenance report must be a regular file")
    report = _load_json(report_path, label="provenance report")
    try:
        provenance = dict(validate_report(report, release_facing=False))
    except ProvenanceError as exc:
        raise N04AuditError(f"provenance report is incomplete: {exc}") from exc
    if provenance.get("provenance_status") != "COMPLETE":
        raise N04AuditError("provenance report is not COMPLETE")

    artifact_sha256 = _sha256_path(app_path)
    executable_sha256 = _sha256_file(_app_executable(app_path))
    if report.get("artifact_sha256") != artifact_sha256:
        raise N04AuditError("provenance artifact hash does not match selected .app")
    if report.get("executable_sha256") != executable_sha256:
        raise N04AuditError("provenance executable hash does not match selected .app executable")
    return {
        "path": str(app_path),
        "report_path": str(report_path),
        "source_commit_sha": provenance.get("source_commit_sha"),
        "checkout_commit_sha": provenance.get("checkout_commit_sha"),
        "tracked_source_tree_status": provenance.get("tracked_source_tree_status"),
        "tracked_source_tree_sha256": provenance.get("tracked_source_tree_sha256"),
        "lock_hashes": provenance.get("lock_hashes"),
        "toolchain": provenance.get("toolchain"),
        "os": provenance.get("os"),
        "architecture": provenance.get("architecture"),
        "provenance_status": provenance.get("provenance_status"),
        "artifact_sha256": artifact_sha256,
        "executable_sha256": executable_sha256,
    }


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _require_separate_data(app_path: Path, data_dir: Path) -> None:
    app_resolved = app_path.resolve(strict=False)
    data_resolved = data_dir.resolve(strict=False)
    if _is_within(data_resolved, app_resolved) or _is_within(app_resolved, data_resolved):
        raise N04AuditError("application and data directories must be separate")
    if data_dir.is_symlink() or not data_dir.is_dir():
        raise N04AuditError("data directory must be an existing non-symlink directory")


def _require_sandbox(install_root: Path) -> Path:
    install_root = Path(install_root).resolve()
    marker = install_root / SANDBOX_MARKER
    if not install_root.is_dir() or marker.is_symlink() or not marker.is_file():
        raise N04AuditError("install root is not an N04 audit sandbox")
    if marker.read_text(encoding="utf-8") != SANDBOX_MARKER_CONTENT:
        raise N04AuditError("install root sandbox marker is invalid")
    return install_root


def create_audit_sandbox(root: Path) -> Path:
    """Create an explicitly marked, empty sandbox for destructive audit steps."""

    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / SANDBOX_MARKER).write_text(SANDBOX_MARKER_CONTENT, encoding="utf-8")
    return root


def seed_synthetic_data(data_dir: Path) -> str:
    """Write only a deterministic, non-product marker into an isolated data root."""

    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    marker = data_dir / "n04-synthetic-data-marker.json"
    marker.write_text(
        json.dumps(
            {
                "fixture": "N04",
                "trade_id": "n04-synthetic-trade-001",
                "value": "synthetic-only",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return _sha256_path(data_dir)


def _cleanup_tree(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def promote_update(
    install_root: Path,
    new_app: Path,
    *,
    app_name: str | None = None,
    failure_phase: str | None = None,
) -> dict[str, Any]:
    """Promote a staged app and recover atomically when an injected failure occurs.

    The function refuses non-audit install roots.  It models the product's
    manual replacement boundary only; it is not an updater service.
    """

    install_root = _require_sandbox(install_root)
    new_app = _require_existing(new_app, label="new app")
    _app_executable(new_app)
    if app_name is None:
        app_name = new_app.name
    if not app_name.endswith(".app") or Path(app_name).name != app_name:
        raise N04AuditError("app_name must be a plain .app directory name")
    if failure_phase not in (None, *FAILURE_PHASES):
        raise N04AuditError(f"unsupported failure phase: {failure_phase}")

    active = install_root / app_name
    staging = install_root / f".{app_name}.n04-staging"
    backup = install_root / f".{app_name}.n04-previous"
    if not active.is_dir() or active.is_symlink():
        raise N04AuditError("active app is missing or unsafe")
    if staging.exists() or backup.exists():
        raise N04AuditError("install root contains an unfinished prior update")
    if new_app.resolve() == active.resolve():
        raise N04AuditError("new app must be distinct from active app")

    old_sha256 = _sha256_path(active)
    try:
        shutil.copytree(new_app, staging, symlinks=True)
        if failure_phase == "after_stage":
            raise N04InjectedFailure("interrupted after staging")

        os.replace(active, backup)
        if failure_phase == "after_backup":
            raise N04InjectedFailure("interrupted after backup")

        os.replace(staging, active)
        if failure_phase == "after_promotion":
            raise N04InjectedFailure("interrupted after promotion")
    except Exception:
        # Restore the old app for every interruption point.  A successful
        # promotion can be present at this point, so remove only this sandbox's
        # active candidate before restoring the known backup.
        if backup.exists():
            if active.exists():
                _cleanup_tree(active)
            os.replace(backup, active)
        if staging.exists():
            _cleanup_tree(staging)
        raise

    _cleanup_tree(backup)
    return {
        "status": "PASS",
        "failure_phase": failure_phase,
        "old_app_sha256": old_sha256,
        "active_app_sha256": _sha256_path(active),
        "staging_present": staging.exists(),
        "backup_present": backup.exists(),
    }


def uninstall_app_only(app_path: Path, data_dir: Path) -> dict[str, Any]:
    """Remove only an app inside an N04 sandbox and prove data is unchanged."""

    app_path = Path(app_path).resolve()
    install_root = _require_sandbox(app_path.parent)
    if app_path.parent != install_root:
        raise N04AuditError("app must be directly inside the audit sandbox")
    _app_executable(app_path)
    _require_separate_data(app_path, Path(data_dir))
    data_before = _sha256_path(Path(data_dir))
    _cleanup_tree(app_path)
    data_after = _sha256_path(Path(data_dir))
    if data_before != data_after:
        raise N04AuditError("app-only uninstall changed the isolated data snapshot")
    return {
        "status": "PASS",
        "app_removed": not app_path.exists(),
        "data_sha256_before": data_before,
        "data_sha256_after": data_after,
        "data_preserved": data_before == data_after,
        "install_root": str(install_root),
    }


def evaluate_schema_rollback(
    *,
    data_schema_version: int,
    selected_build_min_schema: int,
    selected_build_max_schema: int,
    verified_backup_available: bool = False,
    forward_fix_available: bool = False,
) -> dict[str, Any]:
    """Return the user-facing fail-closed decision for an older executable.

    This function does not run migrations or downgrade a database.  A newer
    schema requires a verified restore or a forward fix before an older build can
    be selected; otherwise the result remains blocked.
    """

    values = {
        "data_schema_version": data_schema_version,
        "selected_build_min_schema": selected_build_min_schema,
        "selected_build_max_schema": selected_build_max_schema,
    }
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values.values()):
        raise N04AuditError("schema versions must be non-negative integers")
    if selected_build_min_schema > selected_build_max_schema:
        raise N04AuditError("selected build schema range is invalid")
    if not isinstance(verified_backup_available, bool) or not isinstance(forward_fix_available, bool):
        raise N04AuditError("rollback evidence flags must be boolean")

    if data_schema_version > selected_build_max_schema:
        if forward_fix_available:
            status = "BLOCKED_FORWARD_FIX_REQUIRED"
            action = "apply_a_verified_forward_fix_with_owner_approval"
        elif verified_backup_available:
            status = "BLOCKED_VERIFIED_RESTORE_REQUIRED"
            action = "restore_a_verified_backup_before_selecting_the_older_build"
        else:
            status = "BLOCKED_NO_SAFE_ROLLBACK"
            action = "keep_the_current_build_and_preserve_data_until_a_safe_path_exists"
        return {
            "status": status,
            "action": action,
            "direct_old_executable": False,
            "automatic_schema_downgrade": False,
            "data_schema_version": data_schema_version,
            "selected_build_schema": [selected_build_min_schema, selected_build_max_schema],
        }

    if data_schema_version < selected_build_min_schema:
        return {
            "status": "BLOCKED_BUILD_TOO_OLD",
            "action": "select_a_build_that_supports_the_existing_schema_or_use_the_documented_upgrade_path",
            "direct_old_executable": False,
            "automatic_schema_downgrade": False,
            "data_schema_version": data_schema_version,
            "selected_build_schema": [selected_build_min_schema, selected_build_max_schema],
        }

    return {
        "status": "SUPPORTED_SCHEMA_RANGE",
        "action": "continue_without_schema_downgrade",
        "direct_old_executable": True,
        "automatic_schema_downgrade": False,
        "data_schema_version": data_schema_version,
        "selected_build_schema": [selected_build_min_schema, selected_build_max_schema],
    }


def validate_n04_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the source-level N04 audit report without relaxing boundaries."""

    if not isinstance(report, Mapping):
        raise N04AuditError("N04 report must be an object")
    if report.get("schema_version") != "N04.update-uninstall.v1" or report.get("status") != "PASS":
        raise N04AuditError("N04 report is not PASS")
    if report.get("acceptance_status") != "IMPLEMENTATION_ONLY":
        raise N04AuditError("N04 report must remain implementation-only until host evidence")
    if report.get("host_artifact_evidence") != "REQUIRED":
        raise N04AuditError("N04 report must retain the host/artifact evidence obligation")

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise N04AuditError("N04 artifact provenance is missing")
    previous = artifacts.get("previous")
    current = artifacts.get("current")
    if not isinstance(previous, Mapping) or not isinstance(current, Mapping):
        raise N04AuditError("N04 previous/current artifact records are missing")
    for label, artifact in (("previous", previous), ("current", current)):
        for key in ("path", "source_commit_sha", "artifact_sha256", "executable_sha256"):
            if not isinstance(artifact.get(key), str) or not artifact[key].strip():
                raise N04AuditError(f"N04 {label} artifact is missing {key}")
        if artifact.get("provenance_status") != "COMPLETE":
            raise N04AuditError(f"N04 {label} artifact provenance is not COMPLETE")
    if previous.get("artifact_sha256") == current.get("artifact_sha256"):
        raise N04AuditError("N04 previous/current artifacts must be different")

    update = report.get("update")
    interruptions = report.get("interruptions")
    uninstall = report.get("uninstall")
    rollback = report.get("schema_rollback")
    if not isinstance(update, Mapping) or update.get("status") != "PASS":
        raise N04AuditError("N04 successful update is not PASS")
    if update.get("data_preserved") is not True or update.get("active_is_current") is not True:
        raise N04AuditError("N04 successful update did not preserve data or promote current app")
    if not isinstance(interruptions, list) or len(interruptions) != len(FAILURE_PHASES):
        raise N04AuditError("N04 interruption evidence is incomplete")
    observed_phases = set()
    for item in interruptions:
        if not isinstance(item, Mapping) or item.get("status") != "PASS":
            raise N04AuditError("N04 interruption evidence is not PASS")
        observed_phases.add(item.get("failure_phase"))
        if item.get("old_app_preserved") is not True or item.get("data_preserved") is not True:
            raise N04AuditError("N04 interruption did not preserve old app/data")
        if item.get("staging_present") or item.get("backup_present"):
            raise N04AuditError("N04 interruption left transaction debris")
    if observed_phases != set(FAILURE_PHASES):
        raise N04AuditError("N04 interruption phase coverage is incomplete")
    if not isinstance(uninstall, Mapping) or uninstall.get("status") != "PASS":
        raise N04AuditError("N04 uninstall evidence is not PASS")
    if uninstall.get("app_removed") is not True or uninstall.get("data_preserved") is not True:
        raise N04AuditError("N04 app-only uninstall/data preservation is not proven")
    if not isinstance(rollback, Mapping) or not str(rollback.get("status", "")).startswith("BLOCKED"):
        raise N04AuditError("N04 schema rollback is not fail-closed")
    if rollback.get("direct_old_executable") is not False or rollback.get("automatic_schema_downgrade") is not False:
        raise N04AuditError("N04 schema rollback crossed the fail-closed boundary")

    contract = report.get("contract")
    if not isinstance(contract, Mapping) or any(
        contract.get(key) is not False
        for key in ("real_user_data", "credentials", "network", "live_execution", "migration_apply")
    ):
        raise N04AuditError("N04 report crossed a real-data/network/migration boundary")
    claims = report.get("claims")
    if not isinstance(claims, Mapping) or any(
        claims.get(key) is not False
        for key in ("automatic_updater", "production_ready", "commercial_support", "signing", "notarized")
    ):
        raise N04AuditError("N04 report made an unsupported product claim")
    return report


def run_audit(
    *,
    previous_app: Path,
    current_app: Path,
    previous_provenance: Path,
    current_provenance: Path,
) -> dict[str, Any]:
    """Run the isolated N04 filesystem audit against two explicit app artifacts."""

    if sys.platform != "darwin":
        raise N04AuditError("N04 packaged artifact audit requires macOS")
    previous_app = _require_existing(previous_app, label="previous app")
    current_app = _require_existing(current_app, label="current app")
    _app_executable(previous_app)
    _app_executable(current_app)
    if previous_app.name != current_app.name:
        raise N04AuditError("previous/current apps must have the same bundle directory name")

    previous_record = _validate_provenance_report(previous_provenance, app_path=previous_app)
    current_record = _validate_provenance_report(current_provenance, app_path=current_app)
    if previous_record["artifact_sha256"] == current_record["artifact_sha256"]:
        raise N04AuditError("previous/current packaged artifacts are identical")

    with tempfile.TemporaryDirectory(prefix="kuantra-n04-audit-") as temporary_name:
        temporary = Path(temporary_name)
        install_root = create_audit_sandbox(temporary / "install")
        data_dir = temporary / "data"
        data_before = seed_synthetic_data(data_dir)
        active = install_root / current_app.name
        shutil.copytree(previous_app, active, symlinks=True)
        previous_active_sha256 = _sha256_path(active)

        interruptions: list[dict[str, Any]] = []
        for phase in FAILURE_PHASES:
            try:
                promote_update(install_root, current_app, failure_phase=phase)
            except N04InjectedFailure:
                active_after_failure = _sha256_path(active)
                data_after_failure = _sha256_path(data_dir)
                stage = install_root / f".{current_app.name}.n04-staging"
                backup = install_root / f".{current_app.name}.n04-previous"
                interruptions.append(
                    {
                        "status": "PASS",
                        "failure_phase": phase,
                        "old_app_preserved": active_after_failure == previous_active_sha256,
                        "data_preserved": data_after_failure == data_before,
                        "staging_present": stage.exists(),
                        "backup_present": backup.exists(),
                    }
                )

        update = promote_update(install_root, current_app)
        current_active_sha256 = _sha256_path(active)
        data_after_update = _sha256_path(data_dir)
        update_record = {
            "status": "PASS",
            "active_is_current": current_active_sha256 == current_record["artifact_sha256"],
            "data_preserved": data_after_update == data_before,
            "data_sha256_before": data_before,
            "data_sha256_after": data_after_update,
            "active_app_sha256": current_active_sha256,
            "transaction": update,
        }

        uninstall = uninstall_app_only(active, data_dir)
        rollback = evaluate_schema_rollback(
            data_schema_version=2,
            selected_build_min_schema=0,
            selected_build_max_schema=1,
        )
        report = {
            "schema_version": "N04.update-uninstall.v1",
            "status": "PASS",
            "acceptance_status": "IMPLEMENTATION_ONLY",
            "host_artifact_evidence": "REQUIRED",
            "platform": {
                "os": platform.system(),
                "os_version": platform.platform(),
                "architecture": platform.machine(),
            },
            "artifacts": {"previous": previous_record, "current": current_record},
            "update": update_record,
            "interruptions": interruptions,
            "uninstall": uninstall,
            "schema_rollback": rollback,
            "claims": {
                "automatic_updater": False,
                "production_ready": False,
                "commercial_support": False,
                "signing": False,
                "notarized": False,
            },
            "contract": {
                "real_user_data": False,
                "credentials": False,
                "network": False,
                "live_execution": False,
                "migration_apply": False,
            },
        }
        validate_n04_report(report)
        return report


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise N04AuditError("output must be a new file in an existing directory")
    with path.open("x", encoding="utf-8") as output_handle:
        json.dump(payload, output_handle, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the N04 macOS manual update/uninstall audit")
    parser.add_argument("--previous-app", type=Path, required=True, help="explicit previous supported .app")
    parser.add_argument("--current-app", type=Path, required=True, help="explicit current .app")
    parser.add_argument("--previous-provenance", type=Path, required=True)
    parser.add_argument("--current-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = [
        args.previous_app,
        args.current_app,
        args.previous_provenance,
        args.current_provenance,
        args.output,
    ]
    if any(not Path(path).is_absolute() for path in paths):
        parser.error("all app, provenance and output paths must be absolute")
    try:
        report = run_audit(
            previous_app=args.previous_app,
            current_app=args.current_app,
            previous_provenance=args.previous_provenance,
            current_provenance=args.current_provenance,
        )
        _write_new_json(args.output, report)
    except (N04AuditError, N04InjectedFailure, OSError):
        print("N04_AUDIT_BLOCKED", file=sys.stderr)
        return 1
    print(f"N04_AUDIT_OK {args.output}")
    return 0


__all__ = [
    "FAILURE_PHASES",
    "N04AuditError",
    "N04InjectedFailure",
    "create_audit_sandbox",
    "evaluate_schema_rollback",
    "main",
    "promote_update",
    "run_audit",
    "seed_synthetic_data",
    "uninstall_app_only",
    "validate_n04_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
