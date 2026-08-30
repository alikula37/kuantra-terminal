import pytest
from app.services.mcp.client_gateway import mcp_gateway, FinancialMCPGateway
from app.services.ai.reverse_skill import reverse_skill_engine, ReverseSkillTranspiler

class TestPhase17MCPAndReverseSkill:
    """Test suite for Financial MCP Gateway (BlockRunAI) and Reverse-Skill Strategy Transpiler (zhaoxuya520)."""

    def test_mcp_gateway_sources_and_dispatch(self):
        gateway = FinancialMCPGateway()
        sources_meta = gateway.list_sources()
        assert sources_meta["total_sources"] == 4
        assert "sec_edgar" in sources_meta["sources"]
        assert "macro_fundamentals" in sources_meta["sources"]
        assert "cryptopanic_sentiment" in sources_meta["sources"]
        assert "onchain_analytics" in sources_meta["sources"]

        # Test Onchain Dispatch
        onchain_res = gateway.dispatch_query("onchain_analytics", "network", {"network": "ethereum"})
        assert onchain_res["network"] == "ethereum"
        assert onchain_res["base_fee_gwei"] > 0
        assert onchain_res["network_security_status"] == "OPTIMAL_HEALTH"

    def test_mcp_sec_and_sentiment_pipeline(self):
        gateway = FinancialMCPGateway()
        # 1. SEC EDGAR
        sec_res = gateway.query_sec_edgar(ticker="MSFT", filing_type="10-K")
        assert sec_res["ticker"] == "MSFT"
        assert sec_res["filing_type"] == "10-K"
        assert "financial_statements" in sec_res
        assert sec_res["financial_statements"]["total_revenue_billions"] > 0
        assert len(sec_res["risk_factors_item_1a"]) >= 4
        assert "Operating income" in sec_res["mda_highlights"]

        # 2. CryptoPanic Sentiment & Composite Stream
        sent_stream = gateway.get_sentiment_stream()
        assert "composite_market_score" in sent_stream
        assert -1.0 <= sent_stream["composite_market_score"] <= 1.0
        assert sent_stream["market_regime"] in ["RISK_ON_EXPANSION", "NEUTRAL"]
        assert sent_stream["crypto_sentiment"]["fear_and_greed_index"] > 0

    def test_reverse_skill_pinescript_transpiler(self):
        engine = ReverseSkillTranspiler()
        sample_pine = """
//@version=5
strategy("EMA Trend Crossover Strategy", overlay=true)
fast_len = 9
slow_len = 21
ema_fast = ta.ema(close, fast_len)
ema_slow = ta.ema(close, slow_len)
rsi_val = ta.rsi(close, 14)

longCondition = ta.crossover(ema_fast, ema_slow) and rsi_val < 30
if (longCondition)
    strategy.entry("Long", strategy.long)

strategy.exit("TP_SL", "Long", loss=45, profit=110)
"""
        trans = engine.transpile_pinescript(sample_pine)
        assert trans["status"] == "TRANSPILED_SUCCESS"
        assert trans["strategy_name"] == "EMA Trend Crossover Strategy"

        ruleset = trans["ruleset"]
        assert ruleset["source_language"] == "PINE_SCRIPT_V5"
        assert len(ruleset["indicators"]) >= 2
        assert len(ruleset["entry_triggers"]) >= 1
        assert ruleset["risk_parameters"]["stop_loss_ticks"] == 45.0
        assert ruleset["risk_parameters"]["take_profit_ticks"] == 110.0

        # Verify executable python code generation
        py_code = trans["python_agent_code"]
        assert "class EMATrendCrossoverStrategySwarmAgent:" in py_code
        assert "evaluate_trade_signal" in py_code

    def test_reverse_skill_csv_analyzer(self):
        engine = ReverseSkillTranspiler()
        csv_data = """timestamp,symbol,side,entry_price,exit_price,qty,pnl,duration
2026-02-15T10:00:00,BTCUSDT,BUY,64000,64900,1.0,900.0,1800
2026-02-15T11:00:00,BTCUSDT,BUY,64900,64700,1.0,-200.0,900
2026-02-15T12:00:00,BTCUSDT,BUY,64700,65800,1.0,1100.0,2400
2026-02-15T13:00:00,BTCUSDT,SELL,65800,65100,1.0,700.0,1500
2026-02-15T14:00:00,BTCUSDT,BUY,65100,64850,1.0,-250.0,720
2026-02-15T15:00:00,BTCUSDT,BUY,64850,66000,1.0,1150.0,3600
"""
        analysis = engine.analyze_csv_trades(csv_data)
        assert analysis["status"] == "ANALYSIS_COMPLETE"
        assert analysis["archetype"] in ["TREND_FOLLOWING_BREAKOUT", "MEAN_REVERSION_OSCILLATOR", "ORDER_FLOW_SCALPING"]

        metrics = analysis["signature"]["metrics"]
        assert metrics["total_trades_analyzed"] == 6
        assert metrics["win_rate_pct"] > 50.0
        assert metrics["profit_factor"] > 1.0
        assert metrics["gross_pnl_usd"] > 0

    def test_reverse_skill_agent_deployment(self):
        engine = ReverseSkillTranspiler()
        config = {
            "strategy_name": "Momentum_Quant_V1",
            "indicators": [{"type": "RSI", "length": 14}],
            "risk_parameters": {"stop_loss_ticks": 40, "take_profit_ticks": 100}
        }
        res = engine.deploy_agent(
            agent_name="Momentum_Quant_V1",
            strategy_config=config,
            initial_capital=75000.0
        )
        assert res["status"] == "DEPLOYED_SUCCESS"
        assert res["agent_id"].startswith("AGENT-REVERSE-")
        assert res["deployed_agents_count"] == 1
        assert res["agent_id"] in engine.deployed_agents