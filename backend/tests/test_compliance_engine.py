import pytest
from app.services.compliance_engine import ComplianceEngine, ComplianceConfig

class TestComplianceEngine:
    """Test suite for Prop Firm Risk & Compliance Engine."""

    def test_default_config_initialization(self):
        engine = ComplianceEngine()
        assert engine.config.account_size == 100000.0
        assert engine.config.daily_loss_limit_pct == 5.0  # $5,000
        assert engine.config.max_drawdown_pct == 10.0     # $10,000

    def test_daily_loss_and_warning_thresholds(self):
        engine = ComplianceEngine()
        engine.update_config({"account_size": 100000.0, "daily_loss_limit_pct": 5.0})
        # Daily budget = $5,000

        # Scenario 1: Normal safe trade ($1,000 open loss = 20% utilization)
        mock_positions = [{"id": "P1", "unrealized_pnl": -1000.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=[])
        assert res["overall_status"] == "COMPLIANT"
        assert res["daily_loss_remaining"] == 4000.0

        # Scenario 2: Warning threshold ($3,600 open loss = 72% utilization >= 70%)
        mock_positions = [{"id": "P1", "unrealized_pnl": -3600.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=[])
        assert res["overall_status"] == "WARNING"
        assert res["rules"][0]["status"] == "WARN"

        # Scenario 3: Critical threshold ($4,600 open loss = 92% utilization >= 90%)
        mock_positions = [{"id": "P1", "unrealized_pnl": -4600.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=[])
        assert res["overall_status"] == "CRITICAL"
        assert res["rules"][0]["status"] == "CRITICAL"

        # Scenario 4: Breach threshold ($5,100 open loss >= $5,000 limit)
        mock_positions = [{"id": "P1", "unrealized_pnl": -5100.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=[])
        assert res["overall_status"] == "BREACHED"
        assert res["is_breached"] is True
        assert res["rules"][0]["status"] == "BREACH"

    def test_overall_max_drawdown_trailing(self):
        engine = ComplianceEngine()
        engine.update_config({"account_size": 100000.0, "max_drawdown_pct": 10.0, "trailing_drawdown": True})
        # Simulate previous closed trades bringing balance to $110,000 high watermark
        closed = [{"pnl": 10000.0, "exit_time": "2026-08-29T12:00:00"}]
        engine.high_watermark = 110000.0
        # Drawdown budget is $10,000 (breach below $100,000)

        # Equity drops to $102,000 (DD = $8,000 -> 80% utilization = WARN)
        mock_positions = [{"id": "P1", "unrealized_pnl": -8000.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=closed)
        assert res["current_drawdown_amount"] == 8000.0
        assert res["rules"][1]["status"] == "WARN"

        # Equity drops to $99,000 (DD = $11,000 >= $10,000 budget -> BREACH)
        mock_positions = [{"id": "P1", "unrealized_pnl": -11000.0, "stop_loss": 60000.0, "entry_time": "2026-08-30T10:00:00"}]
        res = engine.evaluate_compliance(mock_positions, closed_trades=closed)
        assert res["is_breached"] is True
        assert res["rules"][1]["status"] == "BREACH"

    def test_mandatory_stop_loss_naked_position_detector(self):
        engine = ComplianceEngine()
        engine.update_config({"require_stop_loss": True})

        # Position with missing stop loss
        naked_positions = [
            {"id": "P1", "unrealized_pnl": 100.0, "stop_loss": None, "entry_time": "2026-08-30T10:00:00"},
            {"id": "P2", "unrealized_pnl": 50.0, "stop_loss": 62000.0, "entry_time": "2026-08-30T10:00:00"}
        ]
        res = engine.evaluate_compliance(naked_positions, closed_trades=[])
        assert res["naked_positions_count"] == 1
        assert res["rules"][2]["status"] == "BREACH"

    def test_profit_target_completion(self):
        engine = ComplianceEngine()
        engine.update_config({"account_size": 100000.0, "profit_target_pct": 10.0})
        res = engine.evaluate_compliance([], closed_trades=[])
        assert "Profit Target" in [r["rule"] for r in res["rules"]]