"""
SQLite Market Candle Caching Layer for Kuantra Terminal.
Provides zero-overhead local caching, deduplication, and cache-first query resolution
for crypto and macro OHLCV candlestick data.
"""

import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional
from app.core.paths import get_sqlite_path
from app.db.sqlite_driver import sqlite_driver
from app.services.market_data.public_fetcher import (
    public_market_fetcher,
    normalize_crypto_symbol,
    normalize_interval,
    MACRO_SYMBOL_MAP
)

logger = logging.getLogger("candles_repo")


# Expected bar duration in milliseconds; used only to decide whether the
# cached window is still current enough to skip a provider request.
TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_629_800_000,
}


class CandlesRepository:
    """
    High-performance SQLite caching repository for financial market candles.
    Uses WAL-mode transactions and composite index deduplication.
    """

    @staticmethod
    def _timeframe_ms(timeframe: str) -> int:
        return TIMEFRAME_MS.get(normalize_interval(timeframe), 3_600_000)

    @classmethod
    def _is_fresh(cls, timeframe: str, newest_ts_ms: int, now_ms: Optional[int] = None) -> bool:
        """A cached window is fresh until two bar durations have passed."""

        now = now_ms if now_ms is not None else int(time.time() * 1000)
        age = now - int(newest_ts_ms)
        return 0 <= age < 2 * cls._timeframe_ms(timeframe)

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_sqlite_path()
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        if not self.db_path or self.db_path == sqlite_driver.db_path:
            return sqlite_driver.get_connection()
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _ensure_schema(self):
        """Ensures market_candles_cache table and composite indices are present."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS market_candles_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_candles_sym_tf_time 
                ON market_candles_cache(symbol, timeframe, timestamp);

                CREATE INDEX IF NOT EXISTS idx_candles_lookup 
                ON market_candles_cache(symbol, timeframe, timestamp ASC);
            """)
            conn.commit()

    @staticmethod
    def _normalize_requested_symbol(symbol: str) -> str:
        """Preserve generic provider tickers instead of inventing a USDT pair."""
        raw = str(symbol or "").strip().upper()
        if raw in MACRO_SYMBOL_MAP:
            return raw
        crypto_pair = public_market_fetcher._crypto_pair_symbol(raw)
        return normalize_crypto_symbol(raw) if crypto_pair is not None else raw

    def save_candles_batch(
        self,
        candles: List[Dict[str, Any]],
        symbol: str,
        timeframe: str = "1h"
    ) -> int:
        """
        Saves a batch of OHLCV candles to SQLite cache with INSERT OR IGNORE deduplication.
        Returns the number of records actually inserted.
        """
        if not candles:
            return 0

        norm_sym = self._normalize_requested_symbol(symbol)
        norm_tf = normalize_interval(timeframe)

        records = []
        for c in candles:
            try:
                records.append((
                    norm_sym,
                    norm_tf,
                    int(c["timestamp"]),
                    float(c["open"]),
                    float(c["high"]),
                    float(c["low"]),
                    float(c["close"]),
                    float(c["volume"])
                ))
            except (KeyError, ValueError, TypeError):
                continue

        if not records:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            initial_changes = conn.total_changes
            cursor.executemany("""
                INSERT OR IGNORE INTO market_candles_cache (
                    symbol, timeframe, timestamp, open, high, low, close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()
            inserted = conn.total_changes - initial_changes
            logger.info(f"[CANDLE-CACHE] Stored {inserted} new candles for {norm_sym} ({norm_tf}). (Total received: {len(records)})")
            return inserted

    def get_cached_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves cached OHLCV candles within specified time boundaries or recent limit.
        Always returns in ascending chronological order.
        """
        norm_sym = self._normalize_requested_symbol(symbol)
        norm_tf = normalize_interval(timeframe)

        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_candles_cache
            WHERE symbol = ? AND timeframe = ?
        """
        params: List[Any] = [norm_sym, norm_tf]

        if start_ts is not None:
            query += " AND timestamp >= ?"
            params.append(int(start_ts))
        if end_ts is not None:
            query += " AND timestamp <= ?"
            params.append(int(end_ts))

        if limit is not None and start_ts is None and end_ts is None:
            # When requesting recent limit, fetch the latest N candles and sort ascending
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(int(limit))
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
            candles = [
                {
                    "timestamp": int(r["timestamp"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"])
                }
                for r in rows
            ]
            candles.reverse()  # Reverse from DESC to ASC
            return candles
        else:
            query += " ORDER BY timestamp ASC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(int(limit))

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()

            return [
                {
                    "timestamp": int(r["timestamp"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"])
                }
                for r in rows
            ]

    async def get_or_fetch_candles(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Cache-first candle retrieval pipeline.
        1. Checks local SQLite cache.
        2. If sufficient cached data exists and force_refresh is False, returns immediately.
        3. If cache miss, calls PublicMarketDataFetcher and writes to SQLite cache.
        4. Returns unified ascending candle array.
        """
        norm_sym = self._normalize_requested_symbol(symbol)
        norm_tf = normalize_interval(timeframe)
        clamped_limit = max(1, min(1000, limit))

        if not force_refresh:
            cached = self.get_cached_candles(
                symbol=norm_sym,
                timeframe=norm_tf,
                start_ts=start_ts,
                end_ts=end_ts,
                limit=clamped_limit
            )
            enough = len(cached) >= clamped_limit
            history_query = start_ts is not None or end_ts is not None
            fresh = bool(cached) and not history_query and self._is_fresh(norm_tf, cached[-1]["timestamp"])
            # A full request window is used only while it is still current;
            # otherwise the provider is asked for newer bars instead of serving
            # a frozen chart.  History queries keep the exact-range shortcut.
            if (enough and (fresh or (start_ts is not None and end_ts is not None))) or (
                history_query and start_ts is not None and end_ts is not None and cached
            ):
                logger.info(f"[CANDLE-CACHE] Cache HIT for {norm_sym} ({norm_tf}): {len(cached)} candles returned from SQLite.")
                return cached

        logger.info(f"[CANDLE-CACHE] Cache MISS/REFRESH for {norm_sym} ({norm_tf}). Initiating zero-auth public fetch...")
        # Exact generic provider tickers use the Yahoo/Stooq macro-compatible
        # path; only explicit crypto pairs go through exchange klines.
        if norm_sym in MACRO_SYMBOL_MAP or public_market_fetcher._crypto_pair_symbol(symbol) is None:
            fetched = await public_market_fetcher.fetch_macro_candles(
                symbol=norm_sym,
                interval=norm_tf,
                period=None,
                start_time=start_ts,
                end_time=end_ts,
            )
        else:
            fetched = await public_market_fetcher.fetch_crypto_candles(
                symbol=norm_sym,
                interval=norm_tf,
                limit=clamped_limit,
                start_time=start_ts,
                end_time=end_ts
            )

        if fetched:
            self.save_candles_batch(fetched, symbol=norm_sym, timeframe=norm_tf)

        # Retrieve and return from cache to ensure consistent structure & sorting
        return self.get_cached_candles(
            symbol=norm_sym,
            timeframe=norm_tf,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=clamped_limit
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Returns diagnostic statistics about cached candle data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM market_candles_cache;")
            total_count = cursor.fetchone()["total"]

            cursor.execute("SELECT DISTINCT symbol FROM market_candles_cache ORDER BY symbol;")
            symbols = [r["symbol"] for r in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT timeframe FROM market_candles_cache ORDER BY timeframe;")
            timeframes = [r["timeframe"] for r in cursor.fetchall()]

            cursor.execute("SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM market_candles_cache;")
            row = cursor.fetchone()
            oldest_ts = row["oldest"]
            newest_ts = row["newest"]

        return {
            "total_records": total_count,
            "symbols_count": len(symbols),
            "symbols": symbols,
            "timeframes": timeframes,
            "oldest_timestamp": oldest_ts,
            "newest_timestamp": newest_ts
        }

    def clear_cache(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> int:
        """Purges cached candle records. Returns number of deleted rows."""
        query = "DELETE FROM market_candles_cache WHERE 1=1"
        params: List[Any] = []
        if symbol:
            norm_sym = self._normalize_requested_symbol(symbol)
            query += " AND symbol = ?"
            params.append(norm_sym)
        if timeframe:
            norm_tf = normalize_interval(timeframe)
            query += " AND timeframe = ?"
            params.append(norm_tf)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            deleted = cursor.rowcount
            logger.info(f"[CANDLE-CACHE] Cleared {deleted} cache records.")
            return deleted


# Global Singleton Instance
candles_repo = CandlesRepository()
