"""Focused N04 manual update/uninstall boundary tests."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scripts.run_n04_macos_update_uninstall_audit import (
    FAILURE_PHASES,
    N04AuditError,
    N04InjectedFailure,
    _sha256_path,
    _validate_provenance_report,
    create_audit_sandbox,
    evaluate_schema_rollback,
    promote_update,
    run_audit,
    seed_synthetic_data,
    uninstall_app_only,
    validate_n04_report,
)


def _make_app(root: Path, payload: str, *, name: str = "Kuantra Terminal.app") -> Path:
    app = root / name
    executable = app / "Contents" / "MacOS" / app.stem
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(payload, encoding="utf-8")
    (app / "Contents" / "Info.plist").write_text(
        json.dumps({"CFBundleName": app.stem, "payload": payload}, sort_keys=True),
        encoding="utf-8",
    )
    return app


def _sandbox_with_old_app(tmp_path: Path) -> tuple[Path, Path, Path, Path, str, str]:
    old_app = _make_app(tmp_path / "source-old", "old-build")
    new_app = _make_app(tmp_path / "source-new", "new-build")
    install_root = create_audit_sandbox(tmp_path / "install")
    active = install_root / old_app.name
    shutil.copytree(old_app, active)
    data_dir = tmp_path / "data"
    data_before = seed_synthetic_data(data_dir)
    return install_root, active, new_app, data_dir, data_before, _sha256_path(active)


def test_successful_manual_update_promotes_new_app_and_preserves_data(tmp_path: Path) -> None:
    install_root, active, new_app, data_dir, data_before, old_sha256 = _sandbox_with_old_app(tmp_path)

    result = promote_update(install_root, new_app)

    assert result["status"] == "PASS"
    assert result["active_app_sha256"] != old_sha256
    assert active.exists()
    assert not (install_root / f".{active.name}.n04-staging").exists()
    assert not (install_root / f".{active.name}.n04-previous").exists()
    assert _sha256_path(data_dir) == data_before


@pytest.mark.parametrize("phase", FAILURE_PHASES)
def test_interrupted_update_restores_old_app_without_transaction_debris(tmp_path: Path, phase: str) -> None:
    install_root, active, new_app, data_dir, data_before, old_active_sha256 = _sandbox_with_old_app(tmp_path)

    with pytest.raises(N04InjectedFailure):
        promote_update(install_root, new_app, failure_phase=phase)
    assert active.exists()
    assert _sha256_path(active) == old_active_sha256
    assert _sha256_path(data_dir) == data_before
    assert not (install_root / f".{active.name}.n04-staging").exists()
    assert not (install_root / f".{active.name}.n04-previous").exists()


def test_app_only_uninstall_preserves_data(tmp_path: Path) -> None:
    install_root, active, _new_app, data_dir, data_before, _old_sha256 = _sandbox_with_old_app(tmp_path)

    result = uninstall_app_only(active, data_dir)

    assert result["status"] == "PASS"
    assert result["app_removed"] is True
    assert result["data_preserved"] is True
    assert result["data_sha256_before"] == data_before
    assert (data_dir / "n04-synthetic-data-marker.json").exists()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {"data_schema_version": 2, "selected_build_min_schema": 0, "selected_build_max_schema": 1},
            "BLOCKED_NO_SAFE_ROLLBACK",
        ),
        (
            {
                "data_schema_version": 2,
                "selected_build_min_schema": 0,
                "selected_build_max_schema": 1,
                "verified_backup_available": True,
            },
            "BLOCKED_VERIFIED_RESTORE_REQUIRED",
        ),
        (
            {
                "data_schema_version": 2,
                "selected_build_min_schema": 0,
                "selected_build_max_schema": 1,
                "forward_fix_available": True,
            },
            "BLOCKED_FORWARD_FIX_REQUIRED",
        ),
    ],
)
def test_schema_rollback_is_fail_closed(kwargs: dict[str, object], expected: str) -> None:
    result = evaluate_schema_rollback(**kwargs)

    assert result["status"] == expected
    assert result["direct_old_executable"] is False
    assert result["automatic_schema_downgrade"] is False


def test_schema_range_support_does_not_allow_downgrade() -> None:
    result = evaluate_schema_rollback(
        data_schema_version=1,
        selected_build_min_schema=0,
        selected_build_max_schema=2,
    )

    assert result["status"] == "SUPPORTED_SCHEMA_RANGE"
    assert result["automatic_schema_downgrade"] is False


def test_unmarked_install_root_and_nested_data_are_rejected(tmp_path: Path) -> None:
    app = _make_app(tmp_path, "old")
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    with pytest.raises(N04AuditError):
        uninstall_app_only(app, data_dir)

    sandbox = create_audit_sandbox(tmp_path / "sandbox")
    active = sandbox / app.name
    shutil_copy = __import__("shutil").copytree(app, active)
    assert shutil_copy == active
    with pytest.raises(N04AuditError):
        uninstall_app_only(active, active / "nested-data")


def test_n04_report_validator_requires_implementation_only_and_boundaries() -> None:
    artifact = {
        "path": "/tmp/build.app",
        "source_commit_sha": "a" * 40,
        "artifact_sha256": "b" * 64,
        "executable_sha256": "c" * 64,
        "provenance_status": "COMPLETE",
    }
    report = {
        "schema_version": "N04.update-uninstall.v1",
        "status": "PASS",
        "acceptance_status": "IMPLEMENTATION_ONLY",
        "host_artifact_evidence": "REQUIRED",
        "artifacts": {"previous": artifact, "current": {**artifact, "artifact_sha256": "d" * 64}},
        "update": {"status": "PASS", "active_is_current": True, "data_preserved": True},
        "interruptions": [
            {
                "status": "PASS",
                "failure_phase": phase,
                "old_app_preserved": True,
                "data_preserved": True,
                "staging_present": False,
                "backup_present": False,
            }
            for phase in FAILURE_PHASES
        ],
        "uninstall": {"status": "PASS", "app_removed": True, "data_preserved": True},
        "schema_rollback": {
            "status": "BLOCKED_NO_SAFE_ROLLBACK",
            "direct_old_executable": False,
            "automatic_schema_downgrade": False,
        },
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

    assert validate_n04_report(report) is report

    report["claims"]["automatic_updater"] = True
    with pytest.raises(N04AuditError):
        validate_n04_report(report)


def _write_provenance(path: Path, app: Path, commit: str) -> None:
    executable = app / "Contents" / "MacOS" / app.stem
    artifact_sha256 = _sha256_path(app)
    executable_sha256 = _sha256_path(executable)
    provenance = {
        "source_commit_sha": commit,
        "checkout_commit_sha": commit,
        "source_commit_matches_checkout": True,
        "tracked_source_tree_status": "clean",
        "tracked_source_tree_sha256": "1" * 64,
        "lock_hashes": {
            "backend_requirements_lock_sha256": "2" * 64,
            "frontend_package_lock_sha256": "3" * 64,
        },
        "toolchain": {
            "python": "3.11.16",
            "node": "v20.20.2",
            "npm": "10.8.2",
            "uv": "0.12.10",
            "pyinstaller": "6.22.2",
        },
        "os": "darwin",
        "architecture": "arm64",
        "executable_sha256": executable_sha256,
        "artifact_sha256": artifact_sha256,
        "provenance_status": "COMPLETE",
    }
    path.write_text(
        json.dumps(
            {
                "build_commit": commit,
                "executable_sha256": executable_sha256,
                "artifact_sha256": artifact_sha256,
                "build_provenance": provenance,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_full_isolated_audit_binds_two_artifacts_and_keeps_host_gate_open(tmp_path: Path) -> None:
    previous_app = _make_app(tmp_path / "previous", "previous-build")
    current_app = _make_app(tmp_path / "current", "current-build")
    previous_report = tmp_path / "previous-provenance.json"
    current_report = tmp_path / "current-provenance.json"
    _write_provenance(previous_report, previous_app, "a" * 40)
    _write_provenance(current_report, current_app, "b" * 40)

    report = run_audit(
        previous_app=previous_app,
        current_app=current_app,
        previous_provenance=previous_report,
        current_provenance=current_report,
    )

    assert validate_n04_report(report) is report
    assert report["acceptance_status"] == "IMPLEMENTATION_ONLY"
    assert report["host_artifact_evidence"] == "REQUIRED"
    assert report["update"]["active_is_current"] is True
    assert {item["failure_phase"] for item in report["interruptions"]} == set(FAILURE_PHASES)


def test_local_ci_provenance_shape_is_normalized_without_inventing_hashes(tmp_path: Path) -> None:
    app = _make_app(tmp_path / "app", "local-ci-build")
    smoke_style_report = tmp_path / "smoke-style.json"
    _write_provenance(smoke_style_report, app, "a" * 40)
    original = json.loads(smoke_style_report.read_text(encoding="utf-8"))
    local_ci_report = tmp_path / "local-ci.json"
    local_ci_report.write_text(
        json.dumps(
            {
                "local_ci_schema_version": 1,
                "build_provenance": original["build_provenance"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = _validate_provenance_report(local_ci_report, app_path=app)

    assert result["provenance_status"] == "COMPLETE"
    assert result["artifact_sha256"] == _sha256_path(app)
    assert result["executable_sha256"] == _sha256_path(app / "Contents" / "MacOS" / app.stem)
