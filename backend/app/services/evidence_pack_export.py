"""Deterministic, source-linked Trade Evidence Pack export service.

The read adapter already removes raw payloads and exposes ledger integrity. This
module turns that bounded object into a portable JSON or static HTML artifact,
with a stable payload digest and a separate artifact digest. It never adds
receipt time, machine paths, credentials, or other non-deterministic fields.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import html
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from app.db.repositories.evidence_ledger_repo import canonical_json
from app.services.trade_read_adapter import TradeReadAdapter, trade_read_adapter


class EvidencePackExportError(ValueError):
    """Raised when an evidence pack cannot be exported safely."""


class EvidencePackNotFoundError(EvidencePackExportError):
    """Raised when a trade has neither a projection nor ledger evidence."""


_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|api[_-]?secret|password|passphrase|private[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|authorization|credential)",
    re.IGNORECASE,
)


def _assert_export_safe(value: Any, path: str = "pack") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                raise EvidencePackExportError(f"{path}.{key} is not exportable")
            _assert_export_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_export_safe(child, f"{path}[{index}]")


def _safe_trade_id(trade_id: str) -> str:
    normalized = str(trade_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", normalized):
        raise EvidencePackExportError(
            "trade_id must be 1-160 characters using letters, numbers, '.', '_', ':' or '-'")
    return normalized


@dataclass(frozen=True)
class EvidencePackArtifact:
    """Immutable bytes and hashes returned to the HTTP/desktop boundary."""

    trade_id: str
    artifact_format: str
    artifact_version: str
    content: bytes
    media_type: str
    filename: str
    payload_sha256: str
    artifact_sha256: str


class EvidencePackExportService:
    """Build deterministic JSON/HTML exports from a read-only trade adapter."""

    ARTIFACT_VERSION = "1"

    def __init__(self, adapter: Optional[TradeReadAdapter] = None):
        self.adapter = adapter or trade_read_adapter

    def _load_pack(self, trade_id: str) -> Dict[str, Any]:
        trade_id = _safe_trade_id(trade_id)
        pack = self.adapter.get_evidence_pack(trade_id)
        if not isinstance(pack, dict):
            raise EvidencePackExportError("evidence pack must be an object")
        if pack.get("trade") is None and int(pack.get("event_count") or 0) == 0:
            raise EvidencePackNotFoundError(f"trade evidence not found: {trade_id}")
        _assert_export_safe(pack)
        snapshot_sha256 = pack.get("snapshot_sha256")
        if snapshot_sha256 is not None:
            snapshot = {key: value for key, value in pack.items() if key != "snapshot_sha256"}
            expected = hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
            if snapshot_sha256 != expected:
                raise EvidencePackExportError("evidence pack snapshot digest is invalid")
        return pack

    @staticmethod
    def _json_payload(pack: Dict[str, Any]) -> tuple[bytes, str]:
        payload_text = canonical_json(pack)
        return payload_text.encode("utf-8"), hashlib.sha256(payload_text.encode("utf-8")).hexdigest()

    def _json_artifact(self, trade_id: str, pack: Dict[str, Any]) -> EvidencePackArtifact:
        payload_bytes, payload_sha256 = self._json_payload(pack)
        envelope = {
            "artifact_type": "kuantra.trade_evidence_pack",
            "artifact_version": self.ARTIFACT_VERSION,
            "trade_id": trade_id,
            "payload_sha256": payload_sha256,
            "pack": pack,
        }
        content = (canonical_json(envelope) + "\n").encode("utf-8")
        return EvidencePackArtifact(
            trade_id=trade_id,
            artifact_format="json",
            artifact_version=self.ARTIFACT_VERSION,
            content=content,
            media_type="application/json",
            filename=f"kuantra-evidence-{trade_id}.json",
            payload_sha256=payload_sha256,
            artifact_sha256=hashlib.sha256(content).hexdigest(),
        )

    def _html_artifact(self, trade_id: str, pack: Dict[str, Any]) -> EvidencePackArtifact:
        payload_bytes, payload_sha256 = self._json_payload(pack)
        payload_text = payload_bytes.decode("utf-8")
        title = html.escape(f"Kuantra Trade Evidence Pack — {trade_id}")
        escaped_trade_id = html.escape(trade_id)
        escaped_payload_hash = html.escape(payload_sha256)
        content_text = (
            "<!doctype html>\n"
            "<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{title}</title>"
            "<style>body{font-family:system-ui,sans-serif;margin:2rem;"
            "background:#0b1220;color:#e5e7eb}pre{white-space:pre-wrap;"
            "background:#111827;padding:1rem;border-radius:.5rem;overflow:auto}"
            ".meta{color:#93c5fd}</style></head><body>"
            f"<h1>{title}</h1><p class=\"meta\">Trade ID: {escaped_trade_id}</p>"
            f"<p class=\"meta\">Payload SHA-256: {escaped_payload_hash}</p>"
            f"<pre>{html.escape(payload_text)}</pre>"
            "</body></html>\n"
        )
        content = content_text.encode("utf-8")
        return EvidencePackArtifact(
            trade_id=trade_id,
            artifact_format="html",
            artifact_version=self.ARTIFACT_VERSION,
            content=content,
            media_type="text/html; charset=utf-8",
            filename=f"kuantra-evidence-{trade_id}.html",
            payload_sha256=payload_sha256,
            artifact_sha256=hashlib.sha256(content).hexdigest(),
        )

    @staticmethod
    def _csv_cell(value: Any) -> str:
        if value is None:
            text = ""
        elif isinstance(value, (dict, list)):
            text = canonical_json(value)
        else:
            text = str(value)
        if text.startswith(("=", "@")):
            return f"'{text}"
        if text.startswith(("+", "-")):
            try:
                Decimal(text)
            except InvalidOperation:
                return f"'{text}"
        return text

    def _csv_artifact(self, trade_id: str, pack: Dict[str, Any]) -> EvidencePackArtifact:
        _, payload_sha256 = self._json_payload(pack)
        trade = pack.get("trade") if isinstance(pack.get("trade"), dict) else {}
        summary = pack.get("coverage_summary") if isinstance(pack.get("coverage_summary"), dict) else {}
        rules = pack.get("applicable_rules") if isinstance(pack.get("applicable_rules"), list) else []
        events = pack.get("events") if isinstance(pack.get("events"), list) else []
        source_event_hashes = sorted({
            str(event.get("event_hash"))
            for event in events
            if isinstance(event, dict) and event.get("event_hash")
        })
        columns = [
            "trade_id", "snapshot_sha256", "symbol", "side", "status", "pnl",
            "read_source", "overall_coverage", "trade_snapshot", "fees",
            "funding_transfer", "market_context", "ledger_integrity", "rule_ids",
            "source_event_hashes",
        ]
        row = {
            "trade_id": trade_id,
            "snapshot_sha256": pack.get("snapshot_sha256") or payload_sha256,
            "symbol": trade.get("symbol"),
            "side": trade.get("side"),
            "status": trade.get("status"),
            "pnl": trade.get("pnl"),
            "read_source": pack.get("read_source"),
            "overall_coverage": summary.get("overall", "UNKNOWN"),
            "trade_snapshot": summary.get("trade_snapshot", "UNKNOWN"),
            "fees": summary.get("fees", "UNKNOWN"),
            "funding_transfer": summary.get("funding_transfer", "UNKNOWN"),
            "market_context": summary.get("market_context", "UNKNOWN"),
            "ledger_integrity": (
                "COMPLETE"
                if isinstance(pack.get("ledger_integrity"), dict)
                and pack["ledger_integrity"].get("valid") is True
                else "UNKNOWN"
            ),
            "rule_ids": [
                rule.get("rule_id")
                for rule in rules
                if isinstance(rule, dict) and rule.get("rule_id")
            ],
            "source_event_hashes": source_event_hashes,
        }
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerow({column: self._csv_cell(row.get(column)) for column in columns})
        content = output.getvalue().encode("utf-8")
        return EvidencePackArtifact(
            trade_id=trade_id,
            artifact_format="csv",
            artifact_version=self.ARTIFACT_VERSION,
            content=content,
            media_type="text/csv; charset=utf-8",
            filename=f"kuantra-evidence-{trade_id}.csv",
            payload_sha256=payload_sha256,
            artifact_sha256=hashlib.sha256(content).hexdigest(),
        )

    def export(self, trade_id: str, artifact_format: str = "json") -> EvidencePackArtifact:
        normalized_trade_id = _safe_trade_id(trade_id)
        normalized_format = str(artifact_format or "").strip().lower()
        if normalized_format not in {"json", "html", "csv"}:
            raise EvidencePackExportError("format must be json, html, or csv")
        pack = self._load_pack(normalized_trade_id)
        if normalized_format == "json":
            return self._json_artifact(normalized_trade_id, pack)
        if normalized_format == "csv":
            return self._csv_artifact(normalized_trade_id, pack)
        return self._html_artifact(normalized_trade_id, pack)


evidence_pack_export_service = EvidencePackExportService()
