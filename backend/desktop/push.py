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

    MAX_QUEUE = 5000

    def __init__(self, flush_interval: float = 0.05, max_batch: int = 500):
        # Bounded: if the UI stalls, market ticks must not grow the queue without limit. The
        # oldest message is the one worth losing, so a full queue drops from the front.
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=self.MAX_QUEUE)
        self._interval = flush_interval
        self._max_batch = max_batch
        self._get_windows: Callable[[], list] = lambda: []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def attach_windows(self, get_windows: Callable[[], list]) -> None:
        self._get_windows = get_windows

    async def send_text(self, text: str) -> None:  # ConnectionManager sink protocol
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            try:
                self._queue.get_nowait()  # drop the oldest, keep the freshest state
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                logger.debug("push queue full; dropping message")

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
        # A stopped channel must not stay subscribed: nothing drains the queue any more, so
        # every later broadcast would just accumulate. There is no runtime reference here to hop
        # onto the backend loop with; ConnectionManager.detach documents this shutdown path as the
        # one allowed off-loop caller. Imported here to avoid an import cycle.
        try:
            from app.websocket.connection_manager import ws_manager
            ws_manager.detach(self)
        except Exception as exc:  # noqa: BLE001
            logger.debug("detach on stop failed: %s", exc)

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
            # Each item is already a complete JSON document from json.dumps (ensure_ascii=True by
            # default), so it carries no raw newline or non-ASCII byte and concatenating is valid.
            batch = "[" + ",".join(items) + "]"
            script = f"window.__kuantraPush && window.__kuantraPush({batch})"
            for win in list(self._get_windows()):
                try:
                    win.run_js(script)
                except Exception as exc:  # noqa: BLE001 - a closing window must not kill the stream
                    logger.debug("push to window failed: %s", exc)
