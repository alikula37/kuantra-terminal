"""
Multi-Asset Portfolio Aggregator & Risk Exposure Engine for Kuantra Terminal.
Transforms trade journal data into institutional-grade portfolio metrics:
Total Equity, Net PnL, Open R-Risk, Multi-Asset Breakdown, Drawdown,
PnL Calendar Heatmap, and Cumulative Equity Curve.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.core.position_math import instrument_unit_basis
from app.services.market_data.instrument_catalog import instrument_catalog
from app.db.sqlite_driver import sqlite_driver
from app.services.quote_refresh import QuoteRefreshService, quote_refresh_service
from app.services.trade_read_adapter import trade_read_adapter

logger = logging.getLogger("portfolio_service")

FOREX_SYMBOLS = {
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "EURCAD", "GBPCHF"
}

COMMODITY_SYMBOLS = {
    "XAUUSD", "GOLD", "XAGUSD", "SILVER", "WTI", "BRENT", "CRUDE", "CL=F", "GC=F", "SI=F"
}

EQUITY_SYMBOLS = {
    "SPY", "QQQ", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META",
    "SP500", "NASDAQ", "DOW", "^GSPC", "^IXIC", "^DJI"
}


def classify_asset_class(symbol: str) -> str:
    """Categorizes a financial symbol into crypto, forex, commodity, or equity."""
    cleaned = symbol.upper().replace("/", "").replace("_", "").replace("-", "").strip()
    if cleaned in FOREX_SYMBOLS or cleaned.endswith("=X"):
        return "forex"
    if cleaned in COMMODITY_SYMBOLS:
        return "commodity"
    if cleaned in EQUITY_SYMBOLS or cleaned.startswith("^"):
        return "equity"
    return "crypto"


class PortfolioAnalyticsService:
    """
    Unified portfolio aggregator and institutional risk analytics engine.
    Computes real-time exposure, historical equity curve, drawdowns, and multi-asset breakdown.
    Operates strictly with zero-mock data and dynamic user-configured initial balance.
    """

    def __init__(self, default_initial_balance: Optional[float] = None):
        self._default_initial_balance = default_initial_balance

    def get_configured_initial_balance(self) -> float:
        """Retrieves user-configured starting balance from SQLite settings with 0.0 default."""
        if self._default_initial_balance is not None:
            return float(self._default_initial_balance)
        try:
            from app.services.settings_service import settings_service
            settings = settings_service.get_settings()
            if "user_initial_balance" in settings and settings["user_initial_balance"] is not None:
                return float(settings["user_initial_balance"])
            if "initial_balance" in settings and settings["initial_balance"] is not None:
                return float(settings["initial_balance"])
            if "paper_balance" in settings and settings["paper_balance"] is not None:
                return float(settings["paper_balance"])
        except Exception as e:
            logger.debug(f"[PORTFOLIO] Could not retrieve initial balance from settings: {e}")
        return 0.0

    def set_initial_balance(self, new_balance: float) -> Dict[str, Any]:
        """Sets and persists starting equity balance in SQLite settings."""
        from app.services.settings_service import settings_service
        val = max(0.0, float(new_balance))
        settings_service.update_settings({
            "user_initial_balance": val,
            "initial_balance": val,
            "paper_balance": val
        })
        logger.info(f"[PORTFOLIO] Updated user starting balance to ${val:,.2f}")
        return self.get_portfolio_summary(initial_balance=val)

    def get_portfolio_summary(self, initial_balance: Optional[float] = None) -> Dict[str, Any]:
        """
        Computes holistic portfolio health, equity metrics, and open risk exposures.
        Guarantees zero divide-by-zero errors even on empty or initial states.

        A missing PnL (for example an unknown contract size) is never summed as
        a synthetic zero; those trades are counted separately and excluded from
        monetary aggregates.

        ``total_equity`` stays the realized ledger (balance + closed results).
        ``live_equity`` adds the mark-to-market result of open positions whose
        unit is verified and whose quote this server already refreshed, and
        reports its basis: COMPLETE (every open position priced), PARTIAL (some
        excluded, see ``live_positions_unpriced``), or NOT_AVAILABLE (no open
        position could be priced, so ``live_equity`` is null).  Open positions
        without a fetched quote are never valued at their entry price.
        """
        balance = initial_balance if initial_balance is not None else self.get_configured_initial_balance()
        trades = trade_read_adapter.list_trades(limit=100000)

        closed_trades = [t for t in trades if str(t.get("status", "")).upper() == "CLOSED"]
        open_trades = [t for t in trades if str(t.get("status", "")).upper() == "OPEN"]
        known_closed = [t for t in closed_trades if t.get("pnl") is not None]
        unknown_pnl_trades = len(closed_trades) - len(known_closed)

        # 1. Realized Net PnL & Total Equity (known results only)
        net_pnl = sum(float(t["pnl"]) for t in known_closed)
        total_equity = balance + net_pnl
        net_pnl_pct = (net_pnl / balance * 100.0) if balance > 0 else 0.0

        # 2. Today's Realized PnL & Activity
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_closed = [
            t for t in closed_trades
            if (str(t.get("exit_time") or t.get("entry_time") or "")).startswith(today_utc)
        ]
        today_known = [t for t in today_closed if t.get("pnl") is not None]
        today_pnl = sum(float(t["pnl"]) for t in today_known)
        today_pnl_pct = (today_pnl / balance * 100.0) if balance > 0 else 0.0
        today_wins = len([t for t in today_known if float(t["pnl"]) > 0])
        today_losses = len([t for t in today_known if float(t["pnl"]) < 0])
        today_trades_count = {
            "wins": today_wins,
            "losses": today_losses,
            "total": len(today_closed),
            "unknown_pnl": len(today_closed) - len(today_known),
        }

        # 3. Open Positions Risk Exposure Calculation
        open_risk_usd = 0.0
        open_risk_r = 0.0
        unverified_open_positions = 0
        unrealized_pnl_usd = 0.0
        live_positions_covered = 0
        live_positions_unpriced = 0
        live_quotes_stale = False
        oldest_live_age: Optional[float] = None
        oldest_live_observed_at: Optional[str] = None
        query_time = datetime.now(timezone.utc)
        for t in open_trades:
            entry = float(t.get("entry_price") or 0.0)
            qty = float(t.get("qty") or 0.0)
            side = str(t.get("side", "BUY")).upper()
            sl = float(t["stop_loss"]) if t.get("stop_loss") is not None else None
            verified_unit = instrument_unit_basis(
                t.get("symbol"),
                qty_unit=t.get("qty_unit"),
                server_verified=instrument_catalog.is_verified(str(t.get("symbol") or "")),
            )["contract_size"] == "BASE_UNIT"
            if not verified_unit:
                unverified_open_positions += 1
                live_positions_unpriced += 1
                continue

            if sl is not None and sl > 0:
                if side in ("BUY", "LONG"):
                    risk_per_unit = max(0.0, entry - sl)
                else:
                    risk_per_unit = max(0.0, sl - entry)
                trade_dollar_risk = risk_per_unit * qty
            else:
                # Conservative fallback: 2% of position notional value
                trade_dollar_risk = entry * qty * 0.02

            open_risk_usd += trade_dollar_risk
            open_risk_r += 1.0  # 1R planned risk unit per open trade

            # Mark-to-market reads only quotes this server already obtained for
            # the trade's confirmed identity; a missing quote is counted, never
            # replaced with an entry-price zero.
            quote = quote_refresh_service.cached_quote(t)
            if quote is None or quote.get("price") is None:
                live_positions_unpriced += 1
                continue
            direction = 1.0 if side in ("BUY", "LONG") else -1.0
            unrealized_pnl_usd += direction * (float(quote["price"]) - entry) * qty
            live_positions_covered += 1
            if quote.get("stale"):
                live_quotes_stale = True
            age = QuoteRefreshService._age_seconds(quote.get("observed_at"), query_time)
            if age is not None and (oldest_live_age is None or age > oldest_live_age):
                oldest_live_age = age
                oldest_live_observed_at = quote.get("observed_at")

        active_positions_count = len(open_trades)

        if live_positions_unpriced == 0:
            live_equity_basis = "COMPLETE"
        elif live_positions_covered == 0:
            live_equity_basis = "NOT_AVAILABLE"
        else:
            live_equity_basis = "PARTIAL"

        if open_trades and live_positions_covered == 0:
            live_equity: Optional[float] = None
        else:
            live_equity = total_equity + unrealized_pnl_usd
        unrealized_pnl_pct = (unrealized_pnl_usd / balance * 100.0) if balance > 0 else 0.0

        # 4. Win Rate, Profit Factor, and R-Multiple Math
        win_trades = [t for t in known_closed if float(t["pnl"]) > 0]
        loss_trades = [t for t in known_closed if float(t["pnl"]) < 0]
        win_rate = (len(win_trades) / len(known_closed) * 100.0) if known_closed else 0.0

        gross_profit = sum(float(t["pnl"]) for t in win_trades)
        gross_loss = abs(sum(float(t["pnl"]) for t in loss_trades))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 999.0  # Infinite profit factor
        else:
            profit_factor = 0.0

        r_multiples = [
            float(t["r_multiple"])
            for t in closed_trades
            if t.get("r_multiple") is not None
        ]
        avg_r_multiple = (sum(r_multiples) / len(r_multiples)) if r_multiples else None

        if unverified_open_positions == 0:
            open_risk_basis = "COMPLETE"
        elif unverified_open_positions == len(open_trades):
            open_risk_basis = "NOT_AVAILABLE"
        else:
            open_risk_basis = "PARTIAL"

        # 5. Peak-to-Trough Drawdown Calculation
        max_drawdown_usd, max_drawdown_pct = self._calculate_max_drawdown(closed_trades, balance)

        return {
            "initial_balance": round(balance, 2),
            "total_equity": round(total_equity, 2),
            "live_equity": round(live_equity, 2) if live_equity is not None else None,
            "live_equity_basis": live_equity_basis,
            "unrealized_pnl_usd": round(unrealized_pnl_usd, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "live_positions_covered": live_positions_covered,
            "live_positions_unpriced": live_positions_unpriced,
            "live_quotes_stale": live_quotes_stale,
            "oldest_live_quote_age_seconds": round(oldest_live_age, 3) if oldest_live_age is not None else None,
            "oldest_live_quote_observed_at": oldest_live_observed_at,
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "today_pnl": round(today_pnl, 2),
            "today_pnl_pct": round(today_pnl_pct, 2),
            "today_trades_count": today_trades_count,
            "open_risk_usd": round(open_risk_usd, 2),
            "open_risk_r": round(open_risk_r, 2),
            "active_positions_count": active_positions_count,
            "unverified_open_positions": unverified_open_positions,
            "open_risk_basis": open_risk_basis,
            "total_closed_trades": len(closed_trades),
            "unknown_pnl_trades": unknown_pnl_trades,
            "known_r_trades": len(r_multiples),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "profit_factor_basis": "INFINITE_NO_LOSS" if profit_factor >= 999.0 else "READY",
            "avg_r_multiple": round(avg_r_multiple, 2) if avg_r_multiple is not None else None,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _calculate_max_drawdown(self, closed_trades: List[Dict[str, Any]], initial_balance: float) -> (float, float):
        """Calculates maximum peak-to-trough drawdown in USD and percentage."""
        if not closed_trades:
            return 0.0, 0.0

        sorted_trades = sorted(
            closed_trades,
            key=lambda t: str(t.get("exit_time") or t.get("entry_time") or "")
        )

        running_equity = initial_balance
        peak_equity = initial_balance
        max_dd_usd = 0.0
        max_dd_pct = 0.0

        for t in sorted_trades:
            if t.get("pnl") is None:
                # An unknown result cannot move a monetary equity curve.
                continue
            pnl = float(t["pnl"])
            running_equity += pnl
            if running_equity > peak_equity:
                peak_equity = running_equity
            else:
                dd_usd = peak_equity - running_equity
                dd_pct = (dd_usd / peak_equity * 100.0) if peak_equity > 0 else 0.0
                if dd_usd > max_dd_usd:
                    max_dd_usd = dd_usd
                if dd_pct > max_dd_pct:
                    max_dd_pct = dd_pct

        return max_dd_usd, max_dd_pct

    def get_multi_asset_breakdown(self) -> List[Dict[str, Any]]:
        """
        Aggregates performance, volume, and trade metrics grouped by asset symbol.
        Supports heterogeneous assets (Crypto, Forex, Commodities, Equities).
        """
        trades = trade_read_adapter.list_trades(limit=100000)
        grouped: Dict[str, Dict[str, Any]] = {}

        total_portfolio_pnl = sum(
            float(t["pnl"])
            for t in trades
            if str(t.get("status", "")).upper() == "CLOSED" and t.get("pnl") is not None
        )

        for t in trades:
            status = str(t.get("status", "")).upper()
            # CANCELED is an audit tombstone, not a performance observation.
            # Keep it in the journal/evidence chain, but never create a zeroed
            # asset bucket or count it in portfolio performance analytics.
            if status not in {"OPEN", "CLOSED"}:
                continue

            raw_sym = str(t.get("symbol", "UNKNOWN")).upper().strip()
            if not raw_sym:
                continue

            if raw_sym not in grouped:
                grouped[raw_sym] = {
                    "symbol": raw_sym,
                    "asset_class": classify_asset_class(raw_sym),
                    "net_pnl": 0.0,
                    "closed_trades": 0,
                    "open_positions": 0,
                    "wins": 0,
                    "losses": 0,
                    "unknown_pnl_trades": 0,
                    "unverified_unit_trades": 0,
                    "total_volume": 0.0
                }

            entry_price = float(t.get("entry_price") or 0.0)
            qty = float(t.get("qty") or 0.0)
            verified_unit = instrument_unit_basis(
                raw_sym,
                qty_unit=t.get("qty_unit"),
                server_verified=instrument_catalog.is_verified(raw_sym),
            )["contract_size"] == "BASE_UNIT"
            if verified_unit:
                grouped[raw_sym]["total_volume"] += entry_price * qty
            else:
                grouped[raw_sym]["unverified_unit_trades"] += 1

            if status == "CLOSED":
                grouped[raw_sym]["closed_trades"] += 1
                if t.get("pnl") is None:
                    grouped[raw_sym]["unknown_pnl_trades"] += 1
                    continue
                pnl = float(t["pnl"])
                grouped[raw_sym]["net_pnl"] += pnl
                if pnl > 0:
                    grouped[raw_sym]["wins"] += 1
                elif pnl < 0:
                    grouped[raw_sym]["losses"] += 1
            elif status == "OPEN":
                grouped[raw_sym]["open_positions"] += 1

        results = []
        for sym, data in grouped.items():
            closed_cnt = data["closed_trades"]
            known_cnt = closed_cnt - data["unknown_pnl_trades"]
            total_cnt = closed_cnt + data["open_positions"]
            win_rate = (data["wins"] / known_cnt * 100.0) if known_cnt > 0 else 0.0
            pnl_share_pct = (
                (data["net_pnl"] / abs(total_portfolio_pnl) * 100.0)
                if total_portfolio_pnl != 0
                else 0.0
            )

            results.append({
                "symbol": sym,
                "asset_class": data["asset_class"],
                "net_pnl": round(data["net_pnl"], 2),
                "pnl_percentage": round(pnl_share_pct, 2),
                "trade_count": total_cnt,
                "closed_count": closed_cnt,
                "open_positions": data["open_positions"],
                "unknown_pnl_trades": data["unknown_pnl_trades"],
                "unverified_unit_trades": data["unverified_unit_trades"],
                "volume_basis": "PARTIAL" if data["unverified_unit_trades"] else "READY",
                "win_rate": round(win_rate, 2),
                "total_volume": round(data["total_volume"], 2)
            })

        # Sort by trade_count descending, then by volume descending
        results.sort(key=lambda x: (x["trade_count"], x["total_volume"]), reverse=True)
        return results

    def get_equity_curve_series(self, initial_balance: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Builds chronological cumulative equity and drawdown progression time-series.
        Ideal for rendering continuous equity growth charts in the frontend.
        """
        balance = initial_balance if initial_balance is not None else self.get_configured_initial_balance()
        trades = trade_read_adapter.list_trades(limit=100000)
        closed_trades = [t for t in trades if str(t.get("status", "")).upper() == "CLOSED"]

        today_utc = datetime.now(timezone.utc)
        today_str = today_utc.strftime("%Y-%m-%d")
        today_ts = int(today_utc.timestamp() * 1000)

        if not closed_trades:
            return [{
                "timestamp": today_ts,
                "date": today_str,
                "equity": round(balance, 2),
                "drawdown_pct": 0.0,
                "trade_pnl": 0.0,
                "cumulative_pnl": 0.0,
                "symbol": "INITIAL"
            }]

        sorted_trades = sorted(
            closed_trades,
            key=lambda t: str(t.get("exit_time") or t.get("entry_time") or "")
        )

        series: List[Dict[str, Any]] = []
        running_equity = balance
        peak_equity = balance
        cumulative_pnl = 0.0

        first_time_str = str(sorted_trades[0].get("exit_time") or sorted_trades[0].get("entry_time") or "")
        try:
            first_dt = datetime.fromisoformat(first_time_str.replace("Z", "+00:00"))
            baseline_ts = int(first_dt.timestamp() * 1000) - 1
            baseline_date = first_dt.strftime("%Y-%m-%d")
        except Exception:
            baseline_ts = today_ts
            baseline_date = today_str
        series.append({
            "timestamp": baseline_ts,
            "date": baseline_date,
            "equity": round(balance, 2),
            "drawdown_pct": 0.0,
            "trade_pnl": 0.0,
            "cumulative_pnl": 0.0,
            "symbol": "INITIAL",
        })

        for t in sorted_trades:
            if t.get("pnl") is None:
                # Unknown monetary results do not create an equity/drawdown
                # point; they are surfaced through the summary's unknown count.
                continue
            pnl = float(t["pnl"])
            cumulative_pnl += pnl
            running_equity = balance + cumulative_pnl

            if running_equity > peak_equity:
                peak_equity = running_equity

            dd_usd = peak_equity - running_equity
            dd_pct = (dd_usd / peak_equity * 100.0) if peak_equity > 0 else 0.0

            time_str = str(t.get("exit_time") or t.get("entry_time") or "")
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                ts_ms = int(dt.timestamp() * 1000)
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                ts_ms = today_ts
                date_str = today_str

            series.append({
                "timestamp": ts_ms,
                "date": date_str,
                "equity": round(running_equity, 2),
                "drawdown_pct": -round(dd_pct, 2),
                "trade_pnl": round(pnl, 2),
                "cumulative_pnl": round(cumulative_pnl, 2),
                "symbol": str(t.get("symbol", "TRADE")).upper()
            })

        return series

    def get_daily_pnl_heatmap(self) -> List[Dict[str, Any]]:
        """
        Aggregates daily performance into calendar heatmap data with normalized intensity.
        """
        trades = trade_read_adapter.list_trades(limit=100000)
        closed_trades = [t for t in trades if str(t.get("status", "")).upper() == "CLOSED"]

        if not closed_trades:
            return []

        daily_groups: Dict[str, Dict[str, Any]] = {}
        for t in closed_trades:
            if t.get("pnl") is None:
                continue
            time_str = str(t.get("exit_time") or t.get("entry_time") or "")
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            if date_str not in daily_groups:
                daily_groups[date_str] = {
                    "date": date_str,
                    "pnl": 0.0,
                    "trades_count": 0,
                    "wins": 0,
                    "losses": 0
                }

            pnl = float(t["pnl"])
            daily_groups[date_str]["pnl"] += pnl
            daily_groups[date_str]["trades_count"] += 1
            if pnl > 0:
                daily_groups[date_str]["wins"] += 1
            elif pnl < 0:
                daily_groups[date_str]["losses"] += 1

        # Calculate max daily PnL for intensity normalization
        max_abs_pnl = max([abs(g["pnl"]) for g in daily_groups.values()] or [1.0])
        if max_abs_pnl == 0:
            max_abs_pnl = 1.0

        heatmap_list = []
        for date_str in sorted(daily_groups.keys()):
            g = daily_groups[date_str]
            total_cnt = g["trades_count"]
            win_rate = (g["wins"] / total_cnt * 100.0) if total_cnt > 0 else 0.0
            normalized_intensity = round(g["pnl"] / max_abs_pnl, 3)

            heatmap_list.append({
                "date": date_str,
                "pnl": round(g["pnl"], 2),
                "trades_count": total_cnt,
                "wins": g["wins"],
                "losses": g["losses"],
                "win_rate": round(win_rate, 2),
                "intensity": normalized_intensity
            })

        return heatmap_list


# Global Singleton Instance
portfolio_service = PortfolioAnalyticsService()
