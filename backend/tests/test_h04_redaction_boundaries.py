"""H04 misuse tests for evidence and diagnostics redaction."""

from __future__ import annotations

import zipfile

import pytest

from app.core import logging_config
from app.services.evidence_pack_export import EvidencePackExportError, EvidencePackExportService


def _pack_with_notes(notes: str) -> dict:
    return {
        "trade_id": "H04-REDACTION",
        "trade": {
            "id": "H04-REDACTION",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "CLOSED",
            "notes": notes,
        },
        "read_source": "compatibility_legacy",
        "coverage_summary": {"overall": "PARTIAL"},
        "ledger_integrity": {"valid": True},
        "events": [],
        "event_count": 1,
    }


def test_redaction_scrubs_secret_email_and_local_path_values():
    raw = "api_key=secret-value-123456 /Users/alice/private/journal.sqlite alice@example.com"
    redacted = logging_config.redact_sensitive_text(raw)

    assert "secret-value-123456" not in redacted
    assert "alice@example.com" not in redacted
    assert "/Users/alice/private/journal.sqlite" not in redacted
    assert "[REDACTED_PATH]" in redacted


def test_diagnostics_zip_contains_redacted_log_content(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "synthetic.log").write_text(
        "api_key=secret-value-123456 path=/Users/alice/private/journal.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(logging_config, "LOGS_DIR", log_dir)
    output = tmp_path / "diagnostics.zip"

    archive_path = logging_config.export_logs_zip(str(output))

    with zipfile.ZipFile(archive_path) as archive:
        content = archive.read("synthetic.log").decode("utf-8")
    assert "secret-value-123456" not in content
    assert "/Users/alice/private/journal.sqlite" not in content


@pytest.mark.parametrize("unsafe", [
    "api_key=secret-value-123456",
    "Bearer secret-token-value-123456",
    "/Users/alice/private/journal.sqlite",
])
def test_evidence_export_fails_closed_on_secret_or_local_path_value(unsafe):
    service = EvidencePackExportService(
        type("Reader", (), {"get_evidence_pack": lambda _self, _trade_id: _pack_with_notes(unsafe)})()
    )

    with pytest.raises(EvidencePackExportError, match="not exportable"):
        service.export("H04-REDACTION", "json")
