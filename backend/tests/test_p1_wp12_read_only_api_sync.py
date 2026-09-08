"""P1-WP12 read-only CCXT snapshot, pagination, scope and manifest contracts."""

from dataclasses import replace

import ccxt
import pytest
from fastapi.testclient import TestClient

from main import create_app
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.services.broker_import_service import BrokerImportService, BrokerImportValidationError
from app.services.exchange.read_only_broker_sync import (
    ReadOnlyBrokerSyncService,
    ReadOnlyCredentialScopeError,
    ReadOnlyExchangeClient,
    ReadOnlySnapshotManifest,
    SnapshotManifestValidationError,
)
from app.services.exchange.credentials_manager import ExchangeCredentialsManager
from app.db.sqlite_driver import sqlite_driver


class _PagedClient:
    def __init__(self):
        self.order_calls = []
        self.fill_calls = []
        self.fill_attempts = 0

    def fetch_orders(self, *, symbol, since, limit, params):
        self.order_calls.append((symbol, since, limit, params))
        if since is None:
            return [
                {
                    "id": "O-1",
                    "symbol": "BTC/USDT",
                    "side": "buy",
                    "status": "closed",
                    "amount": 1,
                    "filled": 1,
                    "average": 100,
                    "timestamp": 1_000_000_000_000,
                },
                {
                    "id": "O-2",
                    "symbol": "BTC/USDT",
                    "side": "buy",
                    "status": "closed",
                    "amount": 2,
                    "filled": 1,
                    "average": 200,
                    "timestamp": 1_000_000_002_000,
                },
            ]
        return [
            {
                "id": "O-3",
                "symbol": "BTC/USDT",
                "side": "buy",
                "status": "closed",
                "amount": 1,
                "filled": 1,
                "average": 300,
                "timestamp": 1_000_000_003_000,
            }
        ]

    def fetch_my_trades(self, *, symbol, since, limit, params):
        self.fill_calls.append((symbol, since, limit, params))
        self.fill_attempts += 1
        if self.fill_attempts == 1:
            raise ccxt.RateLimitExceeded("retryable test throttle")
        if since is None:
            return [
                {"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_000_000},
                {"id": "F-2", "order": "O-2", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 200, "timestamp": 1_000_000_002_000},
            ]
        return [
            {"id": "F-3", "order": "O-3", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 300, "timestamp": 1_000_000_003_000}
        ]

    def create_order(self, *args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("read-only sync attempted create_order")


def test_read_only_sync_paginates_retries_and_records_manifest(tmp_path):
    fake = _PagedClient()
    sleeps = []
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))
    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(ledger),
        sleeper=sleeps.append,
        jitter_fn=lambda: 0.0,
        backoff_base_seconds=0.01,
    )

    report = service.sync(
        exchange_id="binance_spot",
        account_id="pilot-account",
        symbol="BTC/USDT",
        page_limit=2,
        client=fake,
    )

    assert report["status"] == "RECONCILED"
    assert report["order_count"] == 3
    assert report["fill_count"] == 3
    assert report["snapshot_complete"] is True
    manifest = report["snapshot_manifest"]
    assert manifest["permission_scope"] == "READ_ONLY"
    assert manifest["orders_page_count"] == 2
    assert manifest["fills_page_count"] == 2
    assert manifest["request_count"] == 5  # one rate-limit retry
    assert sleeps == [0.01]
    assert fake.order_calls[1][1] == 1_000_000_002_000
    assert fake.fill_calls[2][1] == 1_000_000_002_000

    events = list(ledger.export_events(account_id="pilot-account"))
    assert len(events) == 6
    assert all(event["provenance"]["source"] == "broker_api_snapshot" for event in events)
    assert all(event["provenance"]["snapshot_permission_scope"] == "READ_ONLY" for event in events)


