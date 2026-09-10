"""Regression tests for the versioned release truth contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_release_truth.py"
RENDERER = ROOT / "scripts" / "render_current_release_notes.py"
MATRIX = ROOT / "docs" / "release" / "truth-matrix.v1.0.0.json"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_current_release_truth_contract_passes():
    result = run_script(CHECKER)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "[truth-contract] PASS" in result.stdout


def test_release_truth_rejects_a_non_matrix_tag():
    result = run_script(CHECKER, "--tag", "v1.4.0")
    assert result.returncode != 0
    assert "accepted tag 'v1.0.0'" in result.stderr


def test_renderer_excludes_historical_release_claims(tmp_path):
    output = tmp_path / "CURRENT_RELEASE_NOTES.md"
    result = run_script(RENDERER, "--output", str(output))
    assert result.returncode == 0, result.stderr or result.stdout
    rendered = output.read_text(encoding="utf-8")
    assert "Mac Candidate Truth & Safety" in rendered
    assert "Zero-Mock Institutional Release" not in rendered
    assert "CURRENT_RELEASE_NOTES:START" not in rendered


def test_truth_matrix_has_unique_capabilities_and_explicit_authority_boundary():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    capabilities = matrix["capabilities"]
    ids = [capability["id"] for capability in capabilities]
    assert len(ids) == len(set(ids))
    assert all(capability["external_execution_authority"] is False for capability in capabilities)
    assert any(capability["status"] == "VERIFIED_CORE" for capability in capabilities)
    assert any(capability["status"] == "EXPERIMENTAL_DISABLED" for capability in capabilities)


def test_v1_release_scope_is_mac_dual_architecture_only():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["product"]["version"] == "1.0.0"
    assert matrix["distribution"]["release_scope"] == "macOS arm64 and x86_64"
    assert matrix["distribution"]["minimum_os"] == "macOS 12 Monterey or later"
    assert matrix["distribution"]["architectures"] == ["arm64", "x86_64"]
    assert matrix["distribution"]["architecture_evidence"]["x86_64"] == "PENDING_NATIVE_CI"
    assert matrix["distribution"]["current_artifact_status"] == "AD_HOC_DEVELOPMENT_ONLY"
    assert set(matrix["distribution"]["unclaimed_platforms"]) == {
        "Windows", "Linux"
    }
