"""Bounded, shared quote polling for local tracking while the app is running."""
import asyncio
import logging
import time

from app.core.config import settings
from app.db.sqlite_driver import sqlite_driver
from app.services.local_tracking import LocalTrackingService, decimal
from app.services.market_data.public_fetcher import public_market_fetcher

logger = logging.getLogger(__name__)


class TrackingMonitor:
    def __init__(self, service=None, fetch=None):
        self.service = service or LocalTrackingService(sqlite_driver)
        self.fetch = fetch or public_market_fetcher.fetch_tracking_quote
        self.quotes = {}
        self.next_poll = {}
        self.failures = {}
        self.provider_backoff = {}
        self.task = None
        self.enabled = True

    def view(self, state):
        key = (state["source_id"], state["source_symbol"])
        observation = self.quotes.get(key)
        status = "WAITING_QUOTE"
        if decimal(state["remaining_qty"], positive=False) == 0:
            status = "COMPLETED"
        elif state.get("external_status", "OPEN") != "OPEN" or not state["enabled"]:
            status = "PAUSED"
        elif not state["targets"] and state["stop_loss"] is None:
            status = "WAITING_TARGETS"
        elif self.enabled and observation and self.service.eligible(state, observation):
            status = "ACTIVE"
        return {**state, "tracking_status": status,
                "last_quote": observation if observation and self.service.eligible(state, observation) else None}

    async def poll(self, *, enabled):
        self.enabled = enabled
        if not enabled:
            self.quotes.clear()
            return
        states = await asyncio.to_thread(self.service.list)
        groups = {}
        for state in states:
            if (state["enabled"] and state["external_status"] == "OPEN"
                    and decimal(state["remaining_qty"], positive=False) > 0
                    and (state["targets"] or state["stop_loss"] is not None)
                    and state["source_id"] and state["source_symbol"]):
                key = (state["source_id"], state["source_symbol"])
                groups.setdefault(key, []).append(state)
        for cache in (self.quotes, self.next_poll, self.failures):
            for key in set(cache) - set(groups):
                cache.pop(key, None)
        semaphore = asyncio.Semaphore(4)

        async def update(key):
            async with semaphore:
                if self.provider_backoff.get(key[0], 0) > time.monotonic():
                    return
                try:
                    observation = await asyncio.wait_for(self.fetch(*key), timeout=12)
                    self.quotes[key] = observation
                    if not any(self.service.eligible(state, observation) for state in groups[key]):
                        raise ValueError("No eligible provider observation")
                    for state in groups[key]:
                        await asyncio.to_thread(self.service.observe, state["trade_id"], observation)
                    self.failures[key] = 0
                    self.next_poll[key] = time.monotonic() + 15
                except Exception as exc:
                    self.quotes.pop(key, None)
                    self.failures[key] = min(self.failures.get(key, 0) + 1, 6)
                    delay = max(15 * 2 ** self.failures[key], getattr(exc, "retry_after", 0))
                    self.next_poll[key] = time.monotonic() + delay
                    if getattr(exc, "retry_after", 0):
                        self.provider_backoff[key[0]] = time.monotonic() + delay
                    logger.debug("Local tracking waits for eligible quote: %s", type(exc).__name__)

        due = sorted((key for key in groups if self.next_poll.get(key, 0) <= time.monotonic()),
                     key=lambda key: self.next_poll.get(key, 0))[:20]
        await asyncio.gather(*(update(key) for key in due))

    async def _run(self):
        while True:
            try:
                await self.poll(enabled=settings.market_data_enabled)
            except Exception:
                self.quotes.clear()
                logger.exception("Local tracking paused after evidence/read failure")
            await asyncio.sleep(5)

    async def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        self.quotes.clear()


tracking_monitor = TrackingMonitor()
