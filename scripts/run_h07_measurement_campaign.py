"""Run the H07 packaged cold/warm/append-tail measurement protocol.

This is a non-release diagnostic. It prepares a synthetic SQLite fixture in a
temporary source process, then launches the explicit packaged executable for
each measured sample. The OS page cache is deliberately not controlled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_h07_packaged_benchmark import run_packaged_mode
from scripts.build_provenance import _sha256_file, _sha256_path, collect_provenance


DEFAULT_OUTPUT = ROOT / "artifacts" / "evidence" / "h07" / "measurement-campaign"
DEFAULT_SEED = "H07-SYNTHETIC-V1"


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _summary(values, *, expected_status="SUCCESS"):
    if not values:
        return {"status": "UNKNOWN", "reason": "NO_SAMPLES", "sample_count": 0,
                "p50_ms": None, "p95_ms": None, "p99_ms": None,
                "peak_rss_mb": None, "peak_temp_disk_bytes": None,
                "resource_status": "UNKNOWN", "resource_reason": "NO_SAMPLES"}
    ordered = sorted(float(value["elapsed_ms"]) for value in values)

    def percentile(percent):
        position = (len(ordered) - 1) * percent / 100.0
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 4)

    statuses = {str(value.get("status") or "UNKNOWN") for value in values}
    measured = len(values) >= 3 and statuses == {expected_status}
    resource_values = [
        value for value in values
        if value.get("rss_mb") is not None and value.get("temp_disk_bytes") is not None
    ]
    resource_complete = len(resource_values) == len(values)
    return {
        "status": "MEASURED" if measured else "UNKNOWN" if statuses == {expected_status} else "FAILED",
        "reason": None if measured else "INSUFFICIENT_SAMPLES" if statuses == {expected_status} else "UNEXPECTED_OPERATION_STATUS",
        "sample_count": len(values),
        "p50_ms": percentile(50), "p95_ms": percentile(95), "p99_ms": percentile(99),
        "peak_rss_mb": round(max(float(value["rss_mb"]) for value in resource_values), 4) if resource_values else None,
        "peak_temp_disk_bytes": max(int(value["temp_disk_bytes"]) for value in resource_values) if resource_values else None,
        "resource_status": "MEASURED" if resource_complete else "UNKNOWN",
        "resource_reason": None if resource_complete else "MISSING_RESOURCE_SAMPLES",
    }


def _read_sample(evidence_dir: Path, manifest: dict, *, mode: str) -> dict:
    worker_path = evidence_dir / "worker.json"
    worker = json.loads(worker_path.read_text(encoding="utf-8"))
    run = worker.get("run")
    if not isinstance(run, dict) or run.get("size") is None:
        raise ValueError("worker run is missing")
    samples = run.get("operation_samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("worker operation samples are missing")
    return {
        "mode": mode,
        "pid": manifest["pid"],
        "worker_execution": worker["execution"],
        "operation_samples": samples,
        "warmup": run.get("warmup"),
        "cache_state": run.get("cache_state"),
        "counts": run["counts"],
        "determinism": run["determinism"],
        "verification": run.get("verification"),
        "rebuild": run.get("rebuild"),
        "process_elapsed_ms": manifest["process_elapsed_ms"],
        "process_resource": manifest.get("process_resource"),
        "worker_file_sha256": manifest["worker_file_sha256"],
        "process_log_sha256": manifest["process_log_sha256"],
        "manifest_path": str(evidence_dir / "manifest.json"),
    }


def _mode_result(samples: list[dict], *, mode: str, evidence_root: Path) -> dict:
    operation_samples = [
        item
        for sample in samples
        for item in sample["operation_samples"]
    ]
    process_samples = [
        {
            "elapsed_ms": sample["process_elapsed_ms"],
            "status": "SUCCESS",
            "rss_mb": (sample.get("process_resource") or {}).get("peak_rss_mb"),
            "temp_disk_bytes": (sample.get("process_resource") or {}).get("peak_temp_disk_bytes"),
        }
        for sample in samples
    ]
    return {
        "mode": mode,
        "operation": _summary(operation_samples),
        "process": _summary(process_samples),
        "cache_policy": "UNCONTROLLED_OS_CACHE",
        "fresh_process_per_sample": mode in {"cold", "append-tail", "projection-rebuild"},
        "warmup_excluded": mode in {"warm", "append-tail"},
        "samples": [
            {**{key: value for key, value in sample.items() if key != "operation_samples"},
             "operation_samples": sample["operation_samples"],
             "evidence_dir": str(Path(sample["manifest_path"]).parent.relative_to(evidence_root))}
            for sample in samples
        ],
    }


def _prepare_fixture(path: Path, *, size: int, seed: str, batch_size: int) -> dict:
    # Import after the caller has placed KUANTRA_DATA_DIR in a disposable root.
    from run_h07_benchmark import H07BenchmarkRunner

    runner = H07BenchmarkRunner(seed=seed, batch_size=batch_size, operation_repetitions=3)
    run = runner._run_size(size, path)
    return {
        "size": size,
        "counts": run["counts"],
        "snapshot_sha256": run["determinism"]["snapshot_sha256"],
        "fixture_sha256": _sha256_file(path),
        "preparation_mode": "SOURCE_PROCESS",
    }


def run_campaign(*, executable, artifact, output_dir, sizes=(1000, 10000, 100000),
                 runs=2, cold_samples=20, warm_samples=20, append_samples=20,
                 projection_rebuild_samples=20,
                 seed=DEFAULT_SEED, batch_size=1000, timeout=1800):
    executable, artifact = Path(executable).resolve(), Path(artifact).resolve()
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise ValueError("campaign output directory must be new")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("explicit executable is missing or not executable")
    if not artifact.is_dir() or not executable.is_relative_to(artifact):
        raise ValueError("artifact directory must contain the explicit executable")
    normalized_sizes = tuple(sorted({int(size) for size in sizes}))
    if not normalized_sizes or any(size < 1 or size > 100_000 for size in normalized_sizes):
        raise ValueError("sizes must be between 1 and 100000")
    if (
        not 1 <= runs <= 2
        or not 3 <= cold_samples <= 100
        or not 3 <= warm_samples <= 100
        or not 3 <= append_samples <= 100
        or not 3 <= projection_rebuild_samples <= 100
    ):
        raise ValueError("campaign repetitions are outside the bounded protocol")
    if not 1 <= batch_size <= 5_000:
        raise ValueError("batch size is outside the bounded protocol")
    output_dir.mkdir(parents=True, exist_ok=False)
    artifact_hashes = {"executable": _sha256_file(executable), "artifact": _sha256_path(artifact)}
    if not all(artifact_hashes.values()):
        raise ValueError("unable to hash explicit artifact")
    all_runs = []
    with tempfile.TemporaryDirectory(prefix="kuantra-h07-campaign-") as fixture_root_name:
        fixture_root = Path(fixture_root_name)
        previous_data_dir = os.environ.get("KUANTRA_DATA_DIR")
        os.environ["KUANTRA_DATA_DIR"] = str(fixture_root / "source-data")
        try:
            for run_number in range(1, runs + 1):
                run_dir = output_dir / f"run-{run_number:02d}"
                run_dir.mkdir()
                run_results = []
                for size in normalized_sizes:
                    fixture = fixture_root / f"run-{run_number:02d}-{size}.sqlite"
                    preparation = _prepare_fixture(
                        fixture, size=size, seed=seed, batch_size=batch_size,
                    )
                    size_dir = run_dir / f"size-{size}"
                    size_dir.mkdir()
                    (size_dir / "fixture-preparation.json").write_text(
                        _canonical(preparation), encoding="utf-8",
                    )

                    cold = []
                    for sample_number in range(1, cold_samples + 1):
                        evidence_dir = size_dir / "cold" / f"sample-{sample_number:02d}"
                        manifest = run_packaged_mode(
                            executable=executable, artifact=artifact, evidence_dir=evidence_dir,
                            size=size, repetitions=1, mode="cold", fixture=fixture,
                            timeout=timeout,
                        )
                        cold.append(_read_sample(evidence_dir, manifest, mode="cold"))

                    warm_dir = size_dir / "warm"
                    warm_manifest = run_packaged_mode(
                        executable=executable, artifact=artifact, evidence_dir=warm_dir,
                        size=size, repetitions=warm_samples, mode="warm", fixture=fixture,
                        timeout=timeout,
                    )
                    warm = [_read_sample(warm_dir, warm_manifest, mode="warm")]

                    append = []
                    for sample_number in range(1, append_samples + 1):
                        evidence_dir = size_dir / "append-tail" / f"sample-{sample_number:02d}"
                        manifest = run_packaged_mode(
                            executable=executable, artifact=artifact, evidence_dir=evidence_dir,
                            size=size, repetitions=3, mode="append-tail", fixture=fixture,
                            timeout=timeout,
                        )
                        append.append(_read_sample(evidence_dir, manifest, mode="append-tail"))

                    projection_rebuild = []
                    for sample_number in range(1, projection_rebuild_samples + 1):
                        evidence_dir = size_dir / "projection-rebuild" / f"sample-{sample_number:02d}"
                        manifest = run_packaged_mode(
                            executable=executable, artifact=artifact, evidence_dir=evidence_dir,
                            size=size, repetitions=1, mode="projection-rebuild", fixture=fixture,
                            timeout=timeout,
                        )
                        projection_rebuild.append(
                            _read_sample(evidence_dir, manifest, mode="projection-rebuild")
                        )

                    run_results.append({
                        "size": size,
                        "fixture": preparation,
                        "cold": _mode_result(cold, mode="cold", evidence_root=output_dir),
                        "warm": _mode_result(warm, mode="warm", evidence_root=output_dir),
                        "append_tail": _mode_result(append, mode="append-tail", evidence_root=output_dir),
                        "projection_rebuild": _mode_result(
                            projection_rebuild, mode="projection-rebuild", evidence_root=output_dir,
                        ),
                    })
                all_runs.append({"run": run_number, "sizes": run_results})
        finally:
            if previous_data_dir is None:
                os.environ.pop("KUANTRA_DATA_DIR", None)
            else:
                os.environ["KUANTRA_DATA_DIR"] = previous_data_dir

    checkout = collect_provenance(ROOT, executable=executable, artifact=artifact)
    report = {
        "schema_version": "H07.measurement-campaign.v2",
        "status": "MEASURED",
        "execution": {
            "mode": "PACKAGED_PROCESS", "artifact_executed": True,
            "cold_samples_per_size": cold_samples, "warm_samples_per_size": warm_samples,
            "append_tail_samples_per_size": append_samples,
            "projection_rebuild_samples_per_size": projection_rebuild_samples, "runs": runs,
            "fresh_process_cold": True, "fresh_process_append_tail": True,
            "fresh_process_projection_rebuild": True,
            "warmup_excluded_from_warm": True, "os_cache": "UNCONTROLLED",
            "source_fixture_preparation": "SOURCE_PROCESS",
            "source_to_binary_attestation": "NOT_VERIFIED",
        },
        "contract": {
            "real_data": False, "credentials": False, "network": False,
            "live_execution": False, "support_limit_claim": False,
        },
        "platform": {"os": platform.system(), "os_version": platform.release(),
                     "architecture": platform.machine(), "python": platform.python_version()},
        "dataset": {"seed": seed, "sizes": list(normalized_sizes), "runs": runs},
        "artifact": artifact_hashes,
        "checkout_observation": checkout,
        "runs_detail": all_runs,
        "release_provenance": "UNKNOWN",
    }
    body = _canonical(report).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(body).hexdigest()
    report_path = output_dir / "campaign-report.json"
    report_path.write_text(_canonical(report), encoding="utf-8")
    file_manifest = {
        "schema_version": "H07.measurement-campaign-manifest.v2",
        "status": "MEASURED",
        "report": str(report_path), "report_sha256": _sha256_file(report_path),
        "artifact": artifact_hashes,
        "release_provenance": "UNKNOWN", "support_limit_claim": False,
        "os_cache": "UNCONTROLLED",
    }
    (output_dir / "campaign-manifest.json").write_text(
        _canonical(file_manifest), encoding="utf-8",
    )
    return report


def _parse_sizes(value):
    try:
        return tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("sizes must be comma-separated integers") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sizes", type=_parse_sizes, default=(1000, 10000, 100000))
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--cold-samples", type=int, default=20)
    parser.add_argument("--warm-samples", type=int, default=20)
    parser.add_argument("--append-samples", type=int, default=20)
    parser.add_argument("--projection-rebuild-samples", type=int, default=20)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    report = run_campaign(
        executable=args.executable, artifact=args.artifact, output_dir=args.output_dir,
        sizes=args.sizes, runs=args.runs, cold_samples=args.cold_samples,
        warm_samples=args.warm_samples, append_samples=args.append_samples,
        projection_rebuild_samples=args.projection_rebuild_samples,
        seed=args.seed, batch_size=args.batch_size, timeout=args.timeout,
    )
    print(json.dumps({"status": report["status"], "report": str(args.output_dir / "campaign-report.json"),
                      "report_sha256": report["report_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