def test_max_pages_is_fail_closed_and_never_claims_reconciled(tmp_path):
    class FullPageClient:
        def fetch_orders(self, **kwargs):
            return [{"id": "O-1", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 1_000_000_000_000}]

        def fetch_my_trades(self, **kwargs):
            return [{"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_000_000}]

    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )
    report = service.sync(exchange_id="okx", page_limit=1, max_pages=1, client=FullPageClient())
    assert report["status"] == "UNRECONCILED"
    assert report["snapshot_complete"] is False
    assert any(item["type"] == "SNAPSHOT_INCOMPLETE" for item in report["discrepancies"])
    assert "ORDERS_MAX_PAGES_REACHED" in report["snapshot_manifest"]["warnings"]


def test_same_timestamp_page_boundary_is_overlapped_and_not_silently_dropped(tmp_path):
    """An inclusive timestamp cursor must not skip a full-page timestamp tie."""

    class SameTimestampClient:
        timestamp = 1_000_000_000_000

        def __init__(self):
            self.order_calls = []
            self.fill_calls = []

        @staticmethod
        def _order(order_id, quantity):
            return {
                "id": order_id,
                "symbol": "BTC/USDT",
                "side": "buy",
                "status": "closed",
                "amount": quantity,
                "filled": quantity,
                "average": 100,
                "timestamp": SameTimestampClient.timestamp,
            }

        @staticmethod
        def _fill(fill_id, order_id, quantity):
            return {
                "id": fill_id,
                "order": order_id,
                "symbol": "BTC/USDT",
                "side": "buy",
                "amount": quantity,
                "price": 100,
                "timestamp": SameTimestampClient.timestamp,
            }

        def fetch_orders(self, *, since, **_kwargs):
            self.order_calls.append(since)
            if since is None:
                return [self._order("O-1", 1), self._order("O-2", 1)]
            if since == self.timestamp:
                if len(self.order_calls) > 2:
                    return []
                return [self._order("O-2", 1), self._order("O-3", 1)]
            return []

        def fetch_my_trades(self, *, since, **_kwargs):
            self.fill_calls.append(since)
            if since is None:
                return [self._fill("F-1", "O-1", 1), self._fill("F-2", "O-2", 1)]
            if since == self.timestamp:
                if len(self.fill_calls) > 2:
                    return []
                return [self._fill("F-2", "O-2", 1), self._fill("F-3", "O-3", 1)]
            return []

    fake = SameTimestampClient()
    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )

    report = service.sync(
        exchange_id="binance_spot",
        account_id="same-timestamp-account",
        symbol="BTC/USDT",
        page_limit=2,
        client=fake,
    )

    assert report["status"] == "RECONCILED"
    assert report["snapshot_complete"] is True
    assert report["order_count"] == 3
    assert report["fill_count"] == 3
    assert fake.order_calls == [None, SameTimestampClient.timestamp, SameTimestampClient.timestamp]
    assert fake.fill_calls == [None, SameTimestampClient.timestamp, SameTimestampClient.timestamp]


def test_unsorted_full_page_is_incomplete_even_when_the_import_rows_reconcile(tmp_path):
    class UnsortedClient:
        def fetch_orders(self, **_kwargs):
            return [
                {"id": "O-2", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 2_000_000_000_000},
                {"id": "O-1", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 1_000_000_000_000},
            ]

        def fetch_my_trades(self, **_kwargs):
            return [
                {"id": "F-2", "order": "O-2", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 2_000_000_000_000},
                {"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_000_000},
            ]

    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )
    report = service.sync(exchange_id="binance_spot", page_limit=2, client=UnsortedClient())

    assert report["status"] == "UNRECONCILED"
    assert report["snapshot_complete"] is False
    assert "ORDERS_UNSORTED_PAGE" in report["snapshot_manifest"]["warnings"]
    assert "FILLS_UNSORTED_PAGE" in report["snapshot_manifest"]["warnings"]


