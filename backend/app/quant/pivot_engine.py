"""
Dynamic Pivot Grid & Analytical Grouping Engine for Kuantra Terminal.
Executes multi-dimensional slicing and dicing of trading performance in DuckDB.
"""

from typing import List, Dict, Any, Optional
import duckdb
import numpy as np
import pandas as pd
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.quant.quant_engine import quant_engine

class PivotEngine:
    """Multi-dimensional pivot matrix calculator powered by vectorized DuckDB queries."""

    SUPPORTED_DIMENSIONS = {
        "symbol", "side", "day_of_week", "session", "hold_time_range", "status"
    }

    @classmethod
    def compute_pivot_grid(
        cls,
        group_by: Optional[List[str]] = None,
        symbol_filter: Optional[str] = None,
        side_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Group trades across arbitrary dimensions and compute full quant metrics per bucket."""
        dimensions = [d for d in (group_by or ["symbol"]) if d in cls.SUPPORTED_DIMENSIONS]
        if not dimensions:
            dimensions = ["symbol"]

        # Fetch closed trades from SQLite
        all_trades = [
            t for t in sqlite_driver.list_trades(limit=10000, symbol=symbol_filter, status="CLOSED")
            if str(t.get("record_mode") or "").upper() != "SIMULATION"
        ]
        if side_filter and side_filter != "ALL":
            all_trades = [t for t in all_trades if str(t.get("side", "")).upper() == side_filter.upper()]

        if not all_trades:
            # No closed trades means no analytics.  Invented "seed" rows were a
            # silent fabrication and are never returned; the basis is explicit.
            return {"dimensions": dimensions, "total_buckets": 0, "rows": [], "basis": "NO_CLOSED_TRADES"}

        # Enrich trade records with analytical dimensions
        enriched = []
        for t in all_trades:
            entry_t_str = t.get("entry_time")
            exit_t_str = t.get("exit_time")
            side = str(t.get("side", "BUY")).upper()
            side_clean = "LONG" if side in ("BUY", "LONG") else "SHORT"
            
            day_name = "Unknown"
            session_name = "Off-Hours"
            duration_label = "Day Trade (15m-4h)"
            duration_sec = 0.0

            if entry_t_str:
                try:
                    dt = pd.to_datetime(entry_t_str)
                    day_name = dt.strftime("%A")
                    hour = dt.hour
                    if 0 <= hour < 8:
                        session_name = "Asia"
                    elif 8 <= hour < 14:
                        session_name = "London"
                    elif 14 <= hour < 21:
                        session_name = "New York"
                    else:
                        session_name = "Off-Hours"
                except Exception:
                    pass

            if entry_t_str and exit_t_str:
                try:
                    dt_in = pd.to_datetime(entry_t_str)
                    dt_out = pd.to_datetime(exit_t_str)
                    duration_sec = (dt_out - dt_in).total_seconds()
                    if duration_sec < 900:
                        duration_label = "Scalp (<15m)"
                    elif duration_sec <= 14400:
                        duration_label = "Day Trade (15m-4h)"
                    else:
                        duration_label = "Swing (>4h)"
                except Exception:
                    pass

            pnl = float(t.get("pnl") or 0.0)
            r_mult = float(t.get("r_multiple") or (pnl / (abs(float(t.get("entry_price", 100)) - float(t.get("stop_loss", 99))) * float(t.get("qty", 1))) if t.get("stop_loss") else (1.0 if pnl > 0 else -1.0)))

            enriched.append({
                "id": str(t["id"]),
                "symbol": str(t["symbol"]),
                "side": side_clean,
                "day_of_week": day_name,
                "session": session_name,
                "hold_time_range": duration_label,
                "status": str(t.get("status", "CLOSED")),
                "pnl": pnl,
                "r_multiple": r_mult,
                "duration_seconds": duration_sec
            })

        df = pd.DataFrame(enriched)
        conn = duckdb.connect()
        try:
            conn.register("trades_df", df)

            dim_select = ", ".join(dimensions)
            query = f"""
                SELECT 
                    {dim_select},
                    COUNT(*) as trades_count,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as win_count,
                    COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as loss_count,
                    COALESCE(SUM(pnl), 0.0) as total_pnl,
                    COALESCE(AVG(pnl), 0.0) as avg_pnl,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0.0) as gross_profit,
                    COALESCE(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0.0) as gross_loss,
                    COALESCE(AVG(r_multiple), 0.0) as avg_r_multiple,
                    COALESCE(MAX(pnl), 0.0) as max_win,
                    COALESCE(MIN(pnl), 0.0) as max_loss
                FROM trades_df
                GROUP BY {dim_select}
                ORDER BY total_pnl DESC
            """
            result = conn.execute(query).fetchall()
            col_names = [d for d in dimensions] + [
                "trades_count", "win_count", "loss_count", "total_pnl", "avg_pnl",
                "gross_profit", "gross_loss", "avg_r_multiple", "max_win", "max_loss"
            ]

            rows = []
            for r in result:
                item = dict(zip(col_names, r))
                n = int(item["trades_count"])
                wins = int(item["win_count"])
                losses = int(item["loss_count"])
                win_rate = (wins / n) * 100.0 if n > 0 else 0.0
                gross_p = float(item["gross_profit"])
                gross_l = float(item["gross_loss"])
                pf = (gross_p / gross_l) if gross_l > 0 else (gross_p if gross_p > 0 else 0.0)

                # Filter trade records for SQN and EV
                filter_cond = True
                subset = df
                for d in dimensions:
                    subset = subset[subset[d] == item[d]]
                pnls_subset = subset["pnl"].tolist()
                r_subset = subset["r_multiple"].tolist()

                sqn = quant_engine.calculate_sqn(r_subset)
                avg_win = float(np.mean([p for p in pnls_subset if p > 0])) if wins > 0 else 0.0
                avg_loss = float(abs(np.mean([p for p in pnls_subset if p < 0]))) if losses > 0 else 0.0
                ev = quant_engine.calculate_expectancy(win_rate / 100.0, avg_win, (n - wins) / n, avg_loss)

                formatted = {
                    "dimensions": {d: item[d] for d in dimensions},
                    "group_key": " | ".join(str(item[d]) for d in dimensions),
                    "trades_count": n,
                    "win_rate": round(win_rate, 2),
                    "total_pnl": round(float(item["total_pnl"]), 2),
                    "avg_pnl": round(float(item["avg_pnl"]), 2),
                    "profit_factor": round(pf, 2),
                    "avg_r_multiple": round(float(item["avg_r_multiple"]), 2),
                    "sqn": round(sqn, 2),
                    "expectancy": round(ev, 2),
                    "max_win": round(float(item["max_win"]), 2),
                    "max_loss": round(float(item["max_loss"]), 2),
                }
                rows.append(formatted)

            return {
                "dimensions": dimensions,
                "total_buckets": len(rows),
                "rows": rows
            }
        finally:
            conn.close()


pivot_engine = PivotEngine()
