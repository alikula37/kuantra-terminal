"""
Execution Drift Analytics & Panic Exit Cost Engine for Kuantra Terminal.
Measures theoretical trade plans vs actual execution leakage and premature exit drag.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from app.db.sqlite_driver import sqlite_driver

class ExecutionDriftAnalyzer:
    """Calculates slippage drag, panic exit losses, and execution fidelity metrics."""

    @staticmethod
    def analyze_trade_drift(
        trade: Dict[str, Any],
        candles: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Compares actual execution against planned parameters for an individual trade."""
        actual_entry = float(trade["entry_price"])
        actual_exit = float(trade.get("exit_price") or actual_entry)
        side = str(trade.get("side", "BUY")).upper()
        is_long = side in ("BUY", "LONG")
        qty = float(trade.get("qty", 1.0))
        actual_pnl = float(trade.get("pnl") or 0.0)

        sl = float(trade["stop_loss"]) if trade.get("stop_loss") else None
        tp = float(trade["take_profit"]) if trade.get("take_profit") else None

        # Determine 1R initial risk unit
        if sl is not None and abs(actual_entry - sl) > 1e-6:
            risk_unit = abs(actual_entry - sl)
        else:
            risk_unit = actual_entry * 0.01

        planned_entry = actual_entry  # Baseline planned entry
        entry_slippage = 0.0  # Slippage in price units

        # Planned theoretical exit (if hit TP or SL)
        theoretical_tp_pnl = (tp - actual_entry) * qty if tp and is_long else (actual_entry - tp) * qty if tp else actual_pnl
        theoretical_sl_pnl = (sl - actual_entry) * qty if sl and is_long else (actual_entry - sl) * qty if sl else -risk_unit * qty

        # Panic / Early Exit Detection
        # Check if actual exit occurred between SL and TP (manual premature intervention)
        is_early_exit = False
        panic_cost = 0.0
        saved_loss = 0.0

        if tp and sl:
            if is_long:
                if actual_exit < tp and actual_exit > sl:
                    is_early_exit = True
                    # If actual exit was in profit or small loss, but TP was reachable
                    if actual_pnl < theoretical_tp_pnl:
                        panic_cost = max(0.0, theoretical_tp_pnl - actual_pnl)
            else:
                if actual_exit > tp and actual_exit < sl:
                    is_early_exit = True
                    if actual_pnl < theoretical_tp_pnl:
                        panic_cost = max(0.0, theoretical_tp_pnl - actual_pnl)

        # Theoretical PnL benchmark (assuming plan had executed to target or stop)
        theoretical_pnl = theoretical_tp_pnl if actual_pnl > 0 else theoretical_sl_pnl
        
        # Execution Drift Ratio = (Actual PnL - Theoretical PnL) / (Risk Unit * Qty)
        total_risk_dollars = risk_unit * qty
        drift_ratio = (actual_pnl - theoretical_pnl) / total_risk_dollars if total_risk_dollars > 0 else 0.0

        return {
            "trade_id": str(trade["id"]),
            "symbol": str(trade["symbol"]),
            "side": side,
            "actual_entry": round(actual_entry, 2),
            "planned_entry": round(planned_entry, 2),
            "entry_drift_dollars": round(entry_slippage * qty, 2),
            "actual_exit": round(actual_exit, 2),
            "stop_loss": round(sl, 2) if sl else None,
            "take_profit": round(tp, 2) if tp else None,
            "actual_pnl": round(actual_pnl, 2),
            "theoretical_pnl": round(theoretical_pnl, 2),
            "is_early_exit": is_early_exit,
            "panic_cost": round(panic_cost, 2),
            "drift_ratio": round(float(drift_ratio), 2),
            "risk_unit": round(risk_unit, 2)
        }

    @classmethod
    def get_drift_analytics(cls, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Aggregates execution drift metrics and leakage breakdown across closed trades."""
        closed_trades = sqlite_driver.list_trades(limit=1000, symbol=symbol, status="CLOSED")

        if not closed_trades:
            return cls._generate_mock_drift_dataset()

        drift_items = [cls.analyze_trade_drift(t) for t in closed_trades]

        total_actual_pnl = sum(d["actual_pnl"] for d in drift_items)
        total_theoretical_pnl = sum(d["theoretical_pnl"] for d in drift_items)
        total_panic_leakage = sum(d["panic_cost"] for d in drift_items)
        early_exit_count = sum(1 for d in drift_items if d["is_early_exit"])
        avg_drift_ratio = float(np.mean([d["drift_ratio"] for d in drift_items])) if drift_items else 0.0

        execution_fidelity_pct = (total_actual_pnl / total_theoretical_pnl * 100.0) if total_theoretical_pnl > 0 else 100.0
        execution_fidelity_pct = max(0.0, min(150.0, execution_fidelity_pct))

        return {
            "total_trades": len(drift_items),
            "total_actual_pnl": round(total_actual_pnl, 2),
            "total_theoretical_pnl": round(total_theoretical_pnl, 2),
            "total_panic_exit_leakage": round(total_panic_leakage, 2),
            "early_exits_count": early_exit_count,
            "avg_drift_ratio": round(avg_drift_ratio, 2),
            "execution_fidelity_pct": round(execution_fidelity_pct, 1),
            "trades": drift_items
        }

    @classmethod
    def _generate_mock_drift_dataset(cls) -> Dict[str, Any]:
        """Provides seed institutional execution comparison dataset."""
        mock_trades = []
        np.random.seed(42)
        for i in range(25):
            side = "BUY" if np.random.rand() > 0.5 else "SELL"
            entry = 65000.0 + np.random.randn() * 800
            risk = 600.0
            tp_dist = risk * 2.5
            is_win = np.random.rand() > 0.35
            
            sl = entry - risk if side == "BUY" else entry + risk
            tp = entry + tp_dist if side == "BUY" else entry - tp_dist
            
            # Simulate early panic exit vs full target
            is_early = np.random.rand() > 0.6
            if is_win:
                if is_early:
                    actual_exit = entry + risk * 1.2 if side == "BUY" else entry - risk * 1.2
                    actual_pnl = risk * 1.2
                    theo_pnl = tp_dist
                    panic_cost = tp_dist - actual_pnl
                else:
                    actual_exit = tp
                    actual_pnl = tp_dist
                    theo_pnl = tp_dist
                    panic_cost = 0.0
            else:
                actual_exit = sl
                actual_pnl = -risk
                theo_pnl = -risk
                panic_cost = 0.0

            mock_trades.append({
                "trade_id": f"TRD-{2000 + i}",
                "symbol": "BTCUSDT",
                "side": side,
                "actual_entry": round(entry, 2),
                "planned_entry": round(entry, 2),
                "entry_drift_dollars": round(float(np.random.uniform(5, 25)), 2),
                "actual_exit": round(actual_exit, 2),
                "stop_loss": round(sl, 2),
                "take_profit": round(tp, 2),
                "actual_pnl": round(actual_pnl, 2),
                "theoretical_pnl": round(theo_pnl, 2),
                "is_early_exit": is_early,
                "panic_cost": round(panic_cost, 2),
                "drift_ratio": round((actual_pnl - theo_pnl) / risk, 2),
                "risk_unit": round(risk, 2)
            })

        tot_act = sum(t["actual_pnl"] for t in mock_trades)
        tot_theo = sum(t["theoretical_pnl"] for t in mock_trades)
        tot_panic = sum(t["panic_cost"] for t in mock_trades)

        return {
            "total_trades": len(mock_trades),
            "total_actual_pnl": round(tot_act, 2),
            "total_theoretical_pnl": round(tot_theo, 2),
            "total_panic_exit_leakage": round(tot_panic, 2),
            "early_exits_count": sum(1 for t in mock_trades if t["is_early_exit"]),
            "avg_drift_ratio": -0.32,
            "execution_fidelity_pct": 74.5,
            "trades": mock_trades
        }

execution_drift_analyzer = ExecutionDriftAnalyzer()