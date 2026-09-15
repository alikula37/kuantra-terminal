"""P1-WP30 free quote provenance and external journal contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.api import webhook_tv
from app.api.webhook_tv import WEBHOOK_SECRET_KEY
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services.market_data.public_fetcher import PublicMarketDataFetcher
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


def _response(*, status_code: int, payload=None, text: str = "") -> MagicMock:
    response = MagicMock(status_code=status_code, text=text)
    response.json.return_value = payload
    return response


@pytest.mark.asyncio
async def test_free_crypto_quote_has_live_provenance_without_credentials():
    fetcher = PublicMarketDataFetcher()
    binance = _response(status_code=200, payload={"symbol": "BTCUSDT", "price": "65001.25"})

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=binance)) as get:
        quote = await fetcher.fetch_quote("BTCUSDT")

    assert quote.as_dict() == {
        "requested_symbol": "BTCUSDT",
        "source_id": "binance_public",
        "source_symbol": "BTCUSDT",
        "price": 65001.25,
        "status": "LIVE",
        "price_kind": "LAST",
        "observed_at": quote.observed_at,
        "reason": None,
        "free_source": True,
        "credentials_required": False,
    }
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_gold_quote_keeps_spot_identity_and_never_falls_back_to_paxg():
    fetcher = PublicMarketDataFetcher()
    calls = []

    async def mock_get(url, *args, **kwargs):
        calls.append((url, kwargs))
        if "yahoo.com" in url:
            return _response(status_code=403)
        return _response(status_code=404)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        quote = await fetcher.fetch_quote("XAUUSD")

    assert quote.status == "UNAVAILABLE"
    assert quote.price is None
    assert quote.source_symbol is None
    assert all("PAXGUSDT" not in str(call) for call in calls)
    assert any("XAUUSD=X" in str(call) for call in calls)


@pytest.mark.asyncio
async def test_yahoo_gold_quote_reports_exact_provider_symbol_and_delayed_status():
    fetcher = PublicMarketDataFetcher()
    yahoo = _response(
        status_code=200,
        payload={
            "chart": {
                "result": [{
                    "timestamp": [1_700_000_000],
                    "indicators": {"quote": [{
                        "open": [2000.0], "high": [2010.0], "low": [1995.0],
                        "close": [2005.0], "volume": [10.0],
                    }]},
                }],
            },
        },
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=yahoo)):
        quote = await fetcher.fetch_quote("XAUUSD", source="yahoo_public")

    assert quote.source_id == "yahoo_public"
    assert quote.source_symbol == "XAUUSD=X"
    assert quote.price == 2005.0
    assert quote.status == "DELAYED"
    assert quote.price_kind == "CLOSE"


@pytest.mark.asyncio
async def test_quote_with_missing_observation_time_is_unavailable():
    fetcher = PublicMarketDataFetcher()
    yahoo = _response(
        status_code=200,
        payload={
            "chart": {
                "result": [{
                    "timestamp": [0],
                    "indicators": {"quote": [{
                        "open": [2000.0], "high": [2010.0], "low": [1995.0],
                        "close": [2005.0], "volume": [10.0],
                    }]},
                }],
            },
        },
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=yahoo)):
        quote = await fetcher.fetch_quote("XAUUSD", source="yahoo_public")

    assert quote.status == "UNAVAILABLE"
    assert quote.price is None
    assert quote.reason == "YAHOO_QUOTE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_generic_asset_uses_exact_free_ticker_without_crypto_rewrite():
    fetcher = PublicMarketDataFetcher()
    yahoo = _response(
        status_code=200,
        payload={
            "chart": {
                "result": [{
                    "timestamp": [1_700_000_000],
                    "indicators": {"quote": [{
                        "open": [140.0], "high": [142.0], "low": [139.0],
                        "close": [141.0], "volume": [100.0],
                    }]},
                }],
            },
        },
    )

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=yahoo)) as get:
        quote = await fetcher.fetch_quote("GOOG")

    assert quote.source_id == "yahoo_public"
    assert quote.source_symbol == "GOOG"
    assert quote.price == 141.0
    request_url = get.await_args.args[0]
    assert request_url.endswith("/GOOG")
    assert all("BINANCE" not in str(call).upper() for call in get.await_args_list)


@pytest.mark.asyncio
async def test_paid_or_credential_source_is_rejected_without_network_call():
    fetcher = PublicMarketDataFetcher()
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as get:
        quote = await fetcher.fetch_quote("EURUSD", source="twelvedata")

    assert quote.status == "UNAVAILABLE"
    assert quote.reason == "UNSUPPORTED_OR_PAID_SOURCE"
    get.assert_not_awaited()


def test_quote_endpoint_returns_unavailable_when_market_data_is_disabled(monkeypatch):
    monkeypatch.setattr(endpoints.binance_client, "market_data_enabled", False)
    fetch_quote = AsyncMock(side_effect=AssertionError("disabled quote must not connect"))
    monkeypatch.setattr(endpoints.public_market_fetcher, "fetch_quote", fetch_quote)

    response = TestClient(create_app()).get("/api/v1/market-data/quote?symbol=XAUUSD")

    assert response.status_code == 200
    assert response.json()["status"] == "UNAVAILABLE"
    assert response.json()["reason"] == "MARKET_DATA_DISABLED"
    fetch_quote.assert_not_awaited()


def _isolated_journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(webhook_tv, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    return driver


def test_external_trade_record_is_default_and_never_dispatches_order(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    with patch.object(endpoints.ccxt_execution_engine, "create_order", side_effect=AssertionError("journal must not dispatch")):
        response = client.post(
            "/api/v1/trades",
            json={
                "symbol": "OANDA:XAUUSD",
                "side": "BUY",
                "entry_price": 2500.50,
                "qty": 1,
                "execution_venue": "OANDA",
                "price_source": "manual",
                "price_status": "UNAVAILABLE",
                "price_origin": "MANUAL",
            },
        )

    assert response.status_code == 200
    trade = response.json()
    assert trade["record_mode"] == "EXTERNAL"
    assert trade["execution_venue"] == "OANDA"
    assert trade["price_source"] == "manual"
    assert trade["price_status"] == "UNAVAILABLE"
    assert trade["price_origin"] == "MANUAL"
    assert driver.get_trade(trade["id"])["symbol"] == "OANDA:XAUUSD"


def test_spot_position_survives_reopen_and_evidence_rebuild(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    result = client.post("/api/v1/trades", json={
        "symbol": "LINKUSDT", "side": "BUY", "position_type": "SPOT", "entry_price": 10, "qty": 2,
        "qty_unit": "BASE",
    })
    assert result.status_code == 200
    saved = result.json()
    assert saved["position_type"] == "SPOT"
    reopened = SQLiteDriver(driver.db_path)
    assert reopened.get_trade(saved["id"])["position_type"] == "SPOT"
    adapter = TradeReadAdapter(legacy_driver=reopened, projection_repo=EvidenceTradeProjectionRepository(driver.db_path))
    pack_before = adapter.get_evidence_pack(saved["id"])
    assert pack_before["trade"]["position_type"] == "SPOT"
    assert adapter.projection_repo.rebuild(dry_run=False)["ledger_valid"] is True
    assert adapter.get_evidence_pack(saved["id"])["trade"] == pack_before["trade"]
    from app.services.evidence_pack_export import EvidencePackExportService
    exporter = EvidencePackExportService(adapter)
    import csv
    import io
    exported = list(csv.DictReader(io.StringIO(exporter.export(saved["id"], "csv").content.decode())))
    assert exported[0]["position_type"] == "SPOT"
    closed = client.post(f"/api/v1/trades/{saved['id']}/close", json={"exit_price": 12, "commission": 1})
    assert closed.status_code == 200
    assert closed.json()["position_type"] == "SPOT"
    assert closed.json()["pnl"] == 3
    canceled = client.delete(f"/api/v1/trades/{saved['id']}")
    assert canceled.json()["trade"]["position_type"] == "SPOT"
    final_pack = adapter.get_evidence_pack(saved["id"])
    assert final_pack["trade"]["status"] == "CANCELED"
    assert final_pack["event_count"] > pack_before["event_count"]
    assert pack_before["events"][0]["event_hash"] in {event["event_hash"] for event in final_pack["events"]}


@pytest.mark.parametrize("position_type,side", [("SPOT", "SELL"), ("LONG", "SELL"), ("SHORT", "BUY"), ("INVALID", "BUY")])
def test_position_type_rejects_contradictory_or_unknown_input(monkeypatch, tmp_path, position_type, side):
    driver = _isolated_journal(monkeypatch, tmp_path)
    result = TestClient(create_app()).post("/api/v1/trades", json={
        "symbol": "LINKUSDT", "position_type": position_type, "side": side, "entry_price": 10, "qty": 2,
    })
    assert result.status_code == 422
    assert driver.get_open_trades() == []


def test_trade_endpoint_rejects_public_quote_without_complete_provenance(monkeypatch, tmp_path):
    _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "GOOG",
            "entry_price": 141.0,
            "qty": 1,
            "price_source": "yahoo_public",
            "price_status": "UNAVAILABLE",
            "price_origin": "PUBLIC_QUOTE",
        },
    )

    assert response.status_code == 422
    assert "PUBLIC_QUOTE" in response.text


def test_quote_provenance_survives_evidence_projection_and_rebuild(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "provenance.sqlite"))
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))

    saved = sync_pipeline_module.sync_pipeline.record_and_sync_trade(
        {
            "id": "QUOTE-PROVENANCE-1",
            "symbol": "EURUSD",
            "side": "BUY",
            "entry_price": 1.0875,
            "qty": 1.0,
            "status": "OPEN",
            "record_mode": "EXTERNAL",
            "price_source": "yahoo_public",
            "price_source_symbol": "EURUSD=X",
            "price_status": "DELAYED",
            "price_observed_at": "2026-09-11T09:00:00Z",
            "price_origin": "PUBLIC_QUOTE",
        },
        source="journal_external",
    )
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )

    pack = adapter.get_evidence_pack(saved["id"])
    assert pack["trade"]["price_source_symbol"] == "EURUSD=X"
    assert pack["trade"]["price_status"] == "DELAYED"
    rebuilt = adapter.projection_repo.rebuild(dry_run=False)
    assert rebuilt["ledger_valid"] is True
    assert adapter.get_trade(saved["id"])["price_origin"] == "PUBLIC_QUOTE"


def test_additive_schema_migration_marks_old_rows_unknown(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE trades (
                id TEXT PRIMARY KEY, symbol TEXT NOT NULL, side TEXT NOT NULL,
                entry_price REAL NOT NULL, qty REAL NOT NULL, entry_time TEXT NOT NULL,
                status TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO trades (id, symbol, side, entry_price, qty, entry_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("LEGACY-1", "BTCUSDT", "BUY", 100.0, 1.0, "2026-09-11T00:00:00Z", "OPEN"),
        )
        connection.commit()

    trade = SQLiteDriver(str(path)).get_trade("LEGACY-1")
    assert trade["record_mode"] == "UNKNOWN"
    assert trade["price_source"] == "unknown"
    assert trade["price_status"] == "UNAVAILABLE"
    assert trade["price_origin"] == "UNKNOWN"
    assert trade["position_type"] == "UNKNOWN"


def _signed_body(payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET_KEY.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return body, {
        "Content-Type": "application/json",
        "X-TradingView-Signature": signature,
    }


def test_tradingview_alert_is_pending_until_user_confirms_external_fill(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    body, headers = _signed_body({
        "symbol": "OANDA:XAUUSD",
        "action": "BUY",
        "price": 2501.0,
        "qty": 2.0,
        "strategy": "gold-breakout",
        "timeframe": "15m",
        "timestamp": 1_700_000_000,
    })

    received = client.post("/api/v1/webhook/tradingview", content=body, headers=headers)
    assert received.status_code == 200
    assert received.json()["status"] == "PENDING_REVIEW"
    observation_id = received.json()["observation_id"]
    assert driver.get_trade(f"TV-{observation_id}") is None

    listed = client.get("/api/v1/tradingview/observations")
    assert listed.status_code == 200
    assert listed.json()["observations"][0]["symbol"] == "OANDA:XAUUSD"

    confirmed = client.post(
        f"/api/v1/tradingview/observations/{observation_id}/confirm",
        json={"entry_price": 2502.25, "execution_venue": "OANDA"},
    )
    assert confirmed.status_code == 200
    trade = confirmed.json()["trade"]
    assert trade["record_mode"] == "EXTERNAL"
    assert trade["entry_price"] == 2502.25
    assert trade["price_origin"] == "MANUAL"
    assert trade["price_source"] == "tradingview_alert"
    assert trade["symbol"] == "OANDA:XAUUSD"

    listed_after_confirmation = client.get("/api/v1/tradingview/observations")
    assert listed_after_confirmation.status_code == 200
    confirmed_observation = listed_after_confirmation.json()["observations"][0]
    assert confirmed_observation["status"] == "CONFIRMED"
    assert confirmed_observation["confirmation_event_id"]
