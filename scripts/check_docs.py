"""Dependency-free documentation routing/link gate; no runtime or network access."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


class DocumentationError(ValueError):
    pass


CURRENT_ROLES = ("agent-entry", "product-contract", "current-roadmap", "current-status", "current-work-package")
ROLE = re.compile(r"<!--\s*doc-role:\s*([\w-]+)\s*-->")
LINK = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")


def run_checks(root: Path) -> dict[str, int]:
    root = root.resolve()
    errors: list[str] = []
    try:
        registry = json.loads((root / "docs/documentation.json").read_text(encoding="utf-8"))
        documents = registry["documents"]
        startup = registry["startup"]
        counts = registry["archived_unchecked_counts"]
        if registry.get("schema_version") != 1 or not isinstance(documents, dict) or not isinstance(startup, list) or not isinstance(counts, dict):
            raise ValueError("invalid registry schema")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DocumentationError(f"invalid documentation registry: {exc}") from exc

    def local_path(relative: str) -> Path:
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise DocumentationError(f"invalid document path: {relative!r}")
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise DocumentationError(f"document escapes repository: {relative}")
        return target

    texts: dict[str, str] = {}
    for name, role in documents.items():
        if role not in (*CURRENT_ROLES, "reference", "archived"):
            errors.append(f"unknown role: {name}: {role}")
        path = local_path(name)
        try:
            texts[name] = path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"missing document: {name}")
            continue
        markers = ROLE.findall(texts[name])
        if role in CURRENT_ROLES and markers != [role]:
            errors.append(f"current role marker mismatch: {name}")
        if role == "archived" and markers != ["archived"]:
            errors.append(f"archive marker missing or conflicting: {name}")
        if role not in CURRENT_ROLES and any(m in CURRENT_ROLES for m in markers):
            errors.append(f"competing current role: {name}")

    expected_startup = []
    for role in CURRENT_ROLES:
        matches = [p for p, r in documents.items() if r == role]
        if len(matches) != 1:
            errors.append(f"expected exactly one {role}, found {len(matches)}")
        else:
            expected_startup.append(matches[0])
    if startup != expected_startup:
        errors.append("startup must contain exactly the five current roles in order; no archive")
    for item in startup:
        local_path(item)
        if documents.get(item) == "archived" or "/archive/" in item:
            errors.append(f"archived mandatory startup document: {item}")

    # A newly added competing plan cannot bypass the registry merely by omission.
    managed = list(root.glob("*.md")) + list((root / "docs").rglob("*.md"))
    for path in managed:
        name = path.relative_to(root).as_posix()
        if name not in documents:
            errors.append(f"unregistered document: {name}")

    checked_links = 0
    for name, source in texts.items():
        # Archived links are historical references; code paths may legitimately no
        # longer exist. Current/reference docs must resolve local inline links.
        if documents[name] == "archived":
            continue
        source = re.sub(r"```.*?```", "", source, flags=re.S)
        for link in LINK.findall(source):
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (local_path(name).parent / unquote(parsed.path)).resolve()
            checked_links += 1
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f"broken local link: {name}: {link}")

    for name, count in counts.items():
        if documents.get(name) != "archived" or not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"invalid archived obligation count: {name}")
            continue
        actual = len(re.findall(r"^- \[ \]", texts.get(name, ""), re.M))
        if actual != count:
            errors.append(f"archived unchecked criteria changed: {name}: {actual} != {count}")
    for name, role in documents.items():
        if role == "archived" and "/work-packages/" in name and name not in counts:
            errors.append(f"missing archived obligation count: {name}")

    status = next((p for p, r in documents.items() if r == "current-status"), None)
    active = next((p for p, r in documents.items() if r == "current-work-package"), None)
    if active:
        if not re.search(r"^status: (Ready|InProgress)\s*$", texts.get(active, ""), re.M):
            errors.append("active work package must be Ready or InProgress")
        if status:
            targets = {(local_path(status).parent / urlsplit(link).path).resolve() for link in LINK.findall(texts.get(status, "")) if not urlsplit(link).scheme}
            if local_path(active) not in targets:
                errors.append("STATUS must link to the selected active work package")
    if errors:
        raise DocumentationError("\n".join(errors))
    return {"documents": len(texts), "local_links": checked_links, "startup_documents": len(startup)}


def main() -> int:
    try:
        result = run_checks(Path(__file__).resolve().parents[1])
    except DocumentationError as exc:
        print(f"[docs] FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"[docs] PASS: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
