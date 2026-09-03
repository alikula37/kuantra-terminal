"""
PushChannel: a ConnectionManager sink that forwards broadcast messages to every pywebview
window as `window.__kuantraPush([...])`, batched every `flush_interval` seconds.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Callable, List

logger = logging.getLogger("desktop.push")


class PushChannel:
    CHANNELS = {"market_ticks", "kline_updates", "open_positions", "system_metrics", "tv_sync"}

    def __init__(self, flush_interval: float = 0.05, max_batch: int = 500):
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._interval = flush_interval
        self._max_batch = max_batch
        self._get_windows: Callable[[], list] = lambda: []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def attach_windows(self, get_windows: Callable[[], list]) -> None:
        self._get_windows = get_windows

    async def send_text(self, text: str) -> None:  # ConnectionManager sink protocol
        self._queue.put_nowait(text)

    def pending(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._flush_loop, name="kuantra-push", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _drain(self) -> List[str]:
        items: List[str] = []
        try:
            items.append(self._queue.get(timeout=self._interval))
            while len(items) < self._max_batch:
                items.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return items

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            items = self._drain()
            if not items:
                continue
            batch = "[" + ",".join(items) + "]"
            script = f"window.__kuantraPush && window.__kuantraPush({batch})"
            for win in list(self._get_windows()):
                try:
                    win.run_js(script)
                except Exception as exc:  # noqa: BLE001 - a closing window must not kill the stream
                    logger.debug("push to window failed: %s", exc)
