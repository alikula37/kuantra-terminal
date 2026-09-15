from datetime import datetime, timezone, timedelta

import pytest

from app.db.sqlite_driver import SQLiteDriver
from app.services.local_tracking import LocalTrackingService, TrackingConflict


@pytest.fixture
def setup(tmp_path):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite3"))
    trade = driver.record_trade_with_evidence(
        {"id": "t1", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 100, "qty": 2,
         "qty_unit": "BASE"},
        event_type="IntentRecorded", idempotency_key="create",
    )
    return driver, LocalTrackingService(driver), trade


def plan(side="BUY"):
    return {"enabled": True, "source_id": "binance_public", "source_symbol": "BTCUSDT",
            "targets": [{"price": p, "percent": n} for p, n in
                        zip(([110, 120, 130] if side == "BUY" else [90, 80, 70]), [50, 25, 25])],
            "stop_loss": 95 if side == "BUY" else 105}


def quote(value, **extra):
    return {"source_id": "binance_public", "source_symbol": "BTCUSDT", "price": value,
            "status": "LIVE", "timestamp_basis": "PROVIDER_EVENT",
            "observed_at": datetime.now(timezone.utc).isoformat(), **extra}


def test_plan_revision_and_external_history(setup):
    driver, svc, trade = setup
    result = svc.edit("t1", plan(), expected_revision=0)
    assert result["revision"] == 1
    assert result["remaining_qty"] == "2"
    with pytest.raises(TrackingConflict):
        svc.edit("t1", plan(), expected_revision=0)
    assert driver.get_trade("t1") == trade


@pytest.mark.parametrize("targets", [
    [{"price": 110, "percent": 90}],
    [{"price": 90, "percent": 100}],
    [{"price": 120, "percent": 50}, {"price": 110, "percent": 50}],
])
def test_invalid_plan_is_atomic(setup, targets):
    driver, svc, _ = setup
    with pytest.raises(ValueError):
        svc.edit("t1", {**plan(), "targets": targets}, expected_revision=0)
    assert svc.get("t1") is None


def test_partial_replay_and_gap_price(setup):
    driver, svc, trade = setup
    svc.edit("t1", plan(), expected_revision=0)
    observation = quote(125)
    result = svc.observe("t1", observation)
    assert result["remaining_qty"] == "0.5"
    assert result["gross_pnl"] == "37.5"
    assert len(result["closures"]) == 2
    assert svc.observe("t1", observation) == result
    reopened = LocalTrackingService(driver)
    assert reopened.get("t1")["closures"] == result["closures"]
    assert driver.get_trade("t1") == trade


@pytest.mark.parametrize("extra", [
    {"source_symbol": "ETHUSDT"}, {"source_id": "bybit_public"},
    {"status": "DELAYED"}, {"status": "EOD"}, {"timestamp_basis": "RECEIVED"},
    {"price": float("nan")},
    {"observed_at": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()},
])
def test_unqualified_quote_never_closes(setup, extra):
    _, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    assert svc.observe("t1", quote(150, **extra))["remaining_qty"] == "2"


def test_completed_target_edit_sl_and_manual_close(setup):
    _, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    first = svc.observe("t1", quote(110))
    invalid = plan()
    invalid["targets"][0]["price"] = 111
    with pytest.raises(TrackingConflict):
        svc.edit("t1", invalid, expected_revision=first["revision"])
    edited = plan()
    edited["targets"][1]["price"] = 125
    result = svc.edit("t1", edited, expected_revision=first["revision"])
    result = svc.observe("t1", quote(94))
    assert result["remaining_qty"] == "0"
    assert result["gross_pnl"] == "4"
    assert svc.observe("t1", quote(140)) == result


def test_short_and_manual_revision(setup):
    driver, svc, _ = setup
    driver.record_trade_with_evidence({"id": "t1", "side": "SELL"},
        event_type="TradeCorrected", idempotency_key="short")
    svc.edit("t1", plan("SELL"), expected_revision=0)
    state = svc.observe("t1", quote(85))
    assert state["gross_pnl"] == "15"
    with pytest.raises(TrackingConflict):
        svc.observe("t1", {"price": 80}, manual=True, expected_revision=1)
    result = svc.observe("t1", {"price": 80}, manual=True, expected_revision=2)
    assert result["remaining_qty"] == "0"
    assert result["gross_pnl"] == "35"


def test_rollback_and_rebuild(setup):
    driver, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    def fail(phase, conn):
        if phase == "after_local_tracking_projection":
            raise RuntimeError("disk failure")
    driver._transaction_hook = fail
    with pytest.raises(RuntimeError):
        svc.observe("t1", quote(150))
    driver._transaction_hook = None
    assert svc.get("t1")["remaining_qty"] == "2"
    assert len(svc.history("t1")) == 1
    from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
    with driver.get_connection() as conn:
        conn.execute("DELETE FROM local_tracking_projections")
    EvidenceTradeProjectionRepository(driver.db_path).rebuild(dry_run=False)
    with driver.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM local_tracking_projections").fetchone()[0] == 1


