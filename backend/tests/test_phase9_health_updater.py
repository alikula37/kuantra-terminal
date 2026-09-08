import os
from app.core.telemetry import PrivacyTelemetryManager
import pytest
from app.core.logging_config import redact_sensitive_text, LOG_FILE_PATH, export_logs_zip
from app.core.telemetry import telemetry_manager

class TestPhase9HealthAndUpdater:
    """Test suite for PII log redaction, opt-in privacy telemetry, and Ed25519 updater manifest."""

    def test_log_rotation_and_file_creation(self):
        assert LOG_FILE_PATH is not None
        assert os.path.exists(os.path.dirname(str(LOG_FILE_PATH)))

        zip_out = export_logs_zip()
        assert os.path.exists(zip_out)
        assert zip_out.endswith(".zip")

    def test_pii_redaction_secrets_and_auth_headers(self):
        # 1. API Keys & Secrets
        raw_key = "Accessing binance with api_key: vmPUAZKZBm6rVo304oGGNZuJJ9VbdwjpCXkj"
        clean_key = redact_sensitive_text(raw_key)
        assert "vmPUAZKZ" not in clean_key
        assert "[REDACTED_SECRET]" in clean_key

        # 2. Stripe & Github tokens
        raw_gh = "Pushing commit with ghp_EXAMPLEMOCKTOKENTESTING1234567890 to remote"
        clean_gh = redact_sensitive_text(raw_gh)
        assert "ghp_EXAMPLEMOCKTOKEN" not in clean_gh
        assert "[REDACTED_GITHUB_TOKEN]" in clean_gh

        # 3. Bearer Auth Tokens
        raw_auth = "Headers: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        clean_auth = redact_sensitive_text(raw_auth)
        assert "eyJhbGci" not in clean_auth

        # 4. Emails
        raw_email = "Support notification for user trader.one@institution.com"
        clean_email = redact_sensitive_text(raw_email)
        assert "trader.one@institution.com" not in clean_email
        assert "[REDACTED_EMAIL]" in clean_email

    def test_telemetry_opt_in_default_and_toggle(self):
        # Set opt-in False
        telemetry_manager.set_opt_in(False)
        assert telemetry_manager.is_opted_in() is False

        # Set opt-in True
        telemetry_manager.set_opt_in(True)
        assert telemetry_manager.is_opted_in() is True

    def test_offline_crash_queue_spooling_and_flushing(self, tmp_path):
        telemetry_manager.queue_file = tmp_path / "telemetry_queue.json"
        telemetry_manager.set_opt_in(False)
        telemetry_manager.spool_crash(
            "WebSocketDisconnect",
            "Lost connection to Binance socket with token secret_token_12345",
            "Traceback (most recent call last):\n  File 'binance_client.py', line 50"
        )
        assert telemetry_manager.get_queued_crashes_count() >= 1

        # While opted-out, flush skips network dispatch
        res_skipped = telemetry_manager.flush_queue()
        assert res_skipped["status"] == "SKIPPED_OPT_OUT"

        # Opt-in without a configured transport retains the queue and does not
        # claim that a network delivery happened.
        telemetry_manager.set_opt_in(True)
        res_without_transport = telemetry_manager.flush_queue()
        assert res_without_transport["status"] == "NO_TRANSPORT"
        assert telemetry_manager.get_queued_crashes_count() == 1

        # An explicit test transport can acknowledge delivery and clear it.
        delivery_manager = PrivacyTelemetryManager(
            queue_file=telemetry_manager.queue_file,
            flush_transport=lambda records: True,
        )
        delivery_manager.set_opt_in(True)
        res_flushed = delivery_manager.flush_queue()
        assert res_flushed["status"] == "SUCCESS"
        assert telemetry_manager.get_queued_crashes_count() == 0

    def test_health_endpoint_reports_running_backend(self):
        # The Tauri updater manifest is gone with the sidecar; the in-process /health
        # endpoint is what the pywebview shell (and its smoke test) relies on.
        from fastapi.testclient import TestClient
        from main import create_app

        client = TestClient(create_app())
        res = client.get("/health")
        assert res.status_code == 200
        payload = res.json()
        assert payload["status"] == "online"
        assert payload["version"]
