"""Run and independently validate the packaged P1-WP27 G0-G2 audit.

This launcher is intentionally independent from application calculations.  It
supplies a tiny known fixture, invokes the explicit executable selected by the
caller, and compares the worker's report to a hand-authored oracle.  The output
is non-release evidence: source-to-binary attestation and release provenance
remain explicitly unknown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_CSV = (
    b"symbol,side,entry_price,exit_price,qty,entry_time,exit_time,status,pnl,commission,notes\n"
    b"AUDITUSDT,BUY,100,102,1,2026-09-08T10:00:00Z,2026-09-08T10:05:00Z,CLOSED,2,0.1,fixture\n"
)
EXPECTED_TRADE = {
    "symbol": "AUDITUSDT",
    "side": "BUY",
    "entry_price": 100.0,
    "exit_price": 102.0,
    "qty": 1.0,
    "status": "CLOSED",
    "pnl": 2.0,
    "commission": 0.1,
}
EXPECTED_COVERAGE = {
    "overall": "PARTIAL",
    "trade_snapshot": "COMPLETE",
    "realized_pnl": "COMPLETE",
    "fees": "COMPLETE",
    "funding_transfer": "NOT_AVAILABLE",
    "account_events": "NOT_AVAILABLE",
    "market_context": "NOT_AVAILABLE",
}
EXPECTED_IMPORT_COVERAGE = {
    "status": "PARTIAL",
    "source_rows": 1,
    "normalized_rows": 1,
    "rejected_rows": 0,
    "trade_snapshot": "COMPLETE",
    "realized_pnl": "COMPLETE",
    "commission": "COMPLETE",
    "account_scope": "NOT_AVAILABLE",
    "funding_transfer": "NOT_AVAILABLE",
    "market_context": "NOT_AVAILABLE",
}


def _oracle_mismatch(message: str) -> ValueError:
    return ValueError(f"oracle mismatch: {message}")


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
        raise ValueError(f"artifact must be a regular file or directory: {candidate}")
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


def _require_path(path: Path, *, kind: str) -> Path:
    raw = Path(path)
    if raw.is_symlink():
        raise ValueError(f"{kind} must not be a symlink")
    candidate = raw.resolve()
    if kind == "executable" and not candidate.is_file():
        raise ValueError("executable must be an existing regular file")
    if kind == "artifact" and not (candidate.is_file() or candidate.is_dir()):
        raise ValueError("artifact must be an existing file or directory")
    return candidate


def _assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise _oracle_mismatch(f"{label}: expected {expected!r}, got {actual!r}")


def _assert_sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise _oracle_mismatch(f"{label} is not a SHA-256 digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise _oracle_mismatch(f"{label} is not a SHA-256 digest") from exc


def validate_worker_report(
    report: Mapping[str, Any], *, fixture_sha256: str, packaged: bool
) -> Mapping[str, Any]:
    """Validate worker output against constants independent of app code."""

    if not isinstance(report, Mapping):
        raise _oracle_mismatch("worker report is not an object")
    _assert_equal(report.get("schema_version"), "P1-WP27.worker.v1", "schema_version")
    _assert_equal(report.get("status"), "PASS", "status")
    _assert_equal((report.get("fixture") or {}).get("sha256"), fixture_sha256, "fixture sha256")

    execution = report.get("execution")
    if not isinstance(execution, Mapping):
        raise _oracle_mismatch("execution metadata is missing")
    if packaged and execution.get("artifact_executed") is not True:
        raise ValueError("packaged executable was not executed (oracle mismatch)")
    _assert_equal(execution.get("artifact_executed"), packaged, "artifact_executed")
    _assert_equal(
        execution.get("mode"), "PACKAGED_PROCESS" if packaged else "SOURCE_PROCESS", "execution mode"
    )
    _assert_equal(execution.get("release_provenance"), "UNKNOWN", "release provenance")
    _assert_equal(
        execution.get("source_to_binary_attestation"), "NOT_VERIFIED", "source-to-binary attestation"
    )
    _assert_sha(execution.get("executable_sha256"), "worker executable")

    contract = report.get("contract")
    _assert_equal(
        contract,
        {
            "real_data": False,
            "credentials": False,
            "network": False,
            "live_execution": False,
            "production_claim": False,
        },
        "execution contract",
    )
    stages = report.get("stages")
    if not isinstance(stages, Mapping):
        raise _oracle_mismatch("stages are missing")

    clean = stages.get("clean_preview")
    if not isinstance(clean, Mapping):
        raise _oracle_mismatch("clean preview is missing")
    _assert_equal(clean.get("status"), "READY", "clean preview status")
    _assert_equal(clean.get("decision"), "IMPORT_ALLOWED", "clean preview decision")
    _assert_equal(clean.get("db_trade_count_before"), 0, "clean preview before count")
    _assert_equal(clean.get("db_trade_count_after"), 0, "clean preview after count")
    _assert_equal(clean.get("coverage"), EXPECTED_IMPORT_COVERAGE, "clean preview coverage")

    malformed = stages.get("malformed_preview")
    if not isinstance(malformed, Mapping):
        raise _oracle_mismatch("malformed preview is missing")
    if malformed.get("status") not in {"PARTIAL", "REJECTED"}:
        raise _oracle_mismatch("malformed preview was treated as complete")
    if malformed.get("decision") not in {"USER_REVIEW_REQUIRED", "IMPORT_BLOCKED"}:
        raise _oracle_mismatch("malformed preview did not fail closed")
    _assert_equal(malformed.get("db_trade_count_before"), 0, "malformed preview before count")
    _assert_equal(malformed.get("db_trade_count_after"), 0, "malformed preview after count")
    malformed_coverage = malformed.get("coverage")
    if not isinstance(malformed_coverage, Mapping):
        raise _oracle_mismatch("malformed preview coverage is missing")
    if malformed_coverage.get("status") not in {"PARTIAL", "UNKNOWN"}:
        raise _oracle_mismatch("malformed coverage was upgraded to complete")

    imported = stages.get("import")
    if not isinstance(imported, Mapping):
        raise _oracle_mismatch("import stage is missing")
    _assert_equal(imported.get("success"), True, "import success")
    _assert_equal(imported.get("imported"), 1, "import count")
    _assert_equal(imported.get("duplicates_skipped"), 0, "duplicate count")
    _assert_equal(imported.get("source_file_sha256"), fixture_sha256, "import source hash")
    _assert_equal(imported.get("event_count"), 1, "source event count")
    trade = imported.get("trade")
    if not isinstance(trade, Mapping):
        raise _oracle_mismatch("imported trade is missing")
    for key, expected in EXPECTED_TRADE.items():
        _assert_equal(trade.get(key), expected, f"trade {key}")

    evidence = stages.get("evidence_pack")
    if not isinstance(evidence, Mapping):
        raise _oracle_mismatch("Evidence Pack stage is missing")
    _assert_equal(evidence.get("read_source"), "typed_projection", "Evidence Pack read source")
    _assert_equal(evidence.get("event_count"), 1, "Evidence Pack event count")
    _assert_equal(evidence.get("coverage_summary"), EXPECTED_COVERAGE, "Evidence Pack coverage")
    _assert_equal(evidence.get("ledger_integrity", {}).get("valid"), True, "ledger integrity")
    source_event_hashes = evidence.get("source_event_hashes")
    if not isinstance(source_event_hashes, list) or len(source_event_hashes) != 1:
        raise _oracle_mismatch("source event hash is missing")
    _assert_sha(source_event_hashes[0], "source event hash")
    _assert_equal(evidence.get("import_review_source_file_sha256"), fixture_sha256, "Evidence Pack source hash")
    _assert_equal(evidence.get("replay_equal"), True, "Evidence Pack replay")

    exports = stages.get("exports")
    if not isinstance(exports, Mapping):
        raise _oracle_mismatch("export stage is missing")
    _assert_equal(exports.get("replay_equal"), True, "export replay")
    formats = exports.get("formats")
    if not isinstance(formats, Mapping) or set(formats) != {"json", "html", "csv"}:
        raise _oracle_mismatch("JSON/HTML/CSV export set is incomplete")
    for artifact_format, summary in formats.items():
        if not isinstance(summary, Mapping):
            raise _oracle_mismatch(f"{artifact_format} export summary is missing")
        _assert_equal(summary.get("replay_equal"), True, f"{artifact_format} replay")
        _assert_equal(summary.get("payload_sha256"), summary.get("replay_payload_sha256"), f"{artifact_format} payload replay")
        _assert_equal(summary.get("artifact_sha256"), summary.get("replay_artifact_sha256"), f"{artifact_format} artifact replay")
        _assert_sha(summary.get("payload_sha256"), f"{artifact_format} payload")
        _assert_sha(summary.get("artifact_sha256"), f"{artifact_format} artifact")
        _assert_sha(summary.get("content_sha256"), f"{artifact_format} content")
        if not isinstance(summary.get("content_bytes"), int) or summary["content_bytes"] <= 0:
            raise _oracle_mismatch(f"{artifact_format} export is empty")

    weekly = stages.get("weekly_review")
    if not isinstance(weekly, Mapping):
        raise _oracle_mismatch("weekly review stage is missing")
    initial = weekly.get("initial")
    complete = weekly.get("complete")
    reopen = weekly.get("reopen")
    for name, review in (("initial", initial), ("complete", complete), ("reopen", reopen)):
        if not isinstance(review, Mapping):
            raise _oracle_mismatch(f"weekly {name} review is missing")
        _assert_equal(review.get("is_pass"), False, f"weekly {name} pass")
        _assert_equal(review.get("coverage", {}).get("overall"), "PARTIAL", f"weekly {name} coverage")
        _assert_sha(review.get("snapshot_sha256"), f"weekly {name} snapshot")
    _assert_equal(initial.get("review_status"), "LIMITED", "weekly initial status")
    _assert_equal(complete.get("review_status"), "COMPLETED", "weekly complete status")
    _assert_equal(reopen.get("review_status"), "LIMITED", "weekly reopen status")
    _assert_equal(reopen.get("completion", {}).get("decision"), "REOPENED", "weekly reopen decision")
    _assert_equal(weekly.get("identity_preserved"), True, "weekly identity lineage")

    scope = report.get("scope_guard")
    if not isinstance(scope, Mapping):
        raise _oracle_mismatch("scope guard is missing")
    _assert_equal(scope.get("funding_transfer_schema_added"), False, "funding/transfer schema boundary")
    _assert_equal(scope.get("forbidden_event_types"), [], "forbidden event boundary")
    _assert_equal(scope.get("forbidden_schema_objects"), [], "forbidden schema boundary")
    _assert_equal(scope.get("forbidden_modules_loaded"), [], "runtime boundary")
    _assert_equal(scope.get("market_data_enabled"), False, "market data boundary")
    _assert_equal(scope.get("gateway_enabled"), False, "gateway boundary")

    claims = report.get("claims")
    if not isinstance(claims, Mapping) or any(value is not False for value in claims.values()):
        raise _oracle_mismatch("worker made a production or authority claim")
    return report


def _within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def run_packaged_audit(
    executable: Path,
    artifact: Path,
    output_dir: Path,
    *,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Invoke the selected packaged executable and write one new evidence file."""

    executable = _require_path(Path(executable), kind="executable")
    artifact = _require_path(Path(artifact), kind="artifact")
    output_dir = Path(output_dir).resolve()
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("output directory must be an existing regular directory")
    if _within(artifact, output_dir) or _within(output_dir, artifact):
        raise ValueError("output directory must be outside the packaged artifact")
    if timeout <= 0 or timeout > 900:
        raise ValueError("timeout must be between 0 and 900 seconds")

    fixture_sha256 = hashlib.sha256(SYNTHETIC_CSV).hexdigest()
    executable_sha256_before = _sha256_file(executable)
    artifact_sha256_before = _sha256_path(artifact)
    report_name = output_dir / "g0-g2-packaged-audit.json"

    with tempfile.TemporaryDirectory(prefix="kuantra-g0-g2-launch-") as temporary_name:
        temporary = Path(temporary_name)
        fixture = temporary / "synthetic.csv"
        fixture.write_bytes(SYNTHETIC_CSV)
        worker_report = temporary / "worker-report.json"
        unexpected_data = temporary / "unexpected-user-data"
        env = os.environ.copy()
        env.update({
            "KUANTRA_DATA_DIR": str(unexpected_data),
            "KUANTRA_MARKET_DATA_ENABLED": "false",
            "KUANTRA_GATEWAY_ENABLED": "false",
            "PYTHONUNBUFFERED": "1",
            "TMPDIR": str(temporary),
            "TMP": str(temporary),
            "TEMP": str(temporary),
        })
        command = [
            str(executable),
            "--g0-g2-audit",
            "--fixture",
            str(fixture),
            "--output",
            str(worker_report),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"packaged G0-G2 audit timed out after {timeout:g}s") from exc
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()[-4000:]
            stdout = (completed.stdout or "").strip()[-1000:]
            raise RuntimeError(
                f"packaged G0-G2 audit failed with exit code {completed.returncode}; "
                f"stdout={stdout!r}; stderr={stderr!r}"
            )
        if unexpected_data.exists():
            raise RuntimeError("packaged diagnostic touched the caller data directory")
        if not worker_report.is_file() or worker_report.is_symlink():
            raise RuntimeError("packaged diagnostic did not produce a worker report")
        try:
            report = json.loads(worker_report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("packaged diagnostic worker report is not valid JSON") from exc
        validate_worker_report(report, fixture_sha256=fixture_sha256, packaged=True)

    executable_sha256_after = _sha256_file(executable)
    artifact_sha256_after = _sha256_path(artifact)
    if executable_sha256_before != executable_sha256_after:
        raise RuntimeError("packaged executable changed during the audit")
    if artifact_sha256_before != artifact_sha256_after:
        raise RuntimeError("packaged artifact changed during the audit")

    result = {
        "schema_version": "P1-WP27.launcher.v1",
        "status": "PASS",
        "platform": {
            "os": platform.system(),
            "version": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "execution": {
            "executable": str(executable),
            "artifact": str(artifact),
            "executable_sha256": executable_sha256_before,
            "artifact_sha256": artifact_sha256_before,
            "executable_sha256_after": executable_sha256_after,
            "artifact_sha256_after": artifact_sha256_after,
            "hashes_stable": True,
            "artifact_executed": True,
            "source_to_binary_attestation": "NOT_VERIFIED",
            "release_provenance": "UNKNOWN",
            "data_directory_touched": False,
            "credentials_used": False,
            "network_used": False,
            "live_execution": False,
        },
        "oracle": {
            "status": "PASS",
            "fixture_sha256": fixture_sha256,
            "expected_trade": EXPECTED_TRADE,
            "expected_coverage": EXPECTED_COVERAGE,
        },
        "worker_report": report,
    }
    if report_name.exists() or report_name.is_symlink():
        raise ValueError("packaged audit output must be a new file")
    with report_name.open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run P1-WP27 packaged G0-G2 audit")
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    try:
        result = run_packaged_audit(
            args.executable,
            args.artifact,
            args.output_dir,
            timeout=args.timeout,
        )
    except Exception as exc:
        print(f"G0_G2_PACKAGED_AUDIT_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "G0_G2_PACKAGED_AUDIT_OK "
        + json.dumps(
            {
                "status": result["status"],
                "artifact_sha256": result["execution"]["artifact_sha256"],
                "executable_sha256": result["execution"]["executable_sha256"],
                "oracle": result["oracle"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
