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
        self.notes = {}
        self.task = None
        self.enabled = True

    def _note(self, key, reason, *, error=None, attempt=True):
        note = {
            "wait_reason": reason,
            "last_error": error,
            "last_attempt_at": time.time() if attempt else (self.notes.get(key) or {}).get("last_attempt_at"),
            "last_observation_at": time.time() if reason is None else (self.notes.get(key) or {}).get("last_observation_at"),
        }
        self.notes[key] = note

    def _monitor_view(self, key):
        if not self.enabled:
            reason = "MARKET_DATA_DISABLED"
        elif self.provider_backoff.get(key[0], 0) > time.monotonic():
            reason = "PROVIDER_RATE_LIMIT"
        elif self.failures.get(key, 0) > 0:
            reason = "PROVIDER_ERROR"
        else:
            reason = (self.notes.get(key) or {}).get("wait_reason") or "WAITING_PROVIDER_OBSERVATION"
        note = self.notes.get(key) or {}
        next_at = self.next_poll.get(key)
        return {
            "enabled": self.enabled,
            "wait_reason": reason,
            "last_error": note.get("last_error"),
            "last_attempt_at": note.get("last_attempt_at"),
            "last_observation_at": note.get("last_observation_at"),
            "next_poll_in_seconds": round(max(0.0, next_at - time.monotonic()), 1) if next_at else None,
        }

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
                "monitor": self._monitor_view(key),
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
        for cache in (self.quotes, self.next_poll, self.failures, self.notes):
            for key in set(cache) - set(groups):
                cache.pop(key, None)
        semaphore = asyncio.Semaphore(4)

        async def update(key):
            async with semaphore:
                if self.provider_backoff.get(key[0], 0) > time.monotonic():
                    return
                try:
                    observation = await asyncio.wait_for(self.fetch(*key), timeout=12)
                except Exception as exc:
                    # A real provider failure: back off and say why.
                    self.quotes.pop(key, None)
                    self.failures[key] = min(self.failures.get(key, 0) + 1, 6)
                    delay = max(15 * 2 ** self.failures[key], getattr(exc, "retry_after", 0))
                    self.next_poll[key] = time.monotonic() + delay
                    if getattr(exc, "retry_after", 0):
                        self.provider_backoff[key[0]] = time.monotonic() + delay
                    self._note(key, "PROVIDER_ERROR", error=str(exc) or type(exc).__name__)
                    logger.info("Local tracking provider error for %s: %s", key, exc)
                    return
                if not any(self.service.eligible(state, observation) for state in groups[key]):
                    # The provider answered but the observation is not usable yet
                    # (stale, wrong identity or not newer than armed_at).  That is
                    # a normal waiting state, not a failure: retry soon, no backoff,
                    # and keep the reason visible instead of a silent wait.
                    self.quotes.pop(key, None)
                    self.next_poll[key] = time.monotonic() + 5
                    self.failures[key] = 0
                    self._note(key, "WAITING_FRESH_PROVIDER_EVENT")
                    logger.info("Local tracking waits for a fresh provider event: %s", key)
                    return
                self.quotes[key] = observation
                for state in groups[key]:
                    await asyncio.to_thread(self.service.observe, state["trade_id"], observation)
                self.failures[key] = 0
                self.next_poll[key] = time.monotonic() + 15
                self._note(key, None)

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
