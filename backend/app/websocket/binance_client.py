from app.services.compliance_engine import compliance_engine
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import websockets
from app.core.config import settings
from app.websocket.connection_manager import ws_manager
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

logger = logging.getLogger(__name__)

LIVE = "LIVE"
DEGRADED = "DEGRADED"
UNAVAILABLE = "UNAVAILABLE"

class BinanceStreamClient:
    """AsyncIO Binance Market Data WebSocket Client with real-time PnL recalculator."""

    def __init__(self, symbol: str = "BTCUSDT", market_data_enabled: Optional[bool] = None):
        self.symbol = symbol.upper()
        self.market_data_enabled = settings.market_data_enabled if market_data_enabled is None else bool(market_data_enabled)
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.last_price: Optional[float] = None
        self.last_tick_time: Optional[float] = None
        self.event_age_ms: Optional[float] = None
        self.candle_buffer: Dict[str, Any] = {}
        self.market_data_status = DEGRADED if self.market_data_enabled else UNAVAILABLE

    def _set_live(self):
        self.market_data_status = LIVE

    def _set_degraded(self):
        if self.market_data_enabled:
            self.market_data_status = DEGRADED
        else:
            self.market_data_status = UNAVAILABLE

    def _set_unavailable(self):
        self.market_data_status = UNAVAILABLE

    def _stream_url(self) -> str:
        stream_name = f"{self.symbol.lower()}@trade"
        kline_name = f"{self.symbol.lower()}@kline_1m"
        return f"wss://stream.binance.com:9443/stream?streams={stream_name}/{kline_name}"

    @staticmethod
    def _taker_side(buyer_is_market_maker: Any) -> str:
        """Maps Binance's trade flag to the initiating (aggressor) side."""
        if buyer_is_market_maker is True:
            return "SELL"
        if buyer_is_market_maker is False:
            return "BUY"
        return "UNKNOWN"

    async def start(self):
        if self.is_running:
            return
        if not self.market_data_enabled:
            self._set_unavailable()
            logger.info("Binance market-data stream disabled by KUANTRA_MARKET_DATA_ENABLED.")
            return
        self._set_degraded()
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
        if not self.market_data_enabled:
            self._set_unavailable()
            return
        url = self._stream_url()

        retry_count = 0
        while self.is_running:
            try:
                self._set_degraded()
                await self._broadcast_status()
                logger.info(f"Connecting to Binance WS at {url}...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    retry_count = 0
                    logger.info("Connected to Binance live market stream.")
                    while self.is_running:
                        msg = await ws.recv()
                        await self._handle_message(json.loads(msg))
            except (websockets.exceptions.WebSocketException, OSError, asyncio.TimeoutError) as e:
                retry_count += 1
                self._set_degraded()
                await self._broadcast_status()
                logger.warning(f"Binance WS connection failed: {e}. Market data remains unavailable; reconnecting (attempt {retry_count}).")
                await self._wait_to_reconnect(duration_seconds=10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._set_degraded()
                await self._broadcast_status()
                logger.error(f"Unexpected stream error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def _broadcast_status(self):
        """Publish only the truth state; this never creates a market event or price."""
        await ws_manager.broadcast({
            "type": "MARKET_DATA_STATUS",
            "symbol": self.symbol,
            "status": self.market_data_status,
            "market_data_enabled": self.market_data_enabled,
        }, channel="market_ticks")

    async def _wait_to_reconnect(self, duration_seconds: int = 10):
        """Wait between reconnects without fabricating market events."""
        self._set_degraded()
        logger.warning("[BINANCE WS] No live market data available. Waiting for reconnect...")
        await asyncio.sleep(duration_seconds)

    async def _handle_message(self, data: Dict[str, Any]):
        payload = data.get("data", data)
        if not isinstance(payload, dict):
            logger.warning("Ignoring malformed Binance stream payload.")
            return

        event_type = payload.get("e")
        if event_type == "trade":
            price = float(payload["p"])
            qty = float(payload["q"])
            timestamp = int(payload["E"])
            await self._process_tick(price, timestamp, qty, self._taker_side(payload.get("m")))
        elif event_type == "kline":
            k = payload["k"]
            candle = {
                "symbol": payload["s"],
                "timeframe": k["i"],
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(k["t"] / 1000)),
                "time": int(k["t"] / 1000),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
                "trades_count": int(k["n"]),
                "is_closed": bool(k["x"]),
                # Binance's public kline payload has no monotonic feed
                # sequence.  Preserve the stable kline identity, but keep
                # source_verified false until a gap-aware data plane exists.
                "venue": "BINANCE",
                "feed": "BINANCE_WS_KLINE",
                "source_event_id": f"{payload['s']}:{k['i']}:{k['t']}",
                "source_sequence": None,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "source_verified": False,
            }
            # Broadcast live candle update
            self._set_live()
            await self._broadcast_status()
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

    async def _process_tick(self, price: float, timestamp_ms: int, volume: float, taker_side: str):
        self._set_live()
        self.last_price = price
        self.last_tick_time = timestamp_ms / 1000.0
        self.event_age_ms = max(0.0, round((time.time() * 1000.0) - timestamp_ms, 1))

        # Recalculate open trade PnL instantly
        open_positions = self._recalculate_open_positions(price)

        # Broadcast live tick and positions
        payload = {
            "type": "TICK",
            "symbol": self.symbol,
            "price": price,
            "volume": volume,
            "side": taker_side if taker_side in ("BUY", "SELL", "UNKNOWN") else "UNKNOWN",
            "timestamp": timestamp_ms,
            "event_age_ms": self.event_age_ms,
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

    def _recalculate_open_positions(self, current_price: Optional[float]) -> List[Dict[str, Any]]:
        try:
            open_trades = sqlite_driver.get_open_trades()
            updated_trades = []
            for tr in open_trades:
                entry = float(tr["entry_price"])
                qty = float(tr["qty"])
                side = tr["side"].upper()
                sl = float(tr["stop_loss"]) if tr.get("stop_loss") else None

                if current_price is None:
                    unrealized_pnl = None
                    r_multiple = None
                elif side in ("BUY", "LONG"):
                    unrealized_pnl = (current_price - entry) * qty
                    r_unit = (entry - sl) if sl and (entry > sl) else None
                    r_multiple = (unrealized_pnl / (r_unit * qty)) if (r_unit and qty > 0) else None
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
                    "unrealized_pnl": round(unrealized_pnl, 2) if unrealized_pnl is not None else None,
                    "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,
                    "entry_time": tr["entry_time"]
                })
            return updated_trades
        except Exception as e:
            logger.error(f"Error recalculating open positions: {e}")
            return []

binance_client = BinanceStreamClient()
