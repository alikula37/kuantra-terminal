"""Process-only G0-G2 synthetic value-chain diagnostic.

The diagnostic intentionally lives outside the normal desktop lifecycle.  It
creates a disposable SQLite database, exercises the already bounded import,
read, export, and weekly-review contracts, and emits only a small JSON summary.
It is an evidence tool, not a product capability and not a release attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
from typing import Any, Mapping


_FORBIDDEN_AUDIT_EVENTS = frozenset({
    "socket.connect",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.sendto",
    "subprocess.Popen",
    "os.system",
    "os.posix_spawn",
})
_FORBIDDEN_MODULES = frozenset({"main", "desktop.runtime", "webview"})
_FORBIDDEN_SCOPE_TEXT = ("funding", "transfer")


def deny_external_io(event: str, _args: Any) -> None:
    """Defence-in-depth guard for the packaged diagnostic process.

    This is a Python audit-hook boundary, not an OS-level firewall.  The
    launcher also disables market data and gateway behavior through environment
    variables, and the worker never accepts credentials or network inputs.
    """

    if event in _FORBIDDEN_AUDIT_EVENTS:
        raise RuntimeError("G0-G2 diagnostic forbids network and child processes")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_fixture(path: Path) -> tuple[Path, bytes, str]:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_file():
        raise ValueError("fixture must be an existing regular file")
    content = candidate.read_bytes()
    if not content:
        raise ValueError("fixture must not be empty")
    return candidate, content, hashlib.sha256(content).hexdigest()


def _malformed_fixture(content: bytes) -> bytes:
    """Create a deterministic invalid numeric field without adding a write."""

    for needle in (b",100,", b",100.0,", b",102,", b",102.0,"):
        replacement = needle.replace(needle.split(b",")[1], b"not-a-number")
        mutated = content.replace(needle, replacement, 1)
        if mutated != content:
            return mutated
    raise ValueError("synthetic fixture has no bounded numeric field to corrupt")


def _trade_count(driver: Any) -> int:
    return len(driver.list_trades(limit=100))


def _review_view(review: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "review_id": review.get("review_id"),
        "review_status": review.get("review_status"),
        "completion_allowed": review.get("completion_allowed"),
        "is_pass": review.get("is_pass"),
        "snapshot_sha256": review.get("snapshot_sha256"),
        "source_event_hashes": review.get("source_event_hashes"),
        "coverage": review.get("coverage"),
        "warnings": review.get("warnings"),
        "completion": review.get("completion"),
    }


def _export_view(artifact: Any, replay: Any) -> dict[str, Any]:
    return {
        "payload_sha256": artifact.payload_sha256,
        "artifact_sha256": artifact.artifact_sha256,
        "content_sha256": hashlib.sha256(artifact.content).hexdigest(),
        "content_bytes": len(artifact.content),
        "replay_equal": artifact.content == replay.content,
        "replay_payload_sha256": replay.payload_sha256,
        "replay_artifact_sha256": replay.artifact_sha256,
    }


def _schema_scope(db_path: Path) -> tuple[list[str], list[str]]:
    with sqlite3.connect(db_path) as connection:
        names = sorted(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        )
    forbidden = [
        name for name in names
        if any(token in name.lower() for token in _FORBIDDEN_SCOPE_TEXT)
    ]
    return names, forbidden


def run_audit(fixture: Path, *, network_guard: str = "SOURCE_UNIT_BOUNDARY") -> dict[str, Any]:
    """Run the bounded chain against a clean, temporary database.

    The function is directly testable from source.  Packaged execution calls it
    only after installing :func:`deny_external_io` and before normal app startup.
    """

    _fixture_path, content, fixture_sha256 = _require_fixture(Path(fixture))
    preexisting_forbidden_modules = set(sys.modules) & _FORBIDDEN_MODULES
    previous_environment = {
        key: os.environ.get(key)
        for key in ("KUANTRA_DATA_DIR", "KUANTRA_MARKET_DATA_ENABLED", "KUANTRA_GATEWAY_ENABLED")
    }
    temporary_root = tempfile.TemporaryDirectory(prefix="kuantra-g0-g2-")
    temporary = Path(temporary_root.name)
    database_path = temporary / "synthetic.sqlite"
    try:
        # Set this before any app database module is imported.  The caller's
        # data directory is deliberately never used by this diagnostic.
        os.environ["KUANTRA_DATA_DIR"] = str(temporary / "data")
        os.environ["KUANTRA_MARKET_DATA_ENABLED"] = "false"
        os.environ["KUANTRA_GATEWAY_ENABLED"] = "false"

        from app.db import sync_pipeline as sync_pipeline_module
        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
        from app.db.sqlite_driver import SQLiteDriver
        from app.services import csv_importer as csv_importer_module
        from app.services.csv_importer import csv_trade_importer
        from app.services.evidence_pack_export import EvidencePackExportService
        from app.services.trade_read_adapter import TradeReadAdapter
        from app.services.weekly_review import WeeklyReviewService

        driver = SQLiteDriver(str(database_path))
        previous_csv_driver = csv_importer_module.sqlite_driver
        previous_pipeline_driver = sync_pipeline_module.sqlite_driver
        previous_duckdb_driver = sync_pipeline_module.duckdb_driver
        csv_importer_module.sqlite_driver = driver
        sync_pipeline_module.sqlite_driver = driver
        sync_pipeline_module.duckdb_driver = SimpleNamespace(is_available=False)
        try:
            clean_before = _trade_count(driver)
            clean_preview = csv_trade_importer.parse_and_preview_csv(content, "g0-g2-synthetic.csv")
            clean_after = _trade_count(driver)

            malformed_before = _trade_count(driver)
            malformed_preview = csv_trade_importer.parse_and_preview_csv(
                _malformed_fixture(content), "g0-g2-malformed.csv"
            )
            malformed_after = _trade_count(driver)

            import_result = csv_trade_importer.parse_and_import_csv(
                content, "g0-g2-synthetic.csv"
            )
            if not import_result.get("success") or int(import_result.get("imported") or 0) != 1:
                raise ValueError("clean synthetic import did not import exactly one trade")
            imported_trades = import_result.get("trades")
            if not isinstance(imported_trades, list) or len(imported_trades) != 1:
                raise ValueError("clean synthetic import did not return one trade")
            trade_id = str(imported_trades[0]["id"])

            ledger = EvidenceLedgerRepository(str(database_path))
            projection = EvidenceTradeProjectionRepository(str(database_path))
            adapter = TradeReadAdapter(
                legacy_driver=driver,
                projection_repo=projection,
                ledger_repo=ledger,
            )
            source_events = ledger.list_events_for_trade(trade_id)
            if len(source_events) != 1:
                raise ValueError("clean synthetic import did not produce one source event")
            source_event = source_events[0]

            first_pack = adapter.get_evidence_pack(trade_id)
            replay_pack = adapter.get_evidence_pack(trade_id)
            if first_pack != replay_pack:
                raise ValueError("Evidence Pack replay was not deterministic")

            exporter = EvidencePackExportService(adapter)
            export_views: dict[str, dict[str, Any]] = {}
            for artifact_format in ("json", "html", "csv"):
                first_artifact = exporter.export(trade_id, artifact_format)
                replay_artifact = exporter.export(trade_id, artifact_format)
                export_views[artifact_format] = _export_view(
                    first_artifact, replay_artifact
                )
                if not export_views[artifact_format]["replay_equal"]:
                    raise ValueError(f"{artifact_format} Evidence Pack export was not deterministic")

            review_service = WeeklyReviewService(ledger_repo=ledger)
            review_kwargs = {
                "period_start": "2026-09-08",
                "period_end": "2026-09-09",
                "timezone_name": "UTC",
                "as_of_utc": "2099-01-01T00:00:00Z",
            }
            initial_review = review_service.build_review(**review_kwargs)
            complete_decision = review_service.record_decision(
                initial_review, decision="COMPLETE", note="synthetic G0-G2 audit"
            )
            completed_review = review_service.build_review(**review_kwargs)
            reopen_decision = review_service.record_decision(
                completed_review, decision="REOPEN", note="synthetic G0-G2 audit reopen"
            )
            reopened_review = review_service.build_review(**review_kwargs)
            identity_preserved = (
                initial_review["review_id"] == completed_review["review_id"] == reopened_review["review_id"]
                and initial_review["snapshot_sha256"]
                == completed_review["snapshot_sha256"]
                == reopened_review["snapshot_sha256"]
                and initial_review["source_event_hashes"]
                == reopened_review["source_event_hashes"]
                and reopened_review.get("completion", {}).get("decision") == "REOPENED"
            )
            if not identity_preserved:
                raise ValueError("weekly review identity or snapshot lineage changed")

            event_types = sorted({str(event.get("event_type")) for event in ledger.export_events()})
            schema_tables, forbidden_schema_objects = _schema_scope(database_path)
            forbidden_event_types = [
                event_type for event_type in event_types
                if any(token in event_type.lower() for token in _FORBIDDEN_SCOPE_TEXT)
            ]
            forbidden_modules = sorted(
                (set(sys.modules) & _FORBIDDEN_MODULES) - preexisting_forbidden_modules
            )
            scope_guard = {
                "event_types": event_types,
                "schema_tables": schema_tables,
                "forbidden_event_types": forbidden_event_types,
                "forbidden_schema_objects": forbidden_schema_objects,
                "funding_transfer_schema_added": bool(forbidden_schema_objects),
                "forbidden_modules_loaded": forbidden_modules,
                "market_data_enabled": False,
                "gateway_enabled": False,
            }
            if forbidden_event_types or forbidden_schema_objects or forbidden_modules:
                raise ValueError(
                    "G0-G2 audit crossed a disabled or out-of-scope boundary: "
                    f"events={forbidden_event_types}, "
                    f"schema={forbidden_schema_objects}, modules={forbidden_modules}"
                )

            frozen = bool(getattr(sys, "frozen", False))
            executable = Path(sys.executable).resolve()
            execution = {
                "mode": "PACKAGED_PROCESS" if frozen else "SOURCE_PROCESS",
                "artifact_executed": frozen,
                "pid": os.getpid(),
                "executable": str(executable),
                "executable_sha256": _sha256_file(executable) if executable.is_file() else None,
                "source_to_binary_attestation": "NOT_VERIFIED",
                "release_provenance": "UNKNOWN",
            }
            report = {
                "schema_version": "P1-WP27.worker.v1",
                "status": "PASS",
                "execution": execution,
                "platform": {
                    "os": platform.system(),
                    "version": platform.release(),
                    "architecture": platform.machine(),
                    "python": platform.python_version(),
                },
                "network_guard": network_guard,
                "fixture": {"sha256": fixture_sha256, "bytes": len(content)},
                "contract": {
                    "real_data": False,
                    "credentials": False,
                    "network": False,
                    "live_execution": False,
                    "production_claim": False,
                },
                "stages": {
                    "clean_preview": {
                        "status": clean_preview["import_review"]["status"],
                        "decision": clean_preview["import_review"]["decision"],
                        "db_trade_count_before": clean_before,
                        "db_trade_count_after": clean_after,
                        "coverage": clean_preview["import_review"]["coverage"],
                    },
                    "malformed_preview": {
                        "status": malformed_preview["import_review"]["status"],
                        "decision": malformed_preview["import_review"]["decision"],
                        "errors_count": malformed_preview["errors_count"],
                        "db_trade_count_before": malformed_before,
                        "db_trade_count_after": malformed_after,
                        "coverage": malformed_preview["import_review"]["coverage"],
                        "discrepancies": malformed_preview["import_review"]["discrepancies"],
                    },
                    "import": {
                        "success": import_result["success"],
                        "imported": import_result["imported"],
                        "duplicates_skipped": import_result["duplicates_skipped"],
                        "trade_id": trade_id,
                        "trade": imported_trades[0],
                        "source_file_sha256": import_result["source_file_sha256"],
                        "event_count": len(source_events),
                        "source_event_id": source_event["event_id"],
                        "source_event_hash": source_event["event_hash"],
                        "source_event_provenance": source_event["provenance"],
                    },
                    "evidence_pack": {
                        "read_source": first_pack["read_source"],
                        "event_count": first_pack["event_count"],
                        "snapshot_sha256": first_pack["snapshot_sha256"],
                        "coverage_summary": first_pack["coverage_summary"],
                        "ledger_integrity": first_pack["ledger_integrity"],
                        "source_event_hashes": sorted(
                            str(event["event_hash"])
                            for event in first_pack["events"]
                            if event.get("event_hash")
                        ),
                        "import_review_source_file_sha256": (
                            first_pack.get("import_review") or {}
                        ).get("source_file_sha256"),
                        "replay_equal": first_pack == replay_pack,
                    },
                    "exports": {
                        "formats": export_views,
                        "replay_equal": all(
                            view["replay_equal"] for view in export_views.values()
                        ),
                    },
                    "weekly_review": {
                        "period": review_kwargs,
                        "initial": _review_view(initial_review),
                        "complete_decision": complete_decision,
                        "complete": _review_view(completed_review),
                        "reopen_decision": reopen_decision,
                        "reopen": _review_view(reopened_review),
                        "identity_preserved": identity_preserved,
                    },
                },
                "scope_guard": scope_guard,
                "claims": {
                    "production_ready": False,
                    "commercial_support": False,
                    "full_account_pnl": False,
                    "venue_complete": False,
                    "live_execution": False,
                    "ai_order_authority": False,
                    "release_provenance": False,
                },
            }
            return report
        finally:
            csv_importer_module.sqlite_driver = previous_csv_driver
            sync_pipeline_module.sqlite_driver = previous_pipeline_driver
            sync_pipeline_module.duckdb_driver = previous_duckdb_driver
    finally:
        for key, value in previous_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        temporary_root.cleanup()


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("output must be a new file in an existing directory")
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kuantra-terminal --g0-g2-audit", allow_abbrev=False
    )
    parser.add_argument("--g0-g2-audit", action="store_true", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.output.is_absolute():
        parser.error("output must be an absolute path")
    if not args.fixture.is_absolute():
        parser.error("fixture must be an absolute path")

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    sys.addaudithook(deny_external_io)
    try:
        report = run_audit(args.fixture, network_guard="PYTHON_AUDIT_DENY")
    except Exception as exc:  # pragma: no cover - exercised by packaged preflight failures
        print(f"G0_G2_AUDIT_FAIL {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    _write_new_json(args.output, report)
    print("G0_G2_AUDIT_OK " + json.dumps(report, sort_keys=True), flush=True)
    return 0


__all__ = ["deny_external_io", "main", "run_audit"]
