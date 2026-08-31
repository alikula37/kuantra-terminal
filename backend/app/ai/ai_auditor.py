"""
Deterministic AI Trade Auditor & Executive Coach for Kuantra Terminal.
Compiles 100% verified mathematical snapshots and generates non-hallucinated institutional directives.
"""

from typing import Dict, Any, List, Optional
import json
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.quant.quant_engine import quant_engine
from app.quant.mae_mfe import mae_mfe_analyzer
from app.quant.execution_drift import execution_drift_analyzer
from app.services.compliance_engine import compliance_engine
from app.psychology.psychology_engine import psychology_engine

class AiTradeAuditor:
    """Aggregates deterministic terminal telemetry and generates structured risk audit reports."""

    @classmethod
    def generate_audit_context(cls) -> Dict[str, Any]:
        """Gathers full mathematical context across all trading modules with 0% hallucination."""
        # 1. Closed trades & Performance Scorecard
        all_closed = [t for t in sqlite_driver.list_trades(limit=1000, status="CLOSED") if t.get("pnl") is not None]
        pnls = [float(t["pnl"]) for t in all_closed]
        r_mults = [float(t["r_multiple"]) for t in all_closed if t.get("r_multiple") is not None]

        scorecard = quant_engine.calculate_full_performance_suite(
            pnls,
            r_multiples=r_mults if len(r_mults) == len(pnls) else None
        )

        # 2. Compliance & Drawdown State
        open_positions = sqlite_driver.get_open_trades()
        compliance_state = compliance_engine.evaluate_compliance(open_positions)

        # 3. MAE / MFE Excursion & Best-Exit Efficiency
        mae_mfe_data = mae_mfe_analyzer.get_mae_mfe_scatter_data()

        # 4. Execution Drift & Panic Exit Leakage
        drift_data = execution_drift_analyzer.get_drift_analytics()

        # 5. Behavioral Psychology & Tilt State
        tilt_state = psychology_engine.calculate_session_tilt_score()
        fatigue_state = psychology_engine.compute_mental_fatigue_matrix()
        anomalies_data = psychology_engine.get_all_anomalies()

        return {
            "account_equity": compliance_state.get("current_equity", 0.0),
            "high_watermark": compliance_state.get("high_watermark", 0.0),
            "current_drawdown_pct": compliance_state.get("current_drawdown_pct", 0.0),
            "daily_loss_utilization_pct": compliance_state.get("rules", [{}])[0].get("utilization_pct", 0.0) if compliance_state.get("rules") else 0.0,
            "overall_compliance_status": compliance_state.get("overall_status", "NOMINAL"),
            "total_trades_count": scorecard.get("total_trades", 0),
            "win_rate_pct": scorecard.get("win_rate", 0.0),
            "sqn": scorecard.get("sqn", 0.0),
            "sharpe_ratio": scorecard.get("sharpe_ratio", 0.0),
            "sortino_ratio": scorecard.get("sortino_ratio", 0.0),
            "expectancy": scorecard.get("expectancy", 0.0),
            "profit_factor": scorecard.get("profit_factor", 0.0),
            "avg_exit_efficiency_pct": mae_mfe_data.get("average_exit_efficiency_pct", 0.0),
            "recommended_target_r": mae_mfe_data.get("recommended_target_r", 2.0),
            "trades_left_money_on_table": mae_mfe_data.get("trades_left_money_on_table", 0),
            "total_panic_exit_leakage_dollars": drift_data.get("total_panic_exit_leakage", 0.0),
            "execution_fidelity_pct": drift_data.get("execution_fidelity_pct", 100.0),
            "session_tilt_score": tilt_state.get("tilt_score", 0.0),
            "tilt_status": tilt_state.get("status", "OPTIMAL"),
            "consecutive_losses": tilt_state.get("consecutive_losses", 0),
            "revenge_trades_count": tilt_state.get("revenge_trades_count", 0),
            "fomo_trades_count": tilt_state.get("fomo_trades_count", 0),
            "fatigue_inflection_point": fatigue_state.get("inflection_point", 0),
            "performance_decay_pct": fatigue_state.get("performance_decay_pct", 0.0),
            "total_anomalies_count": anomalies_data.get("total_anomalies_count", 0)
        }

    @classmethod
    def generate_audit_report(cls) -> Dict[str, Any]:
        """Synthesizes deterministic context into executive structured coaching analysis."""
        ctx = cls.generate_audit_context()

        # Deterministic Grade Calculation
        sqn = ctx["sqn"]
        win_rate = ctx["win_rate_pct"]
        tilt = ctx["session_tilt_score"]
        is_breached = ctx["overall_compliance_status"] == "BREACHED"

        if is_breached or tilt >= 80:
            grade = "F"
        elif sqn >= 2.5 and win_rate >= 60.0 and tilt < 30:
            grade = "A+"
        elif sqn >= 2.0 and win_rate >= 55.0 and tilt < 40:
            grade = "A"
        elif sqn >= 1.5 and tilt < 60:
            grade = "B+"
        elif sqn >= 1.0:
            grade = "B"
        else:
            grade = "C"

        # Formulate Non-Hallucinated Strengths
        strengths = []
        if ctx["sqn"] >= 1.5:
            strengths.append(f"Statistically robust System Quality Number (SQN = {ctx['sqn']}), indicating high edge reproducibility.")
        if ctx["avg_exit_efficiency_pct"] >= 65.0:
            strengths.append(f"Solid exit efficiency of {ctx['avg_exit_efficiency_pct']}%, capturing majority of potential MFE price moves.")
        if ctx["profit_factor"] >= 2.0:
            strengths.append(f"Exceptional gross profit-to-loss factor of {ctx['profit_factor']}.")
        if ctx["session_tilt_score"] < 30:
            strengths.append("High psychological discipline with session Tilt Score under 30 (CALM state).")
        if not strengths:
            strengths.append("Baseline trade logging active and connected to real-time risk controls.")

        # Formulate Critical Vulnerabilities
        risks = []
        if ctx["total_panic_exit_leakage_dollars"] > 0:
            risks.append(f"Execution Leakage: -${ctx['total_panic_exit_leakage_dollars']:,.2f} lost to manual premature exits before reaching planned Take Profit.")
        if ctx["fomo_trades_count"] > 0:
            risks.append(f"FOMO Chasing: {ctx['fomo_trades_count']} trades flagged with entry price >2.5x ATR away from EMA20.")
        if ctx["revenge_trades_count"] > 0:
            risks.append(f"Revenge Trading: {ctx['revenge_trades_count']} rapid re-entries (<180s) with escalated position sizing after losses.")
        if ctx["performance_decay_pct"] > 25.0:
            risks.append(f"Mental Fatigue: Performance decays by -{ctx['performance_decay_pct']}% beyond {ctx['fatigue_inflection_point']}.")
        if not risks:
            risks.append("No critical psychological or execution vulnerabilities detected.")

        # Formulate Actionable Directives
        directives = [
            f"Cap maximum trades per session to {ctx['fatigue_inflection_point']} to avoid the {ctx['performance_decay_pct']}% late-session win rate drop.",
            f"Enforce minimum +{ctx['recommended_target_r']}R take-profit orders based on 75th percentile MFE distribution clusters.",
            "Implement mandatory 180-second cool-off lock after any stop loss hit to eliminate revenge execution."
        ]

        summary = (
            f"Terminal account is currently operating with a {ctx['overall_compliance_status']} compliance standing "
            f"at an SQN of {ctx['sqn']} and a Win Rate of {ctx['win_rate_pct']}%. "
            f"Psychological telemetry registers a Tilt Score of {ctx['session_tilt_score']} ({ctx['tilt_status']}). "
            f"Main optimization focus: eliminate ${ctx['total_panic_exit_leakage_dollars']:,.2f} of early-exit drag."
        )

        return {
            "grade": grade,
            "executive_summary": summary,
            "strengths": strengths,
            "critical_risks": risks,
            "actionable_directives": directives,
            "deterministic_context": ctx
        }

ai_auditor = AiTradeAuditor()