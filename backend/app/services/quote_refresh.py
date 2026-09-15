"""Bounded open-trade quote refresh for the journal surfaces.

The service never invents a price.  A quote is requested only for the exact
provider identity the user confirmed when the trade was recorded
(``price_source`` + ``price_source_symbol``); anything else stays explicitly
``UNAVAILABLE``.  Requests are shared per provider identity, concurrency is
bounded, failures back off exponentially, and a failed refresh can only return
the previous quote as explicitly stale "last known" data.

Automatic local TP/SL evaluation is not performed here.  That path stays in the
tracking monitor with its stricter LIVE + provider-event + <=60s contract.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from app.services.market_data.public_fetcher import (
    FREE_QUOTE_SOURCES,
    TrackingQuoteRateLimit,
    public_market_fetcher,
)

QuoteIdentity = Tuple[str, str]


class QuoteRefreshService:
    MAX_TRADES = 200
    MAX_IDENTITIES = 60
    MAX_CONCURRENCY = 4
    FETCH_TIMEOUT_SECONDS = 12.0
    LIVE_CACHE_SECONDS = 8.0
    NON_LIVE_CACHE_SECONDS = 45.0
    BACKOFF_BASE_SECONDS = 15.0
    BACKOFF_MAX_SECONDS = 300.0

    def __init__(
        self,
        fetcher: Any = None,
        clock: Optional[Callable[[], datetime]] = None,
    ):
        self.fetcher = fetcher or public_market_fetcher
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._cache: Dict[QuoteIdentity, Dict[str, Any]] = {}

    @staticmethod
    def _identity(trade: Dict[str, Any]) -> Optional[QuoteIdentity]:
        source = str(trade.get("price_source") or "").strip().lower()
        symbol = trade.get("price_source_symbol")
        if source not in FREE_QUOTE_SOURCES or not symbol:
            return None
        cleaned = str(symbol).strip()
        if not cleaned or len(cleaned) > 128:
            return None
        return source, cleaned

    @staticmethod
    def _age_seconds(observed_at: Optional[str], now: datetime) -> Optional[float]:
        if not observed_at:
            return None
        try:
            parsed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        age = (now - parsed.astimezone(timezone.utc)).total_seconds()
        return round(age, 3) if math.isfinite(age) else None

    @staticmethod
    def _quote_view(quote: Dict[str, Any], checked_at: datetime) -> Dict[str, Any]:
        return {
            "quote_status": quote.get("status") or "UNAVAILABLE",
            "price": quote.get("price"),
            "price_kind": quote.get("price_kind"),
            "source_id": quote.get("source_id"),
            "source_symbol": quote.get("source_symbol"),
            "observed_at": quote.get("observed_at"),
            "checked_at": checked_at.isoformat(),
            "age_seconds": QuoteRefreshService._age_seconds(quote.get("observed_at"), checked_at),
            "reason": quote.get("reason"),
        }

    def _cached_quote(self, identity: QuoteIdentity, now: datetime) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(identity)
        if entry is None:
            return None
        if entry.get("kind") == "error":
            retry_at = entry.get("retry_at")
            if retry_at is not None and now < retry_at:
                return {"status": "UNAVAILABLE", "reason": entry.get("reason") or "PROVIDER_COOLDOWN",
                        "source_id": identity[0], "source_symbol": identity[1],
                        "price": None, "price_kind": None, "observed_at": None}
            return None
        fetched_at = entry.get("fetched_at")
        if fetched_at is None:
            return None
        ttl = (
            self.LIVE_CACHE_SECONDS
            if entry.get("quote", {}).get("status") == "LIVE"
            else self.NON_LIVE_CACHE_SECONDS
        )
        if (now - fetched_at).total_seconds() < ttl:
            return entry["quote"]
        return None

    def _last_known(self, identity: QuoteIdentity) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(identity)
        if not entry:
            return None
        quote = (
            entry.get("quote")
            if entry.get("kind") == "quote"
            else entry.get("last_known_quote")
        ) or {}
        if quote.get("price") is None:
            return None
        return {
            "price": quote.get("price"),
            "observed_at": quote.get("observed_at"),
            "quote_status": quote.get("status"),
        }

    async def _fetch_identity(
        self,
        identity: QuoteIdentity,
        semaphore: asyncio.Semaphore,
        now: datetime,
    ) -> Dict[str, Any]:
        cached = self._cached_quote(identity, now)
        if cached is not None:
            return cached
        async with semaphore:
            identity_after_wait = self._cached_quote(identity, self.clock())
            if identity_after_wait is not None:
                return identity_after_wait
            source, symbol = identity
            try:
                result = await asyncio.wait_for(
                    self.fetcher.fetch_quote(symbol, source),
                    timeout=self.FETCH_TIMEOUT_SECONDS,
                )
                quote = result.as_dict() if hasattr(result, "as_dict") else dict(result)
            except TrackingQuoteRateLimit as exc:
                self._register_failure(identity, now, reason="PROVIDER_RATE_LIMIT", retry_after=float(exc))
                return {"status": "UNAVAILABLE", "reason": "PROVIDER_RATE_LIMIT",
                        "source_id": source, "source_symbol": symbol,
                        "price": None, "price_kind": None, "observed_at": None}
            except Exception:  # noqa: BLE001 - provider failures must stay bounded and visible
                self._register_failure(identity, now, reason="PROVIDER_UNAVAILABLE")
                return {"status": "UNAVAILABLE", "reason": "PROVIDER_UNAVAILABLE",
                        "source_id": source, "source_symbol": symbol,
                        "price": None, "price_kind": None, "observed_at": None}
            quote.setdefault("source_id", source)
            quote.setdefault("source_symbol", symbol)
            if quote.get("status") == "UNAVAILABLE":
                self._register_failure(identity, now, reason=str(quote.get("reason") or "NO_QUOTE"))
            else:
                self._cache[identity] = {"kind": "quote", "quote": quote, "fetched_at": now,
                                         "failures": 0}
            return quote

    def _register_failure(
        self,
        identity: QuoteIdentity,
        now: datetime,
        *,
        reason: str,
        retry_after: Optional[float] = None,
    ) -> None:
        previous = self._cache.get(identity)
        prior_failures = 0
        prior_quote = None
        if previous:
            if previous.get("kind") == "error":
                prior_failures = int(previous.get("failures", 0))
                prior_quote = previous.get("last_known_quote")
            else:
                prior_quote = previous.get("quote")
        failures = prior_failures + 1
        delay = retry_after if retry_after is not None else min(
            self.BACKOFF_BASE_SECONDS * (2 ** min(failures - 1, 5)),
            self.BACKOFF_MAX_SECONDS,
        )
        self._cache[identity] = {
            "kind": "error",
            "reason": reason,
            "failures": failures,
            "retry_at": now + timedelta(seconds=max(1.0, delay)),
            "last_known_quote": prior_quote,
        }

    async def refresh(
        self,
        trades: Iterable[Dict[str, Any]],
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        reference = now or self.clock()
        checked_at = reference.astimezone(timezone.utc)
        capped = [dict(trade) for trade in trades][: self.MAX_TRADES]
        selected = [trade for trade in capped if str(trade.get("status") or "").upper() == "OPEN"]

        groups: Dict[QuoteIdentity, List[str]] = {}
        results: Dict[str, Dict[str, Any]] = {}
        skipped = 0
        for trade in selected:
            trade_id = str(trade.get("id") or "")
            if not trade_id:
                continue
            identity = self._identity(trade)
            if identity is None:
                results[trade_id] = {
                    "quote_status": "UNAVAILABLE",
                    "reason": "NO_VERIFIED_QUOTE_IDENTITY",
                    "price": None,
                    "price_kind": None,
                    "source_id": None,
                    "source_symbol": None,
                    "observed_at": None,
                    "checked_at": checked_at.isoformat(),
                    "age_seconds": None,
                    "last_known": None,
                }
                continue
            groups.setdefault(identity, []).append(trade_id)

        identities = list(groups.items())[: self.MAX_IDENTITIES]
        skipped = max(0, len(groups) - len(identities))
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)
        fetched = await asyncio.gather(
            *(self._fetch_identity(identity, semaphore, reference) for identity, _ in identities)
        )
        for (identity, trade_ids), quote in zip(identities, fetched):
            view = self._quote_view(quote, checked_at)
            last_known = self._last_known(identity) if view["price"] is None else None
            if view["price"] is None and last_known is not None:
                view["last_known"] = {**last_known, "stale": True}
            else:
                view["last_known"] = None
            for trade_id in trade_ids:
                results[trade_id] = dict(view)

        return {
            "checked_at": checked_at.isoformat(),
            "requested": len(selected),
            "identities": len(identities),
            "skipped_identities": skipped,
            "quotes": results,
        }


quote_refresh_service = QuoteRefreshService()
