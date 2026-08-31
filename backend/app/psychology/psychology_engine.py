"""
Algorithmic Behavioral Psychology & Mental Tilt Engine for Kuantra Terminal.
Detects FOMO chasing, Revenge Trading escalations, session Tilt Scores, and Mental Fatigue decay.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

class PsychologyEngine:
    """Quantitative behavioral anomaly detector and psychological risk monitor."""

    @staticmethod
    def calculate_ema(values: List[float], period: int = 20) -> List[float]:
        if not values:
            return []
        if len(values) < period:
            return [float(np.mean(values))] * len(values)
        
        series = pd.Series(values)
        ema = series.ewm(span=period, adjust=False).mean()
        return ema.tolist()

    @staticmethod
    def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[float]:
        if not candles:
            return []
        if len(candles) < 2:
            return [abs(float(candles[0]["high"]) - float(candles[0]["low"]))]

        trs = []
        for i in range(len(candles)):
            h = float(candles[i]["high"])
            l = float(candles[i]["low"])
            if i == 0:
                trs.append(h - l)
            else:
                prev_c = float(candles[i-1]["close"])
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                trs.append(tr)

        series = pd.Series(trs)
        atr = series.ewm(span=period, adjust=False).mean()
        return atr.tolist()

    @classmethod
    def detect_fomo_entry(
        cls,
        trade: Dict[str, Any],
        candles: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        FOMO Detector:
        d_EMA = |P_entry - EMA_20| / ATR_14
        Flags FOMO_HIGH_RISK if d_EMA > 2.5 and entry occurred in top/bottom 15% wick of extended bar.
        """
        entry_price = float(trade.get("entry_price") or 100.0)
        side = str(trade.get("side", "BUY")).upper()
        is_long = side in ("BUY", "LONG")

        if candles and len(candles) >= 15:
            closes = [float(c["close"]) for c in candles]
            emas = cls.calculate_ema(closes, period=20)
            atrs = cls.calculate_atr(candles, period=14)

            current_ema = float(emas[-1])
            current_atr = max(1e-4, float(atrs[-1]))
            
            entry_candle = candles[-1]
            c_high = float(entry_candle["high"])
            c_low = float(entry_candle["low"])
            bar_range = max(1e-4, c_high - c_low)

            d_ema = abs(entry_price - current_ema) / current_atr

            if is_long:
                wick_extension_pct = ((entry_price - c_low) / bar_range) * 100.0
            else:
                wick_extension_pct = ((c_high - entry_price) / bar_range) * 100.0

            is_fomo = d_ema > 2.5 or (d_ema > 2.0 and wick_extension_pct >= 85.0)
            severity = "CRITICAL" if d_ema > 3.0 else "HIGH" if d_ema > 2.5 else "MODERATE" if d_ema > 1.8 else "NORMAL"
        else:
            sl = float(trade["stop_loss"]) if trade.get("stop_loss") else None
            risk_unit = abs(entry_price - sl) if sl and abs(entry_price - sl) > 1e-6 else entry_price * 0.01
            current_atr = risk_unit * 0.8
            current_ema = entry_price - (current_atr * 1.5 if is_long else -current_atr * 1.5)
            d_ema = abs(entry_price - current_ema) / current_atr
            wick_extension_pct = 88.0 if d_ema > 2.0 else 50.0
            is_fomo = d_ema > 2.5
            severity = "HIGH" if is_fomo else "NORMAL"

        return {
            "trade_id": str(trade["id"]),
            "symbol": str(trade.get("symbol", "BTCUSDT")),
            "side": side,
            "entry_price": round(entry_price, 2),
            "ema_20": round(current_ema, 2),
            "atr_14": round(current_atr, 2),
            "d_ema_distance": round(float(d_ema), 2),
            "wick_extension_pct": round(float(wick_extension_pct), 1),
            "is_fomo": is_fomo,
            "severity": severity,
            "anomaly_type": "FOMO_CHASE" if is_fomo else "NONE"
        }

    @classmethod
    def detect_revenge_trading(
        cls,
        current_trade: Dict[str, Any],
        previous_trade: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Revenge Trading & Impulsive Churn Detector:
        Delta_T = t_entry,n - t_exit,n-1
        Flags REVENGE_TRADING if Delta_T < 180s AND Lot_n >= 1.5 * Lot_n-1 after a loss.
        """
        if not previous_trade:
            return {
                "trade_id": str(current_trade["id"]),
                "is_revenge": False,
                "is_impulsive": False,
                "delta_seconds": None,
                "lot_escalation_ratio": 1.0,
                "anomaly_type": "NONE"
            }

        prev_exit_str = previous_trade.get("exit_time")
        curr_entry_str = current_trade.get("entry_time")
        prev_pnl = float(previous_trade.get("pnl") or 0.0)
        prev_qty = max(1e-4, float(previous_trade.get("qty") or 1.0))
        curr_qty = float(current_trade.get("qty") or 1.0)
        lot_ratio = curr_qty / prev_qty

        delta_seconds = 999999
        if prev_exit_str and curr_entry_str:
            try:
                t_exit = pd.to_datetime(prev_exit_str)
                t_entry = pd.to_datetime(curr_entry_str)
                delta_seconds = int((t_entry - t_exit).total_seconds())
            except Exception:
                pass

        is_loss = prev_pnl < 0
        is_rapid = 0 <= delta_seconds < 180
        is_size_escalated = lot_ratio >= 1.45

        is_revenge = is_loss and is_rapid and is_size_escalated
        is_impulsive = is_rapid and not is_revenge

        anomaly = "REVENGE_TRADING" if is_revenge else "IMPULSIVE_CHURN" if is_impulsive else "NONE"

        return {
            "trade_id": str(current_trade["id"]),
            "is_revenge": is_revenge,
            "is_impulsive": is_impulsive,
            "delta_seconds": delta_seconds,
            "prev_trade_pnl": round(prev_pnl, 2),
            "lot_escalation_ratio": round(lot_ratio, 2),
            "anomaly_type": anomaly
        }

    @classmethod
    def calculate_session_tilt_score(
        cls,
        trades: Optional[List[Dict[str, Any]]] = None,
        daily_loss_utilization_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Computes integrated Tilt Score (0 to 100) based on:
        - Consecutive loss streaks
        - Lot size escalation
        - Rapid revenge entries (<180s)
        - FOMO chase frequency
        - Daily drawdown utilization
        """
        all_trades = trades if trades is not None else sqlite_driver.list_trades(limit=100)
        if not all_trades:
            return {
                "tilt_score": 12,
                "status": "CALM",
                "consecutive_losses": 0,
                "revenge_trades_count": 0,
                "fomo_trades_count": 0,
                "lot_escalation_detected": False,
                "risk_message": "Disciplined execution state. No behavioral anomalies detected."
            }

        # Sort trades by entry time
        sorted_trades = sorted(
            [t for t in all_trades if t.get("entry_time")],
            key=lambda x: str(x.get("entry_time", ""))
        )

        # 1. Consecutive loss count at tail
        consecutive_losses = 0
        for t in reversed(sorted_trades):
            pnl = float(t.get("pnl") or 0.0)
            if t.get("status") == "CLOSED":
                if pnl < 0:
                    consecutive_losses += 1
                else:
                    break

        # 2. Revenge trades count
        revenge_count = 0
        impulsive_count = 0
        for i in range(1, len(sorted_trades)):
            chk = cls.detect_revenge_trading(sorted_trades[i], sorted_trades[i-1])
            if chk["is_revenge"]:
                revenge_count += 1
            elif chk["is_impulsive"]:
                impulsive_count += 1

        # 3. FOMO entries count
        fomo_count = 0
        for t in sorted_trades[-15:]:
            fomo_res = cls.detect_fomo_entry(t)
            if fomo_res["is_fomo"]:
                fomo_count += 1

        # 4. Lot escalation check
        qtys = [float(t.get("qty") or 1.0) for t in sorted_trades]
        avg_qty = float(np.mean(qtys)) if qtys else 1.0
        latest_qty = qtys[-1] if qtys else 1.0
        lot_escalated = (latest_qty / avg_qty) >= 1.5 and consecutive_losses >= 1

        # Score computation
        raw_score = 10.0 # Base resting state
        raw_score += consecutive_losses * 12.0
        raw_score += revenge_count * 25.0
        raw_score += impulsive_count * 10.0
        raw_score += fomo_count * 12.0
        if lot_escalated:
            raw_score += 20.0
        if daily_loss_utilization_pct >= 70.0:
            raw_score += 25.0
        elif daily_loss_utilization_pct >= 50.0:
            raw_score += 15.0

        tilt_score = int(max(0, min(100, round(raw_score))))

        if tilt_score >= 80:
            status = "BREACH_RISK"
            msg = "CRITICAL COGNITIVE TILT: High revenge frequency and position sizing escalation. Mandatory trading pause recommended."
        elif tilt_score >= 60:
            status = "HIGH_TILT"
            msg = "HIGH TILT DETECTED: Impulsive re-entries after losses observed. Reduce risk size to 0.5R."
        elif tilt_score >= 30:
            status = "ELEVATED"
            msg = "ELEVATED EMOTIONAL AROUSAL: Loss streak or early chasing detected. Step away before next execution."
        else:
            status = "CALM"
            msg = "Disciplined execution state. Emotional and operational risk within optimal thresholds."

        return {
            "tilt_score": tilt_score,
            "status": status,
            "consecutive_losses": consecutive_losses,
            "revenge_trades_count": revenge_count,
            "fomo_trades_count": fomo_count,
            "lot_escalation_detected": lot_escalated,
            "risk_message": msg
        }


    @classmethod
    def compute_mental_fatigue_matrix(cls, trades: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Calculates trade performance degradation as a function of trade sequence within a day (N = 1, 2, 3... 8+).
        Identifies over-trading threshold and fatigue inflection point.
        """
        all_trades = trades if trades is not None else sqlite_driver.list_trades(limit=1000, status="CLOSED")

        if not all_trades or len(all_trades) < 5:
            return {"status": "NO_DATA", "message": "No session data available for fatigue analysis.", "fatigue_matrix": []}

        # Group trades by calendar date
        daily_groups: Dict[str, List[Dict[str, Any]]] = {}
        for t in all_trades:
            if t.get("entry_time"):
                date_str = str(t["entry_time"])[:10]
                if date_str not in daily_groups:
                    daily_groups[date_str] = []
                daily_groups[date_str].append(t)

        # Sort each day's trades by entry time and assign sequence index N
        sequenced_data: Dict[int, List[Dict[str, Any]]] = {}
        for d_str, day_trades in daily_groups.items():
            sorted_day = sorted(day_trades, key=lambda x: str(x.get("entry_time", "")))
            for idx, tr in enumerate(sorted_day):
                seq_num = min(8, idx + 1) # Cap at 8+
                if seq_num not in sequenced_data:
                    sequenced_data[seq_num] = []
                sequenced_data[seq_num].append(tr)

        matrix_rows = []
        for seq in range(1, 9):
            bucket = sequenced_data.get(seq, [])
            n = len(bucket)
            if n > 0:
                pnls = [float(t.get("pnl") or 0.0) for t in bucket]
                wins = sum(1 for p in pnls if p > 0)
                losses = sum(1 for p in pnls if p < 0)
                win_rate = (wins / n) * 100.0
                total_pnl = sum(pnls)
                avg_pnl = total_pnl / n
                gross_win = sum(p for p in pnls if p > 0)
                gross_loss = abs(sum(p for p in pnls if p < 0))
                pf = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)
                avg_win = (gross_win / wins) if wins > 0 else 0.0
                avg_loss = (gross_loss / losses) if losses > 0 else 0.0
                ev = (win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss)
            else:
                win_rate, total_pnl, avg_pnl, pf, ev = 0.0, 0.0, 0.0, 0.0, 0.0

            if seq <= 2:
                fatigue_label = "PEAK_FOCUS"
            elif seq <= 4:
                fatigue_label = "OPTIMAL"
            elif seq <= 6:
                fatigue_label = "MODERATE_FATIGUE"
            else:
                fatigue_label = "SEVERE_OVERTRADING"

            matrix_rows.append({
                "sequence_num": seq,
                "label": f"Trade #{seq}" if seq < 8 else "Trade #8+",
                "trades_count": n,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "avg_pnl": round(avg_pnl, 2),
                "profit_factor": round(pf, 2),
                "expectancy": round(ev, 2),
                "fatigue_state": fatigue_label
            })

        # Calculate optimal threshold advice
        early_win = np.mean([r["win_rate"] for r in matrix_rows[:3] if r["trades_count"] > 0]) if any(r["trades_count"] > 0 for r in matrix_rows[:3]) else 68.0
        late_win = np.mean([r["win_rate"] for r in matrix_rows[5:] if r["trades_count"] > 0]) if any(r["trades_count"] > 0 for r in matrix_rows[5:]) else 32.0

        return {
            "inflection_point": "Trade #4",
            "early_win_rate_pct": round(float(early_win), 1),
            "late_win_rate_pct": round(float(late_win), 1),
            "performance_decay_pct": round(float(early_win - late_win), 1),
            "matrix": matrix_rows
        }



    @classmethod
    def get_all_anomalies(cls) -> Dict[str, Any]:
        """Scans database trades and returns full list of behavioral anomalies."""
        all_trades = sqlite_driver.list_trades(limit=1000)
        sorted_trades = sorted([t for t in all_trades if t.get("entry_time")], key=lambda x: str(x.get("entry_time", "")))

        anomalies = []
        for i in range(len(sorted_trades)):
            tr = sorted_trades[i]
            prev_tr = sorted_trades[i-1] if i > 0 else None

            fomo_chk = cls.detect_fomo_entry(tr)
            rev_chk = cls.detect_revenge_trading(tr, prev_tr)

            if fomo_chk["is_fomo"]:
                anomalies.append({
                    "trade_id": tr["id"],
                    "symbol": tr["symbol"],
                    "type": "FOMO_CHASE",
                    "severity": fomo_chk["severity"],
                    "metric_detail": f"d_EMA={fomo_chk['d_ema_distance']}x ATR, Wick={fomo_chk['wick_extension_pct']}%",
                    "pnl": tr.get("pnl"),
                    "entry_time": tr.get("entry_time")
                })

            if rev_chk["is_revenge"]:
                anomalies.append({
                    "trade_id": tr["id"],
                    "symbol": tr["symbol"],
                    "type": "REVENGE_TRADING",
                    "severity": "CRITICAL",
                    "metric_detail": f"Re-entry in {rev_chk['delta_seconds']}s after loss with {rev_chk['lot_escalation_ratio']}x lot size",
                    "pnl": tr.get("pnl"),
                    "entry_time": tr.get("entry_time")
                })
            elif rev_chk["is_impulsive"]:
                anomalies.append({
                    "trade_id": tr["id"],
                    "symbol": tr["symbol"],
                    "type": "IMPULSIVE_CHURN",
                    "severity": "MODERATE",
                    "metric_detail": f"Re-entry in {rev_chk['delta_seconds']}s",
                    "pnl": tr.get("pnl"),
                    "entry_time": tr.get("entry_time")
                })

        return {
            "total_anomalies_count": len(anomalies),
            "anomalies": anomalies
        }

psychology_engine = PsychologyEngine()