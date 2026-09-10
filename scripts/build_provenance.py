"""Collect and validate exact source/build/artifact provenance.

This module is intentionally dependency-light so smoke reports can be produced
before the rest of the application starts.  It hashes tracked source content,
lock files, executables and artifacts without reading user data or credentials.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

try:  # Support both `import scripts.build_provenance` and script-local imports.
    from macos_architecture import (
        SUPPORTED_ARCHITECTURES,
        detect_executable_architecture,
        host_architecture,
        host_translation_label,
    )
except ModuleNotFoundError:  # pragma: no cover - import shape depends on the caller
    from scripts.macos_architecture import (
        SUPPORTED_ARCHITECTURES,
        detect_executable_architecture,
        host_architecture,
        host_translation_label,
    )


COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_TOOLCHAINS = ("python", "node", "npm", "uv", "pyinstaller")


class ProvenanceError(ValueError):
    """Raised when release-facing provenance is missing or inconsistent."""


def _run(command: Sequence[str], root: Path) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            list(command),
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return subprocess.CompletedProcess(list(command), 127, b"", b"")


def _git_text(root: Path, *args: str) -> Optional[str]:
    result = _run(("git", *args), root)
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace").strip()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _sha256_path(path: Optional[Path]) -> Optional[str]:
    if path is None or not path.exists():
        return None
    if path.is_file():
        return _sha256_file(path)
    if not path.is_dir():
        return None

    digest = hashlib.sha256()
    try:
        children = sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix())
        for child in children:
            relative = child.relative_to(path).as_posix().encode("utf-8")
            if child.is_symlink():
                digest.update(b"symlink\0" + relative + b"\0")
                digest.update(os.readlink(child).encode("utf-8"))
                digest.update(b"\0")
            elif child.is_file():
                digest.update(b"file\0" + relative + b"\0")
                with child.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                digest.update(b"\0")
    except OSError:
        return None
    return digest.hexdigest()


def _command_version(command: Sequence[str], root: Path) -> Optional[str]:
    result = _run((*command, "--version"), root)
    if result.returncode != 0:
        return None
    text = result.stdout.decode("utf-8", errors="replace").strip()
    return text.splitlines()[0].strip() if text else None


def _tracked_tree(root: Path) -> tuple[str, Optional[str]]:
    status = _git_text(root, "status", "--porcelain", "--untracked-files=no")
    head_tree = _git_text(root, "rev-parse", "HEAD^{tree}")
    diff = _run(("git", "diff", "HEAD", "--binary"), root)
    if status is None or head_tree is None or diff.returncode != 0:
        return "unknown", None
    body = head_tree.encode("ascii", errors="replace") + b"\0" + diff.stdout
    return ("clean" if not status else "dirty"), hashlib.sha256(body).hexdigest()


def _validation_errors(provenance: Mapping[str, Any], *, release_facing: bool) -> list[str]:
    errors: list[str] = []
    source_commit = str(provenance.get("source_commit_sha") or "")
    checkout_commit = str(provenance.get("checkout_commit_sha") or "")
    if not COMMIT_RE.fullmatch(source_commit):
        errors.append("source commit SHA is missing or invalid")
    if not COMMIT_RE.fullmatch(checkout_commit):
        errors.append("checkout commit SHA is missing or invalid")
    if provenance.get("source_commit_matches_checkout") is not True:
        errors.append("source commit does not match checkout commit")

    tree_status = provenance.get("tracked_source_tree_status")
    if tree_status not in {"clean", "dirty"}:
        errors.append("tracked source tree status is missing")
    if not SHA256_RE.fullmatch(str(provenance.get("tracked_source_tree_sha256") or "")):
        errors.append("tracked source tree digest is missing or invalid")

    locks = provenance.get("lock_hashes")
    if not isinstance(locks, Mapping):
        errors.append("lock hashes are missing")
    else:
        for key in ("backend_requirements_lock_sha256", "frontend_package_lock_sha256"):
            if not SHA256_RE.fullmatch(str(locks.get(key) or "")):
                errors.append(f"{key} is missing or invalid")

    toolchain = provenance.get("toolchain")
    if not isinstance(toolchain, Mapping):
        errors.append("toolchain metadata is missing")
    else:
        for key in REQUIRED_TOOLCHAINS:
            if not str(toolchain.get(key) or "").strip():
                errors.append(f"toolchain {key} is missing")

    if not str(provenance.get("os") or "").strip():
        errors.append("operating system metadata is missing")
    architecture = str(provenance.get("architecture") or "").strip()
    if not architecture:
        errors.append("architecture metadata is missing")
    elif architecture not in SUPPORTED_ARCHITECTURES:
        errors.append("architecture metadata is not a supported native architecture")
    if release_facing:
        if provenance.get("architecture_verified") is not True:
            errors.append("verified executable architecture is required")
        if provenance.get("architecture_source") != "executable":
            errors.append("architecture provenance must come from the executable")
        if provenance.get("os") == "darwin":
            if provenance.get("build_host_architecture") != architecture:
                errors.append("macOS build host architecture must match the artifact architecture")
            if provenance.get("build_host_translation") != "native":
                errors.append("macOS build host must be proven native and not Rosetta-translated")
    for key in ("executable_sha256", "artifact_sha256"):
        if not SHA256_RE.fullmatch(str(provenance.get(key) or "")):
            errors.append(f"{key} is missing or invalid")

    if release_facing:
        if tree_status != "clean":
            errors.append("tracked source tree is not clean for release provenance")
        if provenance.get("provenance_status") != "COMPLETE":
            errors.append("provenance status is not COMPLETE")
    return errors


def validate_provenance(
    provenance: Mapping[str, Any],
    *,
    release_facing: bool = False,
) -> Mapping[str, Any]:
    """Validate a provenance object; release-facing mode is fail-closed."""

    if not isinstance(provenance, Mapping):
        raise ProvenanceError("provenance must be an object")
    errors = _validation_errors(provenance, release_facing=release_facing)
    if errors:
        raise ProvenanceError("; ".join(errors))
    return provenance


def validate_report(
    report: Mapping[str, Any],
    *,
    release_facing: bool = False,
) -> Mapping[str, Any]:
    """Validate a smoke/local-CI report and its legacy hash aliases."""

    if not isinstance(report, Mapping):
        raise ProvenanceError("report must be an object")
    provenance = report.get("build_provenance")
    validate_provenance(provenance, release_facing=release_facing)
    if report.get("build_commit") != provenance.get("source_commit_sha"):
        raise ProvenanceError("legacy build_commit does not match source commit SHA")
    reported_architecture = report.get("architecture")
    if reported_architecture is not None and reported_architecture != provenance.get("architecture"):
        raise ProvenanceError("report architecture does not match build provenance")
    if release_facing and reported_architecture != provenance.get("architecture"):
        raise ProvenanceError("release report architecture is missing or does not match build provenance")
    for report_key, provenance_key in (
        ("executable_sha256", "executable_sha256"),
        ("artifact_sha256", "artifact_sha256"),
    ):
        if report.get(report_key) != provenance.get(provenance_key):
            raise ProvenanceError(f"report {report_key} does not match build provenance")
    return provenance


def collect_provenance(
    root: Path,
    *,
    executable: Optional[Path] = None,
    artifact: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Collect deterministic provenance without inspecting user data."""

    root = Path(root).resolve()
    environment = env if env is not None else os.environ
    checkout_commit = _git_text(root, "rev-parse", "HEAD")
    configured_commit = environment.get("GITHUB_SHA") or environment.get("KUANTRA_BUILD_COMMIT")
    if configured_commit:
        source_commit = configured_commit.strip()
        source_origin = "github_sha" if environment.get("GITHUB_SHA") else "build_environment"
    else:
        source_commit = checkout_commit
        source_origin = "checkout"
    source_commit = source_commit if source_commit and COMMIT_RE.fullmatch(source_commit) else None
    tree_status, tree_digest = _tracked_tree(root)

    executable = Path(executable).resolve() if executable is not None else None
    artifact = Path(artifact).resolve() if artifact is not None else executable
    detected_architecture = detect_executable_architecture(executable) if executable else {
        "architecture": None,
        "architectures": [],
        "verified": False,
        "source": "no-executable",
    }
    detected_value = detected_architecture.get("architecture")
    is_verified_architecture = detected_architecture.get("verified") is True
    process_architecture = host_architecture() or platform.machine() or "unknown"
    if isinstance(detected_value, str) and detected_value:
        artifact_architecture = detected_value
        architecture_source = "executable" if is_verified_architecture else str(detected_architecture.get("source"))
    else:
        artifact_architecture = process_architecture
        architecture_source = "host_fallback"
    toolchain = {
        "python": platform.python_version(),
        "node": _command_version(("node",), root),
        "npm": _command_version(("npm",), root),
        "uv": _command_version(("uv",), root),
        "pyinstaller": _command_version((sys.executable, "-m", "PyInstaller"), root),
    }
    provenance: dict[str, Any] = {
        "source_commit_sha": source_commit,
        "checkout_commit_sha": checkout_commit,
        "source_commit_origin": source_origin,
        "source_commit_matches_checkout": bool(source_commit and checkout_commit and source_commit.lower() == checkout_commit.lower()),
        "tracked_source_tree_status": tree_status,
        "tracked_source_tree_sha256": tree_digest,
        "lock_hashes": {
            "backend_requirements_lock_sha256": _sha256_file(root / "backend" / "requirements.lock"),
            "frontend_package_lock_sha256": _sha256_file(root / "frontend" / "package-lock.json"),
        },
        "toolchain": toolchain,
        "os": platform.system().lower(),
        "os_version": platform.platform(),
        # `architecture` describes the artifact target.  The host process is
        # recorded separately because an arm64 host can launch x86_64 under
        # Rosetta and must not mislabel the release artifact.
        "architecture": artifact_architecture,
        "architecture_verified": is_verified_architecture,
        "architecture_source": architecture_source,
        "architecture_detection_tool": detected_architecture.get("source"),
        "executable_architectures": detected_architecture.get("architectures", []),
        "build_host_architecture": process_architecture,
        "build_host_translation": host_translation_label(),
        "executable_path": str(executable) if executable else None,
        "executable_sha256": _sha256_path(executable),
        "artifact_path": str(artifact) if artifact else None,
        "artifact_sha256": _sha256_path(artifact),
    }
    errors = _validation_errors(provenance, release_facing=False)
    if errors:
        provenance["provenance_status"] = "INCOMPLETE"
    elif tree_status == "dirty" or not provenance["source_commit_matches_checkout"]:
        provenance["provenance_status"] = "DEVELOPER_DIRTY"
    else:
        provenance["provenance_status"] = "COMPLETE"
    return provenance


def default_artifact_for_executable(executable: Path) -> Path:
    """Resolve the distributable root represented by a smoke executable."""

    executable = Path(executable).resolve()
    for candidate in (executable, *executable.parents):
        if candidate.name.endswith(".app"):
            return candidate
    return executable