def test_missing_timestamp_never_becomes_complete_on_a_short_page(tmp_path):
    class MissingTimestampClient:
        def fetch_orders(self, **_kwargs):
            return [{"id": "O-1", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100}]

        def fetch_my_trades(self, **_kwargs):
            return [{"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100}]

    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )
    report = service.sync(exchange_id="binance_spot", page_limit=10, client=MissingTimestampClient())
    assert report["status"] == "UNRECONCILED"
    assert report["snapshot_complete"] is False
    assert "ORDERS_MISSING_TIMESTAMP_CURSOR" in report["snapshot_manifest"]["warnings"]
    assert "FILLS_MISSING_TIMESTAMP_CURSOR" in report["snapshot_manifest"]["warnings"]

    orders = service._paginate(
        ReadOnlyExchangeClient(MissingTimestampClient()),
        kind="orders",
        method_name="fetch_orders",
        mapper=lambda row: row,
        symbol=None,
        since_ms=None,
        until_ms=None,
        max_pages=2,
        page_limit=10,
        params=None,
    )
    assert orders.complete is False
    assert "ORDERS_MISSING_TIMESTAMP_CURSOR" in orders.warnings


def test_repeated_full_page_is_incomplete_instead_of_spinning_or_claiming_complete(tmp_path):
    class RepeatedPageClient:
        def fetch_orders(self, **_kwargs):
            return [{"id": "O-1", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 1_000_000_000_000}]

        def fetch_my_trades(self, **_kwargs):
            return [{"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_000_000}]

    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )
    report = service.sync(exchange_id="binance_spot", page_limit=1, max_pages=3, client=RepeatedPageClient())

    assert report["status"] == "UNRECONCILED"
    assert report["snapshot_complete"] is False
    assert "ORDERS_REPEATED_PAGE" in report["snapshot_manifest"]["warnings"]
    assert "FILLS_REPEATED_PAGE" in report["snapshot_manifest"]["warnings"]
    assert report["snapshot_manifest"]["orders_page_count"] == 2


def test_full_page_at_until_boundary_is_incomplete_without_a_tie_breaker(tmp_path):
    class BoundaryClient:
        def fetch_orders(self, **_kwargs):
            return [
                {"id": "O-1", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 1_000_000_000_000},
                {"id": "O-2", "symbol": "BTC/USDT", "side": "buy", "status": "closed", "amount": 1, "filled": 1, "average": 100, "timestamp": 1_000_000_001_000},
            ]

        def fetch_my_trades(self, **_kwargs):
            return [
                {"id": "F-1", "order": "O-1", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_000_000},
                {"id": "F-2", "order": "O-2", "symbol": "BTC/USDT", "side": "buy", "amount": 1, "price": 100, "timestamp": 1_000_000_001_000},
            ]

    service = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    )
    report = service.sync(
        exchange_id="binance_spot",
        page_limit=2,
        until_ms=1_000_000_001_000,
        client=BoundaryClient(),
    )

    assert report["status"] == "UNRECONCILED"
    assert report["snapshot_complete"] is False
    assert "ORDERS_UNTIL_BOUNDARY_UNCERTAIN" in report["snapshot_manifest"]["warnings"]
    assert "FILLS_UNTIL_BOUNDARY_UNCERTAIN" in report["snapshot_manifest"]["warnings"]


def test_api_snapshot_preserves_source_exchange_identity_and_separates_same_venue(tmp_path):
    ledger = EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite"))

    spot = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(ledger),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    ).sync(
        exchange_id="binance_spot",
        account_id="identity-account",
        symbol="BTC/USDT",
        page_limit=2,
        client=_PagedClient(),
    )
    futures = ReadOnlyBrokerSyncService(
        import_service=BrokerImportService(ledger),
        sleeper=lambda _delay: None,
        jitter_fn=lambda: 0.0,
    ).sync(
        exchange_id="binance_futures",
        account_id="identity-account",
        symbol="BTC/USDT",
        page_limit=2,
        client=_PagedClient(),
    )

    assert spot["snapshot_manifest"]["manifest_version"] == "2"
    assert spot["snapshot_manifest"]["source_exchange_id"] == "binance_spot"
    assert spot["snapshot_manifest"]["market_type"] == "spot"
    assert futures["snapshot_manifest"]["source_exchange_id"] == "binance_futures"
    assert futures["snapshot_manifest"]["market_type"] == "swap"
    assert spot["snapshot_source_exchange_id"] == "binance_spot"
    assert futures["snapshot_source_exchange_id"] == "binance_futures"
    assert spot["transport"]["venue"] == futures["transport"]["venue"] == "BINANCE"
    assert spot["transport"]["market_type"] == "spot"
    assert futures["transport"]["market_type"] == "swap"
    assert spot["ledger_created_count"] == 6
    assert futures["ledger_created_count"] == 6

    events = list(ledger.export_events(account_id="identity-account"))
    assert len(events) == 12
    assert {event["provenance"]["source_exchange_id"] for event in events} == {
        "binance_spot",
        "binance_futures",
    }
    assert {event["provenance"]["market_type"] for event in events} == {"spot", "swap"}


def test_manifest_v2_rejects_source_exchange_and_market_mismatch():
    with pytest.raises(SnapshotManifestValidationError, match="market type disagree"):
        ReadOnlySnapshotManifest.build(
            exchange_id="BINANCE",
            account_id="account",
            requested_since_ms=None,
            requested_until_ms=None,
            orders_page_count=0,
            fills_page_count=0,
            order_count=0,
            fill_count=0,
            request_count=0,
            page_hashes=[],
            complete=True,
            source_exchange_id="binance_futures",
            market_type="spot",
        )


