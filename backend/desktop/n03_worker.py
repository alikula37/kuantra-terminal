"""Process-only N03 synthetic persistence worker.

The worker is launched by the installed packaged executable and is deliberately
separate from the normal desktop lifecycle.  ``seed`` writes one synthetic
value-chain snapshot to an explicitly empty private data directory; ``reopen``
reads that same directory in a new process and verifies the immutable evidence
and review lineage.  It never accepts credentials, starts a connector, or uses
the caller's normal data directory implicitly.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator, Mapping

from desktop.g0_g2_worker import (
    _export_view,
    _malformed_fixture,
    _review_view,
    _schema_scope,
    _sha256_file,
    _require_fixture,
    deny_external_io,
)


_FORBIDDEN_SCOPE_TEXT = ("funding", "transfer")
_FORBIDDEN_MODULES = frozenset({"main", "desktop.runtime", "webview"})
_REVIEW_KWARGS = {
    "period_start": "2026-09-08",
    "period_end": "2026-09-09",
    "timezone_name": "UTC",
    "as_of_utc": "2099-01-01T00:00:00Z",
}


def _private_data_dir(path: Path, *, phase: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() or candidate.is_symlink():
        raise ValueError("N03 data directory must be an absolute non-symlink path")
    if not candidate.exists():
        candidate.mkdir(parents=True, mode=0o700)
    if not candidate.is_dir():
        raise ValueError("N03 data directory must be a directory")
    if os.name != "nt":
        mode = candidate.stat().st_mode & 0o777
        if mode & 0o077:
            raise ValueError("N03 data directory must be owner-only")
    if phase == "seed" and any(candidate.iterdir()):
        raise ValueError("N03 seed requires an empty data directory")
    return candidate.resolve()


@contextmanager
def _isolated_environment(data_dir: Path) -> Iterator[None]:
    keys = ("KUANTRA_DATA_DIR", "KUANTRA_MARKET_DATA_ENABLED", "KUANTRA_GATEWAY_ENABLED")
    previous = {key: os.environ.get(key) for key in keys}
    os.environ["KUANTRA_DATA_DIR"] = str(data_dir)
    os.environ["KUANTRA_MARKET_DATA_ENABLED"] = "false"
    os.environ["KUANTRA_GATEWAY_ENABLED"] = "false"
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _components(database_path: Path) -> Iterator[tuple[Any, ...]]:
    """Load app services with explicit per-audit drivers, never global user paths."""

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
        yield (
            driver,
            EvidenceLedgerRepository,
            EvidenceTradeProjectionRepository,
            csv_trade_importer,
            EvidencePackExportService,
            TradeReadAdapter,
            WeeklyReviewService,
        )
    finally:
        csv_importer_module.sqlite_driver = previous_csv_driver
        sync_pipeline_module.sqlite_driver = previous_pipeline_driver
        sync_pipeline_module.duckdb_driver = previous_duckdb_driver


def _scope_guard(ledger: Any, database_path: Path, before_modules: set[str]) -> dict[str, Any]:
    event_types = sorted({str(event.get("event_type")) for event in ledger.export_events()})
    schema_tables, forbidden_schema_objects = _schema_scope(database_path)
    forbidden_event_types = [
        event_type
        for event_type in event_types
        if any(token in event_type.lower() for token in _FORBIDDEN_SCOPE_TEXT)
    ]
    forbidden_modules = sorted((set(sys.modules) & _FORBIDDEN_MODULES) - before_modules)
    if forbidden_event_types or forbidden_schema_objects or forbidden_modules:
        raise ValueError(
            "N03 audit crossed a disabled or out-of-scope boundary: "
            f"events={forbidden_event_types}, schema={forbidden_schema_objects}, "
            f"modules={forbidden_modules}"
        )
    return {
        "event_types": event_types,
        "schema_tables": schema_tables,
        "forbidden_event_types": forbidden_event_types,
        "forbidden_schema_objects": forbidden_schema_objects,
        "forbidden_modules_loaded": forbidden_modules,
        "funding_transfer_schema_added": bool(forbidden_schema_objects),
        "market_data_enabled": False,
        "gateway_enabled": False,
    }


def _export_views(adapter: Any, exporter_cls: Any, trade_id: str) -> dict[str, Any]:
    exporter = exporter_cls(adapter)
    views: dict[str, Any] = {}
    for artifact_format in ("json", "html", "csv"):
        first = exporter.export(trade_id, artifact_format)
        replay = exporter.export(trade_id, artifact_format)
        view = _export_view(first, replay)
        if not view["replay_equal"]:
            raise ValueError(f"{artifact_format} Evidence Pack export was not deterministic")
        views[artifact_format] = view
    return {
        "formats": views,
        "replay_equal": all(view["replay_equal"] for view in views.values()),
    }


def _pack_and_review(
    *,
    driver: Any,
    ledger_cls: Any,
    projection_cls: Any,
    importer: Any,
    exporter_cls: Any,
    adapter_cls: Any,
    review_cls: Any,
    database_path: Path,
    fixture_sha256: str,
    before_modules: set[str],
    expected_trade_id: str | None = None,
    phase: str,
) -> dict[str, Any]:
    trades = driver.list_trades(limit=100)
    if len(trades) != 1:
        raise ValueError(f"N03 {phase} expected exactly one persisted trade, got {len(trades)}")
    trade_id = str(trades[0]["id"])
    if expected_trade_id is not None and trade_id != expected_trade_id:
        raise ValueError("N03 reopen changed the persisted trade identity")

    ledger = ledger_cls(str(database_path))
    projection = projection_cls(str(database_path))
    adapter = adapter_cls(legacy_driver=driver, projection_repo=projection, ledger_repo=ledger)
    events = ledger.list_events_for_trade(trade_id)
    if len(events) != 1:
        raise ValueError(f"N03 {phase} expected one source event, got {len(events)}")
    source_event = events[0]
    provenance = source_event.get("provenance") or {}
    if provenance.get("source_file_sha256") != fixture_sha256:
        raise ValueError("N03 source fixture provenance changed across process boundary")

    review_service = review_cls(ledger_repo=ledger)
    review = review_service.build_review(**_REVIEW_KWARGS)
    review_trace: dict[str, Any] = {"initial": _review_view(review)}
    if review.get("review_status") != "LIMITED":
        raise ValueError(f"N03 {phase} review is not LIMITED")
    if phase == "seed":
        complete_decision = review_service.record_decision(
            review, decision="COMPLETE", note="synthetic N03 audit"
        )
        completed_review = review_service.build_review(**_REVIEW_KWARGS)
        reopen_decision = review_service.record_decision(
            completed_review, decision="REOPEN", note="synthetic N03 audit reopen"
        )
        review = review_service.build_review(**_REVIEW_KWARGS)
        review_trace.update(
            {
                "complete_decision": complete_decision,
                "complete": _review_view(completed_review),
                "reopen_decision": reopen_decision,
                "reopen": _review_view(review),
            }
        )
    else:
        completion = review.get("completion") or {}
        if completion.get("decision") != "REOPENED":
            raise ValueError("N03 reopen did not preserve the REOPENED review")
        review_trace["reopen"] = _review_view(review)
    if review.get("review_status") != "LIMITED" or review.get("is_pass") is not False:
        raise ValueError("N03 review converted incomplete coverage into PASS")
    if phase == "reopen" and (review.get("completion") or {}).get("decision") != "REOPENED":
        raise ValueError("N03 reopen did not preserve the REOPENED LIMITED review")
    if review.get("is_pass") is not False:
        raise ValueError("N03 review converted incomplete coverage into PASS")

    # Build the persisted pack after review decisions.  Review decisions are
    # immutable ledger events; computing the pack before them would make its
    # ledger-integrity count differ after a process reopen even though the
    # source trade/evidence is unchanged.
    first_pack = adapter.get_evidence_pack(trade_id)
    replay_pack = adapter.get_evidence_pack(trade_id)
    if first_pack != replay_pack:
        raise ValueError("N03 Evidence Pack replay was not deterministic")

    scope_guard = _scope_guard(ledger, database_path, before_modules)
    return {
        "phase": phase.upper(),
        "status": "PASS",
        "data": {
            "data_directory": str(database_path.parent),
            "database_path": str(database_path),
            "trade_count": len(trades),
            "ledger_event_count": len(list(ledger.export_events())),
            "database_sha256": _sha256_file(database_path),
        },
        "trade": {
            "id": trade_id,
            "symbol": trades[0]["symbol"],
            "side": trades[0]["side"],
            "qty": trades[0]["qty"],
            "pnl": trades[0]["pnl"],
            "commission": trades[0]["commission"],
            "status": trades[0]["status"],
        },
        "evidence_pack": {
            "read_source": first_pack["read_source"],
            "event_count": first_pack["event_count"],
            "snapshot_sha256": first_pack["snapshot_sha256"],
            "source_event_hashes": sorted(
                str(event["event_hash"])
                for event in first_pack["events"]
                if event.get("event_hash")
            ),
            "coverage_summary": first_pack["coverage_summary"],
            "ledger_integrity": first_pack["ledger_integrity"],
            "replay_equal": first_pack == replay_pack,
            "exports": _export_views(adapter, exporter_cls, trade_id),
        },
        "weekly_review": _review_view(review),
        "review_trace": review_trace,
        "scope_guard": scope_guard,
    }


def run_seed(fixture: Path, data_dir: Path) -> dict[str, Any]:
    fixture_path, content, fixture_sha256 = _require_fixture(Path(fixture))
    target = _private_data_dir(Path(data_dir), phase="seed")
    database_path = target / "kuantra_oltp.sqlite3"
    before_modules = set(sys.modules) & _FORBIDDEN_MODULES
    with _isolated_environment(target):
        with _components(database_path) as (
            driver,
            ledger_cls,
            projection_cls,
            importer,
            exporter_cls,
            adapter_cls,
            review_cls,
        ):
            if driver.list_trades(limit=100) or database_path.stat().st_size <= 0:
                raise ValueError("N03 seed data directory was not empty before import")
            clean_preview = importer.parse_and_preview_csv(content, "n03-synthetic.csv")
            malformed_preview = importer.parse_and_preview_csv(
                _malformed_fixture(content), "n03-malformed.csv"
            )
            if driver.list_trades(limit=100):
                raise ValueError("N03 preview mutated the empty data directory")
            malformed_review = malformed_preview["import_review"]
            if (
                malformed_review["coverage"].get("status") != "UNKNOWN"
                or malformed_review["decision"] != "IMPORT_BLOCKED"
            ):
                raise ValueError("N03 malformed preview did not remain UNKNOWN/IMPORT_BLOCKED")
            result = importer.parse_and_import_csv(content, "n03-synthetic.csv")
            if not result.get("success") or int(result.get("imported") or 0) != 1:
                raise ValueError("N03 seed did not import exactly one synthetic trade")
            chain = _pack_and_review(
                driver=driver,
                ledger_cls=ledger_cls,
                projection_cls=projection_cls,
                importer=importer,
                exporter_cls=exporter_cls,
                adapter_cls=adapter_cls,
                review_cls=review_cls,
                database_path=database_path,
                fixture_sha256=fixture_sha256,
                before_modules=before_modules,
                phase="seed",
            )
            if clean_preview["import_review"]["status"] != "READY":
                raise ValueError("N03 clean preview was not READY")
            chain["preview"] = {
                "clean_status": clean_preview["import_review"]["status"],
                "clean_decision": clean_preview["import_review"]["decision"],
                "malformed_status": malformed_review["status"],
                "malformed_coverage_status": malformed_review["coverage"].get("status"),
                "malformed_decision": malformed_review["decision"],
                "malformed_db_trade_count": 0,
            }
            chain["fixture"] = {
                "path": str(fixture_path),
                "sha256": fixture_sha256,
                "bytes": len(content),
            }
            chain["execution"] = {
                "mode": "PACKAGED_PROCESS" if getattr(sys, "frozen", False) else "SOURCE_PROCESS",
                "artifact_executed": bool(getattr(sys, "frozen", False)),
                "pid": os.getpid(),
                "executable": str(Path(sys.executable).resolve()),
                "executable_sha256": (
                    _sha256_file(Path(sys.executable).resolve())
                    if Path(sys.executable).is_file()
                    else None
                ),
                "source_to_binary_attestation": "NOT_VERIFIED",
                "release_provenance": "UNKNOWN",
            }
            chain["contract"] = {
                "real_data": False,
                "credentials": False,
                "network": False,
                "live_execution": False,
                "production_claim": False,
            }
            return chain


def run_reopen(fixture: Path, data_dir: Path) -> dict[str, Any]:
    _fixture_path, _content, fixture_sha256 = _require_fixture(Path(fixture))
    target = _private_data_dir(Path(data_dir), phase="reopen")
    database_path = target / "kuantra_oltp.sqlite3"
    if not database_path.is_file():
        raise ValueError("N03 reopen requires the seed database")
    before_modules = set(sys.modules) & _FORBIDDEN_MODULES
    with _isolated_environment(target):
        with _components(database_path) as (
            driver,
            ledger_cls,
            projection_cls,
            importer,
            exporter_cls,
            adapter_cls,
            review_cls,
        ):
            chain = _pack_and_review(
                driver=driver,
                ledger_cls=ledger_cls,
                projection_cls=projection_cls,
                importer=importer,
                exporter_cls=exporter_cls,
                adapter_cls=adapter_cls,
                review_cls=review_cls,
                database_path=database_path,
                fixture_sha256=fixture_sha256,
                before_modules=before_modules,
                phase="reopen",
            )
            chain["fixture"] = {"sha256": fixture_sha256, "bytes": len(_content)}
            chain["execution"] = {
                "mode": "PACKAGED_PROCESS" if getattr(sys, "frozen", False) else "SOURCE_PROCESS",
                "artifact_executed": bool(getattr(sys, "frozen", False)),
                "pid": os.getpid(),
                "executable": str(Path(sys.executable).resolve()),
                "executable_sha256": (
                    _sha256_file(Path(sys.executable).resolve())
                    if Path(sys.executable).is_file()
                    else None
                ),
                "source_to_binary_attestation": "NOT_VERIFIED",
                "release_provenance": "UNKNOWN",
            }
            chain["contract"] = {
                "real_data": False,
                "credentials": False,
                "network": False,
                "live_execution": False,
                "production_claim": False,
            }
            return chain


def _write_new_json(path: Path, payload: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("output must be a new file in an existing directory")
    with path.open("x", encoding="utf-8") as output:
        import json

        json.dump(payload, output, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kuantra-terminal --n03-audit", allow_abbrev=False)
    parser.add_argument("--n03-audit", action="store_true", required=True)
    parser.add_argument("--phase", choices=("seed", "reopen"), required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.fixture.is_absolute() or not args.data_dir.is_absolute() or not args.output.is_absolute():
        parser.error("fixture, data-dir and output must be absolute paths")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    sys.addaudithook(deny_external_io)
    try:
        report = (
            run_seed(args.fixture, args.data_dir)
            if args.phase == "seed"
            else run_reopen(args.fixture, args.data_dir)
        )
    except Exception as exc:  # pragma: no cover - packaged failure is asserted by launcher
        print(f"N03_AUDIT_FAIL {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1
    _write_new_json(args.output, report)
    print("N03_AUDIT_OK " + __import__("json").dumps(report, sort_keys=True), flush=True)
    return 0


__all__ = ["main", "run_reopen", "run_seed"]
