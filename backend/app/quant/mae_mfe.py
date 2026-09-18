"""Descriptive MAE/MFE on complete recorded bars, with explicit evidence limits."""

from typing import Any

from app.db.sqlite_driver import sqlite_driver
from app.quant.candle_evidence import (
    EvidenceError, excursion_metrics, finite_number, load_candle_evidence, provenance,
)


class MaeMfeAnalyzer:
    @staticmethod
    def analyze_trade_excursion(trade: dict[str, Any], candles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        try:
            evidence = load_candle_evidence(trade, candles)
        except EvidenceError as error:
            return {
                **error.to_dict(), "trade_id": str(trade.get("id", "")),
                "risk_unit": None, "mae_price": None, "mfe_price": None,
                "mae_r": None, "mfe_r": None, "exit_efficiency": None, "r_multiple": None,
            }
        normalized = evidence.trade
        return {
            "status": "READY", "reason": None, "message": None, "provenance": provenance(),
            "trade_id": str(normalized["id"]), "trade_status": normalized["status"],
            **{key: normalized[key] for key in (
                "symbol", "side", "entry_price", "exit_price", "stop_loss", "take_profit",
                "risk_unit", "risk_reason", "pnl", "entry_time", "exit_time",
            )},
            "bar_count": len(evidence.trade_candles),
            **excursion_metrics(normalized, evidence.trade_candles, closed=True),
        }

    @classmethod
    def get_mae_mfe_scatter_data(cls, symbol: str | None = None) -> dict[str, Any]:
        """Analyze at most the 1,000 latest closed trades; never fill missing history.

        Stop distances describe the observed bar distribution only. They are
        neither counterfactual stop simulations nor optimized recommendations.
        """
        store_error = None
        try:
            candidates = [
                t for t in sqlite_driver.list_trades(limit=1000, symbol=symbol, status="CLOSED", order_by_utc=True)
                if str(t.get("record_mode") or "").upper() != "SIMULATION"
            ]
        except Exception:
            candidates = []
            store_error = EvidenceError("TRADE_STORE_UNAVAILABLE", "The recorded trade store could not be read.", "UNAVAILABLE")
        points, excluded = [], []
        for trade in candidates:
            point = cls.analyze_trade_excursion(trade)
            if point["status"] == "READY":
                points.append(point)
            else:
                excluded.append({key: point[key] for key in ("trade_id", "status", "reason", "message")})
        r_points = [p for p in points if all(p[key] is not None for key in ("mae_r", "mfe_r", "r_multiple"))]

        def average(key: str, values: list[dict[str, Any]], multiplier: float = 1.0) -> float | None:
            numbers = [p[key] for p in values if p[key] is not None]
            # Divide before adding to avoid overflow for finite extreme inputs.
            return finite_number(sum(n / len(numbers) for n in numbers) * multiplier) if numbers else None

        status = "READY" if points else "UNAVAILABLE" if store_error or any(p["status"] == "UNAVAILABLE" for p in excluded) else "NO_DATA"
        return {
            "status": status,
            "reason": store_error.reason if store_error else None if points else "NO_ELIGIBLE_TRADES",
            "message": store_error.message if store_error else None if points else "No closed trades have complete, valid recorded candle history.",
            "provenance": {**provenance(), "stop_sensitivity_basis": "DESCRIPTIVE_BAR_DISTRIBUTION_NOT_STOP_SIMULATION"},
            "candidate_limit": 1000, "candidate_selection": "LATEST_CLOSED_BY_UTC_ENTRY_TIME",
            "total_candidates": len(candidates), "total_analyzed": len(points), "total_r_analyzed": len(r_points),
            "excluded_trades": excluded,
            "average_mae_r": average("mae_r", r_points), "average_mfe_r": average("mfe_r", r_points),
            "average_exit_efficiency_pct": average("exit_efficiency", points, 100),
            "trades_left_money_on_table": sum(1 for p in r_points if p["mfe_r"] >= 2 and p["r_multiple"] <= 0.5),
            "recommended_target_r": None,
            "recommendation_status": "UNAVAILABLE_NOT_VALIDATED",
            "stop_loss_sensitivities": [
                {"stop_distance_r": distance, "survival_rate_pct": round(100 * sum(abs(p["mae_r"]) < distance for p in r_points) / len(r_points), 1), "sample_size": len(r_points)}
                for distance in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
            ] if r_points else [],
            "points": points,
        }


mae_mfe_analyzer = MaeMfeAnalyzer()
