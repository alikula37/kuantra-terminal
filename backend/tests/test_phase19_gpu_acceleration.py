import pytest
from app.services.ai.hardware_engine import hardware_engine, gguf_inference_engine, HardwareDiagnosticsEngine, LocalGGUFInferenceEngine
from app.services.ai.accelerated_swarm import accelerated_swarm, AcceleratedSwarmPipeline

class TestPhase19GPUAccelerationAndSwarm:
    """Test suite for Local LLM GPU Acceleration, VRAM Offloader, and Sub-50ms AI Swarm Pipeline."""

    def test_hardware_engine_detection(self):
        engine = HardwareDiagnosticsEngine()
        hw = engine.detect_hardware()
        assert "engine" in hw
        assert "device_name" in hw
        assert "acceleration_type" in hw
        assert hw["threads"] > 0
        assert hw["recommended_quant"] == "Q4_K_M"

        # Check real-time metrics
        metrics = engine.get_realtime_metrics()
        assert "vram_total_mb" in metrics
        assert "gpu_core_utilization_pct" in metrics
        assert "gpu_temperature_c" in metrics
        assert metrics["status"] == "ACCELERATED_ONLINE"

    def test_vram_layer_allocation_math(self):
        engine = HardwareDiagnosticsEngine()
        # Test 1: Standard 7B model Q4_K_M at 4096 context
        res = engine.compute_optimal_layers(
            model_size_mb=4300.0,
            total_layers=33,
            quant="Q4_K_M",
            context_length=4096,
            safety_buffer_mb=512.0
        )
        assert res["total_layers"] == 33
        assert 0 <= res["optimal_gpu_layers"] <= 33
        assert res["cpu_fallback_layers"] == 33 - res["optimal_gpu_layers"]
        assert res["safety_buffer_reserved_mb"] == 512.0
        assert 0.0 <= res["offload_percentage"] <= 100.0
        assert res["inference_mode"] in ["FULL_GPU_ACCELERATION", "HYBRID_VRAM_OFFLOAD", "CPU_ONLY"]

        # Test 2: Large 70B model with heavy VRAM requirements
        res_large = engine.compute_optimal_layers(
            model_size_mb=38000.0,
            total_layers=80,
            quant="Q4_K_M",
            context_length=8192
        )
        assert res_large["total_layers"] == 80
        assert res_large["cpu_fallback_layers"] >= 0

    def test_accelerated_swarm_inference(self):
        pipeline = AcceleratedSwarmPipeline()

        # Test Case 1: Strong Bullish Confluence with Safe Risk
        bullish_state = {
            "symbol": "BTCUSDT",
            "price": 65400.0,
            "cvd_delta": 620.0,
            "imbalance_ratio": 3.5,
            "rsi": 32.0,
            "account_drawdown_pct": 1.0
        }
        res_bull = pipeline.evaluate_market_state(bullish_state)
        assert res_bull["consensus_decision"] == "APPROVE_BUY_EXECUTION"
        assert res_bull["conviction_score"] > 60.0
        assert len(res_bull["agents"]) == 3
        assert res_bull["gpu_acceleration"]["total_pipeline_latency_ms"] < 50.0
        assert res_bull["gpu_acceleration"]["is_sub_50ms"] is True

        # Test Case 2: Max Drawdown Breach Veto
        veto_state = {
            "symbol": "BTCUSDT",
            "price": 65400.0,
            "cvd_delta": 620.0,
            "imbalance_ratio": 3.5,
            "rsi": 32.0,
            "account_drawdown_pct": 4.8  # >= 4.5% Veto Threshold
        }
        res_veto = pipeline.evaluate_market_state(veto_state)
        assert res_veto["consensus_decision"] == "HOLD_OR_VETO"
        risk_agent = next(a for a in res_veto["agents"] if a["agent"] == "RiskSentinelAgent")
        assert risk_agent["decision"] == "VETO"
        assert risk_agent["risk_score"] == 85.0

    def test_gpu_hardware_endpoints_and_benchmark(self):
        inf_engine = LocalGGUFInferenceEngine(hardware_engine)
        bench = inf_engine.run_benchmark()
        assert bench["status"] == "BENCHMARK_COMPLETE"
        assert bench["tokens_per_second"] > 0
        assert bench["time_to_first_token_ms"] > 0
        assert bench["total_latency_ms"] > 0

        # Configuration update
        cfg = hardware_engine.configure_hardware(
            engine="CUDA",
            n_gpu_layers=28,
            threads=12,
            context_length=8192
        )
        assert cfg["status"] == "CONFIG_PERSISTED"
        assert cfg["active_config"]["n_gpu_layers"] == 28
        assert cfg["active_config"]["context_length"] == 8192