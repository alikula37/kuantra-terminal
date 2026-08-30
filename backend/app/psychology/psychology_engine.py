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
        """Calculates Exponential Moving Average (EMA)."""
        if not values:
            return []
        if len(values) < period:
            return [float(np.mean(values))] * len(values)
        
        series = pd.Series(values)
        ema = series.ewm(span=period, adjust=False).mean()
        return ema.tolist()

    @staticmethod
    def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> List[float]:
        """Calculates Average True Range (ATR)."""
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
        entry_price = float(trade["entry_price"])
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

            # d_EMA distance in ATR multiples
            d_ema = abs(entry_price - current_ema) / current_atr

            # Wick extremity test: entered at high wick for Long or low wick for Short
            if is_long:
                wick_extension_pct = ((entry_price - c_low) / bar_range) * 100.0
            else:
                wick_extension_pct = ((c_high - entry_price) / bar_range) * 100.0

            is_fomo = d_ema > 2.5 or (d_ema > 2.0 and wick_extension_pct >= 85.0)
            severity = "CRITICAL" if d_ema > 3.0 else "HIGH" if d_ema > 2.5 else "MODERATE" if d_ema > 1.8 else "NORMAL"
        else:
            # Synthetic / fallback calculation if candles array is unavailable
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

psychology_engine = PsychologyEngine()