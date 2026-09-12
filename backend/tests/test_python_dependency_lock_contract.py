"""Regression coverage for the P0-WP05 universal Python dependency lock."""

from pathlib import Path
import re

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
LOCK = BACKEND / "requirements.lock"
INPUT = BACKEND / "requirements-all.in"
WORKFLOWS = [
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
    REPO_ROOT / ".github" / "workflows" / "release.yml",
]
DOCKERFILE = REPO_ROOT / "packaging" / "linux" / "Dockerfile.smoke"

LOCK_COMMAND = (
    "uv pip compile --universal --python-version 3.11 --generate-hashes "
    "backend/requirements-all.in -o backend/requirements.lock"
)
LOCK_INSTALL = "pip install --require-hashes -r backend/requirements.lock"
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*==[^\s\\]+(?:\s*;[^\\]+)?\s*\\?$",
    flags=re.MULTILINE,
)


def test_universal_lock_is_generated_from_the_source_manifests_and_hashed():
    assert INPUT.read_text(encoding="utf-8").splitlines() == [
        "# Human-maintained source manifests; compile this file into requirements.lock.",
        "-r requirements.txt",
        "-r requirements-desktop.txt",
    ]

    lock = LOCK.read_text(encoding="utf-8")
    assert f"#    {LOCK_COMMAND}" in lock
    assert "sys_platform == 'win32'" in lock
    assert "sys_platform == 'darwin'" in lock
    assert "sys_platform != 'darwin'" in lock

    requirement_matches = list(EXACT_REQUIREMENT.finditer(lock))
    assert requirement_matches, "lock must contain resolved requirements"
    for index, match in enumerate(requirement_matches):
        next_start = (
            requirement_matches[index + 1].start()
            if index + 1 < len(requirement_matches)
            else len(lock)
        )
        assert "--hash=sha256:" in lock[match.start() : next_start], match.group(0)


def _source_direct_requirements():
    requirements = []
    for manifest in (BACKEND / "requirements.txt", BACKEND / "requirements-desktop.txt"):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("#"):
                requirements.append(Requirement(candidate))
    return requirements


def _locked_requirements_by_name():
    locked = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        # A generated lock entry is the only non-indented, non-comment line
        # containing its requirement. Hashes and provenance are continuations.
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        candidate = line.rstrip().removesuffix("\\").strip()
        if "==" not in candidate:
            continue
        requirement = Requirement(candidate)
        locked.setdefault(canonicalize_name(requirement.name), []).append(requirement)
    return locked


def test_lock_cannot_drift_from_direct_source_requirements():
    locked = _locked_requirements_by_name()

    for source_requirement in _source_direct_requirements():
        package_name = canonicalize_name(source_requirement.name)
        assert package_name in locked, f"lock omits direct dependency {source_requirement.name}"
        for locked_requirement in locked[package_name]:
            exact_versions = [
                specifier.version
                for specifier in locked_requirement.specifier
                if specifier.operator == "=="
            ]

            assert len(exact_versions) == 1, f"lock entry is not exact: {locked_requirement}"
            assert source_requirement.specifier.contains(exact_versions[0], prereleases=True), (
                f"lock version {exact_versions[0]} violates source constraint {source_requirement}"
            )
            if source_requirement.marker:
                assert str(source_requirement.marker) in str(locked_requirement.marker or ""), (
                    f"lock marker drifted for {source_requirement.name}: "
                    f"{locked_requirement.marker!s} no longer preserves {source_requirement.marker!s}"
                )


def test_install_surfaces_use_only_the_hashed_lock_and_current_actions():
    for workflow in WORKFLOWS:
        raw = workflow.read_text(encoding="utf-8")
        assert LOCK_INSTALL in raw
        assert "pip install -r backend/requirements.txt" not in raw
        assert "pip install -r backend/requirements-desktop.txt" not in raw
        assert "backend/requirements.lock" in raw
        assert "--no-deps" not in raw
        assert "--no-verify" not in raw
        assert "--require-hashes=false" not in raw

    ci = WORKFLOWS[0].read_text(encoding="utf-8")
    assert "cache-dependency-path: backend/requirements.lock" in ci
    for action in (
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "actions/setup-node@v7",
        "astral-sh/setup-uv@v10.1.0",
        "actions/upload-artifact@v7",
    ):
        assert action in ci

    release = WORKFLOWS[1].read_text(encoding="utf-8")
    assert "cache-dependency-path: backend/requirements.lock" in release
    for action in (
        "actions/checkout@v7",
        "actions/setup-python@v7",
        "actions/setup-node@v7",
        "astral-sh/setup-uv@v10.1.0",
        "actions/upload-artifact@v7",
        "actions/download-artifact@v8",
    ):
        assert action in release

    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "COPY backend/requirements.lock backend/" in dockerfile
    assert LOCK_INSTALL in dockerfile
    assert "requirements.txt backend/requirements-desktop.txt" not in dockerfile
    assert "pip install -U pip" not in dockerfile