def test_import_boundary_rejects_inconsistent_v2_source_identity(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    manifest = {
        "manifest_version": "2",
        "permission_scope": "READ_ONLY",
        "snapshot_sha256": "a" * 64,
        "complete": True,
        "orders_page_count": 0,
        "fills_page_count": 0,
        "order_count": 0,
        "fill_count": 0,
        "request_count": 0,
        "warnings": [],
        "source_exchange_id": "binance_futures",
        "market_type": "spot",
    }
    with pytest.raises(BrokerImportValidationError, match="market type disagree"):
        service.import_records("BINANCE", snapshot_manifest=manifest)

    manifest["market_type"] = "swap"
    with pytest.raises(BrokerImportValidationError, match="venue disagree"):
        service.import_records("OKX", snapshot_manifest=manifest)


def test_import_boundary_keeps_v1_snapshot_manifest_compatible(tmp_path):
    service = BrokerImportService(EvidenceLedgerRepository(str(tmp_path / "ledger.sqlite")))
    manifest = ReadOnlySnapshotManifest.build(
        exchange_id="BINANCE",
        account_id="legacy-account",
        requested_since_ms=None,
        requested_until_ms=None,
        orders_page_count=0,
        fills_page_count=0,
        order_count=0,
        fill_count=0,
        request_count=0,
        page_hashes=[],
        complete=True,
    )
    report = service.import_records("BINANCE", snapshot_manifest=manifest.as_dict())
    assert manifest.manifest_version == "1"
    assert report["snapshot_complete"] is True


def test_scope_and_write_proxy_fail_closed():
    class WriteScopedCredentials:
        def get_decrypted_credentials(self, _exchange_id):
            return {
                "api_key": "key",
                "api_secret": "secret",
                "permission_scope": "READ_WRITE",
                "is_active": True,
            }

    service = ReadOnlyBrokerSyncService(credentials_manager=WriteScopedCredentials())
    with pytest.raises(ReadOnlyCredentialScopeError):
        service.sync(exchange_id="binance_spot")

    proxy = ReadOnlyExchangeClient(_PagedClient())
    with pytest.raises(ReadOnlyCredentialScopeError):
        proxy.create_order(symbol="BTC/USDT", type="market", side="buy", amount=1)


def test_keychain_credential_metadata_is_explicitly_read_only():
    manager = ExchangeCredentialsManager()
    exchange_id = "binance_spot"
    manager.save_credentials(
        exchange_id=exchange_id,
        api_key="wp12_key",
        api_secret="wp12_secret",
        is_testnet=True,
    )
    try:
        stored = manager.get_decrypted_credentials(exchange_id)
        assert stored["permission_scope"] == "READ_ONLY"
        with sqlite_driver.get_connection() as conn:
            row = conn.execute(
                "SELECT permission_scope FROM exchange_credential_refs WHERE exchange_id = ?",
                (exchange_id,),
            ).fetchone()
        assert row["permission_scope"] == "READ_ONLY"
        with pytest.raises(ValueError, match="READ_ONLY"):
            manager.save_credentials(
                exchange_id=exchange_id,
                api_key="wp12_key",
                api_secret="wp12_secret",
                permission_scope="READ_WRITE",
            )
    finally:
        manager.delete_credentials(exchange_id)


def test_manifest_validation_detects_tampering():
    manifest = ReadOnlySnapshotManifest.build(
        exchange_id="BINANCE",
        account_id="account",
        requested_since_ms=None,
        requested_until_ms=None,
        orders_page_count=1,
        fills_page_count=0,
        order_count=1,
        fill_count=0,
        request_count=1,
        page_hashes=["a" * 64],
        complete=True,
    )
    tampered = replace(manifest, page_hashes=("b" * 64,))
    with pytest.raises(Exception, match="snapshot_sha256"):
        tampered.validate()


def test_read_only_sync_endpoint_is_wired_without_write_surface(monkeypatch):
    from app.services.exchange import read_only_broker_sync as module

    monkeypatch.setattr(
        module.read_only_broker_sync_service,
        "sync",
        lambda **kwargs: {"status": "RECONCILED", "read_only_scope": "READ_ONLY", "exchange_id": kwargs["exchange_id"]},
    )
    response = TestClient(create_app()).post(
        "/api/v1/broker/sync-read-only?exchange_id=binance_spot&account_id=pilot"
    )
    assert response.status_code == 200
    assert response.json()["read_only_scope"] == "READ_ONLY"
