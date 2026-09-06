"""Real temporary storage tests for time-range, coverage and numeric boundaries."""
from datetime import datetime, timedelta, timezone
import pytest

from app.db.duckdb_driver import DuckDBDriver
from app.db.sqlite_driver import SQLiteDriver
from app.quant import candle_evidence
from app.quant.candle_evidence import (
    EvidenceError,
    load_candle_evidence,
    market_context_attachment,
    normalize_trade,
    trade_bar_bounds,
    utc_timestamp,
)


@pytest.fixture
def candle_store(tmp_path, monkeypatch, recorded_candles):
    driver = DuckDBDriver(str(tmp_path / "evidence.duckdb"))
    rows = [
        {**bar, "timestamp": datetime.fromtimestamp(bar["time"], timezone.utc).replace(tzinfo=None), "trades_count": 2}
        for bar in recorded_candles
    ]
    for row in rows:
        del row["time"]
    assert driver.insert_candles(rows) == len(rows)
    monkeypatch.setattr(candle_evidence, "duckdb_driver", driver)
    return driver


def test_real_duckdb_range_is_utc_half_open_chronological_and_bounded(candle_store, recorded_candles):
    # 13:00+03:00 is 10:00Z, and the 10:03 bar must not be included.
    start = datetime.fromisoformat("2026-09-01T13:00:00+03:00")
    end = datetime.fromisoformat("2026-09-01T10:03:00Z")
    rows = candle_store.get_candles_range("btcusdt", start, end)
    assert [r["time"] for r in rows] == [c["time"] for c in recorded_candles[1:4]]
    assert candle_store.get_candles_range("BTCUSDT", start, end, limit=2) == rows[:2]
    assert candle_store.get_candles_range("BTCUSDT' OR 1=1 --", start, end) == []
    assert candle_store.get_candles_range("BTCUSDT", start, end, timeframe="5m") == []
    assert candle_store.get_candles_range("BTCUSDT", start.astimezone(timezone.utc).replace(tzinfo=None), end) == rows


@pytest.mark.parametrize("limit", [0, -1, 20603, True, 1.5])
def test_range_rejects_unbounded_or_invalid_limit(candle_store, limit):
    with pytest.raises(ValueError):
        candle_store.get_candles_range("BTCUSDT", datetime(2026, 9, 1), datetime(2026, 9, 2), limit=limit)


def test_real_history_indices_offsets_and_identical_duplicates(candle_store, recorded_trade):
    recorded_trade.update(entry_time="2026-09-01T13:00:15+03:00", exit_time="2026-09-01T10:02:35")
    evidence = load_candle_evidence(recorded_trade, lookback_bars=30, lookforward_bars=20)
    assert evidence.entry_index == 1 and evidence.exit_index == 3
    assert evidence.trade["entry_time"] == "2026-09-01T10:00:15+00:00"
    with candle_store.get_connection() as conn:
        conn.execute("INSERT INTO market_candles SELECT * FROM market_candles WHERE timestamp = '2026-09-01 10:01:00'")
    deduped = load_candle_evidence(recorded_trade, lookback_bars=30, lookforward_bars=20)
    assert deduped == evidence


def test_market_context_attachment_is_deterministic_and_discloses_boundaries(recorded_trade, recorded_candles):
    first = load_candle_evidence(recorded_trade, recorded_candles, lookback_bars=1, lookforward_bars=2)
    second = load_candle_evidence(recorded_trade, list(reversed(recorded_candles)), lookback_bars=1, lookforward_bars=2)

    attachment = market_context_attachment(first)
    assert attachment == market_context_attachment(second)
    assert attachment["context_start"] == "2026-09-01T09:59:00Z"
    assert attachment["context_end_exclusive"] == "2026-09-01T10:05:00Z"
    assert attachment["source_verified"] is False
    assert len(attachment["fingerprint_sha256"]) == 64


def test_real_conflicting_duplicate_is_rejected(candle_store, recorded_trade):
    with candle_store.get_connection() as conn:
        conn.execute("INSERT INTO market_candles SELECT symbol, timeframe, timestamp, open, high + 1, low, close, volume, trades_count FROM market_candles WHERE timestamp = '2026-09-01 10:01:00'")
    with pytest.raises(EvidenceError, match="Conflicting") as error:
        load_candle_evidence(recorded_trade)
    assert error.value.reason == "CONFLICTING_CANDLES"


def test_real_gap_is_rejected(candle_store, recorded_trade):
    with candle_store.get_connection() as conn:
        conn.execute("DELETE FROM market_candles WHERE timestamp = '2026-09-01 10:01:00'")
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade)
    assert error.value.reason == "INCOMPLETE_CANDLE_HISTORY"


def test_exact_exit_boundary_excludes_next_bar(recorded_trade, recorded_candles):
    recorded_trade["exit_time"] = "2026-09-01T10:02:00Z"
    result = load_candle_evidence(recorded_trade, recorded_candles, lookback_bars=1, lookforward_bars=2)
    assert result.exit_index == 2  # 10:01 complete bar, not 10:02
    assert len(result.trade_candles) == 2


def test_zero_duration_uses_one_explicitly_approximate_bar(recorded_trade, recorded_candles):
    recorded_trade["exit_time"] = recorded_trade["entry_time"]
    result = load_candle_evidence(recorded_trade, recorded_candles)
    assert result.entry_index == result.exit_index == 0
    assert len(result.trade_candles) == 1


