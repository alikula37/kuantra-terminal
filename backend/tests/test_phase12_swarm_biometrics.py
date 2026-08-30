import pytest
from app.services.ai.agent_swarm import swarm_consensus_engine, SwarmConsensusEngine, RiskAgent, QuantAgent, MacroAgent
from app.services.biometrics.watch_bridge import biometric_watch_bridge, BiometricWatchBridge
from app.services.execution.order_router import order_router
from app.services.execution.risk_interceptor import risk_interceptor

class TestPhase12SwarmAndBiometrics:
    """Test suite for Multi-Agent Swarm Debate Consensus and Bluetooth LE Biometric Stress Interceptor."""

    def test_swarm_debate_consensus_approval(self):
        trade_proposal = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 64500.0,
            "stop_loss": 63500.0,
            "take_profit": 67000.0, # 2.5R
            "timeframe": "15m"
        }
        res = swarm_consensus_engine.conduct_debate(trade_proposal)
        assert res["consensus_status"] == "APPROVED"
        assert res["is_approved"] is True
        assert res["risk_agent_veto"] is False
        assert len(res["debate_transcript"]) == 3
        assert res["final_confidence"] >= 0.70

    def test_swarm_debate_risk_agent_veto(self):
        risk_agent = RiskAgent()
        # Evaluate with low rr or extreme risk
        proposal = {"symbol": "ETHUSDT", "side": "SELL", "price": 3200.0, "stop_loss": 3190.0, "take_profit": 3205.0}
        risk_res = risk_agent.evaluate(proposal)
        assert "agent" in risk_res
        assert risk_res["agent"] == "RiskAgent"

    def test_biometric_tilt_score_formula_and_clamping(self):
        # 1. Calm state: BPM 54, HRV 90 -> (54/1.5) + (10*0.6) = 36 + 6 = 42.0
        score_calm = BiometricWatchBridge.calculate_biometric_tilt_score(54.0, 90.0)
        assert score_calm == 42.0
        assert score_calm < 50.0

        # 2. Elevated stress state: BPM 84, HRV 50 -> (84/1.5) + (50*0.6) = 56 + 30 = 86.0
        score_stress = BiometricWatchBridge.calculate_biometric_tilt_score(84.0, 50.0)
        assert score_stress == 86.0
        assert score_stress >= 75.0

        # 3. Extreme clamping: BPM 250 (clamped to 200), HRV 0 (clamped to 5)
        score_extreme = BiometricWatchBridge.calculate_biometric_tilt_score(250.0, 0.0)
        assert score_extreme == 100.0

    def test_biometric_wearable_telemetry_updates(self):
        # Calm update
        calm_st = biometric_watch_bridge.update_telemetry(bpm=56.0, hrv=88.0, device_name="Apple Watch Ultra")
        assert calm_st["is_connected"] is True
        assert calm_st["stress_category"] == "CALM_FLOW_STATE"
        assert calm_st["is_stress_critical"] is False
        assert biometric_watch_bridge.is_stress_critical() is False

        # Panic update
        panic_st = biometric_watch_bridge.update_telemetry(bpm=135.0, hrv=22.0)
        assert panic_st["stress_category"] == "ACUTE_PANIC_TILT"
        assert panic_st["is_stress_critical"] is True
        assert biometric_watch_bridge.is_stress_critical() is True

    def test_pre_trade_interceptor_biometric_and_swarm_blocking(self):
        # 1. Normal order execution when calm
        biometric_watch_bridge.update_telemetry(bpm=58.0, hrv=85.0)
        risk_interceptor.guardrails_active = True
        risk_interceptor.biometrics_gate_active = True
        risk_interceptor.swarm_debate_gate_active = True

        normal_res = order_router.route_order({
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.1,
            "price": 64800.0,
            "stop_loss": 63800.0,
            "take_profit": 67000.0
        })
        assert normal_res["status"] == "EXECUTED"

        # 2. Acute Biometric Panic Veto
        biometric_watch_bridge.update_telemetry(bpm=142.0, hrv=15.0)
        blocked_res = order_router.route_order({
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.1,
            "price": 64800.0
        })
        assert blocked_res["status"] == "REJECTED_RISK_GUARDRAIL"
        assert "ORDER_BLOCKED_BIOMETRIC_STRESS" in blocked_res["reason"]

        # Reset biometrics to calm
        biometric_watch_bridge.update_telemetry(bpm=58.0, hrv=85.0)