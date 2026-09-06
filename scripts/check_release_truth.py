"""Validate the current release-facing truth contract.

This checker is intentionally dependency-free and side-effect free. It does not scan strategy
history or archived release notes; the marker-delimited current release section is the only part
of RELEASE_NOTES.md that can become a GitHub Release body.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from release_truth import (
    DEFAULT_MATRIX_PATH,
    DEFAULT_RELEASE_NOTES_PATH,
    TruthContractError,
    extract_current_release_notes,
    load_matrix,
)


ALLOWED_STATUSES = {"VERIFIED_CORE", "EXPERIMENTAL_DISABLED"}
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TruthContractError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise TruthContractError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TruthContractError(f"invalid JSON file: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TruthContractError(f"missing release-facing file: {path}") from exc


def _validate_matrix(matrix: dict[str, Any]) -> None:
    _require(matrix.get("document_id") == "KTR-001", "matrix document_id must be KTR-001")
    _require(isinstance(matrix.get("version"), str) and SEMVER_RE.fullmatch(matrix["version"]),
             "matrix version must be SemVer")
    _require(matrix.get("status") == "Accepted", "matrix status must be Accepted")

    product = matrix.get("product")
    _require(isinstance(product, dict), "matrix product must be an object")
    for key in ("name", "version", "release_tag", "release_status", "positioning"):
        _require(isinstance(product.get(key), str) and product[key], f"matrix product.{key} is required")
    _require(SEMVER_RE.fullmatch(product["version"]) is not None,
             "matrix product.version must be SemVer")
    _require(product["release_tag"] == f"v{product['version']}",
             "matrix release_tag must equal v<product.version>")

    policy = matrix.get("policy")
    _require(isinstance(policy, dict), "matrix policy must be an object")
    for key in ("current_release_notes_start", "current_release_notes_end", "required_phrases",
                "release_facing_files", "forbidden_patterns"):
        _require(key in policy, f"matrix policy.{key} is required")
    _require(isinstance(policy["required_phrases"], list) and all(
        isinstance(item, str) and item for item in policy["required_phrases"]
    ), "matrix policy.required_phrases must contain non-empty strings")
    _require(isinstance(policy["release_facing_files"], list) and all(
        isinstance(item, str) and item for item in policy["release_facing_files"]
    ), "matrix policy.release_facing_files must contain paths")

    pattern_ids: set[str] = set()
    for pattern in policy["forbidden_patterns"]:
        _require(isinstance(pattern, dict), "each forbidden pattern must be an object")
        pattern_id = pattern.get("id")
        _require(isinstance(pattern_id, str) and pattern_id not in pattern_ids,
                 f"forbidden pattern id is missing or duplicated: {pattern_id!r}")
        pattern_ids.add(pattern_id)
        _require(isinstance(pattern.get("regex"), str) and pattern["regex"],
                 f"forbidden pattern {pattern_id} has no regex")
        try:
            re.compile(pattern["regex"], re.IGNORECASE)
        except re.error as exc:
            raise TruthContractError(f"invalid forbidden pattern {pattern_id}: {exc}") from exc

    capabilities = matrix.get("capabilities")
    _require(isinstance(capabilities, list) and capabilities, "matrix capabilities must be non-empty")
    capability_ids: set[str] = set()
    for capability in capabilities:
        _require(isinstance(capability, dict), "each capability must be an object")
        capability_id = capability.get("id")
        _require(isinstance(capability_id, str) and capability_id not in capability_ids,
                 f"capability id is missing or duplicated: {capability_id!r}")
        capability_ids.add(capability_id)
        _require(capability.get("status") in ALLOWED_STATUSES,
                 f"unknown capability status for {capability_id}")
        for key in ("claim", "provenance"):
            _require(isinstance(capability.get(key), str) and capability[key],
                     f"capability {capability_id} missing {key}")
        _require(capability.get("external_execution_authority") is False,
                 f"capability {capability_id} cannot declare external execution authority")


def _version_from_python(path: Path) -> str:
    text = _read_text(path)
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', text, re.MULTILINE)
    _require(match is not None, f"could not read __version__ from {path}")
    return match.group(1)


def _scan_forbidden(text: str, source: str, patterns: list[dict[str, Any]]) -> None:
    for pattern in patterns:
        match = re.search(pattern["regex"], text, re.IGNORECASE)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            raise TruthContractError(
                f"forbidden claim {pattern['id']} in {source}:{line}: {pattern['message']}"
            )


def run_checks(root: Path, matrix_path: Path = DEFAULT_MATRIX_PATH, tag: str | None = None) -> None:
    """Validate a repository checkout; raises TruthContractError on the first violation."""
    matrix = load_matrix(matrix_path)
    _validate_matrix(matrix)
    product = matrix["product"]
    policy = matrix["policy"]
    expected_version = product["version"]

    _require(_version_from_python(root / "backend" / "app" / "version.py") == expected_version,
             "backend/app/version.py does not match the truth matrix")
    for package_path in (
        root / "package.json",
        root / "package-lock.json",
        root / "frontend" / "package.json",
        root / "frontend" / "package-lock.json",
    ):
        package = _load_json(package_path)
        _require(package.get("version") == expected_version,
                 f"{package_path} version does not match the truth matrix")
    root_package = _load_json(root / "package.json")
    _require(product["positioning"].casefold() in str(root_package.get("description", "")).casefold(),
             "root package description must contain the canonical product positioning")

    if tag is not None:
        _require(tag == product["release_tag"],
                 f"release tag {tag!r} is not the accepted tag {product['release_tag']!r}")

    release_notes = root / "RELEASE_NOTES.md"
    current_notes = extract_current_release_notes(release_notes, matrix)
    release_texts: dict[str, str] = {}
    for relative_path in policy["release_facing_files"]:
        path = root / relative_path
        _require(path.is_file(), f"release-facing file is missing: {relative_path}")
        release_texts[relative_path] = current_notes if relative_path == "RELEASE_NOTES.md" else _read_text(path)

    combined_required_text = "\n".join((release_texts["README.md"], current_notes))
    for phrase in policy["required_phrases"]:
        _require(phrase.casefold() in combined_required_text.casefold(),
                 f"required truth phrase is missing from README/current release notes: {phrase}")

    for relative_path, text in release_texts.items():
        _scan_forbidden(text, relative_path, policy["forbidden_patterns"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Kuantra's current release truth contract")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--tag", default=None, help="Require this exact release tag")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    matrix_path = args.matrix if args.matrix.is_absolute() else root / args.matrix
    try:
        run_checks(root, matrix_path=matrix_path.resolve(), tag=args.tag)
    except TruthContractError as exc:
        print(f"[truth-contract] FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"[truth-contract] PASS: {matrix_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
