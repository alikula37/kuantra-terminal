"""Process-only synthetic diagnostic. Importing this module has no app side effects.

Not a renderer smoke or a cold-chain benchmark. The shared workload imports its
fixture in this process before measuring reads; its caches are consequently mixed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import sys
import tempfile


def deny_external_io(event, args):
    # Defence in depth for this Python diagnostic, NOT an OS-level firewall.
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo",
                 "socket.sendto", "subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise RuntimeError("H07 diagnostic forbids network and child processes")


def bounded_int(low, high):
    def parse(value):
        result = int(value)
        if not low <= result <= high:
            raise argparse.ArgumentTypeError(f"expected {low}..{high}")
        return result
    return parse


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_fixture(path: Path, *, size: int, seed: str) -> dict[str, int | str]:
    """Accept only the bounded synthetic fixture contract; never initialize it."""

    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("fixture must be an existing regular file")
    from scripts.run_h07_benchmark import generate_trade_snapshot

    expected = {
        "trades": size,
        "evidence_trade_projections": size,
        "evidence_events": size + min(size, 3),
    }
    uri = f"file:{path}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            counts = {}
            for table, wanted in expected.items():
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                if counts[table] != wanted:
                    raise ValueError(f"fixture {table} count {counts[table]} != {wanted}")
            first_id = str(connection.execute(
                "SELECT id FROM trades WHERE id = ?", (generate_trade_snapshot(0, seed=seed)["id"],)
            ).fetchone()[0])
    except (sqlite3.DatabaseError, TypeError, ValueError, IndexError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("fixture "):
            raise
        raise ValueError("fixture is not a readable H07 synthetic database") from exc
    return {**counts, "first_trade_id": first_id, "fixture_sha256": _sha256_file(path)}


def _copy_fixture(source: Path, destination: Path) -> None:
    """Copy SQLite plus any WAL sidecars into the worker-owned temporary area."""

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{source}{suffix}")
        if candidate.exists():
            shutil.copy2(candidate, Path(f"{destination}{suffix}"))


def _timed_pack(adapter, trade_id: str, storage_dir: Path):
    from scripts.run_h07_benchmark import ResourceBudget, _timed_call
    return _timed_call(
        lambda resource_check: adapter.get_evidence_pack(
            trade_id, resource_check=resource_check,
        ),
        storage_dir=storage_dir,
        budget=ResourceBudget(),
        dynamic_resource_check=True,
    )


def _fixture_adapter(path: Path):
    from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
    from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
    from app.db.sqlite_driver import SQLiteDriver
    from app.services.trade_read_adapter import TradeReadAdapter

    driver = SQLiteDriver(str(path))
    ledger = EvidenceLedgerRepository(str(path))
    projection = EvidenceTradeProjectionRepository(str(path))
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=projection,
        ledger_repo=ledger,
        account_id="h07-synthetic-account",
        venue="h07-synthetic",
        projection_venues=("h07-synthetic",),
    )
    return driver, ledger, adapter


def _measurement_run(mode: str, *, fixture: Path, size: int, seed: str, repetitions: int, storage_dir: Path):
    from scripts.run_h07_benchmark import SYNTHETIC_ACCOUNT_ID, SYNTHETIC_VENUE, _summarize_samples, generate_trade_snapshot

    driver, ledger, adapter = _fixture_adapter(fixture)
    trade_id = str(generate_trade_snapshot(0, seed=seed)["id"])
    if mode == "cold":
        sample, pack = _timed_pack(adapter, trade_id, storage_dir)
        if not isinstance(pack, dict) or not pack.get("snapshot_sha256"):
            raise ValueError("cold Evidence Pack did not produce a snapshot")
        samples = [sample]
        return {
            "size": size,
            "counts": {"trades": size, "projections": size, "ledger_events": size + min(size, 3)},
            "operations": {"evidence_pack": _summarize_samples(samples)},
            "warmup": None,
            "cache_state": "NEW_PROCESS_NO_WARMUP",
            "operation_samples": samples,
            "determinism": {"status": "COMPLETE", "snapshot_sha256": pack["snapshot_sha256"]},
        }

    warmup_sample, warmup_pack = _timed_pack(adapter, trade_id, storage_dir)
    if not isinstance(warmup_pack, dict) or not warmup_pack.get("snapshot_sha256"):
        raise ValueError("warm-up Evidence Pack did not produce a snapshot")

    if mode == "warm":
        samples = []
        snapshots = {warmup_pack["snapshot_sha256"]}
        for _ in range(repetitions):
            sample, pack = _timed_pack(adapter, trade_id, storage_dir)
            if not isinstance(pack, dict) or not pack.get("snapshot_sha256"):
                raise ValueError("warm Evidence Pack did not produce a snapshot")
            snapshots.add(pack["snapshot_sha256"])
            samples.append(sample)
        if len(snapshots) != 1:
            raise ValueError("warm Evidence Pack snapshot was not deterministic")
        return {
            "size": size,
            "counts": {"trades": size, "projections": size, "ledger_events": size + min(size, 3)},
            "operations": {"evidence_pack": _summarize_samples(samples)},
            "warmup": warmup_sample,
            "cache_state": "WARM_AFTER_WARMUP",
            "operation_samples": samples,
            "determinism": {"status": "COMPLETE", "snapshot_sha256": warmup_pack["snapshot_sha256"]},
        }

    if mode != "append-tail":
        raise ValueError(f"unsupported fixture measurement mode: {mode}")

    source_events = ledger.list_events_for_trade(
        trade_id, account_id=SYNTHETIC_ACCOUNT_ID, venues=(SYNTHETIC_VENUE,),
    )
    if len(source_events) != 1:
        raise ValueError("append-tail source event is not unique")
    source_trade = driver.get_trade(trade_id)
    if source_trade is None:
        raise ValueError("append-tail source trade is missing")
    # The append occurs outside the timed verification call. The existing ledger
    # verifier has a valid prefix cached from warm-up, so verify_chain must inspect
    # only the new tail while preserving the immutable correction relation.
    driver.record_trade_with_evidence(
        dict(source_trade), event_type="TradeCorrected",
        idempotency_key=f"h07:{trade_id}:append-tail:{os.getpid()}",
        account_id=SYNTHETIC_ACCOUNT_ID, venue=SYNTHETIC_VENUE,
        occurred_at=str(source_trade["exit_time"]), received_at=str(source_trade["exit_time"]),
        causation_id=str(source_events[0]["event_id"]),
        provenance={
            "source": "h07-synthetic-append-tail",
            "dataset_seed": seed,
            "corrects_event_id": source_events[0]["event_id"],
            "corrects_event_hash": source_events[0]["event_hash"],
            "coverage": "COMPLETE",
        }, event_id=f"H07-APPEND-TAIL-{os.getpid()}",
    )
    sample, verification = __import__("scripts.run_h07_benchmark", fromlist=["_timed_call"])._timed_call(
        lambda resource_check: ledger.verify_chain(
            account_id=SYNTHETIC_ACCOUNT_ID, resource_check=resource_check,
        ),
        storage_dir=storage_dir,
        budget=__import__("scripts.run_h07_benchmark", fromlist=["ResourceBudget"]).ResourceBudget(),
        dynamic_resource_check=True,
    )
    if not isinstance(verification, dict) or verification.get("valid") is not True:
        raise ValueError("append-tail verification did not remain valid")
    if verification.get("verification_mode") != "APPEND_TAIL":
        raise ValueError("append-tail verification did not reuse a valid prefix")
    if not 0 < int(verification.get("verified_events_this_call", 0)) < size + min(size, 3) + 1:
        raise ValueError("append-tail verification inspected the full chain")
    return {
        "size": size,
        "counts": {"trades": size, "projections": size, "ledger_events": size + min(size, 3) + 1},
        "operations": {"ledger_verify_append_tail": _summarize_samples([sample])},
        "warmup": warmup_sample,
        "cache_state": "APPEND_TAIL_AFTER_WARMUP",
        "operation_samples": [sample],
        "verification": {
            "valid": True,
            "checked_events": verification.get("checked_events"),
            "verified_events_this_call": verification.get("verified_events_this_call"),
            "verification_mode": verification.get("verification_mode"),
        },
        "determinism": {"status": "COMPLETE", "snapshot_sha256": warmup_pack["snapshot_sha256"]},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="kuantra-terminal --h07-benchmark", allow_abbrev=False)
    parser.add_argument("--h07-benchmark", action="store_true", required=True)
    parser.add_argument("--size", type=bounded_int(1, 100_000), required=True)
    parser.add_argument("--mode", choices=("mixed", "cold", "warm", "append-tail"), default="mixed")
    parser.add_argument("--fixture", type=Path, default=None,
                        help="synthetic fixture supplied by the benchmark launcher")
    parser.add_argument("--seed", default="H07-SYNTHETIC-V1")
    parser.add_argument("--repetitions", type=bounded_int(1, 100), default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "mixed" and args.repetitions < 3:
        parser.error("mixed mode requires at least 3 repetitions")
    if args.mode != "mixed" and args.fixture is None:
        parser.error("fixture mode requires --fixture")
    if args.mode == "cold" and args.repetitions != 1:
        parser.error("cold mode requires exactly one repetition per process")
    if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
        parser.error("output must be a new file in an existing directory")
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    source_fixture = args.fixture if args.fixture is not None else None
    fixture_metadata = None
    # Fixture validation imports the benchmark's SQLite modules. Give those
    # imports a disposable data root before they can observe the caller's env.
    preflight = tempfile.TemporaryDirectory(prefix="kuantra-h07-preflight-")
    previous_data_dir = os.environ.get("KUANTRA_DATA_DIR")
    os.environ["KUANTRA_DATA_DIR"] = str(Path(preflight.name) / "data")
    try:
        if source_fixture is not None:
            fixture_metadata = _validate_fixture(source_fixture, size=args.size, seed=args.seed)
    finally:
        if previous_data_dir is None:
            os.environ.pop("KUANTRA_DATA_DIR", None)
        else:
            os.environ["KUANTRA_DATA_DIR"] = previous_data_dir
        preflight.cleanup()
    # O_EXCL rejects existing files and symlinks, including dangling symlinks.
    # The supplied fixture is copied into the worker-owned temporary directory.
    with args.output.open("x", encoding="utf-8") as output:
        with tempfile.TemporaryDirectory(prefix="kuantra-h07-worker-") as temporary:
            os.environ["KUANTRA_DATA_DIR"] = str(Path(temporary) / "data")
            os.environ["KUANTRA_MARKET_DATA_ENABLED"] = "false"
            os.environ["KUANTRA_GATEWAY_ENABLED"] = "false"
            # Windowed Windows builds have no stdout/stderr. Never create normal logs.
            if sys.stdout is None:
                sys.stdout = open(os.devnull, "w")
            if sys.stderr is None:
                sys.stderr = open(os.devnull, "w")
            sys.addaudithook(deny_external_io)
            if args.mode == "mixed":
                from scripts.run_h07_benchmark import H07BenchmarkRunner
                run = H07BenchmarkRunner(
                    seed=args.seed, operation_repetitions=args.repetitions,
                )._run_size(args.size, Path(temporary) / "synthetic.sqlite")
            else:
                working_fixture = Path(temporary) / "synthetic.sqlite"
                _copy_fixture(source_fixture, working_fixture)
                run = _measurement_run(
                    args.mode, fixture=working_fixture, size=args.size, seed=args.seed,
                    repetitions=args.repetitions, storage_dir=Path(temporary),
                )
            forbidden = sorted(set(sys.modules) & {"main", "desktop.runtime", "webview"})
            if forbidden:
                raise RuntimeError("H07 diagnostic unexpectedly loaded application runtime")
            frozen = bool(getattr(sys, "frozen", False))
            executable = Path(sys.executable).resolve()
            digest = hashlib.sha256()
            with executable.open("rb") as binary:
                for chunk in iter(lambda: binary.read(1024 * 1024), b""):
                    digest.update(chunk)
            report = {
                "schema_version": "H07.worker.v1", "status": "MEASURED",
                "execution": {
                    "mode": "PACKAGED_PROCESS" if frozen else "SOURCE_PROCESS",
                    "artifact_executed": frozen, "pid": os.getpid(),
                    "executable": str(executable), "executable_sha256": digest.hexdigest(),
                    "cold_process_measured": args.mode == "cold", "os_cache": "UNCONTROLLED",
                    "workload_cache": {
                        "mixed": "MIXED_AFTER_FIXTURE_IMPORT",
                        "cold": "NEW_PROCESS_NO_WARMUP",
                        "warm": "WARM_AFTER_WARMUP",
                        "append-tail": "APPEND_TAIL_AFTER_WARMUP",
                    }[args.mode],
                },
                "platform": {"os": platform.system(), "version": platform.release(),
                             "architecture": platform.machine(), "python": platform.python_version()},
                "network_guard": "PYTHON_AUDIT_DENY", "runtime_modules_loaded": forbidden,
                "mode": args.mode, "seed": args.seed,
                "fixture": fixture_metadata, "synthetic_directory": temporary, "run": run,
                "release_provenance": "UNKNOWN", "support_limit_claim": False,
            }
        # Only emit a completed report after our own temporary fixture is cleaned up.
        json.dump(report, output, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return 0
