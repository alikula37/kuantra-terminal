"""Security review (ersinkoc/security-check) regression tests.

These tests pin the fixes for the confirmed findings of the 2026-09-15 deep
audit: local file containment, kill-switch fail-closed behaviour, gateway
surface isolation, signal-signature verification, live-mode gates, bounded
numeric inputs, bounded request bodies, bounded import provenance, bounded
archive reads and non-loopback gateway refusal.
"""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.api import endpoints
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.broker_import_service import BrokerImportService
from desktop.gateway import IntegrationsGateway, build_gateway_app
from main import create_app


def _client(tmp_path, monkeypatch, name: str = "sec.sqlite") -> TestClient:
    driver = SQLiteDriver(str(tmp_path / name))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# 1. Local file containment (model downloader)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["../../evil.gguf", "/tmp/evil.gguf", "..", "a/b.gguf", ""])
def test_model_downloader_rejects_names_outside_models_dir(name):
    from app.core import model_downloader as module

    with pytest.raises(ValueError):
        module.model_downloader.start_download(model_name=name)
    with pytest.raises(ValueError):
        module.model_downloader.cancel_download(model_name=name)
    status = module.model_downloader.get_status(model_name=name)
    assert status["status"] == "INVALID_MODEL_NAME"
    assert status.get("file_path") is None


def test_model_downloader_status_hides_arbitrary_paths():
    from app.core import model_downloader as module

    status = module.model_downloader.get_status(model_name="/etc/hosts")
    assert status["status"] == "INVALID_MODEL_NAME"
    assert "size" not in repr(status).lower() or "downloaded_bytes" not in status


def test_model_endpoint_rejects_traversal(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "model.sqlite")
    resume = client.post("/api/v1/system/model/resume", json={"model_name": "../../evil.gguf"})
    assert resume.status_code == 400
    status = client.get("/api/v1/system/model/status", params={"model_name": "/etc/hosts"})
    assert status.status_code == 400


# ---------------------------------------------------------------------------
# 2. Panic kill-switch: no fabricated closes, no hardcoded disarm
# ---------------------------------------------------------------------------


def test_panic_trigger_does_not_write_fabricated_closes(tmp_path, monkeypatch):
    from app.services.biometrics import panic_switch as module

    driver = SQLiteDriver(str(tmp_path / "panic.sqlite"))
    driver.record_trade_with_evidence(
        {
            "id": "PANIC-1",
            "symbol": "XAUUSD",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 2500.0,
            "qty": 1.0,
            "entry_time": "2026-09-10T10:00:00Z",
            "status": "OPEN",
            "qty_unit": "BASE",
        },
        event_type="IntentRecorded",
        idempotency_key="panic:test:1",
        occurred_at="2026-09-10T10:00:00Z",
        provenance={"source": "security_test"},
    )

    engine = module.PanicKillSwitchEngine()
    event = engine.trigger_emergency_kill_switch(source="SECURITY_TEST")

    assert event["flattened_positions_count"] == 0
    assert event["flattening"] == "DISABLED_NO_ORDER_AUTHORITY"
    assert driver.get_trade("PANIC-1")["status"] == "OPEN"
    assert engine.is_locked_down is True


def test_panic_disarm_rejects_hardcoded_pins(monkeypatch):
    from app.services.biometrics import panic_switch as module

    monkeypatch.delenv("KUANTRA_PANIC_DISARM_SECRET", raising=False)
    engine = module.PanicKillSwitchEngine()
    engine.trigger_emergency_kill_switch(source="SECURITY_TEST")
    for guess in ("1234", "admin", "WEBAUTHN_PASSKEY_VERIFIED"):
        with pytest.raises(ValueError):
            engine.disarm_lockdown(guess)
    assert engine.is_locked_down is True


def test_panic_disarm_requires_the_configured_secret(monkeypatch):
    from app.services.biometrics import panic_switch as module

    monkeypatch.setenv("KUANTRA_PANIC_DISARM_SECRET", "s3cret-disarm-value")
    engine = module.PanicKillSwitchEngine()
    engine.trigger_emergency_kill_switch(source="SECURITY_TEST")
    with pytest.raises(ValueError):
        engine.disarm_lockdown("1234")
    result = engine.disarm_lockdown("s3cret-disarm-value")
    assert result["status"] == "DISARMED"
    assert engine.is_locked_down is False


# ---------------------------------------------------------------------------
# 3. Gateway surface isolation and bind policy
# ---------------------------------------------------------------------------


