"""
Core Quantitative Mathematical Engine for Kuantra Terminal.
Provides pure, deterministic, vectorized financial calculations using NumPy and SciPy.
"""

from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from scipy import stats

class QuantEngine:
    """Pure deterministic quantitative finance calculations engine."""

    @staticmethod
    def calculate_mae_mfe(
        entry_price: float,
        price_series: Union[List[float], np.ndarray],
        side: str = "BUY",
        stop_loss: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE).
        
        Formula:
          MAE_i = min( (P_t - P_entry) / sigma_R )
          MFE_i = max( (P_t - P_entry) / sigma_R )
        """
        if entry_price <= 0:
            return {"mae": 0.0, "mfe": 0.0, "mae_price": 0.0, "mfe_price": 0.0, "risk_unit": 0.0}

        prices = np.asarray(price_series, dtype=np.float64)
        if prices.size == 0:
            prices = np.array([entry_price], dtype=np.float64)

        is_long = side.upper() in ("BUY", "LONG")

        # Determine risk unit sigma_R (initial risk)
        if stop_loss is not None and stop_loss > 0:
            risk_unit = abs(entry_price - stop_loss)
        else:
            # Default 1% risk unit if stop loss not specified
            risk_unit = entry_price * 0.01

        if risk_unit <= 1e-9:
            risk_unit = entry_price * 0.01

        if is_long:
            price_deltas = prices - entry_price
            min_delta = float(np.min(price_deltas))
            max_delta = float(np.max(price_deltas))
            mae_price = float(np.min(prices))
            mfe_price = float(np.max(prices))
            mae = min_delta / risk_unit
            mfe = max_delta / risk_unit
        else:
            price_deltas = entry_price - prices
            min_delta = float(np.min(price_deltas))
            max_delta = float(np.max(price_deltas))
            mae_price = float(np.max(prices))
            mfe_price = float(np.min(prices))
            mae = min_delta / risk_unit
            mfe = max_delta / risk_unit

        return {
            "mae": round(float(mae), 4),
            "mfe": round(float(mfe), 4),
            "mae_price": round(float(mae_price), 4),
            "mfe_price": round(float(mfe_price), 4),
            "risk_unit": round(float(risk_unit), 4)
        }

    @staticmethod
    def calculate_exit_efficiency(
        entry_price: float,
        exit_price: float,
        mfe_price: float,
        side: str = "BUY"
    ) -> float:
        """
        Calculate Best-Exit Efficiency Ratio.
        
        Formula:
          E_exit = (P_exit - P_entry) / (P_MFE - P_entry)
        """
        is_long = side.upper() in ("BUY", "LONG")
        
        if is_long:
            actual_move = exit_price - entry_price
            potential_move = mfe_price - entry_price
        else:
            actual_move = entry_price - exit_price
            potential_move = entry_price - mfe_price

        if abs(potential_move) < 1e-9:
            return 1.0 if abs(actual_move) < 1e-9 else 0.0

        efficiency = actual_move / potential_move
        return round(float(np.clip(efficiency, -10.0, 10.0)), 4)

    @staticmethod
    def calculate_sqn(r_multiples: Union[List[float], np.ndarray]) -> float:
        """
        Calculate Van Tharp System Quality Number (SQN).
        
        Formula:
          SQN = sqrt(N) * (mean(R) / std(R))
        """
        r = np.asarray(r_multiples, dtype=np.float64)
        r = r[~np.isnan(r)]
        n = len(r)
        
        if n < 2:
            return 0.0

        mean_r = float(np.mean(r))
        std_r = float(np.std(r, ddof=1))

        if std_r < 1e-9:
            return 0.0

        sqn = np.sqrt(n) * (mean_r / std_r)
        return round(float(sqn), 4)

    @staticmethod
    def calculate_sharpe_ratio(
        returns: Union[List[float], np.ndarray],
        risk_free_rate: float = 0.0,
        annualization_factor: float = 252.0
    ) -> float:
        """
        Calculate Sharpe Ratio.
        
        Formula:
          Sharpe = E[R_p - R_f] / sigma_p * sqrt(periods)
        """
        ret = np.asarray(returns, dtype=np.float64)
        ret = ret[~np.isnan(ret)]
        if len(ret) < 2:
            return 0.0

        excess_returns = ret - (risk_free_rate / annualization_factor)
        mean_excess = float(np.mean(excess_returns))
        std_dev = float(np.std(excess_returns, ddof=1))

        if std_dev < 1e-9:
            return 0.0

        sharpe = (mean_excess / std_dev) * np.sqrt(annualization_factor)
        return round(float(sharpe), 4)

    @staticmethod
    def calculate_sortino_ratio(
        returns: Union[List[float], np.ndarray],
        target_return: float = 0.0,
        annualization_factor: float = 252.0
    ) -> float:
        """
        Calculate Downside-only Sortino Ratio.
        
        Formula:
          Sortino = E[R_p - R_f] / sigma_d * sqrt(periods)
          where sigma_d = sqrt( mean( min(0, R_i - target)^2 ) )
        """
        ret = np.asarray(returns, dtype=np.float64)
        ret = ret[~np.isnan(ret)]
        if len(ret) < 2:
            return 0.0

        excess_returns = ret - (target_return / annualization_factor)
        mean_excess = float(np.mean(excess_returns))
        
        downside_diff = np.minimum(0.0, excess_returns)
        downside_variance = float(np.mean(downside_diff ** 2))
        downside_std = np.sqrt(downside_variance)

        if downside_std < 1e-9:
            # If there are positive returns with zero downside, return high positive ratio
            return round(float(mean_excess * np.sqrt(annualization_factor) * 10.0), 4) if mean_excess > 0 else 0.0

        sortino = (mean_excess / downside_std) * np.sqrt(annualization_factor)
        return round(float(sortino), 4)

    @staticmethod
    def calculate_expectancy(
        win_rate: float,
        avg_win: float,
        loss_rate: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Mathematical Expectancy (EV) per trade.
        
        Formula:
          EV = (WinRate * AvgWin) - (LossRate * AvgLoss)
        """
        # Ensure rates sum to 1.0 or convert percentage
        if win_rate > 1.0 or loss_rate > 1.0:
            win_rate = win_rate / 100.0
            loss_rate = loss_rate / 100.0

        ev = (win_rate * abs(avg_win)) - (loss_rate * abs(avg_loss))
        return round(float(ev), 4)

    @staticmethod
    def calculate_max_drawdown(equity_series: Union[List[float], np.ndarray]) -> Dict[str, float]:
        """Calculate Maximum Drawdown (MDD) in dollars and percentage."""
        eq = np.asarray(equity_series, dtype=np.float64)
        if eq.size == 0:
            return {"max_drawdown_amount": 0.0, "max_drawdown_pct": 0.0}

        running_max = np.maximum.accumulate(eq)
        drawdowns = eq - running_max
        max_dd_amount = float(np.min(drawdowns))  # negative or zero

        # Percentage drawdown
        with np.errstate(divide='ignore', invalid='ignore'):
            pct_drawdowns = np.where(running_max > 0, drawdowns / running_max, 0.0)
        max_dd_pct = float(np.min(pct_drawdowns)) * 100.0

        return {
            "max_drawdown_amount": round(abs(max_dd_amount), 2),
            "max_drawdown_pct": round(abs(max_dd_pct), 2)
        }

    @classmethod
    def calculate_full_performance_suite(
        cls,
        pnls: List[float],
        r_multiples: Optional[List[float]] = None,
        initial_capital: float = 10000.0
    ) -> Dict[str, Any]:
        """Compute holistic institutional quant score card."""
        arr = np.asarray(pnls, dtype=np.float64)
        n = len(arr)
        if n == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "sqn": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "kelly_pct": 0.0
            }

        wins = arr[arr > 0]
        losses = arr[arr < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = win_count / n
        loss_rate = loss_count / n

        avg_win = float(np.mean(wins)) if win_count > 0 else 0.0
        avg_loss = float(abs(np.mean(losses))) if loss_count > 0 else 0.0

        gross_profit = float(np.sum(wins)) if win_count > 0 else 0.0
        gross_loss = float(np.sum(np.abs(losses))) if loss_count > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        ev = cls.calculate_expectancy(win_rate, avg_win, loss_rate, avg_loss)

        # Equity curve & drawdowns
        equity = initial_capital + np.cumsum(arr)
        dd_stats = cls.calculate_max_drawdown(equity)

        # Returns series for Sharpe / Sortino
        returns = arr / initial_capital
        sharpe = cls.calculate_sharpe_ratio(returns)
        sortino = cls.calculate_sortino_ratio(returns)

        # SQN from R-multiples or normalized PnL
        r_series = r_multiples if (r_multiples and len(r_multiples) == n) else (arr / (avg_loss if avg_loss > 0 else 1.0))
        sqn = cls.calculate_sqn(r_series)

        # Half-Kelly Criterion
        win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 1.0
        kelly = (win_rate - ((1.0 - win_rate) / win_loss_ratio)) if win_loss_ratio > 0 else 0.0
        half_kelly_pct = max(0.0, min(100.0, (kelly / 2.0) * 100.0))

        return {
            "total_trades": n,
            "win_rate": round(win_rate * 100.0, 2),
            "loss_rate": round(loss_rate * 100.0, 2),
            "total_pnl": round(float(np.sum(arr)), 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(ev, 2),
            "sqn": round(sqn, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown_amount": dd_stats["max_drawdown_amount"],
            "max_drawdown_pct": dd_stats["max_drawdown_pct"],
            "half_kelly_pct": round(half_kelly_pct, 2)
        }

quant_engine = QuantEngine()