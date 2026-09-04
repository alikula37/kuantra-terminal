"""Clipboard write without extra dependencies (navigator.clipboard is blocked on file://)."""
import shutil
import subprocess
import sys


def copy_text(text: str) -> bool:
    candidates = []
    if sys.platform == "darwin":
        candidates = [["pbcopy"]]
    elif sys.platform.startswith("win"):
        candidates = [["clip"]]
    else:
        candidates = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]
    for cmd in candidates:
        if shutil.which(cmd[0]) is None:
            continue
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False
