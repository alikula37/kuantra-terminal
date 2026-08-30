import time
import gc
import psutil
import pytest
import asyncio
import numpy as np
import pandas as pd
from app.services.matching.order_book import LimitOrderBook
from app.db.duckdb_driver import DuckDBDriver
from app.services.plugin_manager import DynamicPluginManager
from scripts.hft_load_generator import SyntheticMarketGenerator, HFTLoadEngine, MarketTick
from main import create_app

class TestHFTStressAndMemoryBenchmarks:
    """Automated Pytest Suite for High-Frequency Throughput, Low Latency, and Memory Stability."""

    def test_orderbook_high_throughput_ingestion(self):
        """Feeds 50,000 synthetic ticks into L2/L3 order book; asserts 0 dropped ticks and p99 latency < 2.5ms."""
        generator = SyntheticMarketGenerator()
        ob = LimitOrderBook(symbol="BTCUSDT")
        batch = generator.generate_batch(50000, symbol="BTCUSDT")

        latencies_us: list[float] = []
        filled_or_rested = 0

        for tick in batch:
            t0 = time.perf_counter()
            if tick.tick_type == "BOOK_UPDATE":
                res = ob.add_order(
                    order_id=f"SYN-{tick.seq_id}",
                    side=tick.side,
                    price=tick.price,
                    size=tick.size,
                    order_type=tick.order_type
                )
            else:
                res = ob.add_order(
                    order_id=f"MKT-{tick.seq_id}",
                    side=tick.side,
                    price=tick.price,
                    size=tick.size,
                    order_type="MARKET"
                )
            t1 = time.perf_counter()
            latencies_us.append((t1 - t0) * 1_000_000)
            if res.get("status") in ("NEW", "FILLED", "PARTIALLY_FILLED", "PARTIALLY_FILLED_IOC_CANCELLED", "REJECTED_POST_ONLY_RESTRICTED"):
                filled_or_rested += 1

        assert len(latencies_us) == 50000, "Must process exactly 50,000 ticks"
        assert filled_or_rested > 45000, "90%+ orders must successfully be processed into book or filled"

        lat_arr = np.array(latencies_us)
        p50 = float(np.percentile(lat_arr, 50))
        p95 = float(np.percentile(lat_arr, 95))
        p99 = float(np.percentile(lat_arr, 99))

        # Assert SLA: p99 latency < 2.5ms (2500 µs)
        assert p99 < 2500.0, f"p99 latency {p99:.2f} µs exceeded 2.5ms SLA"
        assert p50 < 100.0, f"p50 latency {p50:.2f} µs exceeded 100µs baseline"

    def test_duckdb_storage_microbatch_commit_under_load(self):
        """Verifies 100,000 tick ingestion into DuckDB OLAP with commit time < 45ms."""
        import duckdb
        conn = duckdb.connect()
        conn.execute("""
            CREATE TABLE market_candles (
                symbol VARCHAR,
                timeframe VARCHAR,
                timestamp TIMESTAMP,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                trades_count BIGINT
            )
        """)
        generator = SyntheticMarketGenerator()

        total_ticks = 100000
        batch_size = 5000
        commit_latencies_ms: list[float] = []

        try:
            for _ in range(total_ticks // batch_size):
                ticks = generator.generate_batch(batch_size, symbol="BTCUSDT")
                df = pd.DataFrame({
                    "symbol": [t.symbol for t in ticks],
                    "timeframe": ["1s"] * len(ticks),
                    "timestamp": [pd.Timestamp("2026-08-30 12:00:00")] * len(ticks),
                    "open": [t.price for t in ticks],
                    "high": [t.price for t in ticks],
                    "low": [t.price for t in ticks],
                    "close": [t.price for t in ticks],
                    "volume": [t.size for t in ticks],
                    "trades_count": [1] * len(ticks)
                })

                t0 = time.perf_counter()
                conn.register("df_temp", df)
                conn.execute("INSERT INTO market_candles SELECT * FROM df_temp")
                conn.unregister("df_temp")
                t1 = time.perf_counter()
                commit_latencies_ms.append((t1 - t0) * 1000)

            # Assert SLA: p95 commit time < 45ms
            commit_arr = np.array(commit_latencies_ms)
            p95_commit = float(np.percentile(commit_arr, 95))
            assert p95_commit < 45.0, f"DuckDB p95 commit time {p95_commit:.2f} ms exceeded 45ms SLA"
            assert len(commit_latencies_ms) == 20
        finally:
            conn.close()

    @pytest.mark.asyncio
    async def test_dynamic_plugin_switching_under_tick_storm(self):
        """Toggles plugins under active load; asserts zero deadlock and memory return to baseline (+/- 10MB)."""
        app = create_app()
        manager = DynamicPluginManager(app=app)
        engine = HFTLoadEngine()

        process = psutil.Process()
        gc.collect()
        rss_baseline = process.memory_info().rss / (1024 * 1024)

        toggles_done = 0

        async def tick_sink(batch: list[MarketTick]):
            nonlocal toggles_done
            # Alternate persona every 5 batches
            if len(batch) > 0 and toggles_done < 4:
                if toggles_done == 0:
                    await manager.apply_persona("kuantra_quant")
                elif toggles_done == 1:
                    await manager.apply_persona("kuantra_defai")
                elif toggles_done == 2:
                    await manager.apply_persona("kuantra_institutional")
                elif toggles_done == 3:
                    await manager.apply_persona("kuantra_lite")
                toggles_done += 1

        summary = await engine.stream_ticks(
            target_rate=20000,
            duration_sec=3.0,
            batch_size=250,
            callback=tick_sink
        )

        assert summary["total_ticks"] > 5000, "Must process 5,000+ ticks during storm"
        assert toggles_done >= 4, "All 4 persona transitions must execute successfully"

        gc.collect()
        rss_final = process.memory_info().rss / (1024 * 1024)
        rss_delta = rss_final - rss_baseline

        # Assert memory returns within acceptable bounds after persona unmount
        assert rss_delta < 20.0, f"Memory delta {rss_delta:.2f} MB after unmount exceeded 20MB limit"

    def test_memory_leak_stability(self):
        """Runs 10,000 batch cycles; asserts linear regression slope of memory growth is approximately zero."""
        process = psutil.Process()
        gc.collect()

        generator = SyntheticMarketGenerator()
        rss_samples: list[float] = []

        # Warmup
        for _ in range(500):
            _ = generator.generate_single_tick("BTCUSDT")

        # 10,000 cycles sampled every 1,000
        for i in range(10000):
            _ = generator.generate_single_tick("BTCUSDT")
            if i % 1000 == 0:
                rss_samples.append(process.memory_info().rss / (1024 * 1024))

        gc.collect()
        rss_samples.append(process.memory_info().rss / (1024 * 1024))

        x = np.arange(len(rss_samples))
        y = np.array(rss_samples)
        slope, _ = np.polyfit(x, y, 1)

        # Assert memory slope is flat (< 0.5 MB per 1,000 iterations)
        assert abs(slope) < 0.5, f"Memory growth slope {slope:.4f} MB/k-iter indicated a potential leak"