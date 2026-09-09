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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="kuantra-terminal --h07-benchmark", allow_abbrev=False)
    parser.add_argument("--h07-benchmark", action="store_true", required=True)
    parser.add_argument("--size", type=bounded_int(1, 100_000), required=True)
    parser.add_argument("--repetitions", type=bounded_int(3, 100), default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # O_EXCL rejects existing files and symlinks, including dangling symlinks.
    # No arbitrary database input/work-dir option exists.
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
            if not getattr(sys, "frozen", False):
                sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from scripts.run_h07_benchmark import H07BenchmarkRunner

            run = H07BenchmarkRunner(operation_repetitions=args.repetitions)._run_size(
                args.size, Path(temporary) / "synthetic.sqlite",
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
                    "cold_process_measured": False, "os_cache": "UNCONTROLLED",
                    "workload_cache": "MIXED_AFTER_FIXTURE_IMPORT",
                },
                "platform": {"os": platform.system(), "version": platform.release(),
                             "architecture": platform.machine(), "python": platform.python_version()},
                "network_guard": "PYTHON_AUDIT_DENY", "runtime_modules_loaded": forbidden,
                "synthetic_directory": temporary, "run": run,
                "release_provenance": "UNKNOWN", "support_limit_claim": False,
            }
        # Only emit a completed report after our own temporary fixture is cleaned up.
        json.dump(report, output, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return 0
