"""P1-WP32 independent-review fixes.

Covers the four reported defects:
1. edited stop/take-profit must drive the local tracking plan,
2. entry-time corrections must persist (and stay idempotent for equal instants),
3. (frontend hook tested in vitest),
4. unknown contract sizes must not produce monetary position/margin/PnL math.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.position_math import position_summary
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver
from app.services import portfolio_service as portfolio_service_module
from app.services.local_tracking import LocalTrackingService, TrackingUnsupported
from app.services.trade_edit import TradeEditService
from app.services.trade_read_adapter import TradeReadAdapter
from main import create_app


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _plan(stop: float = 95, targets: list | None = None) -> dict:
    return {
        "enabled": True,
        "source_id": "binance_public",
        "source_symbol": "BTCUSDT",
        "targets": targets or [{"price": 110, "percent": 100}],
        "stop_loss": stop,
    }


def _quote(value: float, symbol: str = "BTCUSDT", **extra) -> dict:
    return {
        "source_id": "binance_public",
        "source_symbol": symbol,
        "price": value,
        "status": "LIVE",
        "timestamp_basis": "PROVIDER_EVENT",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


@pytest.fixture
def journal(monkeypatch, tmp_path):
    driver = SQLiteDriver(str(tmp_path / "review.sqlite"))
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "sqlite_driver", driver)
    monkeypatch.setattr(sync_pipeline_module, "duckdb_driver", SimpleNamespace(is_available=False))
    adapter = TradeReadAdapter(
        legacy_driver=driver,
        projection_repo=EvidenceTradeProjectionRepository(driver.db_path),
    )
    monkeypatch.setattr(endpoints, "trade_read_adapter", adapter)
    monkeypatch.setattr(portfolio_service_module, "trade_read_adapter", adapter)
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver))
    return driver, TestClient(create_app())


def _create(client: TestClient, **overrides) -> dict:
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "position_type": "LONG",
        "entry_price": 100,
        "qty": 2,
        "price_source": "manual",
        "price_status": "UNAVAILABLE",
        "price_origin": "MANUAL",
    }
    payload.update(overrides)
    response = client.post("/api/v1/trades", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# -- 1. stop / target synchronization -----------------------------------


def test_stop_edit_drives_local_plan_and_prevents_stale_stop_close(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan(stop=95))
    assert LocalTrackingService(driver).get(trade["id"])["stop_loss"] == "95"

    edited = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "stop_loss": 90},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["trade"]["stop_loss"] == 90
    state = LocalTrackingService(driver).get(trade["id"])
    assert state["stop_loss"] == "90"

    # 94 does not close under the new stop; the old 95 would have closed it.
    service = LocalTrackingService(driver)
    unchanged = service.observe(trade["id"], _quote(94))
    assert unchanged["closures"] == []
    assert unchanged["remaining_qty"] == "2"

    # 89 closes exactly once; a repeated observation cannot double-close.
    closed = service.observe(trade["id"], _quote(89))
    assert len(closed["closures"]) == 1
    assert closed["closures"][0]["target_id"] == "SL"
    assert closed["remaining_qty"] == "0"
    assert service.observe(trade["id"], _quote(89)) == closed


def test_take_profit_single_target_updates_plan_and_multitarget_is_rejected(journal):
    driver, client = journal
    single = _create(client, qty_unit="BASE", local_tracking=_plan())
    edited = client.patch(
        f"/api/v1/trades/{single['id']}",
        json={"expected_revision": 1, "take_profit": 115},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["trade"]["take_profit"] == 115
    state = LocalTrackingService(driver).get(single["id"])
    assert state["targets"][0]["price"] == "115"
    closed = LocalTrackingService(driver).observe(single["id"], _quote(115))
    assert closed["remaining_qty"] == "0"

    multi = _create(
        client,
        qty_unit="BASE",
        local_tracking=_plan(
            targets=[{"price": 110, "percent": 50}, {"price": 120, "percent": 50}]
        ),
    )
    rejected = client.patch(
        f"/api/v1/trades/{multi['id']}",
        json={"expected_revision": 1, "take_profit": 130},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["reason"] == "TARGETS_MANAGED_BY_PLAN"
    plan = LocalTrackingService(driver).get(multi["id"])
    assert [target["price"] for target in plan["targets"]] == ["110", "120"]
    # The legacy column mirrors TP1 of the plan; the rejected edit did not move it.
    assert driver.get_trade(multi["id"])["take_profit"] == 110.0


def test_stop_edit_preserves_completed_targets_after_partial_close(journal):
    driver, client = journal
    trade = _create(
        client,
        qty_unit="BASE",
        local_tracking=_plan(
            targets=[{"price": 110, "percent": 50}, {"price": 120, "percent": 50}]
        ),
    )
    service = LocalTrackingService(driver)
    partial = service.observe(trade["id"], _quote(110))
    assert len(partial["closures"]) == 1

    edited = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "stop_loss": 92},
    )
    assert edited.status_code == 200, edited.text
    state = service.get(trade["id"])
    assert state["stop_loss"] == "92"
    assert [target["price"] for target in state["targets"]] == ["110", "120"]
    assert state["closures"] == partial["closures"]

    blocked_target = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 2, "take_profit": 130},
    )
    assert blocked_target.status_code == 422
    assert blocked_target.json()["detail"]["reason"] == "TARGETS_MANAGED_BY_PLAN"


def test_plan_edit_payload_updates_trade_and_plan_in_one_transaction(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan(stop=95))
    response = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 1,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 93,
                "targets": [
                    {"price": 110, "percent": 50},
                    {"price": 120, "percent": 50},
                ],
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trade"]["stop_loss"] == 93
    assert body["trade"]["take_profit"] == 110
    assert body["tracking"]["revision"] == 2
    assert [target["price"] for target in body["tracking"]["targets"]] == ["110", "120"]

    stale = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 2,
            "local_tracking": {
                "expected_revision": 1,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 91,
                "targets": [{"price": 110, "percent": 100}],
            },
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "TRACKING_CONFLICT"
    state = LocalTrackingService(driver).get(trade["id"])
    assert state["stop_loss"] == "93"

    ambiguous = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 2,
            "stop_loss": 94,
            "local_tracking": {
                "expected_revision": 2,
                "enabled": True,
                "source_id": "binance_public",
                "source_symbol": "BTCUSDT",
                "stop_loss": 94,
                "targets": [{"price": 110, "percent": 100}],
            },
        },
    )
    assert ambiguous.status_code == 422
    assert ambiguous.json()["detail"]["reason"] == "AMBIGUOUS_ORDER_EDIT"


def test_failed_plan_sync_rolls_back_trade_correction(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", stop_loss=95, local_tracking=_plan(stop=95))

    def fail(phase, conn):
        if phase == "after_projection_update":
            raise RuntimeError("synthetic failure after plan write")

    driver._transaction_hook = fail
    with pytest.raises(RuntimeError):
        client.patch(
            f"/api/v1/trades/{trade['id']}",
            json={"expected_revision": 1, "stop_loss": 90},
        )
    driver._transaction_hook = None

    assert driver.get_trade(trade["id"])["stop_loss"] == 95
    assert driver.get_trade(trade["id"])["revision"] == 1
    assert LocalTrackingService(driver).get(trade["id"])["stop_loss"] == "95"


def test_concurrent_stop_edit_and_observation_cannot_double_close(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan(stop=95))
    service = LocalTrackingService(driver)

    def edit_stop(_):
        try:
            return TradeEditService(driver).edit(
                trade["id"], {"stop_loss": 90}, expected_revision=1
            )["revision"]
        except Exception as exc:  # noqa: BLE001 - the race may lose serialization
            return type(exc).__name__

    def observe(_):
        try:
            return len(service.observe(trade["id"], _quote(94))["closures"])
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit_stop, None), pool.submit(observe, None)]
        results = [future.result() for future in futures]

    state = service.get(trade["id"])
    # Whichever transaction committed first, the state is always internally
    # consistent: at most one legitimate close exists, the plan carries the
    # committed stop, and a post-edit observation cannot close under the old stop.
    assert len(state["closures"]) <= 1
    assert state["stop_loss"] in {"90", "95"}
    if state["stop_loss"] == "90" and state["closures"]:
        # A close can only predate the stop committed here; it was recorded
        # against the old stop and keeps that target price in its evidence.
        assert state["closures"][0]["target_price"] == "95"
    if state["stop_loss"] == "90" and not state["closures"]:
        assert state["remaining_qty"] == "2"
    assert len(results) == 2
    # A follow-up observation under the committed stop is authoritative.
    if state["stop_loss"] == "90":
        assert len(service.observe(trade["id"], _quote(94))["closures"]) <= 1


# -- 2. entry-time corrections ------------------------------------------


def test_entry_time_edit_persists_is_idempotent_and_rebuilds(journal):
    driver, client = journal
    trade = _create(client, entry_time="2026-09-10T10:00")
    assert _utc(trade["entry_time"]) == datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc)

    edited = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "entry_time": "2026-09-11T10:00"},
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["no_change"] is False
    assert body["revision"] == 2
    assert "entry_time" in body["changed_fields"]
    stored = driver.get_trade(trade["id"])
    assert stored["revision"] == 2
    assert _utc(stored["entry_time"]) == datetime(2026, 9, 11, 7, 0, tzinfo=timezone.utc)
    assert stored["entry_time_source"] == "USER"

    history = client.get(f"/api/v1/trades/{trade['id']}/revisions").json()["revisions"]
    assert history[0]["changed_fields"]["entry_time"]["to"] == "2026-09-11T07:00:00.000000Z"

    equivalent = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 2, "entry_time": "2026-09-11T10:00:00+03:00"},
    )
    assert equivalent.status_code == 200
    assert equivalent.json()["no_change"] is True
    assert equivalent.json()["revision"] == 2

    minute = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 2, "entry_time": "2026-09-11T10:05"},
    )
    assert minute.status_code == 200
    assert minute.json()["revision"] == 3
    assert _utc(driver.get_trade(trade["id"])["entry_time"]) == datetime(
        2026, 9, 11, 7, 5, tzinfo=timezone.utc
    )

    future = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={
            "expected_revision": 3,
            "entry_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    assert future.status_code == 422
    assert future.json()["detail"]["reason"] == "TIME_IN_FUTURE"

    adapter = endpoints.trade_read_adapter
    assert adapter.projection_repo.rebuild(dry_run=False)["ledger_valid"] is True
    assert _utc(adapter.get_trade(trade["id"])["entry_time"]) == datetime(
        2026, 9, 11, 7, 5, tzinfo=timezone.utc
    )
    assert client.get(f"/api/v1/trades/{trade['id']}").json()["entry_time"] == (
        driver.get_trade(trade["id"])["entry_time"]
    )


# -- 4. unknown contract size -------------------------------------------


def test_position_summary_withholds_monetary_math_for_unverified_units():
    gold = position_summary(
        symbol="XAUUSD",
        position_type="LONG",
        side="BUY",
        entry_price=2000,
        qty=2,
        leverage=10,
        exit_price=2100,
    )
    assert gold["monetary_calculation"] == {
        "status": "UNAVAILABLE",
        "reason": "CONTRACT_SIZE_UNVERIFIED",
    }
    assert gold["notional"]["value"] is None
    assert gold["margin_estimate"]["value"] is None
    assert gold["returns"]["gross_pnl"] is None
    assert gold["returns"]["position_return_pct_gross"] is None
    assert gold["returns"]["margin_return_pct_gross"] is None
    # The unit-free price move is still informative.
    assert gold["returns"]["price_return_pct"] == pytest.approx(5)

    for symbol in ("GC=F", "ES=F", "EURUSD=X", "^GSPC", "ARCLK.IS", "AAPL"):
        summary = position_summary(
            symbol=symbol, position_type="LONG", side="BUY",
            entry_price=100, qty=1, leverage=10, exit_price=110,
        )
        assert summary["monetary_calculation"]["status"] == "UNAVAILABLE", symbol
        assert summary["notional"]["value"] is None, symbol
        assert summary["returns"]["gross_pnl"] is None, symbol

    verified = position_summary(
        symbol="BTCUSDT", position_type="LONG", side="BUY",
        entry_price=100, qty=2, leverage=10, exit_price=110,
        qty_unit="BASE",
    )
    assert verified["monetary_calculation"]["status"] == "READY"
    assert verified["notional"]["value"] == 200
    assert verified["margin_estimate"]["value"] == 20
    assert verified["returns"]["gross_pnl"] == 20
    assert verified["returns"]["margin_return_pct_gross"] == pytest.approx(100)


def test_local_tracking_plan_is_rejected_for_unverified_instrument(journal):
    driver, client = journal
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "XAUUSD",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 2000,
            "qty": 2,
            "local_tracking": {
                "enabled": True,
                "source_id": "biquote_public",
                "source_symbol": "XAUUSD",
                "targets": [{"price": 2100, "percent": 100}],
                "stop_loss": 1950,
            },
        },
    )
    assert response.status_code == 422
    assert "base-unit" in response.text
    assert driver.list_trades(limit=10) == []


def test_closed_unverified_trade_records_no_money_figure(journal):
    driver, client = journal
    trade = _create(client, symbol="XAUUSD", entry_price=2000, qty=2)
    closed = client.post(
        f"/api/v1/trades/{trade['id']}/close",
        json={"exit_price": 2100},
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["status"] == "CLOSED"
    assert body["pnl"] is None
    assert body["r_multiple"] is None
    assert body["sizing"]["monetary_calculation"]["status"] == "UNAVAILABLE"

    historical = _create(
        client,
        symbol="GC=F",
        status="CLOSED",
        entry_time="2026-09-01T10:00",
        exit_price=2450,
        exit_time="2026-09-02T10:00",
    )
    assert historical["pnl"] is None

    summary = client.get("/api/v1/portfolio/summary").json()
    assert summary["unknown_pnl_trades"] == 2
    assert summary["net_pnl"] == 0

    adapter = endpoints.trade_read_adapter
    assert adapter.projection_repo.rebuild(dry_run=False)["ledger_valid"] is True
    assert adapter.get_trade(trade["id"])["pnl"] is None


def test_legacy_unverified_plan_cannot_produce_close_evidence(journal):
    driver, _ = journal
    trade = driver.record_trade_with_evidence(
        {"id": "LEGACY-GOLD", "symbol": "XAUUSD", "side": "BUY", "entry_price": 2000, "qty": 2},
        event_type="IntentRecorded",
        idempotency_key="legacy-gold",
    )
    state = {
        "version": 1,
        "basis": "LOCAL_ESTIMATE",
        "trade_id": trade["id"],
        "symbol": "XAUUSD",
        "side": "BUY",
        "entry_price": "2000",
        "initial_qty": "2",
        "remaining_qty": "2",
        "gross_pnl": "0",
        "closures": [],
        "targets": [{"id": "TP1", "price": "2100", "percent": "100"}],
        "stop_loss": "1950",
        "enabled": True,
        "source_id": "biquote_public",
        "source_symbol": "XAUUSD",
        "armed_at": datetime.now(timezone.utc).isoformat(),
        "revision": 1,
    }
    ledger = EvidenceLedgerRepository(driver.db_path)
    ledger.append_event(
        event_type="PositionProjectionUpdated",
        account_id="local-journal",
        venue="local-journal",
        idempotency_key="legacy-plan-1",
        correlation_id=trade["id"],
        normalized_payload={"local_tracking": state, "action": "PLAN_SAVED", "observation": None},
        occurred_at=datetime.now(timezone.utc).isoformat(),
        adapter_version="local-tracking-v1",
        provenance={"source": "local_tracking", "basis": "LOCAL_ESTIMATE", "broker_execution": False},
    )
    service = LocalTrackingService(driver)
    listed = service.list()
    assert listed[0]["unit_status"] == "UNVERIFIED"

    observation = _quote(2300, symbol="XAUUSD")
    observation["source_id"] = "biquote_public"
    assert service.observe(trade["id"], observation)["closures"] == []
    with pytest.raises(TrackingUnsupported):
        service.observe(trade["id"], {"price": 2300, "basis": "MANUAL_LOCAL"}, manual=True, expected_revision=1)
