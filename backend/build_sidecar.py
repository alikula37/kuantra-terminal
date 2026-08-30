"""
Nuitka C++ Sidecar Compilation Pipeline for Kuantra Terminal.
Transpiles and compiles the FastAPI Python backend into a standalone native C++ binary for Tauri 2.0.
"""

import os
import sys
import platform
import subprocess
import argparse
from typing import List, Optional

def get_target_triple() -> str:
    """Detects current OS and CPU architecture and returns standard Rust target triple."""
    machine = platform.machine().lower()
    system = sys.platform

    if system.startswith("win"):
        arch = "x86_64" if machine in ("amd64", "x86_64") else "i686"
        return f"{arch}-pc-windows-msvc"
    elif system.startswith("darwin"):
        arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
        return f"{arch}-apple-darwin"
    elif system.startswith("linux"):
        arch = "x86_64" if machine in ("amd64", "x86_64") else "aarch64" if machine in ("arm64", "aarch64") else "i686"
        return f"{arch}-unknown-linux-gnu"
    else:
        return f"{machine}-unknown-{system}"

def get_binary_name(target_triple: Optional[str] = None) -> str:
    """Returns Tauri 2.0 compliant binary name: kuantra-backend-<target-triple>[.exe]."""
    triple = target_triple or get_target_triple()
    ext = ".exe" if "windows" in triple else ""
    return f"kuantra-backend-{triple}{ext}"

def build_nuitka_command(
    output_dir: str = "../src-tauri/binaries",
    entry_point: str = "main.py",
    target_triple: Optional[str] = None
) -> List[str]:
    """Generates the full Nuitka C++ compilation command list."""
    triple = target_triple or get_target_triple()
    binary_name = get_binary_name(triple)
    
    cmd = [
        sys.executable,
        "-m", "nuitka",
        "--standalone",
        "--onefile",
        "--plugin-enable=pydantic",
        "--include-package=app",
        "--include-package=duckdb",
        "--include-package=sqlite3",
        "--include-package=uvicorn",
        "--include-package=fastapi",
        "--include-package=websockets",
        "--assume-yes-for-downloads",
        f"--output-dir={output_dir}",
        f"--output-filename={binary_name}",
    ]

    if "windows" in triple:
        cmd.append("--windows-console-mode=force")

    cmd.append(entry_point)
    return cmd

def run_build(
    output_dir: str = "../src-tauri/binaries",
    dry_run: bool = False
) -> int:
    """Executes Nuitka build pipeline and verifies output binary path."""
    triple = get_target_triple()
    binary_name = get_binary_name(triple)
    
    abs_output_dir = os.path.abspath(output_dir)
    os.makedirs(abs_output_dir, exist_ok=True)
    
    cmd = build_nuitka_command(output_dir=abs_output_dir)
    print(f"[*] Target Architecture: {triple}")
    print(f"[*] Target Binary Name: {binary_name}")
    print(f"[*] Output Directory: {abs_output_dir}")
    print(f"[*] Compilation Command:\n    {' '.join(cmd)}\n")

    if dry_run:
        print("[+] Dry-run flag enabled. Skipping actual compilation.")
        return 0

    print("[*] Starting Nuitka C++ Transpilation & Compilation...")
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode == 0:
        expected_binary = os.path.join(abs_output_dir, binary_name)
        print(f"[+] Build successful! Output: {expected_binary}")
    else:
        print(f"[-] Build failed with exit code: {result.returncode}")
    return result.returncode

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kuantra Terminal Nuitka Sidecar Compiler")
    parser.add_argument("--dry-run", action="store_true", help="Print Nuitka compilation command without running")
    parser.add_argument("--output-dir", default="../src-tauri/binaries", help="Target output directory")
    args = parser.parse_args()

    sys.exit(run_build(output_dir=args.output_dir, dry_run=args.dry_run))