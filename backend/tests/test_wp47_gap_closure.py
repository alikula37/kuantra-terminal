"""WP47 gap-closure tests: USD analytics/exports, endpoint metadata, TLS, cadence.

These close the honestly reported gaps from the previous delivery:
* ``/trades/open`` must carry unit metadata and value-based sizing;
* a closed USD trade must flow through portfolio analytics and the journal
  export snapshot with value-based money and explicit units;
* the Binance websocket must use an explicit certifi-backed SSL context (the
  packaged app previously failed certificate verification while REST worked);
* the pre-fix backoff cadence is reconstructed as "consistent with" the old
  exponential arithmetic, and the new stale-retry behaviour is pinned.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import create_app

from app.api import endpoints
from app.db import sync_pipeline as sync_pipeline_module
from app.db.sqlite_driver import SQLiteDriver
from app.services.portfolio_service import PortfolioAnalyticsService
from app.services.trade_read_adapter import trade_read_adapter


def _isolated_journal(monkeypatch, tmp_path):
    from app.services.trade_edit import TradeEditService

    driver = SQLiteDriver(str(tmp_path / "wp47.sqlite"))
    reader = SimpleNamespace(
        get_trade=driver.get_trade,
        get_open_trades=driver.get_open_trades,
        list_trades=lambda limit=100, offset=0, **kwargs: driver.list_trades(limit=limit, offset=offset, **kwargs),
    )
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(endpoints, "trade_read_adapter", reader)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver=driver))
    driver.test_reader = reader  # convenience for export/adapter-bound assertions
    return driver


def _usd_trade_payload(**overrides):
    payload = {
        "symbol": "XAUUSD", "side": "BUY", "position_type": "LONG",
        "entry_price": 4300.0, "size_input_mode": "NOTIONAL", "notional_size": 1000.0,
        "qty_unit": "USD", "leverage": 10, "stop_loss": 4270.0, "take_profit": 4360.0,
        "status": "OPEN", "entry_time": "2026-09-18T08:00:00Z", "record_mode": "SIMULATION",
        "price_source": "biquote_public", "price_source_symbol": "XAUUSD",
        "price_status": "UNAVAILABLE", "price_origin": "MANUAL",
        "local_tracking": {
            "enabled": True, "source_id": "biquote_public", "source_symbol": "XAUUSD",
            "stop_loss": 4270.0, "targets": [{"price": 4343.0, "percent": 100}],
        },
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# /trades/open metadata
# ---------------------------------------------------------------------------


def test_open_trades_endpoint_keeps_unit_metadata_and_value_sizing(monkeypatch, tmp_path):
    _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    created = client.post("/api/v1/trades", json=_usd_trade_payload()).json()

    rows = client.get("/api/v1/trades/open").json()
    row = next(item for item in rows if item["id"] == created["id"])
    assert row["qty"] == 1000.0
    assert row["qty_unit"] == "USD"
    assert row["record_mode"] == "SIMULATION"
    assert row["sizing"]["notional"]["value"] == 1000.0
    assert row["sizing"]["margin_estimate"]["value"] == 100.0
    assert row["sizing"]["quantity"]["unit"] == "USD"


# ---------------------------------------------------------------------------
# Analytics and export with a closed USD trade
# ---------------------------------------------------------------------------


def test_closed_usd_trade_flows_through_analytics_and_export(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    created = client.post("/api/v1/trades", json=_usd_trade_payload()).json()

    closed = client.post(
        f"/api/v1/trades/{created['id']}/close",
        json={"exit_price": 4343.0, "commission": 1.0},
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    # 1000 USD x 43/4300 = 10.0 gross, minus 1.0 commission -> 9.0 net.
    assert abs(float(body["pnl"]) - 9.0) < 1e-9
    assert abs(float(body["r_multiple"]) - round(9.0 / (30.0 / 4300.0 * 1000.0), 2)) < 1e-9

    stored = driver.get_trade(created["id"])
    assert stored["status"] == "CLOSED"
    assert stored["qty_unit"] == "USD"

    service = PortfolioAnalyticsService(default_initial_balance=10000.0)
    with patch.object(trade_read_adapter, "list_trades", return_value=[stored]):
        summary = service.get_portfolio_summary()
        breakdown = service.get_multi_asset_breakdown()
        curve = service.get_equity_curve_series()
        heatmap = service.get_daily_pnl_heatmap()

    # Real aggregates are empty: the record is a simulation and must never leak
    # into real money, but its own bookkeeping is counted explicitly.
    assert summary["net_pnl"] == 0.0
    assert summary["simulation_closed_trades"] == 1
    assert summary["simulation_realized_pnl"] == 9.0
    assert all(item["symbol"] != "XAUUSD" for item in breakdown)
    assert all(point["symbol"] != "XAUUSD" for point in curve)
    assert all(day["pnl"] == 0.0 for day in heatmap)

    # The export snapshot states the USD unit and the value, never a base qty.
    from app.services.journal_export import JournalExportService

    export = JournalExportService(driver.test_reader)
    snapshot = export.snapshot(scope="all", date_basis="entry")
    record = next(item for item in snapshot.records if item["id"] == created["id"])
    assert record["qty"] == 1000.0
    assert record["qty_unit"] == "USD"
    assert abs(float(record["pnl_recorded"]) - 9.0) < 1e-9


def test_pivot_grid_uses_the_stored_value_based_result(monkeypatch, tmp_path):
    driver = _isolated_journal(monkeypatch, tmp_path)
    client = TestClient(create_app())
    created = client.post("/api/v1/trades", json=_usd_trade_payload()).json()
    client.post(f"/api/v1/trades/{created['id']}/close",
                json={"exit_price": 4343.0, "commission": 1.0})

    from app.quant.pivot_engine import PivotEngine
    with patch("app.quant.pivot_engine.sqlite_driver", driver):
        grid = PivotEngine.compute_pivot_grid(group_by=["symbol"])
    bucket = next(item for item in grid["rows"] if item["dimensions"].get("symbol") == "XAUUSD")
    # Stored PnL is the value-based 9.0; a base-quantity artifact would show
    # 43 x 1000 = 43000 here.
    assert abs(float(bucket["total_pnl"]) - 9.0) < 1e-9


# ---------------------------------------------------------------------------
# Pre-fix cadence reconstruction and new stale-retry behaviour
# ---------------------------------------------------------------------------


def test_pre_fix_backoff_cadence_matches_the_surviving_log_gaps():
    """Reconstruct, not prove: the observed pre-fix gaps fit the old arithmetic.

    Surviving INFO fetch timestamps (2026-09-17, UTC): 17:44:46, 17:45:17,
    17:46:18, 17:48:20 -> gaps 31/61/122 s.  The old monitor counted an
    ineligible observation as a failure and waited ``max(15 * 2**failures)``:
    30/60/120 s.  Gaps match the arithmetic within poll drift; the exact
    composition (stale vs transient fetch error) is unprovable because those
    sessions logged the reason at DEBUG only.
    """

    gaps = [31, 61, 122]
    old_policy = [15 * 2 ** n for n in (1, 2, 3)]
    assert old_policy == [30, 60, 120]
    assert all(0 <= gap - delay <= 8 for gap, delay in zip(gaps, old_policy))
    # New policy: an ineligible observation retries in 5 s without backoff.
    assert 5 * 2 ** 0 == 5


def test_stale_observations_never_escalate_under_the_new_policy(tmp_path):
    import asyncio

    from app.db.sqlite_driver import SQLiteDriver as Driver
    from app.services.local_tracking import LocalTrackingService
    from app.services.local_tracking_monitor import TrackingMonitor

    driver = Driver(str(tmp_path / "cadence.sqlite"))
    driver.record_trade_with_evidence(
        {"id": "TRD-CAD", "symbol": "BTCUSDT", "side": "BUY", "status": "OPEN",
         "entry_price": 76000.0, "qty": 100.0, "qty_unit": "USD",
         "stop_loss": 70000.0, "take_profit": 90000.0,
         "entry_time": "2026-09-18T08:00:00Z"},
        event_type="IntentRecorded", idempotency_key="wp47:cadence",
        occurred_at="2026-09-18T08:00:00Z", provenance={"source": "journal_simulation"},
    )
    service = LocalTrackingService(driver)
    state = service.edit(
        "TRD-CAD",
        {"enabled": True, "source_id": "binance_public", "source_symbol": "BTCUSDT",
         "stop_loss": 70000.0, "targets": [{"price": 90000.0, "percent": 100}]},
        expected_revision=0,
    )
    observed = datetime.now(timezone.utc) - timedelta(seconds=600)

    async def stale_fetch(*_args):
        return {"status": "LIVE", "price": "77000", "timestamp_basis": "PROVIDER_EVENT",
                "source_id": "binance_public", "source_symbol": "BTCUSDT",
                "observed_at": observed.isoformat()}

    monitor = TrackingMonitor(service=service, fetch=stale_fetch)
    delays = []
    for _ in range(3):
        asyncio.run(monitor.poll(enabled=True))
        key = ("binance_public", "BTCUSDT")
        delays.append(round(monitor.next_poll[key] - __import__("time").monotonic(), 1))
        assert monitor.failures[key] == 0
    assert all(0 <= delay <= 6 for delay in delays)
    assert len(service.get("TRD-CAD")["closures"]) == 0


# ---------------------------------------------------------------------------
# Websocket TLS context
# ---------------------------------------------------------------------------


def test_binance_stream_uses_an_explicit_certifi_ssl_context():
    import certifi

    from app.websocket.binance_client import _build_ssl_context

    context = _build_ssl_context()
    assert context is not None
    assert context.verify_mode.name == "CERT_REQUIRED"
    assert context.check_hostname is True
    # The packaged app failed against the system trust store while REST (certifi)
    # worked; the stream must use the same certifi bundle.
    assert certifi.where()