def test_create_plan_failure_rolls_back_external_trade(setup):
    driver, svc, _ = setup
    with pytest.raises(ValueError):
        driver.record_trade_with_evidence(
            {"id": "bad", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 100, "qty": 2,
             "qty_unit": "BASE"},
            event_type="IntentRecorded", idempotency_key="bad-create",
            local_tracking_plan={**plan(), "targets": [{"price": 110, "percent": 50}]},
        )
    assert driver.get_trade("bad") is None
    assert svc.get("bad") is None


def test_concurrent_observation_cannot_double_close(setup):
    from concurrent.futures import ThreadPoolExecutor
    driver, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    observation = quote(150)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: LocalTrackingService(driver).observe("t1", observation), range(4)))
    assert all(r["remaining_qty"] == "0" for r in results)
    assert len(svc.history("t1")) == 2
    assert len(svc.get("t1")["closures"]) == 3


def test_pre_edit_quote_cancellation_and_correction(setup):
    driver, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    stale = quote(150)
    svc.edit("t1", plan(), expected_revision=1)
    assert svc.observe("t1", stale)["remaining_qty"] == "2"
    driver.record_trade_with_evidence({"id": "t1", "qty": 4}, event_type="TradeCorrected", idempotency_key="qty")
    with pytest.raises(TrackingConflict):
        svc.observe("t1", quote(150))
    driver.record_trade_with_evidence({"id": "t1", "status": "CANCELED"}, event_type="TradeCorrected", idempotency_key="cancel")
    assert svc.observe("t1", quote(150))["remaining_qty"] == "2"


def test_sqlite_backup_restore_preserves_local_and_external_evidence(setup, tmp_path):
    import sqlite3
    from app.services.trade_read_adapter import TradeReadAdapter
    from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
    driver, svc, trade = setup
    svc.edit("t1", plan(), expected_revision=0)
    svc.observe("t1", quote(125))
    original_pack = TradeReadAdapter(legacy_driver=driver).get_evidence_pack("t1")
    assert any(e["normalized_payload"].get("local_tracking") for e in original_pack["events"])
    target = str(tmp_path / "restored.sqlite3")
    with driver.get_connection() as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    restored = SQLiteDriver(target)
    EvidenceTradeProjectionRepository(target).rebuild(dry_run=False)
    assert LocalTrackingService(restored).get("t1") == svc.get("t1")
    assert restored.get_trade("t1") == trade
    pack = TradeReadAdapter(legacy_driver=restored).get_evidence_pack("t1")
    assert pack["events"] == original_pack["events"]


def test_tracking_api_is_revisioned_and_never_closes_external_trade(setup, monkeypatch):
    from fastapi.testclient import TestClient
    from main import create_app
    from app.api import endpoints
    driver, svc, trade = setup
    monkeypatch.setattr(endpoints, "sqlite_driver", driver)
    client = TestClient(create_app())
    response = client.put("/api/v1/trades/t1/tracking", json={**plan(), "expected_revision": 0})
    assert response.status_code == 200
    assert client.put("/api/v1/trades/t1/tracking", json={**plan(), "expected_revision": 0}).status_code == 409
    assert client.get("/api/v1/trades/t1/tracking").json()["plan"]["revision"] == 1
    response = client.post("/api/v1/trades/t1/tracking/close", json={"price": 120, "expected_revision": 1})
    assert response.status_code == 200
    assert response.json()["remaining_qty"] == "0"
    assert driver.get_trade("t1") == trade


def test_no_targets_disabled_and_short_stop(setup):
    driver, svc, _ = setup
    svc.edit("t1", {"enabled": True, "targets": [],
              "source_id": "binance_public", "source_symbol": "BTCUSDT"}, expected_revision=0)
    assert svc.observe("t1", quote(150))["remaining_qty"] == "2"
    svc.edit("t1", {**plan(), "enabled": False}, expected_revision=1)
    assert svc.observe("t1", quote(150))["remaining_qty"] == "2"


def test_corrupted_chain_blocks_tracking(setup):
    driver, svc, _ = setup
    svc.edit("t1", plan(), expected_revision=0)
    with driver.get_connection() as conn:
        conn.execute("DROP TRIGGER evidence_events_no_update")
        conn.execute("UPDATE evidence_events SET event_hash=? WHERE chain_sequence=1", ("f" * 64,))
    with pytest.raises(ValueError, match="chain invalid"):
        svc.observe("t1", quote(150))


def test_fractional_allocations_preserve_exact_quantity(setup):
    driver, svc, _ = setup
    driver.record_trade_with_evidence({"id": "t1", "qty": 0.1234567890123456},
        event_type="TradeCorrected", idempotency_key="fractional")
    fractional = plan()
    for target, percent in zip(fractional["targets"], ["33.3333333333333", "33.3333333333333", "33.3333333333334"]):
        target["percent"] = percent
    svc.edit("t1", fractional, expected_revision=0)
    first = svc.observe("t1", quote(110))
    assert len(first["closures"]) == 1
    final = svc.observe("t1", quote(130))
    assert final["remaining_qty"] == "0"
