"""
Institutional Pre-Trade Risk Guardrail Interceptor.
Validates orders across Biometric Wearable Stress, Multi-Agent Swarm Debate, Session Tilt, and Prop Firm Rules.
"""

import logging
from typing import Dict, Any, Tuple
from app.psychology.psychology_engine import psychology_engine
from app.services.compliance_engine import compliance_engine
from app.services.biometrics.watch_bridge import biometric_watch_bridge
from app.services.ai.agent_swarm import swarm_consensus_engine

logger = logging.getLogger("risk_interceptor")

class RiskGuardrailInterceptor:
    """Multi-layer pre-trade risk interception guardian."""

    def __init__(self):
        self.max_allowed_tilt_score: float = 75.0
        self.guardrails_active: bool = True
        self.biometrics_gate_active: bool = True
        self.swarm_debate_gate_active: bool = True

    def evaluate_order(self, order: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Comprehensive pre-trade safety inspection:
        1. Biometric Wearable Stress Interceptor (BPM/HRV)
        2. Multi-Agent Swarm Debate Consensus (Macro, Quant, Risk Veto)
        3. Behavioral Psychology Session Tilt (FOMO/Revenge)
        4. Prop Firm Compliance Shield (Drawdowns/Daily Loss)
        """
        symbol = str(order.get("symbol", "BTCUSDT")).upper()
        side = str(order.get("side", "BUY")).upper()
        qty = float(order.get("qty", 1.0))
        price = float(order.get("price", 0.0))

        # 1. Biometric Wearable Stress Interceptor
        bio_state = biometric_watch_bridge.get_biometric_state()
        if self.guardrails_active and self.biometrics_gate_active and bio_state.get("is_stress_critical"):
            reason = (
                f"ORDER_BLOCKED_BIOMETRIC_STRESS: Physiological tilt score ({bio_state['biometric_tilt_score']}/100) "
                f"exceeds critical threshold. Heart Rate: {bio_state['bpm']} BPM, HRV: {bio_state['hrv_ms']}ms."
            )
            logger.warning(f"[RISK INTERCEPTOR] {reason}")
            return False, reason, {"biometrics": bio_state, "stage": "BIOMETRIC_GUARD"}

        # 2. Multi-Agent Swarm Debate Consensus
        if self.guardrails_active and self.swarm_debate_gate_active:
            swarm_res = swarm_consensus_engine.conduct_debate(order)
            if not swarm_res["is_approved"] or swarm_res["consensus_status"] == "VETOED":
                reason = f"ORDER_BLOCKED_SWARM_VETO: {swarm_res['reason']}"
                logger.warning(f"[RISK INTERCEPTOR] {reason}")
                return False, reason, {"swarm": swarm_res, "stage": "SWARM_DEBATE_GUARD"}
        else:
            swarm_res = {"consensus_status": "BYPASSED", "final_confidence": 1.0}

        # 3. Behavioral Psychology Tilt Check
        tilt_status = psychology_engine.calculate_session_tilt_score()
        tilt_score = float(tilt_status.get("tilt_score", 0.0))

        if self.guardrails_active and tilt_score >= self.max_allowed_tilt_score:
            reason = (
                f"ORDER_BLOCKED_HIGH_TILT: Session Tilt Score ({tilt_score:.1f}/100) "
                f"exceeds safety threshold ({self.max_allowed_tilt_score})."
            )
            logger.warning(f"[RISK INTERCEPTOR] {reason}")
            return False, reason, {"tilt_score": tilt_score, "stage": "PSYCHOLOGY_GUARD"}

        # 4. Prop Firm Compliance Shield Check
        compliance_status = compliance_engine.evaluate_compliance()
        if compliance_status.get("status") == "BREACHED":
            reason = "ORDER_BLOCKED_PROP_FIRM_BREACH: Prop Firm Compliance Shield daily/max drawdown breached."
            logger.warning(f"[RISK INTERCEPTOR] {reason}")
            return False, reason, {"compliance": compliance_status, "stage": "PROP_FIRM_GUARD"}

        logger.info(f"[RISK INTERCEPTOR] Order APPROVED: {side} {qty} {symbol} (Biometric Tilt: {bio_state['biometric_tilt_score']}, Swarm: {swarm_res['consensus_status']})")
        return True, "APPROVED_ALL_GUARDRAILS_PASSED", {
            "biometric_tilt": bio_state["biometric_tilt_score"],
            "swarm_consensus": swarm_res["consensus_status"],
            "session_tilt": tilt_score,
            "stage": "CLEARED"
        }

risk_interceptor = RiskGuardrailInterceptor()