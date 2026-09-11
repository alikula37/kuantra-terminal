"""Canonical macOS artifact architecture helpers.

Release evidence must describe the architecture embedded in the executable, not
the architecture of the Python process that happened to collect the report.  The
helpers in this module are dependency-light and accept a command runner so that
architecture detection can be tested without a macOS binary or a real toolchain.
"""

from __future__ import annotations

import platform
import ctypes
import errno
import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence


SUPPORTED_ARCHITECTURES = frozenset({"arm64", "x86_64"})
ARCHITECTURE_ALIASES = {
    "arm64": "arm64",
    "aarch64": "arm64",
    "x86_64": "x86_64",
    "amd64": "x86_64",
}
ARCHITECTURE_TOKEN_RE = re.compile(r"\b(?:arm64|aarch64|x86_64|amd64)\b", re.IGNORECASE)
_UNSET = object()


def canonical_architecture(value: str | None) -> str | None:
    """Return the release vocabulary for a host/tool/report architecture."""

    if value is None:
        return None
    return ARCHITECTURE_ALIASES.get(value.strip().casefold())


def host_architecture() -> str | None:
    """Return the canonical architecture reported by the current process."""

    return canonical_architecture(platform.machine())


def rosetta_translation_status() -> bool | None:
    """Return whether the current macOS process is running through Rosetta.

    ``platform.machine()`` and ``uname -m`` describe the translated process as
    ``x86_64`` on Apple Silicon.  That is useful for running an Intel process,
    but it is not native Intel evidence.  macOS exposes the process translation
    bit through ``sysctl.proc_translated``. Apple's documented ENOENT result
    means native (the key need not exist on Intel); other errors stay unknown.
    Use errno directly rather than interpreting localized shell output or the
    empty output produced by ``sysctl -i`` for a missing key.
    """

    if platform.system() != "Darwin":
        return False
    try:
        sysctl = ctypes.CDLL(None, use_errno=True).sysctlbyname
        sysctl.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
        sysctl.restype = ctypes.c_int
        value = ctypes.c_int(0)
        size = ctypes.c_size_t(ctypes.sizeof(value))
        ctypes.set_errno(0)
        result = sysctl(b"sysctl.proc_translated", ctypes.byref(value), ctypes.byref(size), None, 0)
        if result == -1:
            return False if ctypes.get_errno() == errno.ENOENT else None
        if result != 0 or size.value != ctypes.sizeof(value):
            return None
    except (OSError, AttributeError):
        return None
    if value.value == 0:
        return False
    if value.value == 1:
        return True
    return None


def host_translation_label() -> str:
    """Return a serializable host-translation label for provenance reports."""

    if platform.system() != "Darwin":
        return "not_applicable"
    status = rosetta_translation_status()
    if status is True:
        return "rosetta"
    if status is False:
        return "native"
    return "unknown"


def native_host_matches(
    expected_architecture: str,
    *,
    observed_architecture: str | None = None,
    translated: bool | None | object = _UNSET,
) -> tuple[bool, str]:
    """Validate that a macOS process can be used as native artifact evidence.

    Intel builds are the sensitive case: an x86_64 process on Apple Silicon can
    run under Rosetta and produce an x86_64 executable, but that does not prove
    an Intel host installation.  The caller may provide observations for
    deterministic tests; otherwise the real host and sysctl state are read.
    """

    expected = canonical_architecture(expected_architecture)
    observed = canonical_architecture(observed_architecture) if observed_architecture is not None else host_architecture()
    if expected is None:
        return False, f"unsupported expected architecture: {expected_architecture}"
    if observed != expected:
        return False, f"expected {expected}, got {observed or 'unknown'}"
    if expected == "x86_64":
        translated_state = rosetta_translation_status() if translated is _UNSET else translated
        if translated_state is True:
            return False, "x86_64 process is running through Rosetta; native Intel host is required"
        if translated_state is not False:
            return False, "Rosetta translation status is unknown; native Intel host cannot be proven"
    return True, f"native {expected} host verified"


CommandRunner = Callable[[Sequence[str]], tuple[int, str, str]]


def _default_runner(command: Sequence[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return 127, "", ""
    return result.returncode, result.stdout, result.stderr


def _tokens(output: str) -> set[str]:
    return {
        canonical_architecture(token)
        for token in ARCHITECTURE_TOKEN_RE.findall(output)
        if canonical_architecture(token) is not None
    }


def _file_tokens(output: str) -> set[str]:
    """Extract architecture tokens from ``file``'s Mach-O description only.

    ``file`` prefixes its description with the inspected path.  A repository
    or temporary directory can legitimately contain a word such as ``arm64``;
    scanning the complete line would then be able to mislabel an otherwise
    opaque file.  Restrict the fallback to the text following the Mach-O
    marker, which is the part produced by the file-format probe.
    """

    marker = re.search(r"\bMach-O\b", output, re.IGNORECASE)
    return _tokens(output[marker.start():]) if marker else set()


def detect_executable_architecture(
    executable: Path,
    *,
    runner: CommandRunner | None = None,
) -> dict[str, object]:
    """Detect the architecture(s) embedded in one executable.

    ``lipo -archs`` is authoritative on macOS.  ``file`` is a conservative
    fallback for environments where lipo cannot inspect the file.  A fat or
    Universal2 executable is deliberately reported as unsupported rather than
    choosing one architecture silently.
    """

    executable = Path(executable).resolve()
    if not executable.is_file():
        return {
            "architecture": None,
            "architectures": [],
            "verified": False,
            "source": "missing",
        }

    run = runner or _default_runner
    observations: list[tuple[str, set[str]]] = []
    for source, command in (
        ("lipo", ("lipo", "-archs", str(executable))),
        ("file", ("file", str(executable))),
    ):
        returncode, stdout, stderr = run(command)
        if returncode == 0:
            detected = _tokens(stdout) if source == "lipo" else _file_tokens(stdout)
            if detected:
                observations.append((source, detected))
                if len(detected) > 1:
                    return {
                        "architecture": "universal2",
                        "architectures": sorted(detected),
                        "verified": False,
                        "source": source,
                    }
                if source == "lipo":
                    architecture = next(iter(detected))
                    return {
                        "architecture": architecture,
                        "architectures": [architecture],
                        "verified": architecture in SUPPORTED_ARCHITECTURES,
                        "source": source,
                    }

    if observations:
        merged = set().union(*(detected for _, detected in observations))
        if len(merged) == 1:
            architecture = next(iter(merged))
            return {
                "architecture": architecture,
                "architectures": [architecture],
                "verified": architecture in SUPPORTED_ARCHITECTURES,
                "source": observations[0][0],
            }
        return {
            "architecture": "universal2",
            "architectures": sorted(merged),
            "verified": False,
            "source": "multiple-tools",
        }

    return {
        "architecture": None,
        "architectures": [],
        "verified": False,
        "source": "undetected",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify the native macOS build host")
    parser.add_argument("--expected-architecture", required=True, choices=sorted(SUPPORTED_ARCHITECTURES))
    args = parser.parse_args()
    if platform.system() != "Darwin":
        parser.exit(2, "native macOS host required\n")
    ok, reason = native_host_matches(args.expected_architecture)
    print(reason)
    raise SystemExit(0 if ok else 2)
