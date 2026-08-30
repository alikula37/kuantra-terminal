import pytest
from app.ai.vision_service import VisionChartParser, vision_chart_parser
from app.ai.ai_auditor import AiTradeAuditor, ai_auditor
from app.ai.ai_query_engine import AiQueryEngine, ai_query_engine

class TestAiAndVisionServices:
    """Test suite for Vision OCR, AI Auditor, and Natural Language Query Engine."""

    def test_vision_ocr_long_trade_parsing(self):
        sample_ocr = "BTCUSDT 15m Long Setup Entry: 64000.00 Stop: 63000.00 Target: 67000.00"
        res = vision_chart_parser.parse_chart_screenshot(hint_text=sample_ocr)
        
        assert res["symbol"] == "BTCUSDT"
        assert res["timeframe"] == "15m"
        assert res["side"] == "BUY"
        assert res["entry_price"] == 64000.0
        assert res["stop_loss"] == 63000.0
        assert res["take_profit"] == 67000.0
        # Risk = 1000, Reward = 3000 -> RR = 3.0
        assert res["risk_unit"] == 1000.0
        assert res["reward_unit"] == 3000.0
        assert res["risk_reward_ratio"] == 3.0
        assert res["confidence_score"] >= 0.8

    def test_vision_ocr_short_trade_and_inversion_validation(self):
        # OCR has stop and target inverted or short keywords
        sample_ocr = "ETHUSDT 5m Short Position Entry: 3200.00 Stop: 3300.00 Target: 2900.00"
        res = vision_chart_parser.parse_chart_screenshot(hint_text=sample_ocr)
        
        assert res["symbol"] == "ETHUSDT"
        assert res["side"] == "SELL"
        assert res["entry_price"] == 3200.0
        assert res["stop_loss"] == 3300.0
        assert res["take_profit"] == 2900.0
        # Risk = 100, Reward = 300 -> RR = 3.0
        assert res["risk_reward_ratio"] == 3.0

    def test_vision_ocr_price_sanity_auto_correction(self):
        # Long trade with Stop Loss erroneously higher than Entry
        res = VisionChartParser.validate_and_sanitize_prices(
            symbol="BTCUSDT",
            side="BUY",
            entry=65000.0,
            sl=66000.0,  # Invalid SL for LONG
            tp=64000.0   # Invalid TP for LONG
        )
        assert res["stop_loss"] < res["entry_price"]
        assert res["take_profit"] > res["entry_price"]
        assert "Corrected" in res["notes"]

    def test_ai_auditor_deterministic_context_generation(self):
        ctx = ai_auditor.generate_audit_context()
        required_keys = [
            "account_equity", "high_watermark", "sqn", "win_rate_pct",
            "sharpe_ratio", "sortino_ratio", "expectancy", "profit_factor",
            "session_tilt_score", "fatigue_inflection_point"
        ]
        for k in required_keys:
            assert k in ctx
            assert ctx[k] is not None

    def test_ai_auditor_report_synthesis(self):
        report = ai_auditor.generate_audit_report()
        assert "grade" in report
        assert report["grade"] in ["A+", "A", "B+", "B", "C", "D", "F"]
        assert len(report["executive_summary"]) > 20
        assert len(report["strengths"]) > 0
        assert len(report["critical_risks"]) > 0
        assert len(report["actionable_directives"]) > 0

    def test_natural_language_ai_query_sql_generation(self):
        # Query 1: Worst trades
        res1 = ai_query_engine.execute_natural_query("Show worst trades on BTCUSDT")
        assert "trades" in res1["sql"]
        assert "pnl" in res1["sql"].lower()
        assert "columns" in res1
        assert "ai_commentary" in res1

        # Query 2: High R-Multiple
        res2 = ai_query_engine.execute_natural_query("Show trades with r_multiple >= 2")
        assert "r_multiple" in res2["sql"]

        # Query 3: Default asset summary
        res3 = ai_query_engine.execute_natural_query("Summarize asset breakdown")
        assert "GROUP BY" in res3["sql"]