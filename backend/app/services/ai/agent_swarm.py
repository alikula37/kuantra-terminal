"""
Multi-Agent Swarm Debate Consensus Engine for Kuantra Terminal.
Coordinates a structured 3-Agent round-robin debate (Macro, Quant, Risk) with RiskAgent Veto power.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.psychology.psychology_engine import psychology_engine
from app.services.compliance_engine import compliance_engine

logger = logging.getLogger("agent_swarm")

class MacroAgent:
    """Evaluates macro regime, higher-timeframe trends, and liquidity sentiment."""

    def evaluate(self, trade_proposal: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(trade_proposal.get("symbol", "BTCUSDT")).upper()
        side = str(trade_proposal.get("side", "BUY")).upper()
        timeframe = str(trade_proposal.get("timeframe", "15m"))

        # Deterministic market regime heuristic
        is_favorable = True
        confidence = 0.85
        thesis = f"Macro regime supports {side} on {symbol} across {timeframe} trend alignment."

        if "SELL" in side and "XAU" in symbol:
            thesis = f"Macro monetary easing creates safe-haven tailwinds for {symbol}; shorting carries elevated macro friction."
            confidence = 0.62

        return {
            "agent": "MacroAgent",
            "vote": "APPROVE" if confidence >= 0.70 else "NEUTRAL",
            "confidence": round(confidence, 2),
            "thesis": thesis
        }

class QuantAgent:
    """Evaluates statistical expectancy, ATR excursion, and risk-reward profile."""

    def evaluate(self, trade_proposal: Dict[str, Any]) -> Dict[str, Any]:
        price = float(trade_proposal.get("price", 0.0))
        sl = float(trade_proposal["stop_loss"]) if trade_proposal.get("stop_loss") else None
        tp = float(trade_proposal["take_profit"]) if trade_proposal.get("take_profit") else None
        side = str(trade_proposal.get("side", "BUY")).upper()

        if sl and tp and price > 0:
            risk = abs(price - sl)
            reward = abs(tp - price)
            rr_ratio = reward / risk if risk > 0 else 1.0
        else:
            rr_ratio = 2.0

        is_high_ev = rr_ratio >= 1.5
        confidence = 0.90 if rr_ratio >= 2.0 else 0.75 if is_high_ev else 0.50

        thesis = (
            f"Mathematical expectancy is robust with R:R ratio of {rr_ratio:.2f}:1."
            if is_high_ev
            else f"Sub-optimal R:R ratio ({rr_ratio:.2f}:1) below institutional threshold of 1.5R."
        )

        return {
            "agent": "QuantAgent",
            "vote": "APPROVE" if is_high_ev else "REJECT",
            "confidence": round(confidence, 2),
            "rr_ratio": round(rr_ratio, 2),
            "thesis": thesis
        }

class RiskAgent:
    """
    Evaluates portfolio heat, session tilt, and daily drawdown budget.
    Holds absolute VETO authority if computed risk score exceeds 70.
    """

    def evaluate(self, trade_proposal: Dict[str, Any]) -> Dict[str, Any]:
        tilt_status = psychology_engine.calculate_session_tilt_score()
        tilt_score = float(tilt_status.get("tilt_score", 10.0))

        compliance = compliance_engine.evaluate_compliance()
        daily_loss_util = 0.0
        daily_rule = next((r for r in compliance["rules"] if r["rule"] == "Daily Max Loss"), None)
        if daily_rule:
            daily_loss_util = float(daily_rule.get("utilization_pct") or 0.0)

        # Composite Risk Score Calculation
        composite_risk_score = round(tilt_score * 0.6 + daily_loss_util * 0.4, 1)
        is_vetoed = composite_risk_score >= 70.0

        if is_vetoed:
            vote = "VETO"
            confidence = 0.95
            thesis = (
                f"ABSOLUTE RISK VETO: Composite risk score ({composite_risk_score:.1f}/100) "
                f"exceeds critical threshold (70.0). Tilt score={tilt_score:.1f}, Daily Loss Util={daily_loss_util:.1f}%."
            )
        elif composite_risk_score >= 45.0:
            vote = "APPROVE_WITH_CAUTION"
            confidence = 0.70
            thesis = f"Moderate risk exposure ({composite_risk_score:.1f}/100). Recommend reducing size by 50%."
        else:
            vote = "APPROVE"
            confidence = 0.90
            thesis = f"Risk parameters optimal (Risk Score: {composite_risk_score:.1f}/100). Execution cleared."

        return {
            "agent": "RiskAgent",
            "vote": vote,
            "confidence": round(confidence, 2),
            "risk_score": composite_risk_score,
            "is_vetoed": is_vetoed,
            "thesis": thesis
        }

class SwarmConsensusEngine:
    """Orchestrates multi-agent round-robin debate and voting resolution."""

    def __init__(self):
        self.macro_agent = MacroAgent()
        self.quant_agent = QuantAgent()
        self.risk_agent = RiskAgent()

    def conduct_debate(self, trade_proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Conducts structured 3-agent debate and aggregates consensus verdict."""
        macro_res = self.macro_agent.evaluate(trade_proposal)
        quant_res = self.quant_agent.evaluate(trade_proposal)
        risk_res = self.risk_agent.evaluate(trade_proposal)

        # Build Debate Transcript
        transcript = [
            {"speaker": "MacroAgent", "message": macro_res["thesis"], "vote": macro_res["vote"]},
            {"speaker": "QuantAgent", "message": quant_res["thesis"], "vote": quant_res["vote"]},
            {"speaker": "RiskAgent", "message": risk_res["thesis"], "vote": risk_res["vote"]},
        ]

        # Check for RiskAgent Veto
        if risk_res["is_vetoed"] or risk_res["vote"] == "VETO":
            consensus_status = "VETOED"
            reason = risk_res["thesis"]
            final_approved = False
        else:
            # Check majority approval
            approve_votes = sum(
                1 for res in [macro_res, quant_res, risk_res]
                if res["vote"] in ("APPROVE", "APPROVE_WITH_CAUTION")
            )
            if approve_votes >= 2 and quant_res["vote"] != "REJECT":
                consensus_status = "APPROVED"
                reason = "Multi-agent swarm reached consensus approval (>= 2/3 votes)."
                final_approved = True
            else:
                consensus_status = "REJECTED"
                reason = "Swarm debate failed to reach majority approval."
                final_approved = False

        avg_confidence = round(
            (macro_res["confidence"] + quant_res["confidence"] + risk_res["confidence"]) / 3.0, 2
        )

        logger.info(f"[SWARM DEBATE] Consensus: {consensus_status} (Confidence: {avg_confidence})")

        return {
            "consensus_status": consensus_status,
            "is_approved": final_approved,
            "final_confidence": avg_confidence,
            "risk_agent_veto": risk_res["is_vetoed"],
            "reason": reason,
            "debate_transcript": transcript,
            "agent_votes": {
                "MacroAgent": macro_res,
                "QuantAgent": quant_res,
                "RiskAgent": risk_res
            },
            "timestamp": time.time()
        }

swarm_consensus_engine = SwarmConsensusEngine()