"""WP46 regression tests: USD value math in every remaining money path.

Real-UI findings on installed 1.1.5: the create form risk/reward and the dashboard
live feed still multiplied the price difference by the USD position value as if it
were a base-asset quantity.  These tests pin the value-based formula, the metadata
that the live feed must carry, and the tracking monitor's visible waiting states.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.db.sqlite_driver import SQLiteDriver
from app.services.local_tracking import LocalTrackingService


def _usd_trade(driver: SQLiteDriver, trade_id: str = "TRD-WS-USD", **overrides):
    trade = {
        "id": trade_id, "symbol": "BTCUSDT", "side": "BUY", "status": "OPEN",
        "entry_price": 76000.0, "qty": 100.0, "qty_unit": "USD",
        "leverage": 2.0, "stop_loss": 70000.0, "take_profit": 90000.0,
        "entry_time": "2026-09-17T17:40:00Z", "record_mode": "SIMULATION",
        "price_source": "binance_public", "price_source_symbol": "BTCUSDT",
    }
    trade.update(overrides)
    driver.record_trade_with_evidence(
        trade, event_type="IntentRecorded", idempotency_key=f"wp46:{trade_id}",
        occurred_at="2026-09-17T17:40:00Z", provenance={"source": "journal_simulation"},
    )
    return trade


# ---------------------------------------------------------------------------
# Dashboard live feed (websocket client)
# ---------------------------------------------------------------------------


def test_live_position_feed_prices_usd_value_and_keeps_unit_metadata(monkeypatch, tmp_path):
    from app.websocket import binance_client as binance_module

    driver = SQLiteDriver(str(tmp_path / "ws.sqlite"))
    _usd_trade(driver)
    monkeypatch.setattr(binance_module, "sqlite_driver", driver)

    client = binance_module.BinanceStreamClient()
    client.symbol = "BTCUSDT"
    rows = client._recalculate_open_positions(76787.70)

    assert len(rows) == 1
    row = rows[0]
    # value x return = 100 x 787.70/76000 = 1.04, NOT 78770.
    assert abs(row["unrealized_pnl"] - 1.04) < 0.01
    # R is the unit-free price-distance ratio: 787.70 / 6000 = 0.13
    assert abs(row["r_multiple"] - 0.13) < 0.01
    # Unit metadata must survive so the dashboard never loses the simulation label.
    assert row["qty_unit"] == "USD"
    assert row["record_mode"] == "SIMULATION"


def test_live_position_feed_handles_short_positions_in_usd(monkeypatch, tmp_path):
    from app.websocket import binance_client as binance_module

    driver = SQLiteDriver(str(tmp_path / "ws-short.sqlite"))
    _usd_trade(driver, trade_id="TRD-WS-SHORT", side="SELL", stop_loss=80000.0)
    monkeypatch.setattr(binance_module, "sqlite_driver", driver)

    client = binance_module.BinanceStreamClient()
    client.symbol = "BTCUSDT"
    row = client._recalculate_open_positions(75000.0)[0]
    # Short: value x -(price-entry)/entry = 100 x 1000/76000 = 1.32 profit.
    assert abs(row["unrealized_pnl"] - 1.32) < 0.01


def test_legacy_base_rows_keep_their_old_meaning(monkeypatch, tmp_path):
    from app.websocket import binance_client as binance_module

    driver = SQLiteDriver(str(tmp_path / "ws-base.sqlite"))
    _usd_trade(driver, trade_id="TRD-WS-BASE", qty=2.0, qty_unit="BASE")
    monkeypatch.setattr(binance_module, "sqlite_driver", driver)

    client = binance_module.BinanceStreamClient()
    client.symbol = "BTCUSDT"
    row = client._recalculate_open_positions(76787.70)[0]
    assert abs(row["unrealized_pnl"] - 1575.40) < 0.01  # 2 x 787.70
    assert row["qty_unit"] == "BASE"


# ---------------------------------------------------------------------------
# Replay payload
# ---------------------------------------------------------------------------


def test_closed_replay_unrealized_uses_the_usd_value():
    from app.replay.replay_service import ReplaySession

    class Evidence:
        trade = {"id": "T1", "symbol": "BTCUSDT", "side": "BUY", "entry_price": 76000.0,
                 "current_price": None, "exit_price": 77000.0, "qty": 100.0,
                 "qty_unit": "USD", "stop_loss": None, "take_profit": None,
                 "risk_unit": None, "risk_reason": None, "pnl": None}
        candles = [
            {"timestamp": 1, "open": 76000.0, "high": 76100.0, "low": 75900.0, "close": 76000.0, "volume": 1},
            {"timestamp": 2, "open": 76000.0, "high": 77100.0, "low": 76000.0, "close": 77000.0, "volume": 1},
            {"timestamp": 3, "open": 77000.0, "high": 77100.0, "low": 76900.0, "close": 77000.0, "volume": 1},
        ]
        entry_index = 0
        exit_index = 2
        market_context = {"fingerprint_sha256": "x"}

    session = ReplaySession("REP-1", Evidence())
    state = session.to_dict()
    assert state["trade"]["unrealized_pnl"] == 0.0
    # At bar 1 (close 77000) the value-based move is 100 x 1000/76000 = 1.3158,
    # never 100 x 1000 = 100000.
    session.current_index = 1
    stepped = session.to_dict()
    assert abs(stepped["trade"]["unrealized_pnl"] - 1.3158) < 0.01
    assert stepped["trade"]["phase"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Tracking monitor visibility and backoff
# ---------------------------------------------------------------------------


def _tracking_state(tmp_path, *, qty=100.0, entry=76000.0, target=76100.0, stop=None):
    driver = SQLiteDriver(str(tmp_path / "monitor.sqlite"))
    _usd_trade(driver, entry_price=entry, qty=qty, stop_loss=stop, take_profit=target)
    service = LocalTrackingService(driver)
    state = service.edit(
        "TRD-WS-USD",
        {"enabled": True, "source_id": "binance_public", "source_symbol": "BTCUSDT",
         "stop_loss": stop, "targets": [{"price": target, "percent": 100}]},
        expected_revision=0,
    )
    return service, state


def _provider_observation(price: float, *, seconds_ago: float = 0.0, status: str = "LIVE"):
    observed = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return {
        "status": status, "price": str(price), "observed_at": observed.isoformat(),
        "timestamp_basis": "PROVIDER_EVENT", "source_id": "binance_public",
        "source_symbol": "BTCUSDT", "provider_event_id": "1",
    }


def test_stale_observation_retries_soon_without_backoff_and_does_not_close(tmp_path):
    from app.services.local_tracking_monitor import TrackingMonitor

    service, state = _tracking_state(tmp_path)
    calls = {"n": 0}

    async def fetch(*_args):
        calls["n"] += 1
        return _provider_observation(77000.0, seconds_ago=600)  # too old: never eligible

    monitor = TrackingMonitor(service=service, fetch=fetch)
    asyncio.run(monitor.poll(enabled=True))
    assert calls["n"] == 1
    assert monitor.failures.get(("binance_public", "BTCUSDT"), 0) == 0
    state_after = service.get("TRD-WS-USD")
    assert state_after["remaining_qty"] == "100"  # untouched
    # Short retry window, not the 30 s+ failure backoff.
    assert monitor.next_poll[("binance_public", "BTCUSDT")] <= time_now_plus(10)
    view = monitor.view(state_after)
    assert view["monitor"]["wait_reason"] == "WAITING_FRESH_PROVIDER_EVENT"


def time_now_plus(seconds: float) -> float:
    import time

    return time.monotonic() + seconds


def test_single_closure_on_repeated_eligible_observations(tmp_path):
    from app.services.local_tracking_monitor import TrackingMonitor

    service, state = _tracking_state(tmp_path)

    async def fetch(*_args):
        return _provider_observation(77000.0)  # above the 76100 target

    monitor = TrackingMonitor(service=service, fetch=fetch)
    asyncio.run(monitor.poll(enabled=True))
    asyncio.run(monitor.poll(enabled=True))
    asyncio.run(monitor.poll(enabled=True))

    final = service.get("TRD-WS-USD")
    assert final["remaining_qty"] == "0"
    assert len(final["closures"]) == 1
    assert final["closures"][0]["target_id"] == "TP1"
    assert abs(float(final["gross_pnl"]) - 100.0 * 1000.0 / 76000.0) < 0.01
    # The completed plan leaves the monitor state and never closes twice.
    assert monitor.failures.get(("binance_public", "BTCUSDT"), 0) == 0


def test_fetch_error_backs_off_and_reports_the_reason(tmp_path):
    from app.services.local_tracking_monitor import TrackingMonitor

    service, state = _tracking_state(tmp_path)

    async def fetch(*_args):
        raise ConnectionError("provider unreachable")

    monitor = TrackingMonitor(service=service, fetch=fetch)
    asyncio.run(monitor.poll(enabled=True))
    key = ("binance_public", "BTCUSDT")
    assert monitor.failures[key] == 1
    assert monitor.next_poll[key] >= time_now_plus(25)
    view = monitor.view(service.get("TRD-WS-USD"))
    assert view["monitor"]["wait_reason"] == "PROVIDER_ERROR"
    assert "unreachable" in (view["monitor"]["last_error"] or "")


def test_monitor_view_reports_disabled_market_data(tmp_path):
    from app.services.local_tracking_monitor import TrackingMonitor

    service, state = _tracking_state(tmp_path)
    monitor = TrackingMonitor(service=service, fetch=lambda *_: None)
    asyncio.run(monitor.poll(enabled=False))
    view = monitor.view(service.get("TRD-WS-USD"))
    assert view["monitor"]["enabled"] is False
    assert view["monitor"]["wait_reason"] == "MARKET_DATA_DISABLED"


def test_provider_clock_skew_is_tolerated_but_future_stamps_are_not(tmp_path):
    """A provider event a moment ahead of the local clock is fresh, not stale.

    Binance event timestamps can lead the local clock by fractions of a second;
    the old ``0 <= age`` check rejected those fresh events forever, so automatic
    closes waited with a misleading "fresh event" reason.  Only a small bounded
    skew is tolerated; clearly future stamps stay ineligible.
    """

    service, _state = _tracking_state(tmp_path)
    now = datetime.now(timezone.utc)

    def observation(offset_seconds: float):
        return {
            "status": "LIVE", "price": "77000", "timestamp_basis": "PROVIDER_EVENT",
            "source_id": "binance_public", "source_symbol": "BTCUSDT",
            "observed_at": (now + timedelta(seconds=offset_seconds)).isoformat(),
        }

    armed = {"source_id": "binance_public", "source_symbol": "BTCUSDT",
             "armed_at": (now - timedelta(minutes=5)).isoformat()}
    assert service.eligible(armed, observation(0.4), now=now) is True       # slight skew
    assert service.eligible(armed, observation(-2.0), now=now) is True      # normal fresh
    assert service.eligible(armed, observation(30.0), now=now) is False     # clearly future
    assert service.eligible(armed, observation(-120.0), now=now) is False   # clearly stale
