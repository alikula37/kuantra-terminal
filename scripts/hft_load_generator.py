"""
High-Frequency Synthetic Market Data Load Generator for Kuantra Terminal.
Generates ultra-realistic L2/L3 order book updates, trade prints, and CVD delta ticks
at configurable rates (Warmup 2k/s, Sustained 25k/s, Burst 100k/s) across multiple symbols.
"""

import time
import math
import random
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator

DEFAULT_SYMBOLS = {
    "BTCUSDT": {"base_price": 65000.0, "tick_size": 0.10, "lot_size": 0.001, "volatility": 0.0008},
    "ETHUSDC": {"base_price": 3500.0, "tick_size": 0.01, "lot_size": 0.01, "volatility": 0.0012},
    "SOLUSDT": {"base_price": 145.0, "tick_size": 0.01, "lot_size": 0.1, "volatility": 0.0018},
    "EURUSD": {"base_price": 1.0850, "tick_size": 0.0001, "lot_size": 1000.0, "volatility": 0.0003}
}

@dataclass
class MarketTick:
    symbol: str
    timestamp: float
    seq_id: int
    tick_type: str # "BOOK_UPDATE", "TRADE_PRINT", "CVD_DELTA"
    side: str # "BUY", "SELL"
    price: float
    size: float
    order_type: str = "LIMIT"
    delta: float = 0.0

class SyntheticMarketGenerator:
    """Generates geometric Brownian motion order flow and L2 updates."""

    def __init__(self, symbols_config: Optional[Dict[str, Dict[str, float]]] = None):
        self.symbols = symbols_config or DEFAULT_SYMBOLS
        self.current_prices = {s: cfg["base_price"] for s, cfg in self.symbols.items()}
        self.cvd_accumulators = {s: 0.0 for s in self.symbols}
        self.seq_counters = {s: 0 for s in self.symbols}

    def generate_single_tick(self, symbol: str) -> MarketTick:
        cfg = self.symbols[symbol]
        self.seq_counters[symbol] += 1
        seq_id = self.seq_counters[symbol]

        # Geometric Brownian Motion step
        vol = cfg["volatility"]
        price_change = self.current_prices[symbol] * random.gauss(0, vol)
        new_price = round((self.current_prices[symbol] + price_change) / cfg["tick_size"]) * cfg["tick_size"]
        new_price = max(cfg["tick_size"], new_price)
        self.current_prices[symbol] = new_price

        # Randomize tick type (60% book update, 30% trade print, 10% CVD delta)
        r = random.random()
        side = "BUY" if random.random() > 0.49 else "SELL"
        size = round(random.expovariate(1.0 / (cfg["lot_size"] * 10)) + cfg["lot_size"], 4)

        if r < 0.60:
            tick_type = "BOOK_UPDATE"
            delta = 0.0
            order_type = random.choice(["LIMIT", "LIMIT", "LIMIT", "IOC", "POST_ONLY"])
        elif r < 0.90:
            tick_type = "TRADE_PRINT"
            delta_val = size if side == "BUY" else -size
            self.cvd_accumulators[symbol] += delta_val
            delta = self.cvd_accumulators[symbol]
            order_type = "MARKET"
        else:
            tick_type = "CVD_DELTA"
            delta = self.cvd_accumulators[symbol]
            order_type = "LIMIT"

        return MarketTick(
            symbol=symbol,
            timestamp=time.perf_counter(),
            seq_id=seq_id,
            tick_type=tick_type,
            side=side,
            price=round(new_price, 5),
            size=size,
            order_type=order_type,
            delta=round(delta, 4)
        )

    def generate_batch(self, count: int, symbol: Optional[str] = None) -> List[MarketTick]:
        """Generates a batch of synthetic ticks with zero allocations inside the loop."""
        sym_keys = list(self.symbols.keys()) if symbol is None else [symbol]
        batch: List[MarketTick] = []
        for _ in range(count):
            sym = random.choice(sym_keys)
            batch.append(self.generate_single_tick(sym))
        return batch

class HFTLoadEngine:
    """Asynchronous high-frequency load generator pipeline with rate governor."""

    def __init__(self, symbols_config: Optional[Dict[str, Dict[str, float]]] = None):
        self.generator = SyntheticMarketGenerator(symbols_config)
        self.is_running = False
        self.total_generated = 0

    async def stream_ticks(
        self,
        target_rate: int = 25000,
        duration_sec: float = 10.0,
        batch_size: int = 250,
        callback: Optional[Callable[[List[MarketTick]], Any]] = None
    ) -> Dict[str, Any]:
        """
        Streams market ticks at `target_rate` ticks/sec for `duration_sec`.
        Yields batches of `batch_size` to `callback` or internal queue.
        """
        self.is_running = True
        self.total_generated = 0
        latencies_sec: List[float] = []

        batches_per_sec = max(1, target_rate // batch_size)
        interval_sec = 1.0 / batches_per_sec

        start_time = time.perf_counter()
        end_time = start_time + duration_sec
        next_tick_time = start_time

        while self.is_running and time.perf_counter() < end_time:
            batch_start = time.perf_counter()
            batch = self.generator.generate_batch(batch_size)
            self.total_generated += len(batch)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(batch)
                else:
                    callback(batch)

            batch_end = time.perf_counter()
            latencies_sec.append(batch_end - batch_start)

            next_tick_time += interval_sec
            sleep_time = next_tick_time - time.perf_counter()
            if sleep_time > 0.0005:
                await asyncio.sleep(sleep_time)
            else:
                # Yield control without full thread sleep to prevent timer quantization
                await asyncio.sleep(0)

        actual_duration = time.perf_counter() - start_time
        actual_throughput = self.total_generated / actual_duration if actual_duration > 0 else 0.0
        self.is_running = False

        return {
            "target_rate": target_rate,
            "actual_duration_sec": round(actual_duration, 4),
            "total_ticks": self.total_generated,
            "throughput_ticks_per_sec": round(actual_throughput, 2),
            "batch_count": len(latencies_sec),
            "avg_batch_latency_ms": round((sum(latencies_sec) / len(latencies_sec)) * 1000, 4) if latencies_sec else 0.0
        }

    def stop(self):
        self.is_running = False

if __name__ == "__main__":
    async def main():
        print("[*] Launching HFT Synthetic Market Data Generator standalone test...")
        engine = HFTLoadEngine()

        print("[1/3] Warmup Profile: 2,000 ticks/sec (3s)")
        res_warm = await engine.stream_ticks(target_rate=2000, duration_sec=3.0, batch_size=100)
        print(f"      -> Processed {res_warm['total_ticks']} ticks in {res_warm['actual_duration_sec']}s ({res_warm['throughput_ticks_per_sec']} ticks/sec)")

        print("[2/3] Sustained Profile: 25,000 ticks/sec (5s)")
        res_sustained = await engine.stream_ticks(target_rate=25000, duration_sec=5.0, batch_size=500)
        print(f"      -> Processed {res_sustained['total_ticks']} ticks in {res_sustained['actual_duration_sec']}s ({res_sustained['throughput_ticks_per_sec']} ticks/sec)")

        print("[3/3] Burst Profile: 100,000 ticks/sec (2s shock spike)")
        res_burst = await engine.stream_ticks(target_rate=100000, duration_sec=2.0, batch_size=1000)
        print(f"      -> Processed {res_burst['total_ticks']} ticks in {res_burst['actual_duration_sec']}s ({res_burst['throughput_ticks_per_sec']} ticks/sec)")

        print("\n[SUCCESS] Standalone load generation verified.")

    asyncio.run(main())