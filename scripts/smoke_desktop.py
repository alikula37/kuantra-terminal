"""Run the packaged app's headless self-test. Exit code = smoke result.

Usage: python scripts/smoke_desktop.py [--report PATH] [--timeout SECONDS]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def executable() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "Kuantra Terminal.app" / "Contents" / "MacOS" / "Kuantra Terminal"
    if sys.platform.startswith("win"):
        return ROOT / "dist" / "Kuantra Terminal" / "Kuantra Terminal.exe"
    return ROOT / "dist" / "kuantra-terminal" / "kuantra-terminal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=str(ROOT / "dist" / "smoke.json"))
    ap.add_argument("--timeout", type=float, default=120)
    args = ap.parse_args()

    exe = executable()
    if not exe.exists():
        print(f"built executable missing: {exe} (run scripts/build_desktop.py first)", file=sys.stderr)
        return 1

    env = {**os.environ,
           "KUANTRA_DATA_DIR": str(ROOT / "dist" / "smoke-data"),
           "KUANTRA_GATEWAY_ENABLED": "0"}
    hard_timeout = args.timeout + 60
    try:
        proc = subprocess.run(
            [str(exe), "--smoke", "--smoke-report", args.report, "--smoke-timeout", str(args.timeout)],
            env=env, timeout=hard_timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"SMOKE FAIL (timeout after {hard_timeout:g} s)")
        return 1
    report = Path(args.report)
    print(report.read_text() if report.exists() else "no smoke report written")
    ok = proc.returncode == 0 and report.exists() and json.loads(report.read_text()).get("ok") is True
    print("SMOKE " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
