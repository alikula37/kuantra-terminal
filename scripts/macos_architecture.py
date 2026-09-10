"""Canonical macOS artifact architecture helpers.

Release evidence must describe the architecture embedded in the executable, not
the architecture of the Python process that happened to collect the report.  The
helpers in this module are dependency-light and accept a command runner so that
architecture detection can be tested without a macOS binary or a real toolchain.
"""

from __future__ import annotations

import platform
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


def canonical_architecture(value: str | None) -> str | None:
    """Return the release vocabulary for a host/tool/report architecture."""

    if value is None:
        return None
    return ARCHITECTURE_ALIASES.get(value.strip().casefold())


def host_architecture() -> str | None:
    """Return the canonical architecture reported by the current process."""

    return canonical_architecture(platform.machine())


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
