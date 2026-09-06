"""P1-WP09 market-candle provenance and legacy migration contracts."""

from datetime import datetime, timezone

import duckdb
import pytest

from app.db.duckdb_driver import DuckDBDriver
from app.quant import candle_evidence
from app.quant.candle_evidence import load_candle_evidence


def _candle_rows(*, verified: bool = False):
    return [
        {
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "timestamp": f"2026-09-01 10:0{minute}:00",
            "open": 100.0 + minute,
            "high": 101.0 + minute,
            "low": 99.0 + minute,
            "close": 100.5 + minute,
            "volume": 10.0 + minute,
            "trades_count": 4,
            "venue": "BINANCE",
            "feed": "BINANCE_WS_KLINE",
            "source_event_id": f"BTCUSDT:1m:{minute}",
            "source_sequence": 1000 + minute,
            "ingested_at": f"2026-09-01 10:10:0{minute}Z",
            "source_verified": verified,
        }
        for minute in range(3)
    ]


def test_provenance_round_trip_is_exposed_to_replay_context(tmp_path, monkeypatch, recorded_trade):
    driver = DuckDBDriver(str(tmp_path / "provenance.duckdb"))
    assert driver.insert_candles(_candle_rows(verified=True)) == 3

    rows = driver.get_candles_range(
        "BTCUSDT",
        datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 1, 10, 3, tzinfo=timezone.utc),
    )
    assert rows[0]["venue"] == "BINANCE"
    assert rows[0]["feed"] == "BINANCE_WS_KLINE"
    assert rows[0]["source_sequence"] == 1000
    assert rows[0]["source_verified"] is True
    assert rows[0]["ingested_at"] is not None

    monkeypatch.setattr(candle_evidence, "duckdb_driver", driver)
    evidence = load_candle_evidence(recorded_trade)
    context = evidence.market_context
    assert context["venue"] == "BINANCE"
    assert context["feed"] == "BINANCE_WS_KLINE"
    assert context["source_verified"] is True
    assert context["provenance_complete"] is True
    assert context["sequence_coverage"] == "COMPLETE"
    assert context["ingested_at_start"].endswith("+00:00")


def test_legacy_nine_column_store_migrates_to_explicit_unverified_provenance(tmp_path):
    path = tmp_path / "legacy.duckdb"
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE market_candles (
                symbol VARCHAR,
                timeframe VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                trades_count BIGINT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO market_candles VALUES
            ('BTCUSDT', '1m', '2026-09-01 10:00:00', 100, 101, 99, 100.5, 10, 4)
            """
        )
    finally:
        conn.close()

    driver = DuckDBDriver(str(path))
    row = driver.get_candles_range(
        "BTCUSDT",
        datetime(2026, 9, 1, 10, 0),
        datetime(2026, 9, 1, 10, 1),
    )[0]
    assert row["venue"] == "UNVERIFIED"
    assert row["feed"] == "UNVERIFIED"
    assert row["source_sequence"] is None
    assert row["source_verified"] is False
    assert row["ingested_at"] is not None


def test_verified_candle_requires_identity_and_timestamp(tmp_path):
    driver = DuckDBDriver(str(tmp_path / "invalid.duckdb"))
    base = _candle_rows()[0]
    base.pop("venue")
    with pytest.raises(ValueError, match="explicit venue and feed"):
        driver.insert_candles([{**base, "source_verified": True}])

    missing_timestamp = {**_candle_rows()[0]}
    missing_timestamp.pop("timestamp")
    with pytest.raises(ValueError, match="source candle timestamp"):
        driver.insert_candles([missing_timestamp])
