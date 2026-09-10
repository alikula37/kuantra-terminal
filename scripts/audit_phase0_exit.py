"""Dependency-free Phase 0 exit audit.

The audit is deliberately conservative: it can say that the evidence bundle is ready for human
release approval, but it never changes product availability or calls a broker.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_provenance import ProvenanceError, validate_report  # noqa: E402
from check_release_truth import TruthContractError, run_checks  # noqa: E402
from release_truth import canonical_matrix_digest, load_matrix  # noqa: E402
from run_n05_macos_distribution_preflight import N05DistributionError, validate_n05_report  # noqa: E402


# WP06 is intentionally split into two separately accepted contracts.  Keep the
# split explicit here so the exit audit cannot accidentally treat replay/data
# truth and order-flow/FIX truth as one unverified umbrella package.
REQUIRED_WORK_PACKAGES = [
    *(f"P0-WP{i:02d}" for i in range(6)),
    "P0-WP06A",
    "P0-WP06B",
    "P0-WP07",
    "P0-WP08",
    "P0-WP09",
]
REQUIRED_SMOKE_CHECKS = {"react_mounted", "bridge_roundtrip", "health", "push_sink", "plugin_boundary"}
# v1.0.0 is intentionally a macOS dual-architecture release train. CI remains
# three-OS engineering coverage, but the release workflow must not imply
# unsupported Windows/Linux artifacts or final-smoke evidence.
REQUIRED_OS = {"darwin"}
REQUIRED_MAC_ARCHITECTURES = {"arm64", "x86_64"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _fail(message: str) -> None:
    raise ValueError(message)


def _read(path: Path) -> str:
    if not path.is_file():
        _fail(f"missing audit input: {path}")
    return path.read_text(encoding="utf-8")


def _check_work_packages(status_text: str) -> None:
    for work_package in REQUIRED_WORK_PACKAGES:
        pattern = rf"^\|\s*{re.escape(work_package)}\b[^|]*\|\s*Verified\s*\|"
        if not re.search(pattern, status_text, re.MULTILINE):
            _fail(f"{work_package} is not recorded as Verified in PHASE-0-STATUS.md")


def _check_workflows(root: Path) -> None:
    ci = _read(root / ".github" / "workflows" / "ci.yml")
    release = _read(root / ".github" / "workflows" / "release.yml")
    for label, workflow in (("ci", ci), ("release", release)):
        for required in ("Verify release truth contract", "Smoke test desktop app"):
            if required not in workflow:
                _fail(f"{label} workflow is missing {required!r}")
    if "windows-latest" not in ci or "macos-latest" not in ci or "ubuntu-22.04" not in ci:
        _fail("CI workflow does not cover all three operating systems")
    for script in ("scripts/package_macos.sh",):
        if script not in release:
            _fail(f"release workflow does not run {script}")
    for forbidden in (
        "scripts/package_windows.sh",
        "scripts/package_linux.sh",
        "final-smoke-windows.json",
        "final-smoke-linux.json",
    ):
        if forbidden in release:
            _fail(f"Mac-only v1 release workflow contains unsupported surface {forbidden}")
    for required in (
        "workflow_dispatch",
        "Smoke test final packaged artifact",
        "run_n05_macos_distribution_preflight.py",
        "n05-macos-distribution-arm64.json",
        "n05-macos-distribution-x86_64.json",
        "scripts/audit_phase0_exit.py",
        "final-smoke-arm64.json",
        "final-smoke-x86_64.json",
    ):
        if required not in release:
            _fail(f"release workflow is missing {required!r}")
    if "CURRENT_RELEASE_NOTES.md" not in release or "MANIFEST.json" not in release:
        _fail("release workflow does not bind current notes and manifest")


def _validate_smoke_report(path: Path, matrix: dict[str, Any]) -> dict[str, Any]:
    try:
        report = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        _fail(f"invalid smoke report {path}: {exc}")
    if not isinstance(report, dict):
        _fail(f"smoke report {path} must be a JSON object")
    if report.get("smoke_schema_version") != 2:
        _fail(f"smoke report {path} has unsupported schema")
    if report.get("ok") is not True:
        _fail(f"smoke report {path} is not successful")
    if report.get("version") != report.get("version_expected"):
        _fail(f"smoke report {path} has a version mismatch")
    checks = report.get("checks")
    if not isinstance(checks, dict) or not REQUIRED_SMOKE_CHECKS.issubset(checks):
        _fail(f"smoke report {path} is missing required checks")
    if not all(checks.get(name) is True for name in REQUIRED_SMOKE_CHECKS):
        _fail(f"smoke report {path} contains a false required check")
    truth = report.get("truth_matrix")
    if not isinstance(truth, dict) or truth.get("document_id") != "KTR-001":
        _fail(f"smoke report {path} has no KTR-001 provenance")
    if truth.get("version") != matrix.get("version") or not SHA256_RE.fullmatch(str(truth.get("sha256", ""))):
        _fail(f"smoke report {path} has invalid truth-matrix provenance")
    if truth.get("sha256") != canonical_matrix_digest(matrix):
        _fail(f"smoke report {path} has a truth-matrix digest mismatch")
    if truth.get("product_version") != report.get("version"):
        _fail(f"smoke report {path} disagrees with its truth-matrix product version")
    for field in ("executable_sha256", "artifact_sha256"):
        if not SHA256_RE.fullmatch(str(report.get(field, ""))):
            _fail(f"smoke report {path} has invalid {field}")
    if not report.get("build_commit") or report.get("build_commit") == "UNKNOWN":
        _fail(f"smoke report {path} has no build commit provenance")
    if not UTC_TIMESTAMP_RE.fullmatch(str(report.get("recorded_at_utc", ""))):
        _fail(f"smoke report {path} has no UTC recording timestamp")
    if report.get("platform") == "darwin" and report.get("architecture") not in REQUIRED_MAC_ARCHITECTURES:
        _fail(f"smoke report {path} has unsupported or missing macOS architecture")
    try:
        validate_report(report, release_facing=True)
    except ProvenanceError as exc:
        _fail(f"smoke report {path} has incomplete release provenance: {exc}")
    return report


def _validate_n05_report(path: Path, macos_smoke: Mapping[str, Any]) -> dict[str, Any]:
    try:
        report = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        _fail(f"invalid N05 report {path}: {exc}")
    if not isinstance(report, dict):
        _fail(f"N05 report {path} must be a JSON object")
    try:
        validate_n05_report(
            report,
            artifact_sha256=str(macos_smoke.get("artifact_sha256") or ""),
            source_commit_sha=str(macos_smoke.get("build_commit") or ""),
        )
    except N05DistributionError as exc:
        _fail(f"N05 report {path} is invalid: {exc}")
    return report


def audit(
    root: Path,
    smoke_reports: list[Path] | None = None,
    n05_macos_report: Path | None = None,
    n05_macos_reports: list[Path] | None = None,
) -> dict[str, Any]:
    """Run the static and optional final-artifact evidence checks."""
    status = _read(root / "docs" / "strategy" / "PHASE-0-STATUS.md")
    _check_work_packages(status)
    _check_workflows(root)
    matrix_path = root / "docs" / "release" / "truth-matrix.v1.0.0.json"
    matrix = load_matrix(matrix_path)
    run_checks(root, matrix_path=matrix_path)

    reports = [_validate_smoke_report(path, matrix) for path in (smoke_reports or [])]
    n05_paths = list(n05_macos_reports or [])
    if n05_macos_report is not None:
        n05_paths.append(n05_macos_report)
    n05_reports: list[dict[str, Any]] = []
    if reports:
        platforms = {str(report.get("platform")) for report in reports}
        if platforms != REQUIRED_OS:
            _fail(f"final artifact smoke must cover {sorted(REQUIRED_OS)}, got {sorted(platforms)}")
        architectures = {str(report.get("architecture")) for report in reports}
        if architectures != REQUIRED_MAC_ARCHITECTURES:
            _fail(
                "final artifact smoke must cover "
                f"{sorted(REQUIRED_MAC_ARCHITECTURES)}, got {sorted(architectures)}"
            )
        evidence = matrix.get("distribution", {}).get("architecture_evidence", {})
        if evidence.get("x86_64") != "VERIFIED_CURRENT_CANDIDATE":
            _fail("x86_64 final evidence is present but the truth matrix still marks it pending")
        versions = {str(report.get("version")) for report in reports}
        if len(versions) != 1:
            _fail("final artifact smoke reports disagree on product version")
        matrix_provenance = {
            (
                report["truth_matrix"]["document_id"],
                report["truth_matrix"]["version"],
                report["truth_matrix"]["sha256"],
            )
            for report in reports
        }
        if len(matrix_provenance) != 1:
            _fail("final artifact smoke reports disagree on truth-matrix provenance")
        macos_reports = [report for report in reports if report.get("platform") == "darwin"]
        if macos_reports:
            if len(n05_paths) != len(macos_reports):
                _fail("each Mac final artifact smoke requires one matching N05 distribution report")
            unmatched_smoke = list(macos_reports)
            for n05_path in n05_paths:
                n05_candidate = json.loads(_read(n05_path))
                if not isinstance(n05_candidate, dict):
                    _fail(f"N05 report {n05_path} must be a JSON object")
                candidate_sha = str(n05_candidate.get("artifacts", {}).get("dmg_sha256") or "")
                matching = next(
                    (
                        report for report in unmatched_smoke
                        if str(report.get("artifact_sha256") or "") == candidate_sha
                    ),
                    None,
                )
                if matching is None:
                    _fail(f"N05 report {n05_path} does not match a final smoke artifact")
                n05_reports.append(_validate_n05_report(n05_path, matching))
                unmatched_smoke.remove(matching)
        elif n05_paths:
            _fail("N05 macOS report supplied without a macOS final smoke report")
    elif n05_paths:
        _fail("N05 macOS report requires final artifact smoke reports")

    return {
        "audit": "PHASE_0_EXIT",
        "verdict": "READY_FOR_HUMAN_RELEASE_APPROVAL" if reports else "STATIC_GATES_PASS_REPORTS_PENDING",
        "work_packages": REQUIRED_WORK_PACKAGES,
        "final_artifact_smoke_reports": [str(path) for path in smoke_reports or []],
        "report_count": len(reports),
        "n05_macos_reports": [str(path) for path in n05_paths],
        "n05_macos_report": str(n05_paths[0]) if len(n05_paths) == 1 else None,
        "n05_macos_statuses": [report.get("status") for report in n05_reports],
        "external_execution_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Kuantra Phase 0 exit evidence")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--smoke-report", action="append", type=Path, default=[])
    parser.add_argument("--n05-macos-report", action="append", type=Path, default=[])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    reports = [path if path.is_absolute() else root / path for path in args.smoke_report]
    n05_reports = [path if path.is_absolute() else root / path for path in args.n05_macos_report]
    try:
        result = audit(root, reports, n05_macos_reports=n05_reports)
    except (TruthContractError, ValueError) as exc:
        print(f"[phase0-exit] FAIL: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[phase0-exit] PASS: {result['verdict']}")
        print(f"[phase0-exit] Work packages: {', '.join(REQUIRED_WORK_PACKAGES)}")
        print(f"[phase0-exit] Final artifact reports: {result['report_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
