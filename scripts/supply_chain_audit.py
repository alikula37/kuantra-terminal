"""Deterministic lock inventory and release secret-boundary audit.

The audit deliberately separates machine-checkable supply-chain facts from
owner/legal decisions.  It never reads user data or credential stores and it
does not claim that a package's metadata is a legal license approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
MAX_SCAN_BYTES = 512 * 1024 * 1024
PYTHON_ENTRY_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)==(?P<version>[^\s\\]+)"
    r"(?:\s*;\s*(?P<marker>[^\\]+))?\s*\\?$"
)
PYTHON_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----.*?"
            r"-----END(?: [A-Z0-9]+)* PRIVATE KEY-----",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    ("cloud-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "bearer-token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    ),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("stripe-live-key", re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b")),
    (
        "credential-assignment",
        re.compile(
            r"\b(?:api[_-]?key|api[_-]?secret|secret[_-]?key|client[_-]?secret|"
            r"password|passphrase|access[_-]?token|refresh[_-]?token|auth[_-]?token|"
            r"test[_-]?secret)\s*[:=]\s*['\"]([^'\"\r\n]{16,})['\"]",
            re.IGNORECASE,
        ),
    ),
)

EXCLUDED_PREFIXES = (
    "backend/tests/",
    "frontend/src/__tests__/",
    "docs/archive/",
    "docs/superpowers/",
    ".codex/",
)
EXCLUDED_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")


def _canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _normalize_marker(marker: str | None) -> str:
    return re.sub(r"\s+", " ", (marker or "").replace('"', "'").strip())


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [root / item for item in result.stdout.decode("utf-8").split("\0") if item]


def _git_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    candidate = result.stdout.strip()
    return candidate if re.fullmatch(r"[0-9a-fA-F]{40}", candidate) else None


def _parse_python_lock(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = PYTHON_ENTRY_RE.match(raw_line)
        if match:
            current = {
                "name": match.group("name"),
                "version": match.group("version"),
                "marker": (match.group("marker") or "").strip() or None,
                "hashes": [],
            }
            entries.append(current)
            continue
        if current is not None:
            current["hashes"].extend(re.findall(r"--hash=sha256:([0-9a-f]{64})", raw_line))
    for entry in entries:
        entry["hashes"] = sorted(set(entry["hashes"]))
    return sorted(entries, key=lambda item: (item["name"].lower(), item["version"], item["marker"] or ""))


def _parse_direct_python_requirements(root: Path) -> dict[str, list[dict[str, str | None]]]:
    result: dict[str, list[dict[str, str | None]]] = {}
    for filename in ("requirements.txt", "requirements-desktop.txt"):
        path = root / "backend" / filename
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            requirement, _, marker = line.partition(";")
            match = PYTHON_NAME_RE.match(requirement.strip())
            if not match:
                continue
            name = match.group(0)
            result.setdefault(_canonical_name(name), []).append(
                {"name": name, "marker": marker.strip() or None}
            )
    return result


def _parse_frontend_lock(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    packages = document.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("frontend package-lock packages object is missing")
    components: list[dict[str, Any]] = []
    for package_path, metadata in packages.items():
        if package_path == "" or not isinstance(metadata, dict):
            continue
        name = str(metadata.get("name") or package_path.rsplit("node_modules/", 1)[-1])
        version = metadata.get("version")
        if not isinstance(version, str) or not version:
            raise ValueError(f"frontend package has no exact version: {package_path}")
        components.append(
            {
                "package_path": package_path,
                "name": name,
                "version": version,
                "resolved": metadata.get("resolved"),
                "integrity": metadata.get("integrity"),
                "license": metadata.get("license"),
                "dev": bool(metadata.get("dev", False)),
                "dependencies": dict(metadata.get("dependencies") or {}),
            }
        )
    return document, sorted(components, key=lambda item: (item["name"], item["version"], item["package_path"]))


def validate_lock_contract(root: Path) -> list[str]:
    """Return machine-checkable lock drift errors; no network is used."""

    root = Path(root)
    errors: list[str] = []
    backend_lock = root / "backend" / "requirements.lock"
    backend_input = root / "backend" / "requirements-all.in"
    if backend_lock.is_file():
        lock_text = backend_lock.read_text(encoding="utf-8")
        if "--generate-hashes backend/requirements-all.in -o backend/requirements.lock" not in lock_text:
            errors.append("backend lock provenance header is missing")
        try:
            locked = _parse_python_lock(backend_lock)
        except (OSError, UnicodeError) as exc:
            errors.append(f"backend lock cannot be parsed: {exc}")
            locked = []
        for entry in locked:
            if not entry["hashes"]:
                errors.append(f"backend lock entry has no sha256 hash: {entry['name']}=={entry['version']}")
        if backend_input.is_file():
            expected_input = [
                "# Human-maintained source manifests; compile this file into requirements.lock.",
                "-r requirements.txt",
                "-r requirements-desktop.txt",
            ]
            if backend_input.read_text(encoding="utf-8").splitlines() != expected_input:
                errors.append("backend requirements-all.in drifted from the lock contract")
        locked_by_name: dict[str, list[dict[str, Any]]] = {}
        for entry in locked:
            locked_by_name.setdefault(_canonical_name(entry["name"]), []).append(entry)
        for name, direct_entries in _parse_direct_python_requirements(root).items():
            if name not in locked_by_name:
                errors.append(f"backend lock omits direct dependency {name}")
                continue
            for direct in direct_entries:
                if direct["marker"] and not any(
                    _normalize_marker(direct["marker"]) == _normalize_marker(entry.get("marker"))
                    for entry in locked_by_name[name]
                ):
                    errors.append(f"backend lock marker drifted for direct dependency {name}")
    else:
        errors.append("backend requirements.lock is missing")

    package_json_path = root / "frontend" / "package.json"
    package_lock_path = root / "frontend" / "package-lock.json"
    if not package_json_path.is_file() or not package_lock_path.is_file():
        errors.append("frontend package.json or package-lock.json is missing")
    else:
        try:
            package = json.loads(package_json_path.read_text(encoding="utf-8"))
            lock, _ = _parse_frontend_lock(package_lock_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"frontend lock cannot be parsed: {exc}")
        else:
            if lock.get("lockfileVersion") != 3:
                errors.append("frontend lockfileVersion must be 3")
            root_package = lock.get("packages", {}).get("")
            if not isinstance(root_package, dict):
                errors.append("frontend package-lock root package is missing")
            else:
                for section in ("dependencies", "devDependencies"):
                    expected = package.get(section, {})
                    actual = root_package.get(section, {})
                    for name, spec in expected.items():
                        if actual.get(name) != spec:
                            errors.append(f"frontend dependency spec drift: {section}.{name}")
    return sorted(set(errors))


def _property(name: str, value: str) -> dict[str, str]:
    return {"name": name, "value": value}


def _python_components(root: Path) -> list[dict[str, Any]]:
    path = root / "backend" / "requirements.lock"
    if not path.is_file():
        return []
    direct = _parse_direct_python_requirements(root)
    components: list[dict[str, Any]] = []
    for entry in _parse_python_lock(path):
        name = entry["name"]
        version = entry["version"]
        bom_ref = f"pkg:pypi/{quote(name.lower(), safe='.-_')}@{quote(version, safe='.+-')}"
        if entry.get("marker"):
            bom_ref += f"?marker={quote(str(entry['marker']), safe='')}"
        properties = [
            _property("kuantra:ecosystem", "python"),
            _property("kuantra:dependency-scope", "direct" if _canonical_name(name) in direct else "transitive"),
            _property("kuantra:license-status", "UNVERIFIED_IN_LOCK"),
        ]
        if entry.get("marker"):
            properties.append(_property("kuantra:environment-marker", str(entry["marker"])))
        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": name,
            "version": version,
            "purl": bom_ref,
            "properties": sorted(properties, key=lambda item: (item["name"], item["value"])),
        }
        if entry["hashes"]:
            component["hashes"] = [{"alg": "SHA-256", "content": value} for value in entry["hashes"]]
        components.append(component)
    return components


def _npm_license(license_value: Any) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(license_value, str) or not license_value.strip():
        return [], "UNVERIFIED_IN_LOCK"
    value = license_value.strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", value):
        return [{"license": {"id": value}}], "DECLARED_IN_LOCK"
    return [{"expression": value}], "DECLARED_IN_LOCK"


def _npm_components(root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    path = root / "frontend" / "package-lock.json"
    package_json_path = root / "frontend" / "package.json"
    if not path.is_file():
        return [], {}
    lock, entries = _parse_frontend_lock(path)
    package = json.loads(package_json_path.read_text(encoding="utf-8")) if package_json_path.is_file() else {}
    direct = set((package.get("dependencies") or {})) | set((package.get("devDependencies") or {}))
    refs_by_path: dict[str, str] = {}
    components: list[dict[str, Any]] = []
    license_status: dict[str, str] = {}
    for entry in entries:
        name = entry["name"]
        version = entry["version"]
        purl = f"pkg:npm/{quote(name, safe='@/-')}@{quote(version, safe='.+-')}"
        bom_ref = f"{purl}?path={quote(entry['package_path'], safe='')}"
        refs_by_path[entry["package_path"]] = bom_ref
        licenses, status = _npm_license(entry.get("license"))
        license_status[name] = status
        properties = [
            _property("kuantra:ecosystem", "npm"),
            _property("kuantra:dependency-scope", "direct" if name in direct else "transitive"),
            _property("kuantra:license-status", status),
        ]
        if entry.get("resolved"):
            properties.append(_property("kuantra:resolved", str(entry["resolved"])))
        if entry.get("integrity"):
            properties.append(_property("kuantra:integrity", str(entry["integrity"])))
        component: dict[str, Any] = {
            "type": "library",
            "bom-ref": bom_ref,
            "name": name,
            "version": version,
            "purl": purl,
            "properties": sorted(properties, key=lambda item: (item["name"], item["value"])),
        }
        if licenses:
            component["licenses"] = licenses
        components.append(component)

    # The npm lock graph is kept as explicit relationships where the exact
    # resolved package path is known. Unknown peer/optional resolution remains
    # represented by the package inventory, never invented as a dependency.
    for entry in entries:
        source_ref = refs_by_path[entry["package_path"]]
        depends_on: set[str] = set()
        for dependency_name in entry["dependencies"]:
            candidate_paths = [
                f"{entry['package_path']}/node_modules/{dependency_name}",
                f"node_modules/{dependency_name}",
            ]
            for candidate in candidate_paths:
                if candidate in refs_by_path:
                    depends_on.add(refs_by_path[candidate])
                    break
        if depends_on:
            for relationship in components:
                if relationship["bom-ref"] == source_ref:
                    relationship.setdefault("properties", []).append(
                        _property("kuantra:resolved-dependency-count", str(len(depends_on)))
                    )
                    relationship["properties"] = sorted(
                        relationship["properties"], key=lambda item: (item["name"], item["value"])
                    )
                    break
    return components, license_status


def build_cyclonedx_bom(root: Path) -> dict[str, Any]:
    """Build a deterministic CycloneDX 1.5 inventory from the two locks."""

    root = Path(root)
    backend_lock = root / "backend" / "requirements.lock"
    frontend_lock = root / "frontend" / "package-lock.json"
    lock_files: list[dict[str, str]] = []
    for path in (backend_lock, frontend_lock):
        if path.is_file():
            lock_files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _sha256_file(path),
                }
            )
    components = _python_components(root)
    npm_components, _ = _npm_components(root)
    components.extend(npm_components)
    components.sort(key=lambda item: (item["purl"], item["version"], item["bom-ref"]))
    combined_lock_hash = _sha256_bytes(
        b"\0".join(path.read_bytes() for path in (backend_lock, frontend_lock) if path.is_file())
    )
    identity = _sha256_bytes(json.dumps(components, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    bom: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'kuantra-cyclonedx-v1:' + identity)}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": "application:kuantra-terminal",
                "name": "kuantra-terminal",
                "version": _product_version(root),
            },
            "properties": [
                _property("kuantra:lock-set-sha256", combined_lock_hash),
                *[
                    _property("kuantra:lock-file", f"{item['path']}:{item['sha256']}")
                    for item in lock_files
                ],
            ],
        },
        "components": components,
    }
    return bom


def _product_version(root: Path) -> str:
    path = Path(root) / "backend" / "app" / "version.py"
    if not path.is_file():
        return "UNKNOWN"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "UNKNOWN"


def _finding(kind: str, source_name: str, text: str, match: re.Match[str]) -> dict[str, Any]:
    line = text.count("\n", 0, match.start()) + 1
    digest = _sha256_bytes(match.group(0).encode("utf-8", errors="replace"))[:16]
    return {
        "kind": kind,
        "source": source_name,
        "line": line,
        "fingerprint": digest,
    }


def scan_text(text: str, *, source_name: str = "<memory>") -> list[dict[str, Any]]:
    """Return secret findings without including matched secret material."""

    findings: list[dict[str, Any]] = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            if kind == "credential-assignment":
                value = match.group(1).lower()
                if any(token in value for token in ("placeholder", "example", "dummy", "fake", "fixture", "redacted")):
                    continue
            findings.append(_finding(kind, source_name, text, match))
    return sorted(findings, key=lambda item: (item["source"], item["line"], item["kind"], item["fingerprint"]))


def scan_file(path: Path, *, source_name: str | None = None) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.is_file():
        return [{"kind": "missing-file", "source": path.name, "line": 0, "fingerprint": ""}]
    size = path.stat().st_size
    if size > MAX_SCAN_BYTES:
        return [{"kind": "scan-limit", "source": source_name or path.name, "line": 0, "fingerprint": ""}]
    return scan_text(
        path.read_bytes().decode("utf-8", errors="ignore"),
        source_name=source_name or path.name,
    )


def scan_path(path: Path, *, source_root: Path | None = None) -> list[dict[str, Any]]:
    """Scan a file or an application directory without following symlinks."""

    path = Path(path)
    if path.is_file():
        source_name = path.name
        if source_root is not None and path.is_relative_to(source_root):
            source_name = path.relative_to(source_root).as_posix()
        return scan_file(path, source_name=source_name)
    if not path.is_dir():
        return [{"kind": "missing-file", "source": path.name, "line": 0, "fingerprint": ""}]
    findings: list[dict[str, Any]] = []
    total_bytes = 0
    for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        if not child.is_file() or child.is_symlink():
            continue
        total_bytes += child.stat().st_size
        if total_bytes > MAX_SCAN_BYTES:
            findings.append({"kind": "scan-limit", "source": path.name, "line": 0, "fingerprint": ""})
            break
        relative = child.relative_to(path).as_posix()
        findings.extend(scan_file(child, source_name=f"{path.name}/{relative}"))
    return findings


def _is_excluded(relative_path: str, *, include_tests: bool) -> bool:
    normalized = relative_path.replace("\\", "/")
    if not include_tests and (
        normalized.startswith(EXCLUDED_PREFIXES)
        or normalized.endswith(EXCLUDED_SUFFIXES)
    ):
        return True
    if normalized.split("/")[-1].startswith(".env") and not normalized.endswith(".example"):
        return True
    return False


def scan_repository(root: Path, *, include_tests: bool = False) -> dict[str, Any]:
    root = Path(root)
    findings: list[dict[str, Any]] = []
    scanned: list[str] = []
    excluded: list[str] = []
    for path in _git_files(root):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.split("/")[-1].startswith(".env") and not relative.endswith(".example"):
            findings.append({"kind": "tracked-secret-file", "source": relative, "line": 0, "fingerprint": ""})
        if _is_excluded(relative, include_tests=include_tests):
            excluded.append(relative)
            continue
        scanned.append(relative)
        findings.extend(scan_file(path, source_name=relative))
    return {
        "status": "PASS" if not findings else "FAIL",
        "files_scanned": len(scanned),
        "files_excluded": len(excluded),
        "excluded_policy": "tests-and-historical-fixtures-excluded-from-release-scan",
        "findings": findings,
    }


def _scan_artifact(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
    findings = scan_path(path, source_root=root)
    return {
        "path": relative,
        "size_bytes": path.stat().st_size if path.is_file() else None,
        "sha256": _sha256_file(path) if path.is_file() else None,
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
    }


def build_audit_report(root: Path, *, artifacts: Sequence[Path] = ()) -> dict[str, Any]:
    root = Path(root).resolve()
    lock_errors = validate_lock_contract(root)
    secret_scan = scan_repository(root)
    bom = build_cyclonedx_bom(root)
    package_components = bom.get("components", [])
    unknown_licenses = sum(
        1
        for component in package_components
        if any(
            prop.get("name") == "kuantra:license-status"
            and prop.get("value") != "DECLARED_IN_LOCK"
            for prop in component.get("properties", [])
        )
    )
    license_paths = {
        "LICENSE": (root / "LICENSE").is_file(),
        "NOTICE": (root / "NOTICE").is_file(),
        "THIRD_PARTY_NOTICES.md": (root / "THIRD_PARTY_NOTICES.md").is_file(),
    }
    owner_review_required = unknown_licenses > 0 or not license_paths["LICENSE"] or not license_paths["THIRD_PARTY_NOTICES.md"]
    artifact_reports = [_scan_artifact(Path(path).resolve(), root) for path in artifacts]
    artifact_findings = [finding for item in artifact_reports for finding in item["findings"]]
    blocking_findings = [*lock_errors, *secret_scan["findings"], *artifact_findings]
    release_status = "FAIL" if blocking_findings else "OWNER_REVIEW_REQUIRED" if owner_review_required else "PASS"
    return {
        "schema_version": 1,
        "audit": "H05-supply-chain-sbom-license-secret-boundary",
        "source_commit": _git_commit(root),
        "lock_contract": {"status": "PASS" if not lock_errors else "FAIL", "errors": lock_errors},
        "sbom": bom,
        "secret_scan": secret_scan,
        "artifacts": artifact_reports,
        "license_review": {
            "status": "OWNER_DECISION_REQUIRED" if owner_review_required else "EVIDENCE_READY",
            "repository_files": license_paths,
            "unverified_package_license_count": unknown_licenses,
        },
        "vulnerability_evidence": {
            "branch_npm_audit": "recorded-by-command",
            "default_branch_dependabot": "external-repository-evidence-required",
        },
        "release_gate": {
            "status": release_status,
            "blocking_findings": blocking_findings,
            "owner_decision_required": owner_review_required,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit locked supply-chain and secret boundaries")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path, default=ROOT / "dist" / "h05-supply-chain-report.json")
    parser.add_argument("--artifact", action="append", type=Path, default=[])
    parser.add_argument("--release", action="store_true", help="fail if owner/legal review is unresolved")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    artifacts = [path if path.is_absolute() else root / path for path in args.artifact]
    report = build_audit_report(root, artifacts=artifacts)
    report_path = args.report if args.report.is_absolute() else root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = report["release_gate"]["status"]
    print(f"[supply-chain] {status}: {report_path}")
    if report["lock_contract"]["errors"] or report["secret_scan"]["findings"] or any(
        item["findings"] for item in report["artifacts"]
    ):
        return 1
    if args.release and status != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
