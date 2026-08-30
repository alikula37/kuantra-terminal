"""
Multi-Account Prop Firm Risk Allocator for Kuantra Terminal.
Fans out trades simultaneously across Binance, OKX, and CME FIX accounts with independent drawdown gating.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from app.services.execution.order_router import order_router
from app.services.execution.fix_bridge import quickfix_dma_client
from app.services.biometrics.watch_bridge import biometric_watch_bridge

logger = logging.getLogger("multi_account_router")

class MultiAccountRiskAllocator:
    """Manages simultaneous multi-broker allocation with strict per-account risk isolation."""

    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {
            "ACC-FTMO-100K": {
                "account_id": "ACC-FTMO-100K",
                "name": "FTMO Challenge $100k",
                "venue": "BINANCE",
                "equity": 100000.0,
                "risk_multiplier": 1.0,
                "max_daily_loss": 5000.0,
                "current_daily_loss": 850.0,
                "is_active": True
            },
            "ACC-MFF-200K": {
                "account_id": "ACC-MFF-200K",
                "name": "MyFundedFutures $200k CME",
                "venue": "CME_FIX_DMA",
                "equity": 200000.0,
                "risk_multiplier": 1.5,
                "max_daily_loss": 6000.0,
                "current_daily_loss": 1200.0,
                "is_active": True
            },
            "ACC-OKX-PERSONAL": {
                "account_id": "ACC-OKX-PERSONAL",
                "name": "Personal OKX High-Yield",
                "venue": "OKX",
                "equity": 50000.0,
                "risk_multiplier": 0.5,
                "max_daily_loss": 4000.0,
                "current_daily_loss": 3950.0, # Near breach (will be tested)
                "is_active": True
            }
        }

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Returns all registered sub-accounts and risk parameters."""
        return list(self.accounts.values())

    def update_account(self, account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Updates account risk configuration or status."""
        if account_id not in self.accounts:
            raise KeyError(f"Account {account_id} not found.")
        self.accounts[account_id].update(updates)
        return self.accounts[account_id]

    def fanout_order(self, master_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fans out master order across all active accounts:
        - Checks Biometric Stress gate
        - Checks individual account daily drawdown limits
        - Scales lot size by account risk_multiplier
        - Dispatches order to appropriate broker/exchange venue
        """
        symbol = str(master_order.get("symbol", "BTCUSDT")).upper()
        side = str(master_order.get("side", "BUY")).upper()
        base_qty = float(master_order.get("qty", 1.0))
        price = float(master_order.get("price", 0.0))

        # Check Global Biometric Stress Lock
        if biometric_watch_bridge.is_stress_critical():
            bio_st = biometric_watch_bridge.get_biometric_state()
            logger.warning(f"[MULTI-ALLOCATOR] Fanout BLOCKED by Biometric Panic Veto! Tilt: {bio_st['biometric_tilt_score']}")
            return {
                "status": "REJECTED_BIOMETRIC_PANIC",
                "reason": f"Acute biometric stress ({bio_st['biometric_tilt_score']}/100) locked all trading terminals.",
                "sub_account_results": []
            }

        results = []
        total_filled_lots = 0.0

        for acc_id, acc in self.accounts.items():
            if not acc.get("is_active"):
                results.append({
                    "account_id": acc_id,
                    "name": acc["name"],
                    "status": "SKIPPED_INACTIVE",
                    "reason": "Account is marked inactive."
                })
                continue

            # Per-Account Daily Max Loss Drawdown Check
            daily_loss = acc.get("current_daily_loss", 0.0)
            max_loss = acc.get("max_daily_loss", 5000.0)
            if daily_loss >= max_loss:
                logger.warning(f"[MULTI-ALLOCATOR] {acc_id} daily loss breached (${daily_loss}/${max_loss}). Skipping.")
                results.append({
                    "account_id": acc_id,
                    "name": acc["name"],
                    "status": "BLOCKED_DRAWDOWN_LIMIT",
                    "reason": f"Account daily loss limit breached (${daily_loss:,.2f} >= ${max_loss:,.2f})."
                })
                continue

            # Scale lot size by account risk multiplier
            scaled_qty = round(base_qty * float(acc.get("risk_multiplier", 1.0)), 2)
            venue = acc.get("venue", "BINANCE").upper()

            if venue == "CME_FIX_DMA":
                # Route via QuickFIX DMA Engine
                fix_res = quickfix_dma_client.send_new_order_single(
                    symbol="ESM6" if "BTC" not in symbol else "BTC",
                    side=side,
                    qty=scaled_qty,
                    price=price
                )
                exec_status = fix_res.get("status", "FAILED")
                latency = fix_res.get("round_trip_latency_us", 350.0)
            else:
                # Route via Binance / OKX Order Router
                sub_order = {
                    "symbol": symbol,
                    "side": side,
                    "qty": scaled_qty,
                    "price": price,
                    "exchange": venue
                }
                router_res = order_router.route_order(sub_order)
                exec_status = router_res.get("status", "FAILED")
                latency = 1200.0

            if exec_status in ("FILLED", "EXECUTED"):
                total_filled_lots += scaled_qty

            results.append({
                "account_id": acc_id,
                "name": acc["name"],
                "venue": venue,
                "allocated_qty": scaled_qty,
                "execution_status": exec_status,
                "latency_us": latency
            })

        logger.info(f"[MULTI-ALLOCATOR] Fanout completed: {len(results)} accounts processed, {total_filled_lots} lots filled.")
        return {
            "status": "FANOUT_COMPLETED",
            "symbol": symbol,
            "side": side,
            "total_allocated_lots": round(total_filled_lots, 2),
            "sub_account_results": results,
            "timestamp": time.time()
        }

multi_account_allocator = MultiAccountRiskAllocator()