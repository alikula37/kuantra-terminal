"""Run the H07 bounded synthetic trade-history benchmark.

This harness measures the canonical SQLite/evidence path on deterministic,
synthetic trade histories.  It deliberately does not start a market-data feed,
load credentials, or touch the developer's data directory.  Timing values are
measurements, not support promises; missing provenance or insufficient samples
remain UNKNOWN and never become a passing release claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import psutil

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.quant.candle_evidence import load_candle_evidence
from app.replay.replay_service import ReplaySession
from app.services.evidence_pack_export import EvidencePackExportService
from app.services.trade_read_adapter import TradeReadAdapter
from scripts.build_provenance import collect_provenance


MAX_SYNTHETIC_TRADES = 100_000
MAX_BATCH_SIZE = 5_000
MIN_PERCENTILE_SAMPLES = 3
DEFAULT_SEED = "H07-SYNTHETIC-V1"
DEFAULT_SIZES = (1_000, 10_000, 100_000)
SYNTHETIC_ACCOUNT_ID = "h07-synthetic-account"
SYNTHETIC_VENUE = "h07-synthetic"
SYNTHETIC_ADAPTER_VERSION = "h07-benchmark-v1"


class BenchmarkContractError(ValueError):
    """Raised when the benchmark contract cannot be evaluated safely."""


class BenchmarkCancelled(RuntimeError):
    """Expected cancellation of a synthetic operation."""


class BenchmarkResourceLimitError(BenchmarkContractError):
    """Raised when an explicitly configured benchmark budget is exceeded."""


def _require_size(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BenchmarkContractError("synthetic dataset size must be an integer")
    if value < 1 or value > MAX_SYNTHETIC_TRADES:
        raise BenchmarkContractError(
            f"synthetic dataset size must be between 1 and {MAX_SYNTHETIC_TRADES}"
        )
    return value


def _require_seed(seed: str) -> str:
    normalized = str(seed or "").strip()
    if not normalized:
        raise BenchmarkContractError("synthetic dataset seed is required")
    if len(normalized) > 128:
        raise BenchmarkContractError("synthetic dataset seed is too long")
    return normalized


def normalize_sizes(sizes: Iterable[int]) -> tuple[int, ...]:
    """Validate and sort benchmark sizes without silently expanding the scope."""

    values = tuple(sorted({_require_size(value) for value in sizes}))
    if not values:
        raise BenchmarkContractError("at least one synthetic dataset size is required")
    return values


def parse_sizes(value: str) -> tuple[int, ...]:
    try:
        return normalize_sizes(int(item.strip()) for item in str(value).split(",") if item.strip())
    except ValueError as exc:
        raise BenchmarkContractError("sizes must be comma-separated integers") from exc


def _seed_digest(seed: str) -> str:
    return hashlib.sha256(_require_seed(seed).encode("utf-8")).hexdigest()


def generate_trade_snapshot(index: int, *, seed: str = DEFAULT_SEED) -> dict[str, Any]:
    """Return one stable trade snapshot derived only from ``seed`` and ``index``."""

    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise BenchmarkContractError("synthetic trade index must be a non-negative integer")
    normalized_seed = _require_seed(seed)
    digest = hashlib.sha256(f"{normalized_seed}:{index}".encode("utf-8")).digest()
    seed_token = _seed_digest(normalized_seed)[:10]
    side = "BUY" if digest[0] % 2 == 0 else "SELL"
    symbol = "BTCUSDT" if digest[1] % 2 == 0 else "ETHUSDT"
    entry_price = round(100.0 + (int.from_bytes(digest[2:6], "big") % 250_000) / 100.0, 2)
    move = round(0.25 + (digest[6] % 1200) / 100.0, 2)
    exit_price = round(entry_price + move if side == "BUY" else entry_price - move, 2)
    qty = round(0.01 + (digest[7] % 500) / 100.0, 4)
    pnl = round(move * qty if side == "BUY" else move * qty * -1.0, 4)
    commission = round(0.01 + (digest[8] % 25) / 100.0, 4)
    entry_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)
    exit_at = entry_at + timedelta(minutes=2)
    entry_time = entry_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
    exit_time = exit_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return {
        "id": f"H07-{seed_token}-{index:06d}",
        "symbol": symbol,
        "side": side,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "qty": qty,
        "stop_loss": round(entry_price * 0.99, 2),
        "take_profit": round(entry_price * 1.01, 2),
        "entry_time": entry_time,
        "exit_time": exit_time,
        "status": "CLOSED",
        "pnl": pnl,
        "r_multiple": round(pnl / max(commission, 0.01), 4),
        "commission": commission,
        "notes": f"H07 synthetic fixture {seed_token}",
    }


def benchmark_snapshot_digest(rows: Iterable[Mapping[str, Any]]) -> str:
    """Hash rows in canonical ID order so input permutation cannot alter the digest."""

    normalized = [dict(row) for row in rows]
    normalized.sort(key=lambda row: str(row.get("id") or ""))
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def _streaming_dataset_digest(size: int, seed: str) -> str:
    digest = hashlib.sha256()
    for index in range(size):
        row = generate_trade_snapshot(index, seed=seed)
        digest.update(canonical_json(row).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def percentile(values: Sequence[float], percent: float) -> float:
    """Return a deterministic linearly interpolated percentile."""

    if not values:
        raise BenchmarkContractError("cannot calculate a percentile from no samples")
    if percent < 0 or percent > 100:
        raise BenchmarkContractError("percentile must be between 0 and 100")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 10)
    position = (len(ordered) - 1) * (percent / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 10)


def _directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    for child in path.rglob("*"):
        try:
            if child.is_file():
                total += child.stat().st_size
        except OSError:
            continue
    return total


def _rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


@dataclass(frozen=True)
class ResourceBudget:
    """Optional, explicit benchmark budget; absent budgets remain measurement-only."""

    max_rss_mb: Optional[float] = None
    max_temp_disk_bytes: Optional[int] = None

    def check(self, *, rss_mb: float, temp_disk_bytes: int) -> None:
        if self.max_rss_mb is not None and rss_mb > self.max_rss_mb:
            raise BenchmarkResourceLimitError(
                f"RSS resource budget exceeded: {rss_mb:.2f} MB > {self.max_rss_mb:.2f} MB"
            )
        if self.max_temp_disk_bytes is not None and temp_disk_bytes > self.max_temp_disk_bytes:
            raise BenchmarkResourceLimitError(
                "temporary disk resource budget exceeded: "
                f"{temp_disk_bytes} > {self.max_temp_disk_bytes} bytes"
            )


class CancellationToken:
    """Small cooperative cancellation boundary for bounded local operations."""

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise BenchmarkCancelled("synthetic benchmark operation cancelled")


def _summarize_samples(samples: Sequence[Mapping[str, Any]], *, expected_status: str = "SUCCESS") -> dict[str, Any]:
    if not samples:
        return {
            "sample_count": 0,
            "status": "UNKNOWN",
            "reason": "NO_SAMPLES",
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "peak_rss_mb": None,
            "peak_temp_disk_bytes": None,
        }
    elapsed = [float(sample["elapsed_ms"]) for sample in samples]
    statuses = {str(sample.get("status") or "UNKNOWN") for sample in samples}
    measured = len(samples) >= MIN_PERCENTILE_SAMPLES
    if statuses != {expected_status}:
        status = "FAILED"
        reason = "UNEXPECTED_OPERATION_STATUS"
    elif not measured:
        status = "UNKNOWN"
        reason = "INSUFFICIENT_SAMPLES"
    else:
        status = "MEASURED"
        reason = None
    return {
        "sample_count": len(samples),
        "status": status,
        "reason": reason,
        "expected_status": expected_status,
        "p50_ms": round(percentile(elapsed, 50), 4),
        "p95_ms": round(percentile(elapsed, 95), 4),
        "p99_ms": round(percentile(elapsed, 99), 4),
        "peak_rss_mb": round(max(float(sample["rss_mb"]) for sample in samples), 4),
        "peak_temp_disk_bytes": max(int(sample["temp_disk_bytes"]) for sample in samples),
    }


def _timed_call(
    callback: Callable[[], Any],
    *,
    storage_dir: Path,
    budget: ResourceBudget,
    expected_status: str = "SUCCESS",
) -> tuple[dict[str, Any], Any]:
    before_disk = _directory_size(storage_dir)
    started = time.perf_counter()
    status = expected_status
    result: Any = None
    try:
        result = callback()
        if isinstance(result, Mapping) and result.get("status"):
            status = str(result["status"])
    except BenchmarkCancelled:
        status = "CANCELLED"
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    after_disk = _directory_size(storage_dir)
    sample = {
        "elapsed_ms": round(elapsed_ms, 4),
        "rss_mb": round(_rss_mb(), 4),
        "temp_disk_bytes": max(0, after_disk - before_disk),
        "status": status,
    }
    budget.check(rss_mb=sample["rss_mb"], temp_disk_bytes=sample["temp_disk_bytes"])
    return sample, result


def _command_for_trade(trade: Mapping[str, Any], index: int, *, seed: str) -> dict[str, Any]:
    trade_id = str(trade["id"])
    return {
        "trade": dict(trade),
        "normalized_payload": {"trade": dict(trade)},
        "event_type": "LegacyTradeImported",
        "account_id": SYNTHETIC_ACCOUNT_ID,
        "venue": SYNTHETIC_VENUE,
        "idempotency_key": f"h07:{trade_id}:import",
        "event_id": f"H07-EVENT-{index:06d}",
        "occurred_at": trade["entry_time"],
        "received_at": trade["entry_time"],
        "schema_version": "1",
        "adapter_version": SYNTHETIC_ADAPTER_VERSION,
        "correlation_id": trade_id,
        "provenance": {
            "source": "h07-synthetic-fixture",
            "dataset_seed": seed,
            "coverage": "COMPLETE",
        },
    }


def _synthetic_replay_candles(
    trade: Mapping[str, Any],
    *,
    lookback_bars: int = 2,
    lookforward_bars: int = 2,
) -> list[dict[str, Any]]:
    """Build bounded, deterministic OHLC fixtures for the recorded-bar replay path."""

    entry_at = datetime.fromisoformat(str(trade["entry_time"]).replace("Z", "+00:00"))
    exit_at = datetime.fromisoformat(str(trade["exit_time"]).replace("Z", "+00:00"))
    entry_second = int(entry_at.timestamp())
    exit_second = int(exit_at.timestamp())
    start = (entry_second // 60) * 60 - lookback_bars * 60
    end = ((exit_second + 59) // 60) * 60 + lookforward_bars * 60
    entry_price = float(trade["entry_price"])
    symbol = str(trade["symbol"])
    candles: list[dict[str, Any]] = []
    for offset, timestamp in enumerate(range(start, end, 60)):
        base = entry_price + (offset - lookback_bars) * 0.05
        close = base + 0.02
        candles.append({
            "time": timestamp,
            "symbol": symbol,
            "timeframe": "1m",
            "open": round(base, 6),
            "high": round(max(base, close) + 0.05, 6),
            "low": round(min(base, close) - 0.05, 6),
            "close": round(close, 6),
            "volume": 1.0,
        })
    return candles


def _synthetic_replay_snapshot(trade: Mapping[str, Any]) -> dict[str, Any]:
    candles = _synthetic_replay_candles(trade)
    evidence = load_candle_evidence(
        dict(trade),
        candles=candles,
        lookback_bars=2,
        lookforward_bars=2,
    )
    session = ReplaySession(f"H07-REPLAY-{trade['id']}", evidence)
    session.current_index = min(session.exit_index, session.entry_index + 1)
    return session.to_dict()


def _cancel_probe(size: int) -> dict[str, Any]:
    token = CancellationToken()
    cancel_at = max(1, min(size // 2, 1_000))
    processed = 0
    try:
        for index in range(size):
            if index == cancel_at:
                token.cancel()
            token.raise_if_cancelled()
            processed += 1
    except BenchmarkCancelled:
        return {"status": "CANCELLED", "processed": processed, "writes": 0}
    return {"status": "COMPLETED", "processed": processed, "writes": 0}


class H07BenchmarkRunner:
    """Execute bounded synthetic operations against an isolated SQLite database."""

    def __init__(
        self,
        *,
        seed: str = DEFAULT_SEED,
        batch_size: int = 1_000,
        operation_repetitions: int = 3,
        budget: Optional[ResourceBudget] = None,
    ) -> None:
        self.seed = _require_seed(seed)
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise BenchmarkContractError(
                f"batch size must be between 1 and {MAX_BATCH_SIZE}"
            )
        if isinstance(operation_repetitions, bool) or not isinstance(operation_repetitions, int) or operation_repetitions < MIN_PERCENTILE_SAMPLES:
            raise BenchmarkContractError(
                f"operation repetitions must be at least {MIN_PERCENTILE_SAMPLES}"
            )
        self.batch_size = batch_size
        self.operation_repetitions = operation_repetitions
        self.budget = budget or ResourceBudget()

    def _run_size(self, size: int, db_path: Path) -> dict[str, Any]:
        size = _require_size(size)
        db_path = Path(db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        driver = SQLiteDriver(str(db_path))
        ingest_samples: list[dict[str, Any]] = []
        for start in range(0, size, self.batch_size):
            end = min(size, start + self.batch_size)
            trades = [
                generate_trade_snapshot(index, seed=self.seed)
                for index in range(start, end)
            ]
            commands = [
                _command_for_trade(trade, index, seed=self.seed)
                for index, trade in zip(range(start, end), trades)
            ]
            sample, persisted = _timed_call(
                lambda commands=commands: driver.record_grouped_evidence_batch(commands),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if not isinstance(persisted, list) or len(persisted) != len(commands):
                raise BenchmarkContractError("synthetic import did not persist the complete batch")
            ingest_samples.append(sample)

        ledger_count = self._table_count(db_path, "evidence_events")
        trade_count = self._table_count(db_path, "trades")
        if ledger_count != size or trade_count != size:
            raise BenchmarkContractError(
                f"synthetic import count mismatch: events={ledger_count}, trades={trade_count}, expected={size}"
            )

        projection = EvidenceTradeProjectionRepository(str(db_path))
        adapter = TradeReadAdapter(
            legacy_driver=driver,
            projection_repo=projection,
            account_id=SYNTHETIC_ACCOUNT_ID,
            venue=SYNTHETIC_VENUE,
            projection_venues=(SYNTHETIC_VENUE,),
        )
        rebuild_samples: list[dict[str, Any]] = []
        rebuild_reports: list[dict[str, Any]] = []
        for _ in range(self.operation_repetitions):
            sample, rebuild_report = _timed_call(
                lambda: projection.rebuild(account_id=SYNTHETIC_ACCOUNT_ID, dry_run=True),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            rebuild_samples.append(sample)
            rebuild_reports.append(dict(rebuild_report))
        if not rebuild_reports or rebuild_reports[-1].get("projections_written") != size:
            raise BenchmarkContractError("projection rebuild did not cover the synthetic history")

        apply_sample, apply_report = _timed_call(
            lambda: projection.rebuild(account_id=SYNTHETIC_ACCOUNT_ID, dry_run=False),
            storage_dir=db_path.parent,
            budget=self.budget,
        )
        rebuild_samples.append(apply_sample)
        rebuild_reports.append(dict(apply_report))

        coverage = adapter.coverage()
        if not coverage.get("ready"):
            raise BenchmarkContractError(f"synthetic projection coverage is not ready: {coverage}")

        query_samples: list[dict[str, Any]] = []
        for _ in range(self.operation_repetitions):
            sample, rows = _timed_call(
                lambda: adapter.list_trades(limit=min(100, size), order_by_utc=True),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if not isinstance(rows, list) or len(rows) != min(100, size):
                raise BenchmarkContractError("synthetic query returned an unexpected row count")
            query_samples.append(sample)

        ledger = EvidenceLedgerRepository(str(db_path))
        correction_specs: list[dict[str, Any]] = []
        for offset in range(self.operation_repetitions):
            correction_index = (size // 2 + offset) % size
            source_trade = generate_trade_snapshot(correction_index, seed=self.seed)
            source_events = ledger.list_events_for_trade(
                source_trade["id"],
                account_id=SYNTHETIC_ACCOUNT_ID,
                venues=(SYNTHETIC_VENUE,),
            )
            if len(source_events) != 1:
                raise BenchmarkContractError(
                    "synthetic correction source event lookup is not unique"
                )
            correction_specs.append({
                "index": correction_index,
                "trade": source_trade,
                "source_event": source_events[0],
                "idempotency_key": f"h07:{source_trade['id']}:correction",
                "event_id": f"H07-CORRECTION-{correction_index:06d}",
                "correction": {
                    "id": source_trade["id"],
                    "exit_price": round(float(source_trade["exit_price"]) + 0.01, 2),
                    "pnl": round(float(source_trade["pnl"]) + 0.01, 4),
                    "commission": round(float(source_trade["commission"]) + 0.001, 4),
                    "status": "CLOSED",
                },
            })

        def _persist_correction(spec: Mapping[str, Any]) -> dict[str, Any]:
            source_event = spec["source_event"]
            saved = driver.record_trade_with_evidence(
                dict(spec["correction"]),
                event_type="TradeCorrected",
                idempotency_key=str(spec["idempotency_key"]),
                account_id=SYNTHETIC_ACCOUNT_ID,
                venue=SYNTHETIC_VENUE,
                occurred_at=str(spec["trade"]["exit_time"]),
                received_at=str(spec["trade"]["exit_time"]),
                causation_id=str(source_event["event_id"]),
                provenance={
                    "source": "h07-synthetic-correction",
                    "dataset_seed": self.seed,
                    "corrects_event_id": source_event["event_id"],
                    "corrects_event_hash": source_event["event_hash"],
                    "coverage": "COMPLETE",
                },
                event_id=str(spec["event_id"]),
            )
            return {"saved": saved}

        correction_samples: list[dict[str, Any]] = []
        correction_records: list[dict[str, Any]] = []
        for spec in correction_specs:
            sample, result = _timed_call(
                lambda spec=spec: _persist_correction(spec),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if not isinstance(result, dict) or not isinstance(result.get("saved"), dict):
                raise BenchmarkContractError("synthetic correction did not return a trade snapshot")
            correction_event = ledger.get_event_by_identity(
                SYNTHETIC_ACCOUNT_ID,
                SYNTHETIC_VENUE,
                "TradeCorrected",
                str(spec["idempotency_key"]),
            )
            if correction_event is None:
                raise BenchmarkContractError("synthetic correction did not create immutable evidence")
            correction_records.append({
                "event_id": correction_event["event_id"],
                "event_hash": correction_event["event_hash"],
                "causation_id": correction_event["causation_id"],
            })
            correction_samples.append(sample)

        corrected_ledger_count = self._table_count(db_path, "evidence_events")
        expected_corrected_count = size + self.operation_repetitions
        if corrected_ledger_count != expected_corrected_count:
            raise BenchmarkContractError(
                "synthetic correction count mismatch: "
                f"events={corrected_ledger_count}, expected={expected_corrected_count}"
            )

        correction_replay_samples: list[dict[str, Any]] = []
        for spec in correction_specs:
            sample, result = _timed_call(
                lambda spec=spec: _persist_correction(spec),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if not isinstance(result, dict) or not isinstance(result.get("saved"), dict):
                raise BenchmarkContractError("synthetic correction replay did not return a trade snapshot")
            correction_replay_samples.append(sample)

        replay_ledger_count = self._table_count(db_path, "evidence_events")
        if replay_ledger_count != corrected_ledger_count:
            raise BenchmarkContractError("synthetic correction replay was not idempotent")

        recorded_replay_samples: list[dict[str, Any]] = []
        recorded_replay_snapshots: list[dict[str, Any]] = []
        representative_id = str(correction_specs[0]["trade"]["id"])
        corrected_trade = driver.get_trade(representative_id)
        if corrected_trade is None:
            raise BenchmarkContractError("synthetic corrected trade is not readable")
        for _ in range(self.operation_repetitions):
            sample, replay_value = _timed_call(
                lambda corrected_trade=corrected_trade: _synthetic_replay_snapshot(corrected_trade),
                storage_dir=db_path.parent,
                budget=self.budget,
                expected_status="READY",
            )
            if not isinstance(replay_value, dict) or replay_value.get("status") != "READY":
                raise BenchmarkContractError("synthetic recorded replay did not become READY")
            if recorded_replay_snapshots and replay_value != recorded_replay_snapshots[0]:
                raise BenchmarkContractError("synthetic recorded replay snapshot is not deterministic")
            recorded_replay_snapshots.append(replay_value)
            recorded_replay_samples.append(sample)

        coverage = adapter.coverage()
        if not coverage.get("ready"):
            raise BenchmarkContractError(f"synthetic post-correction projection coverage is not ready: {coverage}")

        pack_samples: list[dict[str, Any]] = []
        export_samples: list[dict[str, Any]] = []
        exporter = EvidencePackExportService(adapter)
        pack: Optional[dict[str, Any]] = None
        artifact: Optional[Any] = None
        for _ in range(self.operation_repetitions):
            sample, pack_value = _timed_call(
                lambda: adapter.get_evidence_pack(representative_id),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if not isinstance(pack_value, dict) or not pack_value.get("snapshot_sha256"):
                raise BenchmarkContractError("synthetic Evidence Pack has no snapshot digest")
            if pack is None:
                pack = pack_value
            elif pack_value != pack:
                raise BenchmarkContractError("repeated Evidence Pack snapshot is not deterministic")
            pack_samples.append(sample)

            sample, artifact_value = _timed_call(
                lambda: exporter.export(representative_id, "json"),
                storage_dir=db_path.parent,
                budget=self.budget,
            )
            if artifact is None:
                artifact = artifact_value
            elif artifact_value.content != artifact.content:
                raise BenchmarkContractError("repeated Evidence Pack export is not deterministic")
            export_samples.append(sample)

        cancel_samples: list[dict[str, Any]] = []
        cancel_results: list[dict[str, Any]] = []
        for _ in range(self.operation_repetitions):
            sample, cancel_result = _timed_call(
                lambda: _cancel_probe(size),
                storage_dir=db_path.parent,
                budget=self.budget,
                expected_status="CANCELLED",
            )
            cancel_samples.append(sample)
            if not isinstance(cancel_result, dict) or cancel_result.get("status") != "CANCELLED":
                raise BenchmarkContractError("cancellation probe completed instead of cancelling")
            cancel_results.append(cancel_result)

        dataset_digest = _streaming_dataset_digest(size, self.seed)
        deterministic_body = {
            "size": size,
            "seed": self.seed,
            "dataset_digest": dataset_digest,
            "trade_count": trade_count,
            "ledger_count": corrected_ledger_count,
            "coverage": coverage,
            "rebuild": rebuild_reports[-1],
            "representative_trade_id": representative_id,
            "correction_records": correction_records,
            "correction_replay_status": "IDEMPOTENT",
            "recorded_replay_fingerprint": (
                recorded_replay_snapshots[0].get("replay_fingerprint")
                if recorded_replay_snapshots
                else None
            ),
            "evidence_pack_snapshot_sha256": pack["snapshot_sha256"] if pack else None,
            "evidence_artifact_sha256": artifact.artifact_sha256 if artifact else None,
            "cancel_status": cancel_results[0]["status"] if cancel_results else "UNKNOWN",
            "cancel_writes": cancel_results[0].get("writes") if cancel_results else None,
        }
        deterministic_digest = hashlib.sha256(canonical_json(deterministic_body).encode("utf-8")).hexdigest()
        return {
            "size": size,
            "dataset": {
                "seed": self.seed,
                "count": size,
                "sha256": dataset_digest,
            },
            "counts": {
                "trades": trade_count,
                "ledger_events": corrected_ledger_count,
                "projections": coverage.get("projected_count"),
            },
            "operations": {
                "import": _summarize_samples(ingest_samples),
                "projection_rebuild": _summarize_samples(rebuild_samples),
                "query": _summarize_samples(query_samples),
                "correction": _summarize_samples(correction_samples),
                "correction_replay": _summarize_samples(correction_replay_samples),
                "replay": _summarize_samples(recorded_replay_samples, expected_status="READY"),
                "evidence_pack": _summarize_samples(pack_samples),
                "evidence_pack_export": _summarize_samples(export_samples),
                "cancel": _summarize_samples(cancel_samples, expected_status="CANCELLED"),
            },
            "coverage": coverage,
            "determinism": {
                "status": "COMPLETE",
                "snapshot_sha256": deterministic_digest,
                "evidence_pack_snapshot_sha256": pack["snapshot_sha256"] if pack else None,
                "evidence_artifact_sha256": artifact.artifact_sha256 if artifact else None,
            },
        }

    @staticmethod
    def _table_count(db_path: Path, table: str) -> int:
        allowed = {"trades", "evidence_events"}
        if table not in allowed:
            raise BenchmarkContractError("unsupported benchmark table count")
        import sqlite3

        with sqlite3.connect(str(db_path)) as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def run(
        self,
        sizes: Iterable[int],
        *,
        work_dir: Optional[Path] = None,
        executable: Optional[Path] = None,
        artifact: Optional[Path] = None,
    ) -> dict[str, Any]:
        normalized_sizes = normalize_sizes(sizes)
        owns_temp_dir = work_dir is None
        temporary: Optional[tempfile.TemporaryDirectory[str]] = None
        if work_dir is None:
            temporary = tempfile.TemporaryDirectory(prefix="kuantra-h07-")
            work_dir = Path(temporary.name)
        else:
            work_dir = Path(work_dir).resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
        try:
            runs = [
                self._run_size(size, work_dir / f"h07-{size}.sqlite")
                for size in normalized_sizes
            ]
            provenance = collect_provenance(
                ROOT_DIR,
                executable=executable,
                artifact=artifact,
            )
            provenance["artifact_status"] = (
                "COMPLETE"
                if provenance.get("executable_sha256") and provenance.get("artifact_sha256")
                else "UNKNOWN"
            )
            report = build_benchmark_report(
                seed=self.seed,
                sizes=normalized_sizes,
                provenance=provenance,
                runs=runs,
            )
            validate_benchmark_report(report)
            return report
        finally:
            if owns_temp_dir and temporary is not None:
                temporary.cleanup()


def build_benchmark_report(
    *,
    seed: str,
    sizes: Iterable[int],
    provenance: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_sizes = normalize_sizes(sizes)
    normalized_seed = _require_seed(seed)
    report = {
        "schema_version": "H07.v1",
        "status": "MEASURED",
        "contract": {
            "real_data": False,
            "credentials": False,
            "network": False,
            "live_execution": False,
            "support_limit_claim": False,
        },
        "dataset": {
            "seed": normalized_seed,
            "sizes": list(normalized_sizes),
        },
        "provenance": dict(provenance),
        "runs": [dict(run) for run in runs],
        "determinism": {
            "status": "COMPLETE" if all(
                str(run.get("determinism", {}).get("status")) == "COMPLETE"
                for run in runs
            ) and len(runs) == len(normalized_sizes) else "UNKNOWN",
            "run_snapshot_sha256": [
                run.get("determinism", {}).get("snapshot_sha256")
                for run in runs
            ],
        },
    }
    return report


def validate_benchmark_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(report, Mapping):
        raise BenchmarkContractError("benchmark report must be an object")
    if report.get("schema_version") != "H07.v1":
        raise BenchmarkContractError("benchmark report schema version is unsupported")
    dataset = report.get("dataset")
    if not isinstance(dataset, Mapping):
        raise BenchmarkContractError("benchmark dataset metadata is required")
    sizes = normalize_sizes(dataset.get("sizes", ()))
    if not str(dataset.get("seed") or "").strip():
        raise BenchmarkContractError("benchmark dataset seed is required")
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        raise BenchmarkContractError("benchmark provenance is required")
    required_provenance = (
        "source_commit_sha",
        "checkout_commit_sha",
        "source_commit_matches_checkout",
        "tracked_source_tree_status",
        "tracked_source_tree_sha256",
        "lock_hashes",
        "toolchain",
        "os",
        "architecture",
    )
    missing = [key for key in required_provenance if key not in provenance or not provenance.get(key)]
    if missing:
        raise BenchmarkContractError(
            "benchmark provenance is incomplete: " + ", ".join(missing)
        )
    if not isinstance(provenance.get("lock_hashes"), Mapping):
        raise BenchmarkContractError("benchmark provenance lock_hashes must be an object")
    if any(
        not str(provenance["lock_hashes"].get(key) or "").strip()
        for key in ("backend_requirements_lock_sha256", "frontend_package_lock_sha256")
    ):
        raise BenchmarkContractError("benchmark provenance lock hashes are incomplete")
    if not isinstance(provenance.get("toolchain"), Mapping):
        raise BenchmarkContractError("benchmark provenance toolchain must be an object")
    if any(
        not str(provenance["toolchain"].get(key) or "").strip()
        for key in ("python", "node", "npm", "uv", "pyinstaller")
    ):
        raise BenchmarkContractError("benchmark provenance toolchain is incomplete")
    if provenance.get("artifact_status") not in {"COMPLETE", "UNKNOWN"}:
        raise BenchmarkContractError("benchmark artifact provenance status is missing")
    if provenance.get("tracked_source_tree_status") not in {"clean", "dirty"}:
        raise BenchmarkContractError("benchmark tracked source tree status is invalid")
    runs = report.get("runs")
    if not isinstance(runs, Sequence) or isinstance(runs, (str, bytes)):
        raise BenchmarkContractError("benchmark runs are required")
    run_sizes = tuple(sorted(int(run.get("size")) for run in runs if isinstance(run, Mapping) and run.get("size") is not None))
    if run_sizes != sizes:
        raise BenchmarkContractError("benchmark runs do not cover the declared dataset sizes")
    contract = report.get("contract")
    if not isinstance(contract, Mapping) or any(contract.get(key) is not False for key in (
        "real_data", "credentials", "network", "live_execution", "support_limit_claim"
    )):
        raise BenchmarkContractError("benchmark contract must remain non-production and synthetic")
    return report


def write_benchmark_report(path: Path, report: Mapping[str, Any]) -> str:
    validate_benchmark_report(report)
    body = canonical_json(dict(report)).encode("utf-8")
    report_sha256 = hashlib.sha256(body).hexdigest()
    envelope = dict(report)
    envelope["report_sha256"] = report_sha256
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(envelope) + "\n", encoding="utf-8")
    return report_sha256


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Kuantra H07 bounded synthetic benchmark")
    parser.add_argument("--sizes", default=",".join(str(size) for size in DEFAULT_SIZES))
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "dist" / "h07-benchmark-report.json")
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--executable", type=Path, default=None)
    parser.add_argument("--artifact", type=Path, default=None)
    parser.add_argument("--max-rss-mb", type=float, default=None)
    parser.add_argument("--max-temp-disk-bytes", type=int, default=None)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        sizes = parse_sizes(args.sizes)
        runner = H07BenchmarkRunner(
            seed=args.seed,
            batch_size=args.batch_size,
            operation_repetitions=args.repetitions,
            budget=ResourceBudget(
                max_rss_mb=args.max_rss_mb,
                max_temp_disk_bytes=args.max_temp_disk_bytes,
            ),
        )
        report = runner.run(
            sizes,
            work_dir=args.work_dir,
            executable=args.executable,
            artifact=args.artifact,
        )
        report_sha256 = write_benchmark_report(args.output, report)
    except (BenchmarkContractError, OSError, RuntimeError) as exc:
        print(f"[h07] FAIL-CLOSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": report["status"],
        "sizes": report["dataset"]["sizes"],
        "determinism": report["determinism"],
        "report": str(args.output),
        "report_sha256": report_sha256,
        "network": report["contract"]["network"],
        "credentials": report["contract"]["credentials"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
