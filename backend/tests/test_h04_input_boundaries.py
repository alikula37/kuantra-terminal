"""H04 red tests for untrusted input and native/web render boundaries."""

from __future__ import annotations

import hashlib
import hmac
import io
import json

import pytest
from fastapi.testclient import TestClient

from app.api.webhook_tv import WEBHOOK_SECRET_KEY
from app.core.input_limits import MAX_CSV_BYTES, MAX_WEBHOOK_BYTES
from app.services.csv_importer import CsvTradeImporterService
from app.services.evidence_pack_export import EvidencePackExportService
from desktop.bridge import DesktopBridge
from desktop.push import PushChannel
from main import create_app


def _signed_webhook(body: bytes) -> dict[str, str]:
    signature = hmac.new(
        WEBHOOK_SECRET_KEY.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return {"X-TradingView-Signature": signature}


def _webhook_client() -> TestClient:
    return TestClient(create_app())


def test_csv_parser_rejects_invalid_utf8_and_oversized_input():
    with pytest.raises(ValueError, match="UTF-8"):
        CsvTradeImporterService.parse_and_preview_csv(b"symbol,side\n\xff,BUY\n")

    with pytest.raises(ValueError, match="size limit"):
        CsvTradeImporterService.parse_and_preview_csv(b"x" * (MAX_CSV_BYTES + 1))


def test_csv_upload_boundary_rejects_oversized_file():
    payload = b"x" * (MAX_CSV_BYTES + 1)
    response = _webhook_client().post(
        "/api/v1/journal/preview-csv",
        files={"file": ("oversized.csv", io.BytesIO(payload), "text/csv")},
    )

    assert response.status_code == 413
    assert "size limit" in response.json()["detail"].lower()


def test_webhook_rejects_non_object_and_invalid_signal_values():
    client = _webhook_client()

    list_body = b'[{"symbol":"BTCUSDT"}]'
    list_response = client.post(
        "/api/v1/webhook/tradingview",
        content=list_body,
        headers={"Content-Type": "application/json", **_signed_webhook(list_body)},
    )
    assert list_response.status_code == 400

    invalid_action = json.dumps(
        {"symbol": "BTCUSDT", "action": "HOLD", "price": 100.0},
        separators=(",", ":"),
    ).encode("utf-8")
    invalid_action_response = client.post(
        "/api/v1/webhook/tradingview",
        content=invalid_action,
        headers={"Content-Type": "application/json", **_signed_webhook(invalid_action)},
    )
    assert invalid_action_response.status_code == 400

    non_finite = b'{"symbol":"BTCUSDT","action":"BUY","price":NaN}'
    non_finite_response = client.post(
        "/api/v1/webhook/tradingview",
        content=non_finite,
        headers={"Content-Type": "application/json", **_signed_webhook(non_finite)},
    )
    assert non_finite_response.status_code == 400


def test_webhook_rejects_oversized_body_before_processing():
    body = b"{" + b'"padding":"' + b"x" * MAX_WEBHOOK_BYTES + b'"}'
    response = _webhook_client().post(
        "/api/v1/webhook/tradingview",
        content=body,
        headers={"Content-Type": "application/json", **_signed_webhook(body)},
    )

    assert response.status_code == 413


def test_http_cors_does_not_allow_arbitrary_origins_with_credentials():
    client = _webhook_client()
    evil = client.options(
        "/health",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert evil.status_code == 400
    assert "access-control-allow-origin" not in evil.headers


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    def call(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError("unsafe bridge input reached the runtime")


class _Dialog:
    def create_file_dialog(self, *_args, **_kwargs):
        return None


def test_desktop_bridge_rejects_malformed_base64_before_runtime_dispatch():
    runtime = _FakeRuntime()
    bridge = DesktopBridge(
        runtime,
        PushChannel(),
        index_url="file:///tmp/index.html",
        dialog_window_getter=lambda: _Dialog(),
    )

    response = bridge.request(
        {
            "method": "POST",
            "path": "/api/v1/journal/preview-csv",
            "files": [
                {
                    "field": "file",
                    "filename": "x.csv",
                    "data_b64": "not-valid-base64%%%",
                }
            ],
        }
    )

    assert response["status"] == 400
    assert runtime.calls == []


def test_desktop_bridge_rejects_unsafe_navigation_and_backend_paths(monkeypatch):
    runtime = _FakeRuntime()
    bridge = DesktopBridge(runtime, PushChannel(), index_url="file:///tmp/index.html")
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

    assert bridge.open_external("https://user:secret@example.com") == {"ok": False}
    assert bridge.open_external("https://") == {"ok": False}
    assert opened == []

    result = bridge.download({"path": "/api/v1/../../etc/passwd"})
    assert result == {"saved": False, "path": None, "status": 400}
    assert runtime.calls == []


def test_html_evidence_export_escapes_untrusted_markup():
    class Reader:
        def get_evidence_pack(self, _trade_id):
            return {
                "trade_id": "H04-HTML",
                "trade": {
                    "id": "H04-HTML",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "status": "CLOSED",
                    "notes": "</pre><script>alert('xss')</script>",
                },
                "read_source": "compatibility_legacy",
                "coverage_summary": {"overall": "PARTIAL"},
                "ledger_integrity": {"valid": True},
                "events": [],
                "event_count": 1,
            }

    artifact = EvidencePackExportService(Reader()).export("H04-HTML", "html")
    html = artifact.content.decode("utf-8")
    assert "<script>" not in html
    assert "&lt;/pre&gt;&lt;script&gt;" in html
