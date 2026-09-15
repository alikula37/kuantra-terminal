"""P1-WP32 journal trust contracts.

Covers user-supplied Turkey-time trade dates, historical open/closed behavior,
declared leverage with separated returns, revisioned correction lineage,
partial-close protection, bounded quote refresh and schema compatibility.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core.position_math import position_summary
from app.core.trade_time import ISTANBUL_TZ
from app.db import sync_pipeline as sync_pipeline_module
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver, SQLiteRevisionConflict
from app.services.local_tracking import LocalTrackingService
from app.services.quote_refresh import QuoteRefreshService
from app.services.trade_edit import TradeEditService
from app.services.trade_read_adapter import TradeReadAdapter
from app.services.weekly_review import WeeklyReviewService
from main import create_app


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _istanbul_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def _naive_input(value: datetime) -> str:
    return _istanbul_minute(value).astimezone(ISTANBUL_TZ).strftime("%Y-%m-%dT%H:%M")


def _plan(symbol: str = "BTCUSDT") -> dict:
    return {
        "enabled": True,
        "source_id": "binance_public",
        "source_symbol": symbol,
        "targets": [
            {"price": 110, "percent": 50},
            {"price": 120, "percent": 25},
            {"price": 130, "percent": 25},
        ],
        "stop_loss": 95,
    }


def _open_quote(value: float, symbol: str = "BTCUSDT", **extra) -> dict:
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
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
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
    monkeypatch.setattr(endpoints, "trade_edit_service", TradeEditService(driver))
    client = TestClient(create_app())
    return driver, client


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


# -- trade time ----------------------------------------------------------


def test_naive_user_time_is_istanbul_and_stored_utc(journal):
    driver, client = journal
    wall = datetime.now(timezone.utc) - timedelta(days=1, hours=4)
    value = _naive_input(wall)
    trade = _create(client, entry_time=value)

    assert trade["entry_time_source"] == "USER"
    stored = _utc(trade["entry_time"]).astimezone(ISTANBUL_TZ)
    assert _istanbul_minute(stored) == _istanbul_minute(wall.astimezone(ISTANBUL_TZ))
    assert stored.utcoffset() == timedelta(hours=3)
    assert driver.get_trade(trade["id"])["entry_time_source"] == "USER"


def test_offset_time_is_honored_exactly(journal):
    _, client = journal
    trade = _create(client, entry_time="2026-01-05T08:15:00+03:00")
    assert _utc(trade["entry_time"]) == datetime(2026, 1, 5, 5, 15, tzinfo=timezone.utc)


def test_missing_user_time_stays_server_tagged(journal):
    _, client = journal
    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    trade = _create(client)
    assert trade["entry_time_source"] == "SERVER"
    assert _utc(trade["entry_time"]) >= before


def test_future_realized_times_are_rejected(journal):
    driver, client = journal
    future = _naive_input(datetime.now(timezone.utc) + timedelta(days=1))
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 1,
            "entry_time": future,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "TIME_IN_FUTURE"
    assert driver.get_open_trades() == []


def test_historical_closed_trade_requires_close_fields_and_never_tracks(journal):
    driver, client = journal
    missing = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 1,
            "status": "CLOSED",
            "entry_time": _naive_input(datetime.now(timezone.utc) - timedelta(days=2)),
        },
    )
    assert missing.status_code == 422

    entry_wall = _naive_input(datetime.now(timezone.utc) - timedelta(days=3))
    exit_wall = _naive_input(datetime.now(timezone.utc) - timedelta(days=1))
    trade = _create(
        client,
        status="CLOSED",
        entry_time=entry_wall,
        exit_price=112,
        exit_time=exit_wall,
        qty_unit="BASE",
    )
    assert trade["status"] == "CLOSED"
    assert trade["close_source"] == "USER_REPORTED"
    assert trade["pnl"] == 24
    assert driver.get_trade(trade["id"])["status"] == "CLOSED"

    tracking = client.get(f"/api/v1/trades/{trade['id']}/tracking")
    assert tracking.status_code == 200
    assert tracking.json()["plan"] is None

    contradictory = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 1,
            "status": "CLOSED",
            "entry_time": entry_wall,
            "exit_price": 112,
            "exit_time": exit_wall,
            "local_tracking": _plan(),
        },
    )
    assert contradictory.status_code == 422


def test_exit_before_entry_is_rejected(journal):
    _, client = journal
    entry_wall = _naive_input(datetime.now(timezone.utc) - timedelta(days=1))
    exit_wall = _naive_input(datetime.now(timezone.utc) - timedelta(days=2))
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 1,
            "status": "CLOSED",
            "entry_time": entry_wall,
            "exit_price": 90,
            "exit_time": exit_wall,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "EXIT_BEFORE_ENTRY"


def test_historical_open_tracking_starts_after_recording(journal):
    driver, client = journal
    entry_wall = _naive_input(datetime.now(timezone.utc) - timedelta(days=2))
    trade = _create(client, entry_time=entry_wall, qty_unit="BASE", local_tracking=_plan())
    assert trade["tracking_started_at"] is not None
    assert _utc(trade["tracking_started_at"]) >= _utc(trade["entry_time"])

    service = LocalTrackingService(driver)
    state = service.get(trade["id"])
    assert state is not None
    armed = _utc(state["armed_at"])
    entry = _utc(trade["entry_time"])
    assert armed > entry

    # A quote observed during the untracked gap must never close the trade.
    stale = _open_quote(150)
    stale["observed_at"] = entry.isoformat()
    assert float(service.observe(trade["id"], stale)["remaining_qty"]) == float(trade["qty"])
    # A fresh provider observation after arming is eligible.
    fresh = _open_quote(150)
    assert LocalTrackingService.eligible(state, fresh) is True


def test_istanbul_weekly_review_boundaries_are_utc_normalized():
    period = WeeklyReviewService._period("2026-09-14", "2026-09-21", "Europe/Istanbul")
    assert period["start_local"] == "2026-09-14T00:00:00+03:00"
    assert period["start_utc"] == "2026-09-13T21:00:00Z"
    assert period["end_utc"] == "2026-09-20T21:00:00Z"


# -- sizing and leverage -------------------------------------------------


def test_leverage_is_declared_metadata_and_returns_stay_separated(journal):
    _, client = journal
    trade = _create(client, leverage=10, exit_price=110, status="CLOSED", qty_unit="BASE",
                    exit_time=_naive_input(datetime.now(timezone.utc) - timedelta(hours=1)),
                    entry_time=_naive_input(datetime.now(timezone.utc) - timedelta(days=1)))
    assert trade["leverage"] == 10
    sizing = trade["sizing"]
    assert sizing["leverage"] == {"value": 10.0, "source": "USER_DECLARED"}
    assert sizing["notional"]["value"] == 200
    assert sizing["margin_estimate"]["value"] == 20
    returns = sizing["returns"]
    assert returns["gross_pnl"] == 20
    assert returns["price_return_pct"] == pytest.approx(10)
    assert returns["position_return_pct_gross"] == pytest.approx(10)
    assert returns["margin_return_pct_gross"] == pytest.approx(100)
    assert "liquidation" not in json.dumps(trade).lower()


def test_spot_rejects_leverage_and_reports_full_payment(journal):
    _, client = journal
    response = client.post(
        "/api/v1/trades",
        json={
            "symbol": "LINKUSDT",
            "side": "BUY",
            "position_type": "SPOT",
            "entry_price": 10,
            "qty": 2,
            "leverage": 5,
        },
    )
    assert response.status_code == 422
    trade = _create(client, symbol="LINKUSDT", position_type="SPOT", entry_price=10, qty=2, qty_unit="BASE")
    assert trade["leverage"] is None
    assert trade["sizing"]["margin_estimate"]["source"] == "SPOT_FULL_PAYMENT"
    assert trade["sizing"]["margin_estimate"]["value"] == 20


def test_notional_mode_derives_quantity_and_conflicts_fail(journal):
    _, client = journal
    derived = _create(client, size_input_mode="NOTIONAL", notional_size=500, entry_price=100, qty=None)
    assert derived["qty"] == pytest.approx(5)

    both = client.post(
        "/api/v1/trades",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "position_type": "LONG",
            "entry_price": 100,
            "qty": 1,
            "notional_size": 100,
        },
    )
    assert both.status_code == 422
    neither = client.post(
        "/api/v1/trades",
        json={"symbol": "BTCUSDT", "side": "BUY", "position_type": "LONG", "entry_price": 100},
    )
    assert neither.status_code == 422


def test_xauusd_contract_size_is_never_assumed():
    summary = position_summary(
        symbol="XAUUSD",
        position_type="LONG",
        side="BUY",
        entry_price=2000,
        qty=1,
        leverage=10,
        exit_price=2100,
    )
    assert summary["instrument"]["kind"] == "MACRO_OR_COMMODITY"
    assert summary["instrument"]["contract_size"] == "UNVERIFIED"
    assert "CONTRACT_SIZE_UNVERIFIED" in summary["warnings"]
    # No monetary figure at all for an unknown contract size.
    assert summary["monetary_calculation"]["status"] == "UNAVAILABLE"
    assert summary["notional"]["value"] is None
    assert summary["margin_estimate"]["value"] is None
    assert summary["returns"]["gross_pnl"] is None
    assert "liquidation" not in json.dumps(summary).lower()


# -- editing -------------------------------------------------------------


def test_edit_updates_reads_and_preserves_correction_history(journal):
    driver, client = journal
    trade = _create(client, notes="first")
    response = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "entry_price": 105, "qty": 3, "notes": "corrected"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["changed_fields"]["entry_price"] == {"from": 100.0, "to": 105.0}
    assert body["trade"]["entry_price"] == 105
    assert body["trade"]["qty"] == 3

    detail = client.get(f"/api/v1/trades/{trade['id']}").json()
    assert detail["entry_price"] == 105
    assert detail["notes"] == "corrected"
    listed = client.get("/api/v1/trades").json()
    assert next(t for t in listed if t["id"] == trade["id"])["entry_price"] == 105

    revisions = client.get(f"/api/v1/trades/{trade['id']}/revisions").json()
    assert revisions["current_revision"] == 2
    assert revisions["revisions"][0]["changed_fields"]["qty"] == {"from": 2.0, "to": 3.0}

    adapter = endpoints.trade_read_adapter
    pack = adapter.get_evidence_pack(trade["id"])
    assert any(event["event_type"] == "TradeCorrected" for event in pack["events"])
    assert adapter.projection_repo.rebuild(dry_run=False)["ledger_valid"] is True
    assert adapter.get_trade(trade["id"])["qty"] == 3
    assert driver.get_trade(trade["id"])["revision"] == 2


def test_stale_revision_is_rejected_without_writing(journal):
    driver, client = journal
    trade = _create(client)
    first = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "notes": "one"},
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "notes": "two"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["reason"] == "REVISION_CONFLICT"
    assert driver.get_trade(trade["id"])["notes"] == "one"


def test_driver_revision_guard_is_atomic(journal):
    driver, client = journal
    trade = _create(client, entry_price=100, qty=1)
    service = TradeEditService(driver)
    service.edit(trade["id"], {"notes": "first"}, expected_revision=1)

    def attempt(_):
        try:
            sync_pipeline_module.sync_pipeline.record_and_sync_trade(
                {"id": trade["id"], "notes": "race", "revision": 3},
                expected_revision=2,
            )
            return "written"
        except SQLiteRevisionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == ["conflict", "written"]


def test_closed_trade_allows_notes_only_and_cannot_close_twice(journal):
    driver, client = journal
    trade = _create(client)
    closed = client.post(
        f"/api/v1/trades/{trade['id']}/close",
        json={"exit_price": 110},
    )
    assert closed.status_code == 200
    closed_trade = closed.json()
    assert closed_trade["close_source"] == "USER_REPORTED"
    assert _utc(closed_trade["exit_time"]) <= datetime.now(timezone.utc)

    notes = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": closed_trade["revision"], "notes": "post-close note"},
    )
    assert notes.status_code == 200
    size = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": notes.json()["revision"], "qty": 5},
    )
    assert size.status_code == 422
    assert size.json()["detail"]["reason"] == "TRADE_CLOSED_NOTES_ONLY"
    double_close = client.post(f"/api/v1/trades/{trade['id']}/close", json={"exit_price": 120})
    assert double_close.status_code == 409


def test_partial_close_locks_size_but_allows_notes(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    service = LocalTrackingService(driver)
    partial = service.observe(trade["id"], _open_quote(110))
    assert partial["remaining_qty"] == "1"
    assert len(partial["closures"]) == 1
    revision = int(driver.get_trade(trade["id"])["revision"])

    blocked = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": revision, "entry_price": 101},
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["reason"] == "TRACKING_PARTIAL_CLOSE_LOCKS_SIZE"
    blocked_qty = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": revision, "qty": 1},
    )
    assert blocked_qty.status_code == 422

    notes = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": revision, "notes": "partial close note"},
    )
    assert notes.status_code == 200
    assert service.get(trade["id"])["closures"] == partial["closures"]
    assert service.get(trade["id"])["remaining_qty"] == "1"


def test_size_edit_before_any_close_resets_plan_only(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    assert LocalTrackingService(driver).get(trade["id"])["revision"] == 1

    edited = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "qty": 4},
    )
    assert edited.status_code == 200, edited.text
    state = LocalTrackingService(driver).get(trade["id"])
    assert state["initial_qty"] == "4"
    assert state["remaining_qty"] == "4"
    assert state["revision"] == 1
    assert state["closures"] == []
    assert len(state["targets"]) == 3
    assert len(LocalTrackingService(driver).history(trade["id"])) == 2


def test_size_edit_rejects_plan_that_becomes_invalid(journal):
    driver, client = journal
    trade = _create(client, qty_unit="BASE", local_tracking=_plan())
    del driver
    response = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": 1, "entry_price": 125},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "TRACKING_PLAN_INVALID_AFTER_EDIT"


def test_canceled_trade_is_editable_and_can_be_restored(journal):
    driver, client = journal
    trade = _create(client)
    canceled = client.delete(f"/api/v1/trades/{trade['id']}")
    assert canceled.status_code == 200
    revision = canceled.json()["trade"]["revision"]

    # A canceled trade is a note-style record now: fields and status can be
    # corrected, and the ledger keeps every previous value.
    notes = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": revision, "notes": "late"},
    )
    assert notes.status_code == 200, notes.text
    restored = client.patch(
        f"/api/v1/trades/{trade['id']}",
        json={"expected_revision": notes.json()["revision"], "status": "OPEN"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["trade"]["status"] == "OPEN"
    assert driver.get_trade(trade["id"])["status"] == "OPEN"
    # Canceling again is allowed from the restored open state.
    recanceled = client.delete(f"/api/v1/trades/{trade['id']}")
    assert recanceled.status_code == 200
    assert recanceled.json()["trade"]["status"] == "CANCELED"


# -- quote refresh -------------------------------------------------------


class _FakeFetcher:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def fetch_quote(self, symbol, source="auto"):
        self.calls.append((symbol, source))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(as_dict=lambda: dict(result))


def _quote_payload(price, status="LIVE"):
    return {
        "requested_symbol": "BTCUSDT",
        "source_id": "binance_public",
        "source_symbol": "BTCUSDT",
        "price": price,
        "status": status,
        "price_kind": "LAST",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "reason": None,
        "free_source": True,
        "credentials_required": False,
    }


@pytest.mark.asyncio
async def test_quote_refresh_shares_identity_and_marks_failures_stale():
    fixed = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    fetcher = _FakeFetcher([_quote_payload(65000)])
    service = QuoteRefreshService(fetcher=fetcher, clock=lambda: fixed)
    trades = [
        {"id": "A", "status": "OPEN", "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
        {"id": "B", "status": "OPEN", "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
        {"id": "C", "status": "OPEN", "price_source": "manual", "price_source_symbol": None},
        {"id": "D", "status": "CLOSED", "price_source": "binance_public", "price_source_symbol": "BTCUSDT"},
    ]
    result = await service.refresh(trades)
    assert len(fetcher.calls) == 1
    assert result["quotes"]["A"]["quote_status"] == "LIVE"
    assert result["quotes"]["A"]["price"] == 65000
    assert result["quotes"]["A"]["age_seconds"] is not None
    assert result["quotes"]["B"] == result["quotes"]["A"]
    assert result["quotes"]["C"]["reason"] == "NO_VERIFIED_QUOTE_IDENTITY"
    assert "D" not in result["quotes"]

    degraded = _FakeFetcher([RuntimeError("network down")])
    failing = QuoteRefreshService(fetcher=degraded, clock=lambda: fixed + timedelta(seconds=10))
    failing._cache = service._cache
    second = await failing.refresh(trades)
    assert second["quotes"]["A"]["quote_status"] == "UNAVAILABLE"
    assert second["quotes"]["A"]["last_known"]["stale"] is True
    assert second["quotes"]["A"]["last_known"]["price"] == 65000


@pytest.mark.asyncio
async def test_delayed_quote_is_display_only_for_refresh():
    fixed = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    fetcher = _FakeFetcher([_quote_payload(2005, status="DELAYED")])
    service = QuoteRefreshService(fetcher=fetcher, clock=lambda: fixed)
    result = await service.refresh(
        [{"id": "GOLD", "status": "OPEN", "price_source": "yahoo_public", "price_source_symbol": "XAUUSD=X"}]
    )
    assert result["quotes"]["GOLD"]["quote_status"] == "DELAYED"


# -- compatibility -------------------------------------------------------


def test_legacy_shaped_trade_keeps_explicit_unknown_defaults(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "legacy-defaults.sqlite3"))
    saved = driver.insert_trade(
        {"id": "LEGACY-1", "symbol": "ETHUSDT", "side": "BUY", "entry_price": 10, "qty": 2}
    )
    assert saved["revision"] == 1
    assert saved["leverage"] is None
    assert saved["entry_time_source"] == "UNKNOWN"
    assert saved["close_source"] is None
    assert saved["tracking_started_at"] is None
