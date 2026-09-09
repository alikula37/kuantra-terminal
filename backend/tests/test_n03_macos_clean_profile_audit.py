"""N03 clean-profile/install-lifecycle audit contracts."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.run_g0_g2_packaged_audit import SYNTHETIC_CSV
from scripts.run_n03_macos_clean_profile_audit import (
    N03HostRequired,
    validate_n03_report,
    validate_profile_attestation,
)
from desktop.n03_worker import run_reopen, run_seed


def _attestation(**overrides):
    payload = {
        "schema_version": "N03.profile.v1",
        "clean_profile": True,
        "previous_kuantra_data_present": False,
        "developer_cache_present": False,
        "credentials_present": False,
        "attested_by_role": "host-owner",
        "attested_at_utc": "2026-09-09T00:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_profile_attestation_requires_explicit_clean_boundary():
    assert validate_profile_attestation(_attestation())["clean_profile"] is True

    with pytest.raises(N03HostRequired, match="clean_profile"):
        validate_profile_attestation(_attestation(clean_profile=False))

    with pytest.raises(N03HostRequired, match="credentials"):
        validate_profile_attestation(_attestation(credentials_present=True))


def test_profile_attestation_does_not_accept_identity_free_or_stale_payload():
    missing_role = _attestation()
    missing_role.pop("attested_by_role")
    with pytest.raises(N03HostRequired, match="attested_by_role"):
        validate_profile_attestation(missing_role)

    with pytest.raises(N03HostRequired, match="schema_version"):
        validate_profile_attestation(_attestation(schema_version="N03.profile.v0"))


def _valid_report():
    return {
        "schema_version": "N03.launcher.v1",
        "status": "PASS",
        "profile_attestation": _attestation(),
        "installation": {
            "source_kind": "APP",
            "installed_app": "/tmp/installed/Kuantra Terminal.app",
            "executable": "/tmp/installed/Kuantra Terminal.app/Contents/MacOS/Kuantra Terminal",
            "source_artifact_sha256": "a" * 64,
            "installed_app_sha256": "b" * 64,
            "executable_sha256": "c" * 64,
            "quarantine": {"status": "NOT_PRESENT"},
            "gatekeeper": {"status": "OBSERVED"},
        },
        "provenance": {
            "provenance_status": "COMPLETE",
            "artifact_sha256": "a" * 64,
            "executable_sha256": "c" * 64,
        },
        "launches": {
            "first_smoke": {"status": "PASS"},
            "reopen_smoke": {"status": "PASS"},
        },
        "value_chain": {
            "seed": {
                "status": "PASS",
                "evidence_pack": {"snapshot_sha256": "d" * 64},
                "weekly_review": {"review_id": "review-1", "snapshot_sha256": "e" * 64},
            },
            "reopen": {
                "status": "PASS",
                "identity_preserved": True,
                "evidence_pack": {"snapshot_sha256": "d" * 64},
                "weekly_review": {
                    "review_id": "review-1",
                    "snapshot_sha256": "e" * 64,
                    "completion": {"decision": "REOPENED"},
                },
            },
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


def test_n03_report_rejects_production_or_unattested_success():
    report = _valid_report()
    assert validate_n03_report(report)["status"] == "PASS"

    report = _valid_report()
    report["profile_attestation"] = _attestation(clean_profile=False)
    with pytest.raises(N03HostRequired, match="attestation"):
        validate_n03_report(report)

    report = _valid_report()
    report["claims"]["production_ready"] = True
    with pytest.raises(ValueError, match="production"):
        validate_n03_report(report)


def test_n03_report_requires_persistent_reopen_identity():
    report = _valid_report()
    report["value_chain"]["reopen"]["identity_preserved"] = False
    with pytest.raises(ValueError, match="identity"):
        validate_n03_report(report)


def test_n03_source_worker_persists_value_chain_across_process_boundary(tmp_path):
    fixture = tmp_path / "n03-synthetic.csv"
    fixture.write_bytes(SYNTHETIC_CSV)
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)

    seed = run_seed(fixture, data_dir)
    reopen = run_reopen(fixture, data_dir)

    assert seed["status"] == reopen["status"] == "PASS"
    assert seed["trade"]["id"] == reopen["trade"]["id"]
    assert seed["fixture"]["sha256"] == reopen["fixture"]["sha256"]
    assert seed["evidence_pack"]["snapshot_sha256"] == reopen["evidence_pack"]["snapshot_sha256"]
    assert seed["evidence_pack"]["source_event_hashes"] == reopen["evidence_pack"]["source_event_hashes"]
    assert seed["weekly_review"]["review_id"] == reopen["weekly_review"]["review_id"]
    assert seed["weekly_review"]["snapshot_sha256"] == reopen["weekly_review"]["snapshot_sha256"]
    assert reopen["weekly_review"]["completion"]["decision"] == "REOPENED"
    assert seed["weekly_review"]["is_pass"] is False
    assert reopen["weekly_review"]["is_pass"] is False
    assert seed["preview"] == {
        "clean_status": "READY",
        "clean_decision": "IMPORT_ALLOWED",
        "malformed_status": "REJECTED",
        "malformed_coverage_status": "UNKNOWN",
        "malformed_decision": "IMPORT_BLOCKED",
        "malformed_db_trade_count": 0,
    }
    assert seed["scope_guard"]["funding_transfer_schema_added"] is False


def test_n03_source_worker_cli_reopens_in_a_new_python_process(tmp_path):
    fixture = tmp_path / "n03-synthetic.csv"
    fixture.write_bytes(SYNTHETIC_CSV)
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    seed_output = tmp_path / "seed.json"
    reopen_output = tmp_path / "reopen.json"
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(root), str(root / "backend"), environment.get("PYTHONPATH", "")]
    )
    worker_script = "from desktop.n03_worker import main; raise SystemExit(main())"

    seed_result = subprocess.run(
        [
            sys.executable,
            "-c",
            worker_script,
            "--n03-audit",
            "--phase",
            "seed",
            "--fixture",
            str(fixture),
            "--data-dir",
            str(data_dir),
            "--output",
            str(seed_output),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert seed_result.returncode == 0, seed_result.stderr

    reopen_result = subprocess.run(
        [
            sys.executable,
            "-c",
            worker_script,
            "--n03-audit",
            "--phase",
            "reopen",
            "--fixture",
            str(fixture),
            "--data-dir",
            str(data_dir),
            "--output",
            str(reopen_output),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert reopen_result.returncode == 0, reopen_result.stderr

    seed = json.loads(seed_output.read_text(encoding="utf-8"))
    reopen = json.loads(reopen_output.read_text(encoding="utf-8"))
    assert seed["evidence_pack"]["snapshot_sha256"] == reopen["evidence_pack"]["snapshot_sha256"]
    assert seed["weekly_review"]["snapshot_sha256"] == reopen["weekly_review"]["snapshot_sha256"]
    assert reopen["weekly_review"]["completion"]["decision"] == "REOPENED"
