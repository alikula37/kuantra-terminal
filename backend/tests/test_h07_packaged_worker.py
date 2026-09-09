"""The diagnostic entry must run before application path/log/network startup."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def invoke(tmp_path, *extra):
    return subprocess.run(
        [sys.executable, str(ROOT / "backend/desktop_main.py"),
         "--h07-benchmark", "--size", "12", "--repetitions", "3",
         "--output", str(tmp_path / "worker.json"), *extra],
        cwd=tmp_path, env={**os.environ, "KUANTRA_DATA_DIR": str(tmp_path / "must-not-touch")},
        capture_output=True, text=True, timeout=60,
    )


def test_worker_isolated_before_paths_and_runtime(tmp_path):
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "must-not-touch").exists()
    report = json.loads((tmp_path / "worker.json").read_text())
    assert report["execution"]["mode"] == "SOURCE_PROCESS"
    assert report["execution"]["artifact_executed"] is False
    assert report["execution"]["cold_process_measured"] is False
    assert report["execution"]["os_cache"] == "UNCONTROLLED"
    assert report["run"]["counts"] == {"trades": 12, "projections": 12, "ledger_events": 15}
    assert report["runtime_modules_loaded"] == []
    assert report["network_guard"] == "PYTHON_AUDIT_DENY"
    assert not Path(report["synthetic_directory"]).exists()


@pytest.mark.parametrize("extra", [["--size", "100001"], ["--repetitions", "0"], ["--smoke"]])
def test_invalid_worker_options_do_not_start_app(tmp_path, extra):
    result = invoke(tmp_path, *extra)
    assert result.returncode != 0
    assert not (tmp_path / "must-not-touch").exists()
    assert not (tmp_path / "worker.json").exists()


def test_worker_never_overwrites_existing_output(tmp_path):
    output = tmp_path / "worker.json"
    output.write_text("preserve")
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert output.read_text() == "preserve"
    assert not (tmp_path / "must-not-touch").exists()


@pytest.mark.parametrize("event", ["socket.connect", "socket.getaddrinfo", "socket.sendto", "subprocess.Popen"])
def test_worker_network_guard_denies_without_using_network(event):
    from desktop.h07_worker import deny_external_io
    with pytest.raises(RuntimeError, match="forbids"):
        deny_external_io(event, ())
    deny_external_io("open", ())


def packaged_report(executable):
    return {
        "schema_version": "H07.worker.v1", "status": "MEASURED",
        "execution": {"mode": "PACKAGED_PROCESS", "artifact_executed": True,
                      "pid": 42, "executable": str(executable), "executable_sha256": "abc",
                      "cold_process_measured": False, "os_cache": "UNCONTROLLED",
                      "workload_cache": "MIXED_AFTER_FIXTURE_IMPORT"},
        "network_guard": "PYTHON_AUDIT_DENY", "runtime_modules_loaded": [],
        "support_limit_claim": False,
        "run": {"size": 12, "counts": {"trades": 12, "projections": 12, "ledger_events": 15},
                "determinism": {"status": "COMPLETE"}},
    }


@pytest.mark.parametrize("key,value", [
    ("mode", "SOURCE_PROCESS"), ("pid", 43), ("executable_sha256", "other"),
    ("executable", "/wrong"), ("artifact_executed", False),
    ("cold_process_measured", True), ("os_cache", "COLD"),
])
def test_launcher_rejects_execution_mismatch(tmp_path, key, value):
    from scripts.run_h07_packaged_benchmark import validate_worker
    executable = tmp_path / "binary"
    report = packaged_report(executable)
    validate_worker(report, pid=42, executable=executable, executable_sha256="abc", size=12)
    report["execution"][key] = value
    with pytest.raises(ValueError, match="mismatch"):
        validate_worker(report, pid=42, executable=executable, executable_sha256="abc", size=12)


def test_launcher_rejects_failed_process_and_preserves_evidence(tmp_path, monkeypatch):
    from scripts import run_h07_packaged_benchmark as launcher
    artifact = tmp_path / "app"
    artifact.mkdir()
    binary = artifact / "binary"
    binary.write_bytes(b"fixture")
    binary.chmod(0o700)
    class FailedProcess:
        pid = 42
        def wait(self, timeout):
            return 1
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: FailedProcess())
    evidence = tmp_path / "evidence"
    with pytest.raises(ValueError, match="exited 1"):
        launcher.run_packaged(executable=binary, artifact=artifact, evidence_dir=evidence, size=12)
    assert (evidence / "process.log").exists()
    assert not (evidence / "manifest.json").exists()
    with pytest.raises(FileExistsError):
        launcher.run_packaged(executable=binary, artifact=artifact, evidence_dir=evidence, size=12)
