try:
    import duckdb
except ImportError:
    duckdb = None

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import pandas as pd
except ImportError:
    pd = None

from app.core.paths import get_duckdb_path

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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_candles (
                    symbol VARCHAR,
                    timeframe VARCHAR,
                    timestamp TIMESTAMP,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    trades_count BIGINT
                );

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
                    is_winner BOOLEAN
                );

                CREATE INDEX IF NOT EXISTS idx_candles_lookup ON market_candles(symbol, timeframe, timestamp);
            """)
            logger.info("DuckDB OLAP schema initialized.")
        finally:
            conn.close()

    def insert_candles(self, candles: List[Dict[str, Any]]) -> int:
        if not candles:
            return 0
        df = pd.DataFrame(candles)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        conn = self.get_connection()
        try:
            conn.register("incoming_candles", df)
            conn.execute("""
                INSERT INTO market_candles
                SELECT 
                    symbol, timeframe, timestamp,
                    CAST(open AS DOUBLE), CAST(high AS DOUBLE),
                    CAST(low AS DOUBLE), CAST(close AS DOUBLE),
                    CAST(volume AS DOUBLE), CAST(trades_count AS BIGINT)
                FROM incoming_candles
            """)
            return len(df)
        finally:
            conn.close()

    def get_candles(self, symbol: str, timeframe: str = "1m", limit: int = 500) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            query = """
                SELECT 
                    symbol, timeframe, 
                    epoch(timestamp) as time,
                    open, high, low, close, volume, trades_count
                FROM market_candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            result = conn.execute(query, [symbol.upper(), timeframe, limit]).fetchall()
            cols = ["symbol", "timeframe", "time", "open", "high", "low", "close", "volume", "trades_count"]
            candles = [dict(zip(cols, row)) for row in reversed(result)]
            return candles
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

            pnl = float(trade.get("pnl", 0.0) or 0.0)
            is_win = pnl > 0

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
                "is_winner": is_win
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
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as win_count,
                    COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as loss_count,
                    COALESCE(SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END), 0) as breakeven_count,
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
                WHERE status = 'CLOSED'
            """
            row = conn.execute(query).fetchone()
            if not row or row[0] == 0:
                return {
                    "total_trades": 0,
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
                    "total_commission": 0.0
                }

            total_trades = row[0]
            win_count = row[1]
            loss_count = row[2]
            breakeven_count = row[3]
            win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0
            gross_profit = row[10]
            gross_loss = row[11]
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

            return {
                "total_trades": total_trades,
                "win_count": win_count,
                "loss_count": loss_count,
                "breakeven_count": breakeven_count,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(row[4], 2),
                "avg_pnl": round(row[5], 2),
                "avg_win": round(row[6], 2),
                "avg_loss": round(row[7], 2),
                "max_win": round(row[8], 2),
                "max_loss": round(row[9], 2),
                "profit_factor": round(profit_factor, 2),
                "avg_r_multiple": round(row[12], 2),
                "avg_duration_seconds": round(row[13], 1),
                "total_commission": round(row[14], 2)
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
                    COALESCE(SUM(pnl), 0.0) as total_pnl,
                    COALESCE(AVG(pnl), 0.0) as avg_pnl,
                    COALESCE(AVG(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END), 0.0) * 100 as win_rate
                FROM olap_trades
                WHERE status = 'CLOSED'
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """
            result = conn.execute(query).fetchall()
            cols = ["symbol", "count", "total_pnl", "avg_pnl", "win_rate"]
            return [dict(zip(cols, [r[0], r[1], round(r[2], 2), round(r[3], 2), round(r[4], 2)])) for r in result]
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
                WHERE status = 'CLOSED' AND exit_time IS NOT NULL
                ORDER BY exit_time ASC
            """
            result = conn.execute(query).fetchall()
            cols = ["id", "symbol", "exit_time", "pnl", "cumulative_pnl", "r_multiple"]
            return [dict(zip(cols, [r[0], r[1], str(r[2]), round(r[3], 2), round(r[4], 2), r[5]])) for r in result]
        finally:
            conn.close()

duckdb_driver = DuckDBDriver()