def test_gateway_mounts_only_ingest_ws_and_health():
    client = TestClient(build_gateway_app())
    assert client.get("/api/v1/tradingview/observations").status_code == 404
    assert client.post("/api/v1/tradingview/observations/X/confirm", json={}).status_code == 404
    assert client.post("/api/v1/webhook/tradingview", json={"symbol": "XAUUSD", "action": "buy", "price": 2500}).status_code == 401
    assert client.get("/health").status_code == 200


def test_review_routes_remain_on_the_ui_app(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "ui.sqlite")
    assert client.get("/api/v1/tradingview/observations").status_code == 200


def test_gateway_refuses_non_loopback_bind(monkeypatch):
    monkeypatch.delenv("KUANTRA_ALLOW_NON_LOOPBACK_GATEWAY", raising=False)
    gateway = IntegrationsGateway(runtime=None, host="0.0.0.0", port=8765)
    assert gateway.start() is False
    assert gateway.enabled is False


# ---------------------------------------------------------------------------
# 4. Copy-signal signature verification
# ---------------------------------------------------------------------------


def _copy_signal() -> dict:
    return {
        "signal_id": "SIG-TEST-1",
        "master_node_id": "master-1",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "risk_pct": 1.0,
        "timestamp": 1.0,
    }


def test_copy_engine_rejects_length_only_signature(monkeypatch):
    from app.services.p2p import copy_engine as module

    monkeypatch.delenv("KUANTRA_COPY_SIGNAL_SECRET", raising=False)
    engine = module.ZeroKnowledgeCopyEngine()
    signal = {**_copy_signal(), "signature": "x" * 64}
    assert engine.verify_signal(signal) is False
    result = engine.execute_copy_signal(signal)
    assert result["status"] == "REJECTED"


def test_copy_engine_accepts_valid_hmac(monkeypatch):
    from app.services.p2p import copy_engine as module

    monkeypatch.setenv("KUANTRA_COPY_SIGNAL_SECRET", "copy-secret")
    engine = module.ZeroKnowledgeCopyEngine()
    signal = {**_copy_signal(), "signature": "x" * 64}
    signal["signature"] = module.sign_copy_signal(signal, "copy-secret")
    assert engine.verify_signal(signal) is True
    assert engine.verify_signal({**_copy_signal(), "signature": "x" * 64}) is False


def test_copy_broadcast_requires_configured_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("KUANTRA_COPY_SIGNAL_SECRET", raising=False)
    client = _client(tmp_path, monkeypatch, "copy-broadcast.sqlite")
    payload = {"symbol": "BTCUSDT", "side": "BUY", "entry_price": 100.0,
               "stop_loss": 95.0, "take_profit": 110.0}
    assert client.post("/api/v1/p2p/copy/broadcast", json=payload).status_code == 503

    monkeypatch.setenv("KUANTRA_COPY_SIGNAL_SECRET", "copy-secret")
    response = client.post("/api/v1/p2p/copy/broadcast", json=payload)
    assert response.status_code == 200
    from app.services.p2p import copy_engine as module

    assert module.copy_trading_engine.verify_signal(response.json()) is True


# ---------------------------------------------------------------------------
# 5. Live-mode gates on order routes
# ---------------------------------------------------------------------------


def test_live_mode_is_rejected_on_cancel_and_open_order_routes(tmp_path, monkeypatch):
    calls = []

    class SpyEngine:
        def fetch_open_orders(self, **kwargs):
            calls.append(("open", kwargs))
            return {}

        def cancel_order(self, **kwargs):
            calls.append(("cancel", kwargs))
            return {"success": True}

    monkeypatch.setattr(endpoints, "ccxt_execution_engine", SpyEngine())
    client = _client(tmp_path, monkeypatch, "live.sqlite")
    assert client.get("/api/v1/execution/orders/open?mode=LIVE").status_code == 403
    assert client.delete("/api/v1/execution/orders/123?mode=LIVE").status_code == 403
    assert calls == []


# ---------------------------------------------------------------------------
# 6. Bounded numeric inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [-1.0, 0.0, float("inf"), float("nan"), 1e30])
def test_trade_close_schema_rejects_unbounded_values(bad):
    with pytest.raises(ValidationError):
        endpoints.TradeCloseSchema(exit_price=bad)


def test_trade_close_schema_rejects_non_finite_commission():
    with pytest.raises(ValidationError):
        endpoints.TradeCloseSchema(exit_price=100.0, commission=float("nan"))


