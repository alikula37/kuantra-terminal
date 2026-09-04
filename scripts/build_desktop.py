"""Build the desktop app with PyInstaller for the host OS.

Usage: python scripts/build_desktop.py [--skip-frontend]

Outputs:
  macOS   dist/Kuantra Terminal.app
  Windows dist/Kuantra Terminal/Kuantra Terminal.exe
  Linux   dist/kuantra-terminal/kuantra-terminal
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.version import __version__  # noqa: E402


def output_path() -> Path:
    if sys.platform == "darwin":
        return ROOT / "dist" / "Kuantra Terminal.app"
    if sys.platform.startswith("win"):
        return ROOT / "dist" / "Kuantra Terminal" / "Kuantra Terminal.exe"
    return ROOT / "dist" / "kuantra-terminal" / "kuantra-terminal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frontend", action="store_true", help="reuse the existing frontend/dist build")
    args = ap.parse_args()

    if not args.skip_frontend:
        npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
        subprocess.run([npm, "--prefix", str(ROOT / "frontend"), "run", "build"], check=True)
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        print("frontend/dist/index.html missing", file=sys.stderr)
        return 1

    for d in ("build", "dist"):
        shutil.rmtree(ROOT / d, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
           str(ROOT / "packaging" / "kuantra.spec")]
    print("[*] " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT))

    out = output_path()
    if not out.exists():
        print(f"expected output missing: {out}", file=sys.stderr)
        return 1
    print(f"[+] built {out} (version {__version__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
