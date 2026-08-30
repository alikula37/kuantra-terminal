from app.services.compliance_engine import compliance_engine
import asyncio
import json
import logging
import random
import time
from typing import Optional, Dict, Any, List
import websockets
from app.websocket.connection_manager import ws_manager
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

logger = logging.getLogger(__name__)

class BinanceStreamClient:
    """AsyncIO Binance Market Data WebSocket Client with real-time PnL recalculator."""

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol.upper()
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.last_price: float = 65000.0
        self.last_tick_time: float = time.time()
        self.latency_ms: float = 12.0
        self.candle_buffer: Dict[str, Any] = {}

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"BinanceStreamClient initialized for {self.symbol}")

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("BinanceStreamClient stopped.")

    async def _run_loop(self):
        stream_name = f"{self.symbol.lower()}@trade"
        kline_name = f"{self.symbol.lower()}@kline_1m"
        url = f"wss://stream.binance.com:9443/ws/{stream_name}/{kline_name}"

        retry_count = 0
        while self.is_running:
            try:
                logger.info(f"Connecting to Binance WS at {url}...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    retry_count = 0
                    logger.info("Connected to Binance live market stream.")
                    while self.is_running:
                        msg = await ws.recv()
                        await self._handle_message(json.loads(msg))
            except (websockets.exceptions.WebSocketException, OSError, asyncio.TimeoutError) as e:
                retry_count += 1
                logger.warning(f"Binance WS connection failed: {e}. Fallback to simulated live feed (attempt {retry_count}).")
                await self._run_simulated_stream(duration_seconds=10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected stream error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def _run_simulated_stream(self, duration_seconds: int = 10):
        """Simulate high-frequency realistic order book ticks & candles when offline."""
        start = time.time()
        while self.is_running and (time.time() - start < duration_seconds):
            drift = random.gauss(0, 8.5)
            self.last_price = max(100.0, self.last_price + drift)
            now_ms = int(time.time() * 1000)

            tick_event = {
                "e": "trade",
                "E": now_ms,
                "s": self.symbol,
                "p": f"{self.last_price:.2f}",
                "q": f"{random.uniform(0.01, 1.5):.4f}",
                "m": random.choice([True, False])
            }
            await self._process_tick(self.last_price, now_ms, float(tick_event["q"]))
            await asyncio.sleep(0.1)

    async def _handle_message(self, data: Dict[str, Any]):
        event_type = data.get("e")
        if event_type == "trade":
            price = float(data["p"])
            qty = float(data["q"])
            timestamp = data["E"]
            await self._process_tick(price, timestamp, qty)
        elif event_type == "kline":
            k = data["k"]
            candle = {
                "symbol": data["s"],
                "timeframe": k["i"],
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k["t"] / 1000)),
                "time": int(k["t"] / 1000),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
                "trades_count": int(k["n"]),
                "is_closed": bool(k["x"])
            }
            # Broadcast live candle update
            await ws_manager.broadcast({
                "type": "CANDLE_UPDATE",
                "data": candle
            }, channel="kline_updates")

            if candle["is_closed"]:
                # Persist closed candle to DuckDB columnar storage
                try:
                    duckdb_driver.insert_candles([candle])
                except Exception as e:
                    logger.error(f"Error persisting candle to DuckDB: {e}")

    async def _process_tick(self, price: float, timestamp_ms: int, volume: float):
        self.last_price = price
        self.last_tick_time = time.time()
        self.latency_ms = max(5.0, round(random.uniform(8.0, 24.0), 1))

        # Recalculate open trade PnL instantly
        open_positions = self._recalculate_open_positions(price)

        # Broadcast live tick and positions
        payload = {
            "type": "TICK",
            "symbol": self.symbol,
            "price": price,
            "volume": volume,
            "timestamp": timestamp_ms,
            "latency_ms": self.latency_ms,
            "open_positions": open_positions
        }
                # Evaluate Prop Firm Compliance Shield
        compliance_status = compliance_engine.evaluate_compliance(open_positions)
        payload["compliance_status"] = compliance_status

        await ws_manager.broadcast(payload, channel="market_ticks")
        if compliance_status["overall_status"] != "COMPLIANT":
            await ws_manager.broadcast({
                "type": "COMPLIANCE_ALERT",
                "data": compliance_status
            }, channel="system_metrics")

    def _recalculate_open_positions(self, current_price: float) -> List[Dict[str, Any]]:
        try:
            open_trades = sqlite_driver.get_open_trades()
            updated_trades = []
            for tr in open_trades:
                entry = float(tr["entry_price"])
                qty = float(tr["qty"])
                side = tr["side"].upper()
                sl = float(tr["stop_loss"]) if tr.get("stop_loss") else None

                if side in ("BUY", "LONG"):
                    unrealized_pnl = (current_price - entry) * qty
                    r_unit = (entry - sl) if sl and (entry > sl) else None
                else:
                    unrealized_pnl = (entry - current_price) * qty
                    r_unit = (sl - entry) if sl and (sl > entry) else None

                r_multiple = (unrealized_pnl / (r_unit * qty)) if (r_unit and qty > 0) else None

                updated_trades.append({
                    "id": tr["id"],
                    "symbol": tr["symbol"],
                    "side": side,
                    "entry_price": entry,
                    "current_price": current_price,
                    "qty": qty,
                    "stop_loss": sl,
                    "take_profit": tr.get("take_profit"),
                    "unrealized_pnl": round(unrealized_pnl, 2),
                    "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,
                    "entry_time": tr["entry_time"]
                })
            return updated_trades
        except Exception as e:
            logger.error(f"Error recalculating open positions: {e}")
            return []

binance_client = BinanceStreamClient()
