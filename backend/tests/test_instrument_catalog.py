"""Server-verified instrument catalog: provider lookup, cache and money gating."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.position_math import instrument_unit_basis, position_summary
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.local_tracking import LocalTrackingService
from app.services.market_data.instrument_catalog import InstrumentCatalog
from app.services.trade_edit import TradeEditService
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


class _FakeFetcher:
    def __init__(self, instruments):
        self.instruments = instruments
        self.load_calls = 0

    def _get_headers(self):
        return {"User-Agent": "test"}

    async def _load_binance_instruments(self):
        self.load_calls += 1
        return list(self.instruments)


def _bybit_response(payload, status_code=200):
    response = MagicMock(status_code=status_code)
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_binance_spot_lookup_verifies_and_caches(tmp_path):
    fetcher = _FakeFetcher([
        {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT",
         "status": "TRADING", "isSpotTradingAllowed": True},
    ])
    catalog = InstrumentCatalog(fetcher=fetcher, db_path=str(tmp_path / "catalog.sqlite"))

    row = await catalog.ensure_verified("ETHUSDT")
    assert row["provider"] == "binance_spot"
    assert row["base_asset"] == "ETH"
    assert row["quote_asset"] == "USDT"
    assert catalog.is_verified("ETHUSDT") is True

    # A fresh row is served from SQLite without another provider request.
    await catalog.ensure_verified("ETHUSDT")
    assert fetcher.load_calls == 1


@pytest.mark.asyncio
async def test_bybit_spot_fallback_verifies_when_binance_lacks_the_symbol(tmp_path):
    fetcher = _FakeFetcher([])
    catalog = InstrumentCatalog(fetcher=fetcher, db_path=str(tmp_path / "catalog.sqlite"))
    bybit_payload = {
        "retCode": 0,
        "result": {"list": [{
            "symbol": "ETHUSDT", "baseCoin": "ETH", "quoteCoin": "USDT", "status": "Trading",
        }]},
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_bybit_response(bybit_payload))):
        row = await catalog.ensure_verified("ETHUSDT")

    assert row["provider"] == "bybit_spot"
    assert catalog.is_verified("ETHUSDT") is True


@pytest.mark.asyncio
async def test_unknown_symbol_and_provider_failure_stay_unverified(tmp_path):
    fetcher = _FakeFetcher([])
    catalog = InstrumentCatalog(fetcher=fetcher, db_path=str(tmp_path / "catalog.sqlite"))
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_bybit_response({}, 500))):
        row = await catalog.ensure_verified("FAKEUSD")
        description = await catalog.describe("FAKEUSD")

    assert row is None
    assert catalog.is_verified("FAKEUSD") is False
    assert description["status"] == "UNVERIFIED"
    assert description["provider"] is None


def test_catalog_verification_enables_monetary_math():
    verified = position_summary(
        symbol="ETHUSDT",
        position_type="LONG",
        side="BUY",
        entry_price=2500,
        qty=2,
        exit_price=2600,
        server_verified=True,
    )
    assert verified["instrument"]["verification"] == "PROVIDER_CATALOG"
    assert verified["instrument"]["verification_source"] == "PROVIDER_CATALOG"
    assert verified["monetary_calculation"]["status"] == "READY"
    assert verified["notional"]["value"] == 5000
    assert verified["returns"]["gross_pnl"] == 200

    declared = instrument_unit_basis("ETHUSDT", qty_unit="BASE")
    assert declared["verification"] == "EXPLICIT_QTY_UNIT"
    unverified = instrument_unit_basis("ETHUSDT")
    assert unverified["verification"] == "NONE"


@pytest.fixture
def journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    catalog = InstrumentCatalog(fetcher=_FakeFetcher([]), db_path=driver.db_path)
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    monkeypatch.setattr(
        endpoints,
        "trade_read_adapter",
        TradeReadAdapter(
            legacy_driver=driver,
            projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
        ),
    )
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver, catalog=catalog))
    monkeypatch.setattr(endpoints, "instrument_catalog", catalog)
    return driver, catalog, TestClient(create_app())


def test_api_verified_symbol_computes_pnl_without_declaration(journal):
    driver, catalog, client = journal
    catalog._store("ETHUSDT", provider="binance_spot", base_asset="ETH", quote_asset="USDT")

    created = client.post("/api/v1/trades", json={
        "symbol": "ETHUSDT", "side": "SELL", "position_type": "SHORT",
        "entry_price": 2532.5, "qty": 1, "entry_time": "2026-09-14T10:00",
    })
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["qty_unit"] == "UNKNOWN"
    assert body["sizing"]["instrument"]["verification"] == "PROVIDER_CATALOG"
    assert body["sizing"]["monetary_calculation"]["status"] == "READY"

    closed = client.post(f"/api/v1/trades/{body['id']}/close", json={"exit_price": 2461})
    assert closed.status_code == 200, closed.text
    assert closed.json()["pnl"] == pytest.approx(71.5)


def test_api_instrument_endpoint_reports_verified_metadata(journal):
    _, catalog, client = journal
    catalog._store("ETHUSDT", provider="binance_spot", base_asset="ETH", quote_asset="USDT")
    response = client.get("/api/v1/market-data/instrument?symbol=ETHUSDT")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "VERIFIED"
    assert payload["provider"] == "binance_spot"
    assert payload["base_asset"] == "ETH"
    assert payload["contract_size"] == 1.0

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_bybit_response({}, 503))):
        unverified = client.get("/api/v1/market-data/instrument?symbol=FAKEUSD")
    assert unverified.status_code == 200
    assert unverified.json()["status"] == "UNVERIFIED"


def test_local_tracking_accepts_server_verified_symbol(journal):
    driver, catalog, client = journal
    catalog._store("ETHUSDT", provider="binance_spot", base_asset="ETH", quote_asset="USDT")
    created = client.post("/api/v1/trades", json={
        "symbol": "ETHUSDT", "side": "BUY", "position_type": "LONG",
        "entry_price": 2500, "qty": 2,
        "local_tracking": {
            "enabled": True,
            "source_id": "binance_public",
            "source_symbol": "ETHUSDT",
            "targets": [{"price": 2600, "percent": 100}],
            "stop_loss": 2400,
        },
    })
    assert created.status_code == 200, created.text
    state = LocalTrackingService(driver, catalog=catalog).get(created.json()["id"])
    assert state["targets"][0]["price"] == "2600"


def _backdate(catalog, symbol, seconds):
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
    with sqlite3.connect(catalog.db_path) as conn:
        conn.execute(
            "UPDATE verified_instruments SET verified_at = ? WHERE symbol = ?",
            (stamp, symbol),
        )


@pytest.mark.asyncio
async def test_verification_expires_after_seven_days_without_provider_confirmation(tmp_path):
    fetcher = _FakeFetcher([])
    catalog = InstrumentCatalog(fetcher=fetcher, db_path=str(tmp_path / "catalog.sqlite"))
    catalog._store("ETHUSDT", provider="binance_spot", base_asset="ETH", quote_asset="USDT")
    catalog._store("SOLUSDT", provider="binance_spot", base_asset="SOL", quote_asset="USDT")
    _backdate(catalog, "ETHUSDT", 8 * 86_400)
    _backdate(catalog, "SOLUSDT", 6 * 86_400)

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_bybit_response({}, 503))):
        expired = await catalog.ensure_verified("ETHUSDT")
        retained = await catalog.ensure_verified("SOLUSDT")
        description = await catalog.describe("ETHUSDT")

    assert expired is None
    assert catalog.is_verified("ETHUSDT") is False
    assert description["status"] == "UNVERIFIED"
    # A six-day-old row is still inside the honesty horizon.
    assert retained["symbol"] == "SOLUSDT"
    assert catalog.is_verified("SOLUSDT") is True


@pytest.mark.asyncio
async def test_stale_cache_is_refreshed_from_the_provider(tmp_path):
    fetcher = _FakeFetcher([
        {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT",
         "status": "TRADING", "isSpotTradingAllowed": True},
    ])
    catalog = InstrumentCatalog(fetcher=fetcher, db_path=str(tmp_path / "catalog.sqlite"))
    catalog._store("ETHUSDT", provider="binance_spot", base_asset="ETH", quote_asset="USDT")
    _backdate(catalog, "ETHUSDT", 25 * 3_600)

    refreshed = await catalog.ensure_verified("ETHUSDT")

    assert fetcher.load_calls == 1
    assert refreshed["provider"] == "binance_spot"
    assert catalog._row_age_seconds(catalog.get("ETHUSDT")) < 60
