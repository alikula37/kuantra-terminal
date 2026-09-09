"""Execute the explicit frozen application, retaining non-release evidence.

The artifact must contain the executable (a mounted DMG requires a separate mount
workflow). Checkout observations are not an embedded build attestation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import threading
import time
import subprocess
import sys
import tempfile

import psutil

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.build_provenance import _sha256_file, _sha256_path, collect_provenance


PROCESS_RESOURCE_SAMPLE_INTERVAL_SECONDS = 0.01


def _directory_size(path: Path) -> int | None:
    """Return regular-file bytes below an isolated temporary directory."""

    root = Path(path)
    if not root.exists() or root.is_symlink():
        return None
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = list(os.scandir(current))
        except OSError:
            return None
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
            except OSError:
                return None
    return total


class _ProcessResourceSampler:
    """Sample one packaged process and its isolated temporary footprint."""

    def __init__(self, pid: int, temporary_root: Path, *, interval_seconds: float = PROCESS_RESOURCE_SAMPLE_INTERVAL_SECONDS):
        self._temporary_root = Path(temporary_root)
        self._baseline_disk_bytes = _directory_size(self._temporary_root)
        self._interval_seconds = float(interval_seconds)
        self._stop = threading.Event()
        self._thread = None
        try:
            self._process = psutil.Process(pid)
            self._rss_reason = None
        except (psutil.Error, OSError) as exc:
            self._process = None
            self._rss_reason = type(exc).__name__
        self._peak_rss_mb = None
        self._peak_temp_disk_bytes = None
        self._rss_sample_count = 0
        self._temp_disk_sample_count = 0
        self._paired_sample_count = 0

    def _sample_once(self) -> None:
        rss_mb = None
        if self._process is not None:
            try:
                rss_mb = self._process.memory_info().rss / (1024 * 1024)
            except (psutil.Error, OSError) as exc:
                self._rss_reason = type(exc).__name__
        current_disk_bytes = _directory_size(self._temporary_root)
        temp_disk_bytes = (
            max(0, current_disk_bytes - self._baseline_disk_bytes)
            if current_disk_bytes is not None and self._baseline_disk_bytes is not None
            else None
        )
        if rss_mb is not None:
            self._peak_rss_mb = max(self._peak_rss_mb or 0.0, float(rss_mb))
            self._rss_sample_count += 1
        if temp_disk_bytes is not None:
            self._peak_temp_disk_bytes = max(
                self._peak_temp_disk_bytes or 0, int(temp_disk_bytes),
            )
            self._temp_disk_sample_count += 1
        if rss_mb is not None and temp_disk_bytes is not None:
            self._paired_sample_count += 1

    def _run(self) -> None:
        while not self._stop.is_set():
            self._sample_once()
            self._stop.wait(self._interval_seconds)

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="h07-process-resource-sampler", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._sample_once()

    def report(self) -> dict[str, object]:
        measured = self._peak_rss_mb is not None and self._peak_temp_disk_bytes is not None
        reason = None if measured else (
            "RSS_UNAVAILABLE" if self._peak_rss_mb is None else "TEMP_DISK_UNAVAILABLE"
        )
        return {
            "status": "MEASURED" if measured else "UNKNOWN",
            "reason": reason,
            "rss_source": "PSUTIL_PROCESS_MEMORY_INFO_RSS",
            "temp_disk_source": "ISOLATED_TEMP_DIR_OCCUPANCY",
            "sampling_interval_ms": round(self._interval_seconds * 1000.0, 4),
            "sample_count": self._paired_sample_count,
            "rss_sample_count": self._rss_sample_count,
            "temp_disk_sample_count": self._temp_disk_sample_count,
            "peak_rss_mb": round(self._peak_rss_mb, 4) if self._peak_rss_mb is not None else None,
            "peak_temp_disk_bytes": self._peak_temp_disk_bytes,
        }


def validate_worker(report, *, pid, executable, executable_sha256, size, expected_mode="mixed"):
    if not isinstance(report, dict):
        raise ValueError("worker report must be an object")
    execution = report.get("execution", {})
    if not isinstance(execution, dict):
        raise ValueError("worker execution must be an object")
    mode = report.get("mode", "mixed")
    if mode != expected_mode:
        raise ValueError("worker execution identity or isolation mismatch")
    workload_cache = {
        "mixed": "MIXED_AFTER_FIXTURE_IMPORT",
        "cold": "NEW_PROCESS_NO_WARMUP",
        "warm": "WARM_AFTER_WARMUP",
        "append-tail": "APPEND_TAIL_AFTER_WARMUP",
        "projection-rebuild": "PROJECTION_REBUILD_NO_WARMUP",
    }[mode]
    if (report.get("schema_version") != "H07.worker.v1"
            or report.get("status") != "MEASURED"
            or execution.get("mode") != "PACKAGED_PROCESS"
            or execution.get("artifact_executed") is not True
            or execution.get("pid") != pid
            or execution.get("executable") != str(executable)
            or execution.get("executable_sha256") != executable_sha256
            or execution.get("cold_process_measured") is not (mode in {"cold", "projection-rebuild"})
            or execution.get("os_cache") != "UNCONTROLLED"
            or execution.get("workload_cache") != workload_cache
            or report.get("network_guard") != "PYTHON_AUDIT_DENY"
            or report.get("runtime_modules_loaded") != []
            or report.get("support_limit_claim") is not False):
        raise ValueError("worker execution identity or isolation mismatch")
    run = report.get("run", {})
    if not isinstance(run, dict) or not isinstance(run.get("determinism"), dict):
        raise ValueError("worker dataset must be an object with determinism")
    expected_ledger_count = size + min(size, 3) + (1 if mode == "append-tail" else 0)
    if (run.get("size") != size or run.get("counts") != {
            "trades": size, "projections": size, "ledger_events": expected_ledger_count}
            or run.get("determinism", {}).get("status") != "COMPLETE"):
        raise ValueError("worker dataset outcome mismatch")
    if mode == "append-tail":
        verification = run.get("verification", {})
        if (verification.get("valid") is not True
                or verification.get("verification_mode") != "APPEND_TAIL"
                or not 0 < int(verification.get("verified_events_this_call", 0)) < expected_ledger_count):
            raise ValueError("append-tail verification did not attest a bounded tail")
    if mode == "projection-rebuild":
        rebuild = run.get("rebuild", {})
        if (not isinstance(rebuild, dict)
                or rebuild.get("ledger_valid") is not True
                or rebuild.get("projections_written") != size):
            raise ValueError("projection rebuild outcome is incomplete")
    operation_samples = run.get("operation_samples")
    if not isinstance(operation_samples, list) or not operation_samples:
        raise ValueError("worker operation samples are missing")


def run_packaged_mode(*, executable, artifact, evidence_dir, size=1000, repetitions=3,
                      timeout=1800, mode="mixed", fixture=None):
    executable, artifact = Path(executable).resolve(), Path(artifact).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("explicit executable is missing or not executable")
    if not artifact.is_dir() or not executable.is_relative_to(artifact):
        raise ValueError("artifact directory must contain the explicit executable")
    if mode not in {"mixed", "cold", "warm", "append-tail", "projection-rebuild"}:
        raise ValueError("unsupported packaged benchmark mode")
    if not 1 <= size <= 100_000 or not 1 <= repetitions <= 100:
        raise ValueError("invalid bounded workload")
    if mode == "mixed" and repetitions < 3:
        raise ValueError("mixed mode requires at least 3 repetitions")
    if mode in {"cold", "projection-rebuild"} and repetitions != 1:
        raise ValueError(f"{mode} mode requires exactly one repetition per process")
    if mode != "mixed":
        fixture = Path(fixture) if fixture is not None else None
        if fixture is None or fixture.is_symlink() or not fixture.is_file():
            raise ValueError("fixture mode requires an existing regular fixture")
        fixture = fixture.absolute()
    evidence_dir = Path(evidence_dir).resolve()
    if evidence_dir.is_relative_to(artifact):
        raise ValueError("evidence must be outside the measured artifact")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    before = {"executable": _sha256_file(executable), "artifact": _sha256_path(artifact)}
    if not all(before.values()):
        raise ValueError("cannot hash executable/artifact")
    fixture_sha_before = _sha256_file(fixture) if fixture is not None else None
    if fixture is not None and fixture_sha_before is None:
        raise ValueError("cannot hash synthetic fixture")
    output = evidence_dir / "worker.json"
    command = [str(executable), "--h07-benchmark", "--mode", mode,
               "--size", str(size), "--repetitions", str(repetitions),
               "--output", str(output)]
    if fixture is not None:
        command.extend(["--fixture", str(fixture)])
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="kuantra-h07-launch-") as temporary:
        temporary_root = Path(temporary)
        worker_tmp = temporary_root / "tmp"
        worker_tmp.mkdir()
        env = {
            **os.environ,
            "KUANTRA_DATA_DIR": str(temporary_root / "unexpected-data"),
            "KUANTRA_MARKET_DATA_ENABLED": "false",
            "KUANTRA_GATEWAY_ENABLED": "false",
            "TMPDIR": str(worker_tmp), "TMP": str(worker_tmp), "TEMP": str(worker_tmp),
        }
        with (evidence_dir / "process.log").open("xb") as log:
            process = subprocess.Popen(command, cwd=temporary, env=env, stdout=log, stderr=log)
            resource_sampler = _ProcessResourceSampler(process.pid, temporary_root)
            resource_sampler.start()
            try:
                returncode = process.wait(timeout=timeout)
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                resource_sampler.stop()
        process_resource = resource_sampler.report()
        process_elapsed_ms = round((time.perf_counter() - started) * 1000.0, 4)
        if returncode != 0:
            raise ValueError(f"worker exited {returncode}; no successful manifest")
        if (Path(temporary) / "unexpected-data").exists():
            raise ValueError("worker touched normal application data boundary")
    report = json.loads(output.read_text(encoding="utf-8"))
    validate_worker(report, pid=process.pid, executable=executable,
                    executable_sha256=before["executable"], size=size,
                    expected_mode=mode)
    after = {"executable": _sha256_file(executable), "artifact": _sha256_path(artifact)}
    if after != before:
        raise ValueError("executable/artifact changed during benchmark")
    if fixture is not None and _sha256_file(fixture) != fixture_sha_before:
        raise ValueError("synthetic fixture changed during benchmark")
    manifest = {
        "schema_version": "H07.packaged-manifest.v2", "status": "MEASURED",
        "mode": mode, "command": command, "pid": process.pid, "returncode": returncode,
        "process_elapsed_ms": process_elapsed_ms,
        "process_resource": process_resource,
        "hashes_before": before, "hashes_after": after,
        "fixture": str(fixture) if fixture is not None else None,
        "fixture_sha256": fixture_sha_before,
        "worker_file_sha256": _sha256_file(output),
        "process_log_sha256": _sha256_file(evidence_dir / "process.log"),
        "checkout_observation": collect_provenance(ROOT, executable=executable, artifact=artifact),
        "release_provenance": "UNKNOWN", "source_to_binary_attestation": "NOT_VERIFIED",
        "cold_process_measured": mode in {"cold", "projection-rebuild"},
        "support_limit_claim": False,
    }
    with (evidence_dir / "manifest.json").open("x", encoding="utf-8") as target:
        json.dump(manifest, target, sort_keys=True, indent=2, allow_nan=False)
    return manifest


def run_packaged(*, executable, artifact, evidence_dir, size=1000, repetitions=3, timeout=1800):
    """Backward-compatible mixed workload entry point."""
    return run_packaged_mode(
        executable=executable, artifact=artifact, evidence_dir=evidence_dir,
        size=size, repetitions=repetitions, timeout=timeout, mode="mixed",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True, help="new directory; never overwritten")
    parser.add_argument("--size", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--mode", choices=("mixed", "cold", "warm", "append-tail", "projection-rebuild"), default="mixed")
    parser.add_argument("--fixture", type=Path, default=None)
    args = parser.parse_args()
    run_packaged_mode(executable=args.executable, artifact=args.artifact,
                      evidence_dir=args.evidence_dir, size=args.size,
                      repetitions=args.repetitions, mode=args.mode, fixture=args.fixture)
    print(f"MEASURED: {args.evidence_dir / 'manifest.json'} (non-release; not cold-chain evidence)")


if __name__ == "__main__":
    main()