def test_reconciliation_correction_requires_bounded_numbers():
    from app.services.reconciliation_inbox import (
        ReconciliationInboxError,
        ReconciliationInboxService,
    )

    for bad in ({"qty": -5}, {"entry_price": 0}, {"pnl": float("inf")}, {"commission": -1e30}, {"status": "WHATEVER"}):
        with pytest.raises(ReconciliationInboxError):
            ReconciliationInboxService._validate_correction(bad)
    validated = ReconciliationInboxService._validate_correction({"pnl": 1.5, "qty": 2})
    assert validated == {"pnl": 1.5, "qty": 2}


def test_trades_list_limit_is_bounded(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "limit.sqlite")
    assert client.get("/api/v1/trades?limit=0").status_code == 422
    assert client.get("/api/v1/trades?limit=100000").status_code == 422
    assert client.get("/api/v1/trades?limit=-1").status_code == 422


def test_update_trade_rejects_unknown_columns(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "update.sqlite"))
    driver.insert_trade({
        "id": "SEC-UPD-1", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 100.0,
        "qty": 1.0, "entry_time": "2026-09-10T10:00:00Z", "status": "OPEN",
    })
    with pytest.raises(ValueError):
        driver.update_trade("SEC-UPD-1", {"evil_column": 1})
    assert driver.update_trade("SEC-UPD-1", {"status": "CANCELED"})["status"] == "CANCELED"


# ---------------------------------------------------------------------------
# 7. Webhook body and auth hardening
# ---------------------------------------------------------------------------


def test_webhook_rejects_chunked_oversize_body(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "webhook.sqlite")
    chunk = b"A" * (32 * 1024)

    def body_stream():
        for _ in range(5):  # 160 KB > 64 KB limit, no Content-Length
            yield chunk

    response = client.post("/api/v1/webhook/tradingview", content=body_stream())
    assert response.status_code == 413


def test_webhook_auth_handles_non_ascii_without_crashing(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "webhook-auth.sqlite")
    response = client.post(
        "/api/v1/webhook/tradingview",
        json={"symbol": "XAUUSD", "action": "buy", "price": 2500, "passphrase": "päss-word"},
    )
    assert response.status_code in (400, 401)


# ---------------------------------------------------------------------------
# 8. Bounded import provenance and archive reads
# ---------------------------------------------------------------------------


def test_broker_import_review_discrepancies_are_count_bounded(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "broker.sqlite"))
    service = BrokerImportService(ledger)
    orders = [
        {
            "orderId": f"O-{index}",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "origQty": "2",
            "executedQty": "2",
            "avgPrice": "100",
            "updateTime": "2026-09-10T10:00:00Z",
        }
        for index in range(150)
    ]
    report = service.import_records("BINANCE", orders=orders, fills=[])
    assert report["normalized_record_count"] == 150
    assert len(report["review"]["discrepancies"]) <= 100
    assert report["review"]["discrepancy_count"] >= 300
    assert report["review"]["discrepancies_truncated"] is True


def test_migration_member_read_is_byte_bounded():
    from app.services import macos_migration as module

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data/big.bin", b"A" * 5000)
    buffer.seek(0)
    with zipfile.ZipFile(buffer) as archive:
        with pytest.raises(module.MigrationBundleError):
            module._read_member_bounded(archive, "data/big.bin", limit=1000)
        assert module._read_member_bounded(archive, "data/big.bin", limit=5000) == b"A" * 5000


# ---------------------------------------------------------------------------
# 9. Generated-code escaping
# ---------------------------------------------------------------------------


def test_generated_python_string_escapes_injection():
    from app.services.ai.reverse_skill import _safe_python_string

    injected = 'evil"\nimport os\nos.system("id")\nx="'
    rendered = _safe_python_string(injected)
    assert "\n" not in rendered
    assert rendered.startswith('"') and rendered.endswith('"')
    assert '"' not in rendered[1:-1].replace('\\"', "")


def test_exchange_error_messages_are_generic():
    from app.services.exchange.credentials_manager import _safe_exchange_error_message

    for kind in ("AUTHENTICATION_ERROR", "NETWORK_ERROR", "UNEXPECTED_ERROR"):
        message = _safe_exchange_error_message(kind)
        lowered = message.lower()
        assert "signature" not in lowered
        assert "api key" not in lowered
        assert message


def test_package_linux_never_downloads_unverified_tool():
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "scripts" / "package_linux.sh"
    text = script.read_text(encoding="utf-8")
    assert "curl" not in text
    assert "continuous/appimagetool" not in text
    assert "APPIMAGETOOL" in text
    assert "exit 1" in text
