"""
Prop Firm Compliance Shield Service for Kuantra Terminal.
Evaluates daily loss limits, maximum drawdowns, trailing rules, and alerts in real-time.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.db.sqlite_driver import sqlite_driver
from app.websocket.connection_manager import ws_manager

logger = logging.getLogger(__name__)

class ComplianceConfig(BaseModel):
    account_size: float = 100000.0
    daily_loss_limit_pct: float = 5.0      # 5% = $5,000 on $100k
    max_drawdown_pct: float = 10.0         # 10% = $10,000 on $100k
    profit_target_pct: float = 10.0        # 10% = $10,000 profit target
    min_trading_days: int = 5
    trailing_drawdown: bool = True
    require_stop_loss: bool = True
    max_risk_per_trade_pct: float = 2.0    # 2% max risk per trade

class ComplianceEngine:
    """Institutional Prop Firm rule verification and real-time alert dispatching."""

    def __init__(self):
        self.config = ComplianceConfig()
        self.high_watermark: float = self.config.account_size
        self.last_alert_status: str = "COMPLIANT"

    def update_config(self, new_config: Dict[str, Any]) -> ComplianceConfig:
        current_dict = self.config.model_dump()
        current_dict.update(new_config)
        self.config = ComplianceConfig(**current_dict)
        self.high_watermark = max(self.high_watermark, self.config.account_size)
        return self.config

    def evaluate_compliance(
        self,
        open_positions: Optional[List[Dict[str, Any]]] = None,
        closed_trades: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Comprehensive evaluation of account state against all prop firm rules."""
        positions = open_positions if open_positions is not None else []
        if closed_trades is None:
            all_trades = sqlite_driver.list_trades(limit=10000)
            closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]

        # Today's UTC date
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Realized PnLs
        all_time_realized_pnl = sum(float(t.get("pnl") or 0.0) for t in closed_trades)
        today_closed_pnl = sum(
            float(t.get("pnl") or 0.0)
            for t in closed_trades
            if str(t.get("exit_time", "")).startswith(today_str)
        )

        # 2. Unrealized PnL from open positions
        unrealized_pnl = sum(float(p.get("unrealized_pnl") or 0.0) for p in positions)
        today_total_pnl = today_closed_pnl + unrealized_pnl
        current_equity = self.config.account_size + all_time_realized_pnl + unrealized_pnl

        # 3. Update High Watermark
        if current_equity > self.high_watermark:
            self.high_watermark = current_equity

        # 4. Limits & Budgets
        daily_loss_budget = self.config.account_size * (self.config.daily_loss_limit_pct / 100.0)
        max_dd_budget = self.config.account_size * (self.config.max_drawdown_pct / 100.0)
        profit_target_amount = self.config.account_size * (self.config.profit_target_pct / 100.0)

        # 5. Calculate Drawdowns
        if self.config.trailing_drawdown:
            current_drawdown_amount = max(0.0, self.high_watermark - current_equity)
        else:
            current_drawdown_amount = max(0.0, self.config.account_size - current_equity)

        current_drawdown_pct = (current_drawdown_amount / self.config.account_size) * 100.0

        # Current daily loss (positive if in loss)
        current_daily_loss = abs(today_total_pnl) if today_total_pnl < 0 else 0.0
        daily_loss_utilization_pct = (current_daily_loss / daily_loss_budget) * 100.0 if daily_loss_budget > 0 else 0.0
        max_dd_utilization_pct = (current_drawdown_amount / max_dd_budget) * 100.0 if max_dd_budget > 0 else 0.0

        # 6. Active Trading Days
        trading_dates = set()
        for t in closed_trades:
            if t.get("entry_time"):
                trading_dates.add(str(t["entry_time"])[:10])
        for p in positions:
            if p.get("entry_time"):
                trading_dates.add(str(p["entry_time"])[:10])
        days_traded = len(trading_dates)

        # 7. Check Naked Positions (missing Stop Loss)
        naked_positions = []
        for pos in positions:
            if self.config.require_stop_loss and (pos.get("stop_loss") is None or float(pos.get("stop_loss") or 0) <= 0):
                naked_positions.append(pos.get("id"))

        # 8. Rules & Breaches
        rules_status = []
        is_breached = False
        is_critical = False
        is_warning = False

        # Rule A: Daily Max Loss
        daily_breached = current_daily_loss >= daily_loss_budget
        daily_status = "BREACH" if daily_breached else "CRITICAL" if daily_loss_utilization_pct >= 90.0 else "WARN" if daily_loss_utilization_pct >= 70.0 else "PASS"
        if daily_breached:
            is_breached = True
        elif daily_status == "CRITICAL":
            is_critical = True
        elif daily_status == "WARN":
            is_warning = True

        rules_status.append({
            "rule": "Daily Max Loss",
            "limit": f"${daily_loss_budget:,.2f} ({self.config.daily_loss_limit_pct}%)",
            "current": f"${current_daily_loss:,.2f}",
            "utilization_pct": round(daily_loss_utilization_pct, 1),
            "status": daily_status
        })

        # Rule B: Overall Max Drawdown
        dd_breached = current_drawdown_amount >= max_dd_budget
        dd_status = "BREACH" if dd_breached else "CRITICAL" if max_dd_utilization_pct >= 90.0 else "WARN" if max_dd_utilization_pct >= 70.0 else "PASS"
        if dd_breached:
            is_breached = True
        elif dd_status == "CRITICAL":
            is_critical = True
        elif dd_status == "WARN":
            is_warning = True

        rules_status.append({
            "rule": "Max Drawdown (Trailing)" if self.config.trailing_drawdown else "Max Drawdown (Static)",
            "limit": f"${max_dd_budget:,.2f} ({self.config.max_drawdown_pct}%)",
            "current": f"${current_drawdown_amount:,.2f}",
            "utilization_pct": round(max_dd_utilization_pct, 1),
            "status": dd_status
        })

        # Rule C: Mandatory Stop Loss
        sl_status = "BREACH" if len(naked_positions) > 0 else "PASS"
        if len(naked_positions) > 0:
            is_warning = True
        rules_status.append({
            "rule": "Mandatory Stop Loss",
            "limit": "All active positions must have SL",
            "current": f"{len(naked_positions)} open without SL",
            "utilization_pct": 100.0 if naked_positions else 0.0,
            "status": sl_status
        })

        # Rule D: Minimum Trading Days
        min_days_passed = days_traded >= self.config.min_trading_days
        rules_status.append({
            "rule": "Min Trading Days",
            "limit": f"{self.config.min_trading_days} Days",
            "current": f"{days_traded} Days",
            "utilization_pct": round((days_traded / self.config.min_trading_days) * 100.0, 1),
            "status": "PASS" if min_days_passed else "IN_PROGRESS"
        })

        # Rule E: Profit Target
        profit_target_pct_achieved = (all_time_realized_pnl / profit_target_amount) * 100.0 if profit_target_amount > 0 else 0.0
        rules_status.append({
            "rule": "Profit Target",
            "limit": f"${profit_target_amount:,.2f} ({self.config.profit_target_pct}%)",
            "current": f"${all_time_realized_pnl:,.2f}",
            "utilization_pct": round(max(0.0, profit_target_pct_achieved), 1),
            "status": "PASSED" if all_time_realized_pnl >= profit_target_amount else "IN_PROGRESS"
        })

        overall_status = "BREACHED" if is_breached else "CRITICAL" if is_critical else "WARNING" if is_warning else "COMPLIANT"
        self.last_alert_status = overall_status

        return {
            "account_size": self.config.account_size,
            "current_equity": round(current_equity, 2),
            "high_watermark": round(self.high_watermark, 2),
            "today_pnl": round(today_total_pnl, 2),
            "all_time_pnl": round(all_time_realized_pnl + unrealized_pnl, 2),
            "current_drawdown_amount": round(current_drawdown_amount, 2),
            "current_drawdown_pct": round(current_drawdown_pct, 2),
            "daily_loss_budget": round(daily_loss_budget, 2),
            "daily_loss_remaining": round(max(0.0, daily_loss_budget - current_daily_loss), 2),
            "max_dd_budget": round(max_dd_budget, 2),
            "max_dd_remaining": round(max(0.0, max_dd_budget - current_drawdown_amount), 2),
            "profit_target_amount": round(profit_target_amount, 2),
            "days_traded": days_traded,
            "overall_status": overall_status,
            "is_breached": is_breached,
            "rules": rules_status,
            "naked_positions_count": len(naked_positions),
            "config": self.config.model_dump()
        }

    async def check_and_broadcast_alerts(self, open_positions: List[Dict[str, Any]]) -> None:
        try:
            status_data = self.evaluate_compliance(open_positions)
            if status_data["overall_status"] in ("WARN", "WARNING", "CRITICAL", "BREACHED"):
                await ws_manager.broadcast({
                    "type": "COMPLIANCE_ALERT",
                    "data": status_data
                }, channel="system_metrics")
        except Exception as e:
            logger.error(f"Error in compliance alert broadcast: {e}")

compliance_engine = ComplianceEngine()