def test_context_gaps_do_not_remove_complete_trade(recorded_trade, recorded_candles):
    far_before = {**recorded_candles[0], "time": recorded_candles[0]["time"] - 120}
    rows = [far_before, *recorded_candles[1:4], recorded_candles[-1]]
    result = load_candle_evidence(recorded_trade, rows, lookback_bars=30, lookforward_bars=20)
    assert len(result.candles) == 3 and result.entry_index == 0


@pytest.mark.parametrize("key,value,reason", [
    ("high", float("nan"), "INVALID_OHLC"), ("low", float("inf"), "INVALID_OHLC"),
    ("open", 0, "INVALID_OHLC"), ("close", True, "INVALID_OHLC"),
    ("high", 99, "INVALID_OHLC"), ("low", 101, "INVALID_OHLC"),
    ("volume", -1, "INVALID_VOLUME"), ("volume", float("inf"), "INVALID_VOLUME"),
    ("symbol", "ETHUSDT", "CANDLE_IDENTITY_MISMATCH"), ("timeframe", "5m", "CANDLE_IDENTITY_MISMATCH"),
])
def test_invalid_candle_fails_closed(recorded_trade, recorded_candles, key, value, reason):
    recorded_candles[1][key] = value
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade, recorded_candles)
    assert error.value.reason == reason


def test_unaligned_bar_is_not_silently_bucketed(recorded_trade, recorded_candles):
    recorded_candles[1]["time"] += 1
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade, recorded_candles)
    assert error.value.reason == "UNALIGNED_CANDLE"


@pytest.mark.parametrize("key,value,reason", [
    ("entry_price", float("nan"), "INVALID_TRADE"), ("exit_price", float("inf"), "INVALID_TRADE"),
    ("qty", 0, "INVALID_TRADE"), ("qty", True, "INVALID_TRADE"), ("side", "UNKNOWN", "INVALID_TRADE"),
    ("symbol", "", "INVALID_TRADE"), ("entry_time", None, "INVALID_TIMESTAMP"),
    ("exit_time", "not-a-time", "INVALID_TIMESTAMP"), ("exit_time", "2026-09-01T09:59:00Z", "INVALID_TRADE_WINDOW"),
    ("status", "OPEN", "TRADE_NOT_CLOSED"),
])
def test_invalid_trade_fails_before_candle_read(recorded_trade, monkeypatch, key, value, reason):
    recorded_trade[key] = value
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid trade must not query candles")
    monkeypatch.setattr(candle_evidence.duckdb_driver, "get_candles_range", unexpected)
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade)
    assert error.value.reason == reason


@pytest.mark.parametrize("timestamp", [None, True, float("nan"), float("inf"), -1, "invalid"])
def test_bad_timestamp_rejected(timestamp):
    with pytest.raises(EvidenceError):
        utc_timestamp(timestamp)


def test_maximum_duration_allows_two_partial_boundary_minutes(recorded_trade, recorded_candles):
    start = datetime.fromisoformat(recorded_trade["entry_time"])
    end = start + timedelta(minutes=20_000)
    recorded_trade["exit_time"] = end.isoformat()
    normalized = normalize_trade(recorded_trade)
    first, last = trade_bar_bounds(normalized)
    assert (last - first) // 60 == 20_001
    rows = [{**recorded_candles[1], "time": t} for t in range(first, last, 60)]
    assert len(load_candle_evidence(recorded_trade, rows).trade_candles) == 20_001
    recorded_trade["exit_time"] = (end + timedelta(seconds=1)).isoformat()
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade, [])
    assert error.value.reason == "WINDOW_TOO_LARGE"


def test_truncated_read_rejected_even_if_duplicates_would_collapse(recorded_trade, recorded_candles, monkeypatch):
    monkeypatch.setattr(candle_evidence.duckdb_driver, "get_candles_range", lambda *a, **kw: [recorded_candles[1]] * 20602)
    with pytest.raises(EvidenceError) as error:
        load_candle_evidence(recorded_trade)
    assert error.value.reason == "CANDLE_ROW_LIMIT"


def test_actual_sqlite_candidate_limit_uses_utc_not_lexical_order(tmp_path, recorded_trade):
    driver = SQLiteDriver(str(tmp_path / "journal.sqlite"))
    driver.insert_trade({**recorded_trade, "id": "OFFSET-OLDER", "entry_time": "2026-09-01T10:00:00+03:00"})
    driver.insert_trade({**recorded_trade, "id": "UTC-NEWER", "entry_time": "2026-09-01T08:30:00Z"})
    # Put 999 newer trades ahead of those two: UTC-NEWER must take slot 1000.
    with driver.get_connection() as conn:
        conn.executemany("INSERT INTO trades (id,symbol,side,entry_price,qty,entry_time,status,created_at,updated_at) VALUES (?,'BTCUSDT','BUY',100,1,'2026-09-02T00:00:00Z','CLOSED','2026-09-02','2026-09-02')", [(f"NEW-{i:04d}",) for i in range(999)])
    result = driver.list_trades(limit=1000, status="CLOSED", order_by_utc=True)
    assert result[-1]["id"] == "UTC-NEWER"
    assert "OFFSET-OLDER" not in [t["id"] for t in result]
    assert driver.list_trades(limit=1000, status="CLOSED")[-1]["id"] == "OFFSET-OLDER"  # legacy caller unchanged
