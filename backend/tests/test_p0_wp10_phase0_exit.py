"""Static and provenance gates for the Phase 0 exit audit."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.smoke_desktop import enrich_report


ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "audit_phase0_exit.py"


def run_audit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_static_phase0_exit_gates_pass():
    result = run_audit("--json")
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["audit"] == "PHASE_0_EXIT"
    assert payload["verdict"] == "STATIC_GATES_PASS_REPORTS_PENDING"
    assert payload["report_count"] == 0
    assert payload["external_execution_enabled"] is False


def test_phase0_exit_rejects_missing_final_artifact_evidence(tmp_path):
    result = run_audit("--smoke-report", str(tmp_path / "missing.json"))
    assert result.returncode != 0
    assert "missing audit input" in result.stderr


def test_smoke_report_enrichment_binds_hashes_and_truth_matrix(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("KUANTRA_BUILD_COMMIT", raising=False)
    executable = tmp_path / "Kuantra Terminal"
    artifact = tmp_path / "Kuantra-Terminal-1.4.0-test.bin"
    executable.write_bytes(b"packaged executable")
    artifact.write_bytes(b"distributed artifact")

    report = enrich_report(
        {"ok": True, "version": "1.4.0", "checks": {
            "react_mounted": True,
            "bridge_roundtrip": True,
            "health": True,
            "push_sink": True,
            "plugin_boundary": True,
        }},
        executable,
        artifact,
    )

    assert report["smoke_schema_version"] == 2
    assert len(report["executable_sha256"]) == 64
    assert len(report["artifact_sha256"]) == 64
    assert report["truth_matrix"]["document_id"] == "KTR-001"
    assert report["truth_matrix"]["product_version"] == "1.4.0"
    assert report["build_commit"] == "UNKNOWN"
