import pytest
from app.playbook.playbook_service import PlaybookService, playbook_service
from app.quant.execution_drift import ExecutionDriftAnalyzer, execution_drift_analyzer

class TestPlaybookAndExecutionDrift:
    """Test suite for Strategy Playbooks and Execution Drift Analyzer."""

    def test_discipline_score_calculation_perfect_adherence(self):
        rules = [
            {"id": "R1", "rule_text": "HTF Key Level", "is_mandatory": True, "weight": 2.0},
            {"id": "R2", "rule_text": "5m MSS Confirmation", "is_mandatory": True, "weight": 2.0},
            {"id": "R3", "rule_text": "RVOL > 1.5x", "is_mandatory": False, "weight": 1.0},
        ]
        # All rules checked
        res = PlaybookService.calculate_discipline_score(rules, ["R1", "R2", "R3"])
        assert res["score"] == 100.0
        assert res["mandatory_violation"] is False
        assert res["passed_rules"] == 3
        assert res["total_rules"] == 3

    def test_discipline_score_mandatory_rule_violation(self):
        rules = [
            {"id": "R1", "rule_text": "HTF Key Level", "is_mandatory": True, "weight": 2.0},
            {"id": "R2", "rule_text": "5m MSS Confirmation", "is_mandatory": True, "weight": 2.0},
            {"id": "R3", "rule_text": "RVOL > 1.5x", "is_mandatory": False, "weight": 1.0},
        ]
        # Only optional R3 is checked, mandatory R1 & R2 omitted
        res = PlaybookService.calculate_discipline_score(rules, ["R3"])
        assert res["score"] == 20.0  # 1.0 / 5.0 = 20%
        assert res["mandatory_violation"] is True
        assert res["passed_rules"] == 1

    def test_playbook_creation_and_retrieval(self):
        service = PlaybookService()
        pb = service.create_playbook(
            title="VWAP Mean Reversion Scalp",
            description="Testing intraday mean reversion around VWAP bands.",
            win_rate_target=70.0,
            rr_target=2.0,
            rules=[
                {"rule_text": "Price extended > 2 sigma from VWAP", "is_mandatory": True, "weight": 2.0},
                {"rule_text": "Reversal candlestick pattern on 1m", "is_mandatory": False, "weight": 1.0}
            ]
        )
        assert pb is not None
        assert pb["title"] == "VWAP Mean Reversion Scalp"
        assert len(pb["rules"]) == 2

        fetched = service.get_playbook(pb["id"])
        assert fetched["id"] == pb["id"]
        assert fetched["win_rate_target"] == 70.0

    def test_trade_discipline_audit(self):
        service = PlaybookService()
        playbooks = service.list_playbooks()
        assert len(playbooks) > 0
        target_pb = playbooks[0]
        rule_ids = [r["id"] for r in target_pb["rules"]]

        audit = service.audit_trade_discipline(
            trade_id="TRD-AUDIT-999",
            playbook_id=target_pb["id"],
            checked_rule_ids=rule_ids
        )
        assert audit["trade_id"] == "TRD-AUDIT-999"
        assert audit["discipline_score"] == 100.0
        assert audit["mandatory_violation"] is False

    def test_execution_drift_panic_exit_calculation(self):
        trade = {
            "id": "T-DRIFT-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 60000.0,
            "exit_price": 61200.0,  # Exited manually at +1.2R before target
            "stop_loss": 59000.0,   # Risk = $1,000
            "take_profit": 63000.0, # Target = +$3,000 (+3.0R)
            "qty": 1.0,
            "pnl": 1200.0,
            "status": "CLOSED"
        }
        res = ExecutionDriftAnalyzer.analyze_trade_drift(trade)
        assert res["actual_pnl"] == 1200.0
        assert res["theoretical_pnl"] == 3000.0
        assert res["is_early_exit"] is True
        # Panic Exit Cost = Theoretical TP ($3,000) - Actual PnL ($1,200) = $1,800
        assert res["panic_cost"] == 1800.0
        # Drift ratio = (1200 - 3000) / 1000 = -1.8
        assert pytest.approx(res["drift_ratio"], 0.01) == -1.8

    def test_execution_drift_aggregation(self):
        res = execution_drift_analyzer.get_drift_analytics()
        assert "total_trades" in res
        assert "total_panic_exit_leakage" in res
        assert "execution_fidelity_pct" in res
        assert res["total_trades"] > 0