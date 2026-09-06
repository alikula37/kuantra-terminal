"""Canonical DuckDB schema for persisted market-candle provenance.

The candle table is a historical bar store, not a tick-level market-data
ledger.  Provenance columns make that boundary explicit and let downstream
replay code distinguish an identified-but-unverified feed from a legacy row
whose source is unknown.
"""

from typing import Any


MARKET_CANDLE_PROVENANCE_COLUMNS = (
    "venue",
    "feed",
    "source_event_id",
    "source_sequence",
    "ingested_at",
    "source_verified",
)


def ensure_market_candle_schema(conn: Any) -> None:
    """Create or migrate ``market_candles`` in-place.

    Earlier Kuantra databases only had the OHLCV columns.  DuckDB supports
    additive ``ALTER TABLE`` migrations, so existing files are upgraded without
    rebuilding or rewriting their historical bars.  Legacy rows are explicitly
    marked as unverified rather than inheriting a misleading venue/feed.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market_candles (
            symbol VARCHAR,
            timeframe VARCHAR,
            timestamp TIMESTAMP,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            trades_count BIGINT,
            venue VARCHAR DEFAULT 'UNVERIFIED',
            feed VARCHAR DEFAULT 'UNVERIFIED',
            source_event_id VARCHAR,
            source_sequence BIGINT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_verified BOOLEAN DEFAULT FALSE
        )
        """
    )

    # Additive, idempotent migration for v1.4.0-era nine-column databases.
    # Columns are nullable during migration so a partially old file can still
    # be opened; the backfill below gives every pre-existing row an explicit
    # conservative value.
    for statement in (
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS venue VARCHAR",
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS feed VARCHAR",
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS source_event_id VARCHAR",
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS source_sequence BIGINT",
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP",
        "ALTER TABLE market_candles ADD COLUMN IF NOT EXISTS source_verified BOOLEAN",
    ):
        conn.execute(statement)

    conn.execute(
        """
        UPDATE market_candles
        SET venue = 'UNVERIFIED'
        WHERE venue IS NULL
        """
    )
    conn.execute(
        """
        UPDATE market_candles
        SET feed = 'UNVERIFIED'
        WHERE feed IS NULL
        """
    )
    conn.execute(
        """
        UPDATE market_candles
        SET ingested_at = CURRENT_TIMESTAMP
        WHERE ingested_at IS NULL
        """
    )
    conn.execute(
        """
        UPDATE market_candles
        SET source_verified = FALSE
        WHERE source_verified IS NULL
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_candles_provenance
        ON market_candles(venue, feed, timestamp)
        """
    )
