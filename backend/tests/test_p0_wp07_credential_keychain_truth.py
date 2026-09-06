"""P0-WP07 regression tests for keychain-only credential persistence."""

import pytest
from fastapi.testclient import TestClient
from main import create_app

from app.api.webhook_tv import WEBHOOK_SECRET_KEY
from app.core.security import vault
from app.db.sqlite_driver import sqlite_driver
from app.services.exchange.credentials_manager import ExchangeCredentialsManager
from app.services.security.credential_store import (
    CredentialStoreStatus,
    CredentialStoreUnavailable,
    credential_store,
    credential_store_status,
)
from app.services.settings_service import settings_service


def test_tests_use_an_explicit_ephemeral_provider():
    status = credential_store_status()
    assert status["backend"] == "memory-test"
    assert status["available"] is True
    assert status["persistent"] is False


def test_exchange_secrets_are_not_written_to_sqlite():
    manager = ExchangeCredentialsManager()
    exchange_id = "binance_spot"
    raw_key = "wp07_key_that_must_not_reach_sqlite"
    raw_secret = "wp07_secret_that_must_not_reach_sqlite"

    manager.save_credentials(
        exchange_id=exchange_id,
        name="WP07",
        api_key=raw_key,
        api_secret=raw_secret,
        is_testnet=True,
    )
    try:
        stored = manager.get_decrypted_credentials(exchange_id)
        assert stored and stored["api_key"] == raw_key
        assert stored["api_secret"] == raw_secret
        assert stored["storage_backend"] == "memory-test"

        with sqlite_driver.get_connection() as conn:
            ref_row = conn.execute(
                "SELECT api_key_ref, api_secret_ref, passphrase_ref FROM exchange_credential_refs WHERE exchange_id = ?",
                (exchange_id,),
            ).fetchone()
            legacy_row = conn.execute(
                "SELECT 1 FROM exchange_credentials WHERE exchange_id = ?",
                (exchange_id,),
            ).fetchone()
        assert ref_row is not None
        assert legacy_row is None
        assert raw_key not in str(dict(ref_row))
        assert raw_secret not in str(dict(ref_row))
    finally:
        manager.delete_credentials(exchange_id)


def test_unavailable_store_fails_closed(monkeypatch):
    previous = credential_store.status
    monkeypatch.setattr(
        credential_store,
        "status",
        CredentialStoreStatus(
            backend="unavailable",
            available=False,
            persistent=False,
            reason="test unavailable",
        ),
    )
    try:
        with pytest.raises(CredentialStoreUnavailable):
            ExchangeCredentialsManager().save_credentials(
                exchange_id="okx",
                name="WP07",
                api_key="key",
                api_secret="secret",
                passphrase="pass",
            )
    finally:
        monkeypatch.setattr(credential_store, "status", previous)


def test_api_returns_structured_503_when_keychain_is_unavailable(monkeypatch):
    previous = credential_store.status
    monkeypatch.setattr(
        credential_store,
        "status",
        CredentialStoreStatus(
            backend="unavailable",
            available=False,
            persistent=False,
            reason="test unavailable",
        ),
    )
    try:
        response = TestClient(create_app()).post(
            "/api/v1/exchange/credentials",
            json={
                "exchange_id": "binance_spot",
                "api_key": "key",
                "api_secret": "secret",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "CREDENTIAL_STORE_UNAVAILABLE"
    finally:
        monkeypatch.setattr(credential_store, "status", previous)


def test_generic_vault_secret_has_no_sqlite_settings_row():
    key = "WP07_GENERIC_SECRET"
    value = "wp07_generic_value"
    settings_service.store_vault_secret(key, value)
    try:
        assert vault.get_secret(key) == value
        with sqlite_driver.get_connection() as conn:
            row = conn.execute("SELECT value FROM user_settings WHERE key = ?", (key,)).fetchone()
        assert row is None
    finally:
        credential_store.delete_secret(f"generic/{key}")
        vault.delete_secret(key)


def test_webhook_secret_is_not_the_old_shared_default():
    assert WEBHOOK_SECRET_KEY != "change_me_in_production"
