try:
    import duckdb
except ImportError:
    duckdb = None

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

from app.core.paths import get_duckdb_path
from app.db.market_candle_schema import ensure_market_candle_schema

logger = logging.getLogger(__name__)

class DuckDBDriver:
    """OLAP DuckDB Analytical Engine for Columnar Storage & Aggregations."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_duckdb_path()
        self.is_available = duckdb is not None
        if self.is_available:
            self._init_db()
        else:
            logger.info("[DUCKDB] Running in Lite Core mode (DuckDB not loaded)")

    def get_connection(self):
        if not self.is_available or duckdb is None:
            raise RuntimeError("DuckDB is not installed or loaded in current environment.")
        return duckdb.connect(self.db_path)

    def _init_db(self):
        conn = self.get_connection()
        try:
            ensure_market_candle_schema(conn)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS olap_trades (
                    id VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    side VARCHAR,
                    entry_price DOUBLE,
                    exit_price DOUBLE,
                    qty DOUBLE,
                    stop_loss DOUBLE,
                    take_profit DOUBLE,
                    entry_time TIMESTAMP,
                    exit_time TIMESTAMP,
                    status VARCHAR,
                    pnl DOUBLE,
                    r_multiple DOUBLE,
                    commission DOUBLE,
                    duration_seconds DOUBLE,
                    is_winner BOOLEAN,
                    record_mode VARCHAR
                );

                ALTER TABLE olap_trades ADD COLUMN IF NOT EXISTS record_mode VARCHAR;

                CREATE INDEX IF NOT EXISTS idx_candles_lookup ON market_candles(symbol, timeframe, timestamp);
            """)
            logger.info("DuckDB OLAP schema initialized.")
        finally:
            conn.close()

    @staticmethod
    def _utc_naive_timestamp(value: Any) -> datetime:
        """Normalize an incoming timestamp to a naive UTC datetime."""
        if value is None:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        parsed = pd.to_datetime(value, utc=True, errors="raise")
        if hasattr(parsed, "to_pydatetime"):
            parsed = parsed.to_pydatetime()
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalize_identifier(value: Any, default: str) -> str:
        if value is None or not str(value).strip():
            return default
        return str(value).strip().upper()

    @staticmethod
    def _normalize_source_sequence(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("source_sequence must be a non-negative integer")
        try:
            sequence = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("source_sequence must be a non-negative integer") from exc
        if sequence < 0:
            raise ValueError("source_sequence must be a non-negative integer")
        return sequence

    @staticmethod
    def _normalize_verified(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if value in (0, 1):
            return bool(value)
        raise ValueError("source_verified must be a boolean")

    @classmethod
    def _normalize_candle(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Each candle must be a mapping")

        venue = cls._normalize_identifier(raw.get("venue"), "UNVERIFIED")
        feed = cls._normalize_identifier(raw.get("feed") or raw.get("source"), "UNVERIFIED")
        source_verified = cls._normalize_verified(raw.get("source_verified"))
        if source_verified and (venue == "UNVERIFIED" or feed == "UNVERIFIED"):
            raise ValueError("Verified candles require explicit venue and feed provenance")

        timestamp = raw.get("timestamp")
        if timestamp is None and raw.get("time") is not None:
            timestamp = datetime.fromtimestamp(float(raw["time"]), timezone.utc)
        if timestamp is None:
            raise ValueError("A source candle timestamp is required")

        event_id = raw.get("source_event_id")
        event_id = str(event_id).strip() if event_id is not None and str(event_id).strip() else None
        trades_count = raw.get("trades_count")
        if trades_count is not None:
            try:
                trades_count = int(trades_count)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("trades_count must be an integer when supplied") from exc

        return {
            "symbol": str(raw.get("symbol") or "").strip().upper(),
            "timeframe": str(raw.get("timeframe") or "1m").strip(),
            "timestamp": cls._utc_naive_timestamp(timestamp),
            "open": raw.get("open"),
            "high": raw.get("high"),
            "low": raw.get("low"),
            "close": raw.get("close"),
            "volume": raw.get("volume"),
            "trades_count": trades_count,
            "venue": venue,
            "feed": feed,
            "source_event_id": event_id,
            "source_sequence": cls._normalize_source_sequence(raw.get("source_sequence")),
            "ingested_at": cls._utc_naive_timestamp(raw.get("ingested_at")),
            "source_verified": source_verified,
        }

    def insert_candles(self, candles: List[Dict[str, Any]]) -> int:
        if not candles:
            return 0
        records = [self._normalize_candle(candle) for candle in candles]
        df = pd.DataFrame(records)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_localize(None)
        df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True).dt.tz_localize(None)

        conn = self.get_connection()
        try:
            conn.register("incoming_candles", df)
            conn.execute("""
                INSERT INTO market_candles (
                    symbol, timeframe, timestamp,
                    open, high, low, close, volume, trades_count,
                    venue, feed, source_event_id, source_sequence,
                    ingested_at, source_verified
                )
                SELECT 
                    symbol, timeframe, timestamp,
                    CAST(open AS DOUBLE), CAST(high AS DOUBLE),
                    CAST(low AS DOUBLE), CAST(close AS DOUBLE),
                    CAST(volume AS DOUBLE), CAST(trades_count AS BIGINT),
                    venue, feed, source_event_id, CAST(source_sequence AS BIGINT),
                    ingested_at, CAST(source_verified AS BOOLEAN)
                FROM incoming_candles
            """)
            return len(df)
        finally:
            conn.close()

    def insert_market_candle(
        self,
        *,
        symbol: str,
        timeframe: str,
        timestamp: Any,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        volume: float,
        trades_count: Optional[int] = None,
        venue: str = "UNVERIFIED",
        feed: str = "UNVERIFIED",
        source_event_id: Optional[str] = None,
        source_sequence: Optional[int] = None,
        ingested_at: Any = None,
        source_verified: bool = False,
    ) -> int:
        """Compatibility entry point for adapter-managed candle ingestion."""
        return self.insert_candles([{
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": timestamp,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": volume,
            "trades_count": trades_count,
            "venue": venue,
            "feed": feed,
            "source_event_id": source_event_id,
            "source_sequence": source_sequence,
            "ingested_at": ingested_at,
            "source_verified": source_verified,
        }])

    def get_candles(self, symbol: str, timeframe: str = "1m", limit: int = 500) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    symbol, timeframe, 
                    epoch(timestamp) as time,
                    open, high, low, close, volume, trades_count,
                    venue, feed, source_event_id, source_sequence,
                    ingested_at, source_verified
                FROM market_candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            result = conn.execute(query, [symbol.upper(), timeframe, limit]).fetchall()
            cols = [
                "symbol", "timeframe", "time", "open", "high", "low", "close", "volume",
                "trades_count", "venue", "feed", "source_event_id", "source_sequence",
                "ingested_at", "source_verified",
            ]
            candles = [dict(zip(cols, row)) for row in reversed(result)]
            return candles
        finally:
            conn.close()

    def get_candles_range(
        self, symbol: str, start: datetime, end: datetime,
        timeframe: str = "1m", limit: int = 20602,
    ) -> List[Dict[str, Any]]:
        """Read a bounded historical [start, end) window, never the latest N bars.

        The existing TIMESTAMP column is interpreted as UTC. Naive legacy inputs
        use that same convention; aware inputs are converted before comparison.
        Duplicate rows are intentionally retained for evidence validation upstream.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20602:
            raise ValueError("Candle query limit must be an integer between 1 and 20602")

        def utc_naive(value: datetime) -> datetime:
            if not isinstance(value, datetime):
                raise ValueError("Candle range requires datetime boundaries")
            if value.tzinfo is None:
                return value
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        start_utc, end_utc = utc_naive(start), utc_naive(end)
        if end_utc <= start_utc:
            raise ValueError("Candle range end must be after start")
        conn = self.get_connection()
        try:
            rows = conn.execute("""
                SELECT symbol, timeframe, epoch(timestamp) AS time,
                       open, high, low, close, volume, trades_count,
                       venue, feed, source_event_id, source_sequence,
                       ingested_at, source_verified
                FROM market_candles
                WHERE symbol = ? AND timeframe = ? AND timestamp >= ? AND timestamp < ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, [symbol.upper(), timeframe, start_utc, end_utc, limit]).fetchall()
            columns = [
                "symbol", "timeframe", "time", "open", "high", "low", "close", "volume",
                "trades_count", "venue", "feed", "source_event_id", "source_sequence",
                "ingested_at", "source_verified",
            ]
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    def sync_trade(self, trade: Dict[str, Any]) -> None:
        conn = self.get_connection()
        try:
            entry_t = trade.get("entry_time")
            exit_t = trade.get("exit_time")
            duration = None
            if entry_t and exit_t:
                try:
                    dt_in = pd.to_datetime(entry_t)
                    dt_out = pd.to_datetime(exit_t)
                    duration = float((dt_out - dt_in).total_seconds())
                except Exception:
                    pass

            # An unknown PnL stays NULL: missing money is never stored as a
            # realized zero or classified as a breakeven result.
            pnl_value = trade.get("pnl")
            pnl = float(pnl_value) if pnl_value is not None else None
            is_win = (pnl > 0) if pnl is not None else None

            trade_record = {
                "id": str(trade["id"]),
                "symbol": str(trade["symbol"]).upper(),
                "side": str(trade["side"]).upper(),
                "entry_price": float(trade["entry_price"]),
                "exit_price": float(trade["exit_price"]) if trade.get("exit_price") is not None else None,
                "qty": float(trade["qty"]),
                "stop_loss": float(trade["stop_loss"]) if trade.get("stop_loss") is not None else None,
                "take_profit": float(trade["take_profit"]) if trade.get("take_profit") is not None else None,
                "entry_time": pd.to_datetime(trade["entry_time"]) if trade.get("entry_time") else None,
                "exit_time": pd.to_datetime(trade["exit_time"]) if trade.get("exit_time") else None,
                "status": str(trade.get("status", "OPEN")).upper(),
                "pnl": pnl,
                "r_multiple": float(trade["r_multiple"]) if trade.get("r_multiple") is not None else None,
                "commission": float(trade.get("commission", 0.0) or 0.0),
                "duration_seconds": duration,
                "is_winner": is_win,
                "record_mode": str(trade.get("record_mode") or "").upper() or None,
            }

            df = pd.DataFrame([trade_record])
            conn.register("temp_trade", df)
            conn.execute("""
                DELETE FROM olap_trades WHERE id = ?
            """, [trade_record["id"]])
            conn.execute("""
                INSERT INTO olap_trades SELECT * FROM temp_trade
            """)
        finally:
            conn.close()

    def sync_all_trades(self, trades: List[Dict[str, Any]]) -> int:
        if not trades:
            return 0
        for t in trades:
            self.sync_trade(t)
        return len(trades)

    def get_aggregated_stats(self) -> Dict[str, Any]:
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(pnl) as known_pnl_trades,
                    COUNT(*) - COUNT(pnl) as unknown_pnl_trades,
                    COALESCE(SUM(CASE WHEN pnl IS NOT NULL AND pnl > 0 THEN 1 ELSE 0 END), 0) as win_count,
                    COALESCE(SUM(CASE WHEN pnl IS NOT NULL AND pnl < 0 THEN 1 ELSE 0 END), 0) as loss_count,
                    COALESCE(SUM(CASE WHEN pnl IS NOT NULL AND pnl = 0 THEN 1 ELSE 0 END), 0) as breakeven_count,
                    COALESCE(SUM(pnl), 0.0) as total_pnl,
                    COALESCE(AVG(pnl), 0.0) as avg_pnl,
                    COALESCE(AVG(CASE WHEN pnl > 0 THEN pnl END), 0.0) as avg_win,
                    COALESCE(AVG(CASE WHEN pnl < 0 THEN pnl END), 0.0) as avg_loss,
                    COALESCE(MAX(pnl), 0.0) as max_win,
                    COALESCE(MIN(pnl), 0.0) as max_loss,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0.0) as gross_profit,
                    COALESCE(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0.0) as gross_loss,
                    COALESCE(AVG(r_multiple), 0.0) as avg_r_multiple,
                    COALESCE(AVG(duration_seconds), 0.0) as avg_duration_seconds,
                    COALESCE(SUM(commission), 0.0) as total_commission
                FROM olap_trades
                WHERE status = 'CLOSED' AND COALESCE(record_mode, '') <> 'SIMULATION'
            """
            row = conn.execute(query).fetchone()
            if not row or row[0] == 0:
                return {
                    "total_trades": 0,
                    "known_pnl_trades": 0,
                    "unknown_pnl_trades": 0,
                    "win_count": 0,
                    "loss_count": 0,
                    "breakeven_count": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "avg_pnl": 0.0,
                    "avg_win": 0.0,
                    "avg_loss": 0.0,
                    "max_win": 0.0,
                    "max_loss": 0.0,
                    "profit_factor": 0.0,
                    "avg_r_multiple": 0.0,
                    "avg_duration_seconds": 0.0,
                    "total_commission": 0.0,
                    "simulation_trades": 0,
                }

            simulation_row = conn.execute(
                "SELECT COUNT(*) FROM olap_trades WHERE status = 'CLOSED' AND record_mode = 'SIMULATION'"
            ).fetchone()
            simulation_trades = int(simulation_row[0]) if simulation_row else 0

            total_trades = row[0]
            known_pnl_trades = row[1]
            unknown_pnl_trades = row[2]
            win_count = row[3]
            loss_count = row[4]
            breakeven_count = row[5]
            # The win rate denominator contains known results only; unknown
            # outcomes are surfaced through ``unknown_pnl_trades`` instead of
            # silently counting as losses or breakevens.
            win_rate = (win_count / known_pnl_trades) * 100 if known_pnl_trades > 0 else 0.0
            gross_profit = row[12]
            gross_loss = row[13]
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

            return {
                "simulation_trades": simulation_trades,
                "total_trades": total_trades,
                "known_pnl_trades": known_pnl_trades,
                "unknown_pnl_trades": unknown_pnl_trades,
                "win_count": win_count,
                "loss_count": loss_count,
                "breakeven_count": breakeven_count,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(row[6], 2),
                "avg_pnl": round(row[7], 2),
                "avg_win": round(row[8], 2),
                "avg_loss": round(row[9], 2),
                "max_win": round(row[10], 2),
                "max_loss": round(row[11], 2),
                "profit_factor": round(profit_factor, 2),
                "avg_r_multiple": round(row[14], 2),
                "avg_duration_seconds": round(row[15], 1),
                "total_commission": round(row[16], 2)
            }
        finally:
            conn.close()

    def get_symbol_breakdown(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    symbol,
                    COUNT(*) as count,
                    COUNT(pnl) as known_pnl_count,
                    COUNT(*) - COUNT(pnl) as unknown_pnl_count,
                    COALESCE(SUM(pnl), 0.0) as total_pnl,
                    COALESCE(AVG(pnl), 0.0) as avg_pnl,
                    COALESCE(AVG(CASE WHEN pnl IS NULL THEN NULL WHEN pnl > 0 THEN 1.0 ELSE 0.0 END), 0.0) * 100 as win_rate
                FROM olap_trades
                WHERE status = 'CLOSED' AND COALESCE(record_mode, '') <> 'SIMULATION'
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """
            result = conn.execute(query).fetchall()
            cols = ["symbol", "count", "known_pnl_count", "unknown_pnl_count", "total_pnl", "avg_pnl", "win_rate"]
            return [
                dict(zip(cols, [r[0], r[1], r[2], r[3], round(r[4], 2), round(r[5], 2), round(r[6], 2)]))
                for r in result
            ]
        finally:
            conn.close()

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    id,
                    symbol,
                    exit_time,
                    pnl,
                    SUM(pnl) OVER (ORDER BY exit_time ASC, id ASC) as cumulative_pnl,
                    r_multiple
                FROM olap_trades
                WHERE status = 'CLOSED' AND exit_time IS NOT NULL AND pnl IS NOT NULL
                  AND COALESCE(record_mode, '') <> 'SIMULATION'
                ORDER BY exit_time ASC
            """
            result = conn.execute(query).fetchall()
            cols = ["id", "symbol", "exit_time", "pnl", "cumulative_pnl", "r_multiple"]
            return [dict(zip(cols, [r[0], r[1], str(r[2]), round(r[3], 2), round(r[4], 2), r[5]])) for r in result]
        finally:
            conn.close()

duckdb_driver = DuckDBDriver()
