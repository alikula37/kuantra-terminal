import asyncio
import json
import time
import pytest
from app.websocket.connection_manager import ConnectionManager
from desktop.push import PushChannel


class FakeWindow:
    def __init__(self):
        self.scripts = []

    def run_js(self, script):
        self.scripts.append(script)


async def test_attach_receives_broadcasts_for_subscribed_channels():
    manager = ConnectionManager()
    win = FakeWindow()
    push = PushChannel(flush_interval=0.01)
    push.attach_windows(lambda: [win])
    push.start()
    manager.attach(push, PushChannel.CHANNELS)
    await manager.broadcast({"type": "TICK", "price": 1.0}, "market_ticks")
    await manager.broadcast({"type": "TV_SYNC_UPDATE", "symbol": "ETHUSDT"}, "tv_sync")
    await manager.broadcast({"type": "IGNORED"}, "not_a_channel")
    deadline = time.time() + 2
    while time.time() < deadline and len(win.scripts) < 1:
        await asyncio.sleep(0.01)
    push.stop()
    joined = "\n".join(win.scripts)
    assert "window.__kuantraPush" in joined
    types = []
    for s in win.scripts:
        payload = s[s.index("(") + 1: s.rindex(")")]
        types += [m["type"] for m in json.loads(payload)]
    assert types == ["TICK", "TV_SYNC_UPDATE"]
    manager.detach(push)
    assert push not in manager.active_connections


async def test_window_errors_do_not_break_channel():
    class Broken:
        def run_js(self, script):
            raise RuntimeError("window gone")

    push = PushChannel(flush_interval=0.01)
    push.attach_windows(lambda: [Broken()])
    push.start()
    await push.send_text(json.dumps({"type": "TICK"}))
    await asyncio.sleep(0.05)
    push.stop()
    assert push.pending() == 0


async def test_tv_sync_broadcast_reaches_tv_sync_channel():
    from app.websocket import connection_manager as cm
    from app.websocket.tv_sync import TradingViewSyncManager
    received = []

    class Sink:
        async def send_text(self, text):
            received.append(json.loads(text))

    sink = Sink()
    cm.ws_manager.attach(sink, {"tv_sync"})
    try:
        await TradingViewSyncManager().handle_extension_message({"symbol": "ethusdt", "timeframe": "5m", "exchange": "binance"})
    finally:
        cm.ws_manager.detach(sink)
    assert received and received[0]["type"] == "TV_SYNC_UPDATE" and received[0]["symbol"] == "ETHUSDT"
