import pytest
from app.services.dex.rpc_gateway import (
    rpc_gateway,
    MultiChainRPCGateway,
    ConstantProductAMM,
    ConcentratedLiquidityAMM,
    StableSwapAMM
)
from app.services.dex.arbitrage_engine import arbitrage_engine, CrossDEXArbitrageEngine
from app.services.dex.defai_agent import defai_agent, DeFAIArbitrageAgent

class TestPhase20DEXArbitrageAndDeFAI:
    """Test suite for On-Chain Multi-Chain RPC, AMM Math, Flash Loan Simulation, and DeFAI Agent."""

    def test_rpc_gateway_provider_failover(self):
        gateway = MultiChainRPCGateway()
        chains_info = gateway.list_chains()
        assert chains_info["total_chains"] >= 4
        assert "ethereum" in chains_info["chains"]
        assert "arbitrum" in chains_info["chains"]
        assert "base" in chains_info["chains"]
        assert "solana" in chains_info["chains"]

        # Test Failover trigger
        initial_rpc = gateway.chains["ethereum"]["active_rpc"]
        failover_res = gateway.trigger_failover("ethereum")
        assert failover_res["status"] == "FAILOVER_SUCCESS"
        assert failover_res["active_rpc"] != initial_rpc

    def test_amm_pricing_and_slippage_math(self):
        # 1. Constant Product AMM (Uniswap v2)
        res_v2 = ConstantProductAMM.get_amount_out(
            amount_in=10.0,
            reserve_in=1000.0,
            reserve_out=2700000.0,
            fee_bps=30
        )
        assert res_v2["amount_out"] > 0
        assert res_v2["effective_price"] > 0
        assert 0.0 <= res_v2["price_impact_pct"] <= 5.0

        # 2. Concentrated Liquidity AMM (Uniswap v3)
        res_v3 = ConcentratedLiquidityAMM.quote_swap(
            amount_in=5.0,
            current_price=2750.0,
            liquidity=45000000.0,
            fee_tier_bps=5
        )
        assert res_v3["amount_out"] > 0
        assert res_v3["effective_price"] > 0

        # 3. StableSwap AMM (Curve)
        res_curve = StableSwapAMM.get_exchange_amount(
            amount_in=10000.0,
            reserve_a=50000000.0,
            reserve_b=50000000.0,
            amp_coeff_a=100,
            fee_bps=4
        )
        assert res_curve["amount_out"] > 9900.0  # Stable peg near 1:1

    def test_triangular_cycle_detection(self):
        engine = CrossDEXArbitrageEngine()
        spatial_opps = engine.scan_spatial_opportunities("ethereum")
        assert len(spatial_opps) > 0
        assert spatial_opps[0]["type"] == "SPATIAL_CROSS_DEX"
        assert spatial_opps[0]["gross_spread_pct"] > 0

        tri_opps = engine.scan_triangular_opportunities("ethereum")
        assert len(tri_opps) > 0
        assert tri_opps[0]["type"] == "TRIANGULAR_CYCLE"
        assert tri_opps[0]["cycle_product"] > 1.0  # Profitable product > 1.0

    def test_multi_protocol_flash_loan_net_profit(self):
        engine = CrossDEXArbitrageEngine()

        # 1. Balancer (0.00% fee)
        sim_balancer = engine.simulate_flash_loan(
            chain="ethereum",
            protocol="BALANCER_VAULT",
            borrow_asset="WETH",
            amount_usd=100000.0,
            route_spread_pct=0.60
        )
        assert sim_balancer["financial_breakdown"]["flash_loan_fee_usd"] == 0.0
        assert sim_balancer["financial_breakdown"]["net_profit_usd"] > 0
        assert sim_balancer["execution_viable"] is True

        # 2. Aave v3 (0.05% fee)
        sim_aave = engine.simulate_flash_loan(
            chain="ethereum",
            protocol="AAVE_V3",
            borrow_asset="USDC",
            amount_usd=100000.0,
            route_spread_pct=0.60
        )
        assert sim_aave["financial_breakdown"]["flash_loan_fee_usd"] == 50.0  # 100k * 0.05% = $50
        assert sim_aave["financial_breakdown"]["net_profit_usd"] < sim_balancer["financial_breakdown"]["net_profit_usd"]

    def test_mev_protection_and_defai_eval(self):
        agent = DeFAIArbitrageAgent()
        valid_opp = {
            "opportunity_id": "ARB-TEST-001",
            "type": "SPATIAL_CROSS_DEX",
            "chain": "ARBITRUM",
            "gross_spread_pct": 0.65,
            "optimal_loan_usd": 150000.0,
            "estimated_gas_usd": 0.50,
            "mev_protection": "FLASHBOTS_PRIVATE_BUNDLE"
        }
        res = agent.evaluate_opportunity(valid_opp)
        assert res["decision"] == "APPROVE_FLASH_ARBITRAGE"
        assert res["confidence_score"] > 90.0
        assert res["private_rpc_validated"] is True

        # Test Gas Spike Veto
        gas_spike_opp = {
            "opportunity_id": "ARB-TEST-002",
            "type": "SPATIAL_CROSS_DEX",
            "chain": "ETHEREUM",
            "gross_spread_pct": 0.15,
            "optimal_loan_usd": 10000.0, # Gross = $15
            "estimated_gas_usd": 18.00,   # Gas > Gross
            "mev_protection": "FLASHBOTS_PRIVATE_BUNDLE"
        }
        res_gas = agent.evaluate_opportunity(gas_spike_opp)
        assert res_gas["decision"] == "VETO_GAS_INEFFICIENT"
        assert res_gas["confidence_score"] < 50.0

    def test_dex_api_endpoints(self):
        # 1. Chains
        chains = rpc_gateway.list_chains()
        assert chains["total_chains"] >= 4

        # 2. Pool scanner
        pools = rpc_gateway.scan_pool_reserves("ethereum")
        assert len(pools) >= 3

        # 3. Simulate
        sim = arbitrage_engine.simulate_flash_loan(
            chain="arbitrum",
            protocol="MORPHO_BLUE",
            borrow_asset="USDC",
            amount_usd=50000.0,
            route_spread_pct=0.45
        )
        assert sim["protocol"] == "Morpho Blue Flash Loan"
        assert sim["financial_breakdown"]["net_profit_usd"] > 0