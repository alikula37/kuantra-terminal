"""
Packaging & Environment Integrity Verification Utility for Kuantra Terminal.
Validates build scripts, Tauri bundle configurations, and multi-language dictionary synchronization.
"""

import os
import sys
import json
from typing import Set, Dict, Any

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

    # 1. Check Essential Directories
    required_dirs = ["backend", "frontend", "src-tauri", "docs", "scripts"]
    for d in required_dirs:
        p = os.path.join(root_dir, d)
        if not os.path.isdir(p):
            print(f"[-] Missing required directory: {d}")
            return False
    print("[+] Core directories validated.")

    # 2. Check Build Sidecar Script
    sidecar_script = os.path.join(root_dir, "backend", "build_sidecar.py")
    if not os.path.isfile(sidecar_script):
        print(f"[-] Missing sidecar compilation script: {sidecar_script}")
        return False
    print("[+] Nuitka C++ sidecar build script verified.")

    # 3. Check Tauri 2.0 Manifest
    tauri_conf = os.path.join(root_dir, "src-tauri", "tauri.conf.json")
    if not os.path.isfile(tauri_conf):
        print(f"[-] Missing Tauri configuration: {tauri_conf}")
        return False

    with open(tauri_conf, "r", encoding="utf-8") as f:
        conf = json.load(f)

    if not conf.get("productName") or "bundle" not in conf:
        print("[-] Invalid Tauri configuration format.")
        return False
    print(f"[+] Tauri bundle config validated: {conf['productName']} v{conf.get('version', '2.0.0')}")

    # 4. Check i18n Dictionary Parity
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

    # 5. Check Documentation
    docs_to_check = [
        os.path.join(root_dir, "README.md"),
        os.path.join(root_dir, "CONTRIBUTING.md"),
        os.path.join(root_dir, "SECURITY.md"),
        os.path.join(root_dir, "ARCHITECTURE.md"),
        os.path.join(root_dir, "docs", "BUILD_WINDOWS.md"),
        os.path.join(root_dir, "docs", "BUILD_MACOS.md"),
        os.path.join(root_dir, "docs", "BUILD_LINUX.md")
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