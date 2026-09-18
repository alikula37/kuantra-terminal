"""Shared helpers for the dependency-free release truth contract."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX_PATH = ROOT_DIR / "docs" / "release" / "truth-matrix.v1.1.6.json"
DEFAULT_RELEASE_NOTES_PATH = ROOT_DIR / "RELEASE_NOTES.md"


class TruthContractError(ValueError):
    """Raised when the release truth contract cannot be evaluated safely."""


def load_matrix(path: Path = DEFAULT_MATRIX_PATH) -> dict[str, Any]:
    """Load the canonical matrix without importing application dependencies."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            matrix = json.load(handle)
    except FileNotFoundError as exc:
        raise TruthContractError(f"missing truth matrix: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TruthContractError(f"invalid truth matrix JSON: {path}: {exc}") from exc
    if not isinstance(matrix, dict):
        raise TruthContractError("truth matrix root must be an object")
    return matrix


def canonical_matrix_digest(matrix: dict[str, Any]) -> str:
    """Return a platform-independent digest for the parsed truth matrix.

    Hashing the checked-out file bytes is not stable across Git clients that apply
    different line-ending policies.  The release contract is semantic JSON, so its
    provenance digest must be derived from a deterministic serialization instead.
    """
    canonical = json.dumps(
        matrix,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def extract_current_release_notes(
    notes_path: Path = DEFAULT_RELEASE_NOTES_PATH,
    matrix: dict[str, Any] | None = None,
) -> str:
    """Return only the marker-delimited current release body."""
    matrix = matrix or load_matrix()
    policy = matrix.get("policy", {})
    start = policy.get("current_release_notes_start")
    end = policy.get("current_release_notes_end")
    if not isinstance(start, str) or not isinstance(end, str) or not start or not end:
        raise TruthContractError("matrix must define current release-note markers")

    try:
        content = notes_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TruthContractError(f"missing release notes: {notes_path}") from exc

    start_count = content.count(start)
    end_count = content.count(end)
    if start_count != 1 or end_count != 1:
        raise TruthContractError(
            f"release notes markers must occur once (start={start_count}, end={end_count})"
        )
    start_index = content.index(start) + len(start)
    end_index = content.index(end)
    if start_index >= end_index:
        raise TruthContractError("release notes markers are inverted")
    body = content[start_index:end_index].strip()
    if not body:
        raise TruthContractError("current release notes section is empty")
    return body
