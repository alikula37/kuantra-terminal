"""
Packaging & environment integrity verification utility for Kuantra Terminal.

Validates the repository layout required by the pywebview/PyInstaller desktop shell,
the per-platform packaging inputs, multi-language dictionary parity, and the
documentation set that ships with a release.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_release_truth import TruthContractError, run_checks  # noqa: E402


def get_leaf_keys(d: Dict[str, Any], prefix: str = "") -> Set[str]:
    """Recursively extracts all dot-notation leaf keys from a dictionary."""
    keys = set()
    for k, v in d.items():
        p = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(get_leaf_keys(v, p))
        else:
            keys.add(p)
    return keys


def verify_system_integrity() -> bool:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[*] Verifying Kuantra Terminal packaging integrity at: {root_dir}")

    try:
        run_checks(Path(root_dir))
    except TruthContractError as exc:
        print(f"[-] Release truth contract failed: {exc}")
        return False
    print("[+] Current release truth contract validated.")

    # 1. Check essential directories
    required_dirs = ["backend", "frontend", "packaging", "scripts", "docs"]
    for d in required_dirs:
        p = os.path.join(root_dir, d)
        if not os.path.isdir(p):
            print(f"[-] Missing required directory: {d}")
            return False
    print("[+] Core directories validated.")

    # 2. Check packaging & shell entry points
    required_files = [
        os.path.join("packaging", "kuantra.spec"),
        os.path.join("packaging", "windows", "installer.nsi"),
        os.path.join("packaging", "linux", "AppRun"),
        os.path.join("backend", "desktop_main.py"),
        os.path.join("frontend", "vite.config.ts"),
    ]
    for rel in required_files:
        p = os.path.join(root_dir, rel)
        if not os.path.isfile(p):
            print(f"[-] Missing required packaging file: {rel}")
            return False
    print("[+] PyInstaller spec, platform packaging inputs and desktop entry point verified.")

    # 3. Check i18n dictionary parity
    locales_dir = os.path.join(root_dir, "frontend", "src", "locales")
    en_path = os.path.join(locales_dir, "en.json")
    tr_path = os.path.join(locales_dir, "tr.json")
    de_path = os.path.join(locales_dir, "de.json")

    for p in [en_path, tr_path, de_path]:
        if not os.path.isfile(p):
            print(f"[-] Missing locale dictionary: {p}")
            return False

    with open(en_path, "r", encoding="utf-8") as f:
        en_dict = json.load(f)
    with open(tr_path, "r", encoding="utf-8") as f:
        tr_dict = json.load(f)
    with open(de_path, "r", encoding="utf-8") as f:
        de_dict = json.load(f)

    en_keys = get_leaf_keys(en_dict)
    tr_keys = get_leaf_keys(tr_dict)
    de_keys = get_leaf_keys(de_dict)

    if en_keys != tr_keys:
        print(f"[-] i18n mismatch between EN and TR: {en_keys ^ tr_keys}")
        return False
    if en_keys != de_keys:
        print(f"[-] i18n mismatch between EN and DE: {en_keys ^ de_keys}")
        return False
    print(f"[+] Multi-language synchronization verified across {len(en_keys)} translation tokens.")

    # 4. Check documentation
    docs_to_check = [
        os.path.join(root_dir, "README.md"),
        os.path.join(root_dir, "CONTRIBUTING.md"),
        os.path.join(root_dir, "SECURITY.md"),
        os.path.join(root_dir, "ARCHITECTURE.md"),
        os.path.join(root_dir, "docs", "BUILD_WINDOWS.md"),
        os.path.join(root_dir, "docs", "BUILD_MACOS.md"),
        os.path.join(root_dir, "docs", "MACOS_MIGRATION.md"),
        os.path.join(root_dir, "docs", "BUILD_LINUX.md"),
    ]

    for doc in docs_to_check:
        if not os.path.isfile(doc) or os.path.getsize(doc) < 50:
            print(f"[-] Missing or empty documentation file: {doc}")
            return False
    print("[+] All architecture, governance, and build runbooks validated.")

    print("\n=======================================================")
    print("[SUCCESS] ALL PACKAGING PRE-FLIGHT CHECKS PASSED (100%)")
    print("=======================================================")
    return True


if __name__ == "__main__":
    success = verify_system_integrity()
    sys.exit(0 if success else 1)
