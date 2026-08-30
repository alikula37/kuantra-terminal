"""
Institutional Automated Performance, Soak/Stress Harness & Memory Profiling Pipeline.
Measures latency percentiles (p50, p95, p99, p99.9), memory RSS/VMS deltas,
DuckDB micro-batch commit speeds, and DynamicPluginManager route mutation under load.
Exports structured telemetry to /reports/STRESS_BENCHMARK_REPORT.json.
"""

import os
import sys
import gc
import json
import time
import random
import psutil
import argparse
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
backend_path = os.path.join(ROOT_DIR, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from scripts.hft_load_generator import HFTLoadEngine, MarketTick, DEFAULT_SYMBOLS
from app.services.matching.order_book import LimitOrderBook
from app.db.duckdb_driver import DuckDBDriver
from app.services.plugin_manager import DynamicPluginManager
from main import create_app

class MemoryTracker:
    """Tracks RSS, VMS, and Object counts with linear regression slope calculation."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.samples: List[Dict[str, float]] = []
        self.initial_rss_mb = self.get_rss_mb()
        self.initial_vms_mb = self.get_vms_mb()
        self.initial_objects = len(gc.get_objects())

    def get_rss_mb(self) -> float:
        return self.process.memory_info().rss / (1024 * 1024)

    def get_vms_mb(self) -> float:
        return self.process.memory_info().vms / (1024 * 1024)

    def sample(self, label: str = ""):
        self.samples.append({
            "timestamp": time.perf_counter(),
            "rss_mb": round(self.get_rss_mb(), 2),
            "vms_mb": round(self.get_vms_mb(), 2),
            "label": label
        })

    def analyze_leak_stability(self) -> Dict[str, Any]:
        gc.collect()
        final_rss_mb = self.get_rss_mb()
        final_vms_mb = self.get_vms_mb()
        final_objects = len(gc.get_objects())

        rss_delta = final_rss_mb - self.initial_rss_mb
        vms_delta = final_vms_mb - self.initial_vms_mb
        objects_delta = final_objects - self.initial_objects

        # Calculate slope if enough samples
        if len(self.samples) >= 5:
            times = np.array([s["timestamp"] for s in self.samples])
            rss_vals = np.array([s["rss_mb"] for s in self.samples])
            # normalize time
            times_norm = times - times[0]
            if np.max(times_norm) > 0:
                slope, intercept = np.polyfit(times_norm, rss_vals, 1)
            else:
                slope = 0.0
        else:
            slope = 0.0

        peak_rss_mb = max([s["rss_mb"] for s in self.samples]) if self.samples else final_rss_mb

        return {
            "initial_rss_mb": round(float(self.initial_rss_mb), 2),
            "peak_rss_mb": round(float(peak_rss_mb), 2),
            "final_rss_mb": round(float(final_rss_mb), 2),
            "rss_delta_mb": round(float(rss_delta), 2),
            "initial_vms_mb": round(float(self.initial_vms_mb), 2),
            "final_vms_mb": round(float(final_vms_mb), 2),
            "vms_delta_mb": round(float(vms_delta), 2),
            "objects_delta": int(objects_delta),
            "memory_growth_slope_mb_per_sec": round(float(slope), 4),
            "leak_detected": bool(abs(rss_delta) > 25.0 and slope > 0.5)
        }

class StressBenchmarkRunner:
    """Orchestrates high-frequency soak tests across Matching, DuckDB, and Dynamic Plugins."""

    def __init__(self, symbols: Optional[List[str]] = None):
        self.symbols = symbols or list(DEFAULT_SYMBOLS.keys())
        self.order_books = {s: LimitOrderBook(symbol=s) for s in self.symbols}
        self.mem_tracker = MemoryTracker()
        self.duckdb_driver = DuckDBDriver()
        self.load_engine = HFTLoadEngine()

    async def run_full_benchmark(
        self,
        duration_sec: float = 30.0,
        target_rate: int = 25000,
        batch_size: int = 500
    ) -> Dict[str, Any]:
        print("\n==========================================================================================")
        print("                  KUANTRA TERMINAL HFT STRESS & MEMORY BENCHMARK HARNESS                  ")
        print("==========================================================================================")
        print(f"[*] Target Rate: {target_rate:,} ticks/sec | Duration: {duration_sec}s | Batch: {batch_size}")
        print(f"[*] Symbols Monitored: {', '.join(self.symbols)}")
        print(f"[*] Initial Baseline Memory: RSS = {self.mem_tracker.initial_rss_mb:.2f} MB | VMS = {self.mem_tracker.initial_vms_mb:.2f} MB")
        print("------------------------------------------------------------------------------------------")

        tick_latencies_us: List[float] = []
        duckdb_commit_latencies_ms: List[float] = []
        persona_mutation_latencies_ms: List[float] = []

        # Setup Micro-Kernel FastAPI & DynamicPluginManager
        app = create_app()
        plugin_manager = DynamicPluginManager(app=app)
        personas_cycle = ["kuantra_lite", "kuantra_quant", "kuantra_defai", "kuantra_institutional", "kuantra_lite"]
        persona_idx = 0
        last_persona_toggle = time.perf_counter()

        # Persistent DuckDB Connection & Batch Buffer for high-throughput stream
        duck_conn = self.duckdb_driver.get_connection()
        duck_buffer: List[MarketTick] = []

        # Ingestion Callback
        async def process_batch(batch: List[MarketTick]):
            nonlocal persona_idx, last_persona_toggle

            # 1. Feed into L2/L3 Order Book
            for tick in batch:
                t0 = time.perf_counter()
                ob = self.order_books[tick.symbol]
                if tick.tick_type == "BOOK_UPDATE":
                    ob.add_order(
                        order_id=f"SYN-{tick.seq_id}",
                        side=tick.side,
                        price=tick.price,
                        size=tick.size,
                        order_type=tick.order_type
                    )
                elif tick.tick_type == "TRADE_PRINT":
                    ob.add_order(
                        order_id=f"MKT-{tick.seq_id}",
                        side=tick.side,
                        price=tick.price,
                        size=tick.size,
                        order_type="MARKET"
                    )
                t1 = time.perf_counter()
                if len(tick_latencies_us) < 50000:
                    tick_latencies_us.append((t1 - t0) * 1_000_000)
                elif random.random() < 0.05:
                    idx = random.randint(0, len(tick_latencies_us) - 1)
                    tick_latencies_us[idx] = (t1 - t0) * 1_000_000

            # Prune deep book levels to maintain realistic L2 cache bounds (top 250 levels)
            for ob in self.order_books.values():
                if len(ob.bids) > 250:
                    sorted_bids = sorted(ob.bids.keys(), reverse=True)
                    for p in sorted_bids[250:]:
                        level = ob.bids.pop(p)
                        for o in level.orders:
                            ob.orders_map.pop(o.order_id, None)
                if len(ob.asks) > 250:
                    sorted_asks = sorted(ob.asks.keys())
                    for p in sorted_asks[250:]:
                        level = ob.asks.pop(p)
                        for o in level.orders:
                            ob.orders_map.pop(o.order_id, None)

            # 2. Micro-batch Ingestion to DuckDB OLAP (every 2,500 ticks)
            duck_buffer.extend(batch)
            if len(duck_buffer) >= 2500:
                d_t0 = time.perf_counter()
                df = pd.DataFrame({
                    "symbol": [t.symbol for t in duck_buffer],
                    "timeframe": ["1s"] * len(duck_buffer),
                    "timestamp": [pd.Timestamp("2026-08-30 12:00:00")] * len(duck_buffer),
                    "open": [t.price for t in duck_buffer],
                    "high": [t.price for t in duck_buffer],
                    "low": [t.price for t in duck_buffer],
                    "close": [t.price for t in duck_buffer],
                    "volume": [t.size for t in duck_buffer],
                    "trades_count": [1] * len(duck_buffer)
                })
                duck_conn.register("batch_df", df)
                duck_conn.execute("INSERT INTO market_candles SELECT * FROM batch_df")
                duck_conn.unregister("batch_df")
                d_t1 = time.perf_counter()
                duckdb_commit_latencies_ms.append((d_t1 - d_t0) * 1000)
                duck_buffer.clear()

            # 3. Periodic Persona Route Mutation under active load (every 5 seconds)
            now = time.perf_counter()
            if now - last_persona_toggle >= 5.0:
                p_target = personas_cycle[persona_idx % len(personas_cycle)]
                persona_idx += 1
                last_persona_toggle = now

                p_t0 = time.perf_counter()
                await plugin_manager.apply_persona(p_target)
                p_t1 = time.perf_counter()
                p_lat = (p_t1 - p_t0) * 1000
                persona_mutation_latencies_ms.append(p_lat)
                self.mem_tracker.sample(label=f"persona_{p_target}")

            # Sample Memory periodically
            if len(self.mem_tracker.samples) < 200 and random.random() < 0.10:
                self.mem_tracker.sample(label="load_tick")

        # Run stream
        try:
            load_summary = await self.load_engine.stream_ticks(
                target_rate=target_rate,
                duration_sec=duration_sec,
                batch_size=batch_size,
                callback=process_batch
            )
        finally:
            duck_conn.close()

        # Final cleanup & memory profiling
        gc.collect()
        mem_analysis = self.mem_tracker.analyze_leak_stability()

        # Compute Latency Percentiles
        lat_arr = np.array(tick_latencies_us) if tick_latencies_us else np.array([0.0])
        p50 = float(np.percentile(lat_arr, 50))
        p90 = float(np.percentile(lat_arr, 90))
        p95 = float(np.percentile(lat_arr, 95))
        p99 = float(np.percentile(lat_arr, 99))
        p99_9 = float(np.percentile(lat_arr, 99.9))
        max_lat = float(np.max(lat_arr))

        duck_arr = np.array(duckdb_commit_latencies_ms) if duckdb_commit_latencies_ms else np.array([0.0])
        duck_p95 = float(np.percentile(duck_arr, 95))

        # Overall Status against SLAs
        passed_sla = (
            p99 < 2500.0 and # Orderbook p99 < 2.5ms (2500us)
            duck_p95 < 45.0 and # DuckDB p95 commit < 45ms
            not mem_analysis["leak_detected"]
        )

        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "PASSED" if passed_sla else "FAILED",
            "test_configuration": {
                "target_rate_ticks_sec": target_rate,
                "duration_sec": duration_sec,
                "batch_size": batch_size,
                "symbols": self.symbols
            },
            "throughput": {
                "total_ticks_processed": load_summary["total_ticks"],
                "actual_duration_sec": load_summary["actual_duration_sec"],
                "achieved_ticks_per_sec": load_summary["throughput_ticks_per_sec"]
            },
            "orderbook_latency_microseconds": {
                "p50": round(p50, 2),
                "p90": round(p90, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
                "p99_9": round(p99_9, 2),
                "max": round(max_lat, 2)
            },
            "duckdb_commit_latency_ms": {
                "p50": round(float(np.percentile(duck_arr, 50)), 2),
                "p95": round(duck_p95, 2),
                "max": round(float(np.max(duck_arr)), 2),
                "total_batches_committed": len(duckdb_commit_latencies_ms)
            },
            "persona_route_mutation_ms": {
                "avg_mutation_time_ms": round(float(np.mean(persona_mutation_latencies_ms)), 2) if persona_mutation_latencies_ms else 0.0,
                "total_mutations_under_load": len(persona_mutation_latencies_ms)
            },
            "memory_profiling": mem_analysis
        }

        # Export Report to /reports/STRESS_BENCHMARK_REPORT.json
        reports_dir = os.path.join(ROOT_DIR, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, "STRESS_BENCHMARK_REPORT.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Print Terminal Summary
        print("\n==========================================================================================")
        print("                              STRESS BENCHMARK RESULTS SUMMARY                            ")
        print("==========================================================================================")
        print(f"Status:                      {report_data['status']}")
        print(f"Total Ticks Ingested:        {report_data['throughput']['total_ticks_processed']:,} ticks")
        print(f"Achieved Throughput:         {report_data['throughput']['achieved_ticks_per_sec']:,} ticks/sec")
        print("------------------------------------------------------------------------------------------")
        print("Order Book Ingestion Latency:")
        print(f"  • p50:   {p50:.2f} µs ({p50/1000:.4f} ms)")
        print(f"  • p95:   {p95:.2f} µs ({p95/1000:.4f} ms)")
        print(f"  • p99:   {p99:.2f} µs ({p99/1000:.4f} ms) [SLA < 2.50 ms]")
        print(f"  • p99.9: {p99_9:.2f} µs ({p99_9/1000:.4f} ms)")
        print("------------------------------------------------------------------------------------------")
        print("DuckDB Micro-Batch Commit:")
        print(f"  • p95 Commit Latency:      {duck_p95:.2f} ms [SLA < 45.0 ms]")
        print(f"  • Total Batches Committed: {len(duckdb_commit_latencies_ms):,}")
        print("------------------------------------------------------------------------------------------")
        print("Memory & Leak Telemetry:")
        print(f"  • Initial RSS:             {mem_analysis['initial_rss_mb']:.2f} MB")
        print(f"  • Peak RSS:                {mem_analysis['peak_rss_mb']:.2f} MB")
        print(f"  • Final RSS:               {mem_analysis['final_rss_mb']:.2f} MB")
        print(f"  • Net RSS Delta:           {mem_analysis['rss_delta_mb']:+.2f} MB")
        print(f"  • Growth Slope:            {mem_analysis['memory_growth_slope_mb_per_sec']:.4f} MB/s")
        print(f"  • Leak Detected:           {mem_analysis['leak_detected']}")
        print("==========================================================================================")
        print(f"[+] Structured benchmark telemetry exported to: {report_path}\n")

        return report_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Kuantra Terminal HFT Stress & Memory Leak Benchmark")
    parser.add_argument("--duration", type=float, default=15.0, help="Test duration in seconds")
    parser.add_argument("--ticks-per-sec", type=int, default=25000, help="Target ticks per second")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for generator")
    args = parser.parse_args()

    runner = StressBenchmarkRunner()
    result = asyncio.run(runner.run_full_benchmark(
        duration_sec=args.duration,
        target_rate=args.ticks_per_sec,
        batch_size=args.batch_size
    ))

    sys.exit(0 if result["status"] == "PASSED" else 1)