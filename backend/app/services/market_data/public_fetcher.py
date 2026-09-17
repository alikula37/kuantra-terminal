"""
Public Unauthenticated Market Data Fetcher for Kuantra Terminal.
Provides zero-auth crypto and macro/forex market data retrieval with automatic
failover between Binance Public API, Bybit Public API, Yahoo Finance, and Stooq.
Inspired by critic-forecast zero-friction public data architectures.
"""

import asyncio
import csv
import io
import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote as url_quote

import httpx

logger = logging.getLogger("public_market_fetcher")


class TrackingQuoteRateLimit(ValueError):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__("Public quote rate limit")

# Standard intervals supported across public gateways
SUPPORTED_CRYPTO_INTERVALS = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "60m": "1h",
    "2h": "2h",
    "120m": "2h",
    "4h": "4h",
    "240m": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "1D": "1d",
    "d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1W": "1w",
    "w": "1w",
    "1M": "1M",
    "M": "1M"
}

BYBIT_INTERVAL_MAP = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
    "1w": "W",
    "1M": "M"
}

MACRO_SYMBOL_MAP = {
    "EURUSD": ("EURUSD=X", "eurusd"),
    "EUR/USD": ("EURUSD=X", "eurusd"),
    "GBPUSD": ("GBPUSD=X", "gbpusd"),
    "GBP/USD": ("GBPUSD=X", "gbpusd"),
    "USDJPY": ("JPY=X", "usdjpy"),
    "USD/JPY": ("JPY=X", "usdjpy"),
    "AUDUSD": ("AUDUSD=X", "audusd"),
    "USDCAD": ("CAD=X", "usdcad"),
    "USDCHF": ("CHF=X", "usdchf"),
    # Keep spot FX/metal aliases separate from futures/token instruments.  A
    # failed spot quote must never silently become a COMEX future or a token.
    "XAUUSD": ("XAUUSD=X", "xauusd"),
    "XAUUSD=X": ("XAUUSD=X", "xauusd"),
    "GOLD": ("GC=F", "gc.f"),
    "GC=F": ("GC=F", "gc.f"),
    "XAGUSD": ("XAGUSD=X", "xagusd"),
    "XAGUSD=X": ("XAGUSD=X", "xagusd"),
    "SILVER": ("SI=F", "si.f"),
    "SI=F": ("SI=F", "si.f"),
    "WTI": ("CL=F", "cl.f"),
    "CRUDE": ("CL=F", "cl.f"),
    "SPY": ("SPY", "spy.us"),
    "SP500": ("^GSPC", "^spx"),
    "QQQ": ("QQQ", "qqq.us"),
    "NASDAQ": ("^IXIC", "^ndq"),
    "DOW": ("^DJI", "^dji"),
    "AAPL": ("AAPL", "aapl.us"),
    "TSLA": ("TSLA", "tsla.us"),
    "NVDA": ("NVDA", "nvda.us"),
    "MSFT": ("MSFT", "msft.us"),
    "AMZN": ("AMZN", "amzn.us")
}

KNOWN_QUOTE_CURRENCIES = ("USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH", "TRY", "FDUSD", "TUSD")

QUOTE_STATUSES = frozenset({"LIVE", "DELAYED", "EOD", "UNAVAILABLE"})
FREE_QUOTE_SOURCES = frozenset({
    "binance_public",
    "bybit_public",
    "biquote_public",
    "yahoo_public",
    "stooq_public",
})

BIQUOTE_SYMBOL_MAP = {
    "XAUUSD": "XAUUSD",
    "XAUUSD=X": "XAUUSD",
}

BIQUOTE_SEARCH_ALIASES = {"XAU", "XAUUSD", "XAUUSD=X", "GOLD"}

BIQUOTE_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}


@dataclass(frozen=True)
class PublicQuote:
    """A best-effort free quote with explicit source and freshness metadata."""

    requested_symbol: str
    source_id: Optional[str]
    source_symbol: Optional[str]
    price: Optional[float]
    status: str
    price_kind: Optional[str]
    observed_at: Optional[str]
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "requested_symbol": self.requested_symbol,
            "source_id": self.source_id,
            "source_symbol": self.source_symbol,
            "price": self.price,
            "status": self.status,
            "price_kind": self.price_kind,
            "observed_at": self.observed_at,
            "reason": self.reason,
            "free_source": True,
            "credentials_required": False,
        }


@dataclass(frozen=True)
class InstrumentSearchResult:
    """One exact, user-selectable instrument returned by a public provider."""

    symbol: str
    name: str
    exchange: Optional[str]
    asset_type: str
    source_id: str
    source_symbol: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "asset_type": self.asset_type,
            "source_id": self.source_id,
            "source_symbol": self.source_symbol,
        }


def normalize_crypto_symbol(symbol: str) -> str:
    """Normalizes raw input symbol into standard uppercase exchange pair string."""
    cleaned = re.sub(r"[\s/_\-]+", "", symbol).upper().strip()
    if not cleaned:
        return "BTCUSDT"

    # If it is a recognized macro ticker, preserve clean ticker symbol
    if cleaned in MACRO_SYMBOL_MAP or symbol.upper().strip() in MACRO_SYMBOL_MAP:
        return cleaned

    # If ticker has a valid quote currency attached (and isn't just the base ticker itself)
    has_valid_quote = any(
        cleaned.endswith(q) and len(cleaned) > len(q)
        for q in KNOWN_QUOTE_CURRENCIES
    )

    if not has_valid_quote:
        return f"{cleaned}USDT"

    return cleaned


def normalize_interval(interval: str) -> str:
    """Maps varied timeframe strings to standard format."""
    normalized = SUPPORTED_CRYPTO_INTERVALS.get(interval.strip(), "1h")
    return normalized


class ProviderFetchError(ValueError):
    """A declared-provider fetch failed; no other provider may be substituted."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason, self.message = reason, message


class PublicMarketDataFetcher:
    """
    Zero-auth public market data fetcher with high-availability failover.
    Fetches spot/futures klines and macro/forex candles directly from free public endpoints.
    """

    # Bounded provider pagination for "load older" history.  Each page is one
    # provider request; the cap keeps a single user action bounded and polite.
    MAX_HISTORY_PAGES = 10
    BINANCE_PAGE_LIMIT = 1000
    # Yahoo intraday lookbacks (ms).  Longer requests are clamped to the
    # provider's documented window instead of failing or inventing data.
    YAHOO_INTRADAY_LOOKBACK_MS = {
        "1m": 7 * 86_400_000,
        "2m": 60 * 86_400_000,
        "5m": 60 * 86_400_000,
        "15m": 60 * 86_400_000,
        "30m": 60 * 86_400_000,
        "90m": 60 * 86_400_000,
        "60m": 730 * 86_400_000,
    }
    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
    BINANCE_EXCHANGE_INFO_URL = "https://api.binance.com/api/v3/exchangeInfo"
    BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
    BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
    BYBIT_KLINES_URL = "https://api.bybit.com/v5/market/kline"
    BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"
    BIQUOTE_OHLC_URL = "https://biquote.io/api/{symbol}/ohlc"
    YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
    STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={ticker}&i=d"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._binance_instrument_cache: List[Dict[str, Any]] = []
        self._binance_instrument_cache_at = 0.0

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache"
        }

    @staticmethod
    def _search_text(value: Any) -> str:
        return str(value or "").strip().casefold()

    @staticmethod
    def _valid_search_symbol(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        symbol = value.strip().upper()
        if not symbol or len(symbol) > 64 or any(ord(character) < 32 for character in symbol):
            return None
        if not re.fullmatch(r"[A-Z0-9.^=:/_-]+", symbol):
            return None
        return symbol

    @staticmethod
    def _search_rank(query: str, result: InstrumentSearchResult) -> Tuple[int, str]:
        needle = query.casefold()
        symbol = result.symbol.casefold()
        name = result.name.casefold()
        if symbol == needle:
            rank = 0
        elif symbol.startswith(needle):
            rank = 1
        elif name.startswith(needle):
            rank = 2
        elif needle in symbol:
            rank = 3
        elif needle in name:
            rank = 4
        else:
            rank = 5
        return rank, symbol

    @staticmethod
    def _quote_priority(symbol: str) -> int:
        """Prefer the usual USD-backed pair when a crypto base has several pairs."""
        for index, quote in enumerate(("USDT", "USDC", "USD", "FDUSD", "BUSD", "TUSD", "EUR", "BTC", "ETH", "TRY")):
            if symbol.endswith(quote) and len(symbol) > len(quote):
                return index
        return 99

    async def _load_binance_instruments(self) -> List[Dict[str, Any]]:
        now = time.monotonic()
        if self._binance_instrument_cache and now - self._binance_instrument_cache_at < 600:
            return self._binance_instrument_cache

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.BINANCE_EXCHANGE_INFO_URL, headers=self._get_headers())
        if response.status_code != 200:
            raise RuntimeError(f"Binance exchangeInfo returned HTTP {response.status_code}")
        payload = response.json()
        rows = payload.get("symbols") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("Binance exchangeInfo response was malformed")
        instruments = [
            row for row in rows
            if isinstance(row, dict)
            and row.get("status") == "TRADING"
            and row.get("isSpotTradingAllowed", True) is not False
            and self._valid_search_symbol(row.get("symbol"))
        ]
        self._binance_instrument_cache = instruments
        self._binance_instrument_cache_at = now
        return instruments

    async def _search_binance_instruments(self, query: str, limit: int) -> List[InstrumentSearchResult]:
        rows = await self._load_binance_instruments()
        needle = query.casefold()
        candidates: List[InstrumentSearchResult] = []
        for row in rows:
            symbol = self._valid_search_symbol(row.get("symbol"))
            base_asset = self._search_text(row.get("baseAsset"))
            quote_asset = self._search_text(row.get("quoteAsset"))
            if not symbol:
                continue
            haystack = " ".join((symbol.casefold(), base_asset, quote_asset))
            if needle not in haystack:
                continue
            base_display = str(row.get("baseAsset") or symbol)
            quote_display = str(row.get("quoteAsset") or "")
            candidates.append(InstrumentSearchResult(
                symbol=symbol,
                name=f"{base_display} / {quote_display}" if quote_display else base_display,
                exchange="Binance Spot",
                asset_type="CRYPTO",
                source_id="binance_public",
                source_symbol=symbol,
            ))
        return sorted(
            candidates,
            key=lambda item: (*self._search_rank(query, item)[:1], self._quote_priority(item.symbol), item.symbol.casefold()),
        )[:limit]

    async def _search_biquote_instruments(self, query: str, limit: int) -> List[InstrumentSearchResult]:
        """Expose the exact keyless spot-metal route without inventing a catalog."""
        compact_query = re.sub(r"[\s/_-]+", "", query).upper()
        if compact_query not in BIQUOTE_SEARCH_ALIASES:
            return []
        return [InstrumentSearchResult(
            symbol="XAUUSD",
            name="Gold / US Dollar",
            exchange="Biquote Spot",
            asset_type="COMMODITY",
            source_id="biquote_public",
            source_symbol="XAUUSD",
        )][:limit]

    async def _search_yahoo_instruments(self, query: str, limit: int) -> List[InstrumentSearchResult]:
        params = {
            "q": query,
            "quotesCount": max(10, min(50, limit * 3)),
            "newsCount": 0,
            "enableFuzzyQuery": "false",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.YAHOO_SEARCH_URL, params=params, headers=self._get_headers())
        if response.status_code != 200:
            raise RuntimeError(f"Yahoo search returned HTTP {response.status_code}")
        payload = response.json()
        rows = payload.get("quotes") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError("Yahoo search response was malformed")

        type_map = {
            "EQUITY": "STOCK",
            "ETF": "ETF",
            "CURRENCY": "FOREX",
            "FUTURE": "FUTURE",
            "INDEX": "INDEX",
            "MUTUALFUND": "FUND",
        }
        results: List[InstrumentSearchResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            # Binance provides exact spot pairs for crypto. Yahoo's crypto
            # symbols (for example LINK-USD) do not use the candle/quote
            # routing contract, so they are not promoted from this provider.
            quote_type = str(row.get("quoteType") or "").upper()
            if quote_type == "CRYPTOCURRENCY":
                continue
            symbol = self._valid_search_symbol(row.get("symbol"))
            if not symbol:
                continue
            name = str(row.get("longname") or row.get("shortname") or symbol).strip()
            exchange = str(row.get("exchDisp") or row.get("exchange") or "").strip() or None
            results.append(InstrumentSearchResult(
                symbol=symbol,
                name=name,
                exchange=exchange,
                asset_type=type_map.get(quote_type, quote_type or "OTHER"),
                source_id="yahoo_public",
                source_symbol=symbol,
            ))
        return sorted(results, key=lambda item: self._search_rank(query, item))[:limit]

    async def search_instruments(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search exact instruments across free public inventories.

        Search results are suggestions only. The UI must retain the exact
        ``source_symbol`` and require an explicit user confirmation before a
        quote or candle request is made.
        """
        cleaned_query = str(query or "").strip()
        if not cleaned_query:
            return {"status": "INVALID_QUERY", "reason": "QUERY_REQUIRED", "query": "", "results": [], "sources": []}
        if len(cleaned_query) > 64 or any(ord(character) < 32 for character in cleaned_query):
            return {"status": "INVALID_QUERY", "reason": "QUERY_INVALID", "query": cleaned_query[:64], "results": [], "sources": []}

        clamped_limit = max(1, min(50, int(limit)))
        provider_results: List[InstrumentSearchResult] = []
        successful_sources: List[str] = []
        failures: List[str] = []
        provider_calls = (
            ("binance_public", self._search_binance_instruments),
            ("yahoo_public", self._search_yahoo_instruments),
        )
        responses = await asyncio.gather(
            *(self._run_instrument_search_provider(source_id, provider, cleaned_query, clamped_limit) for source_id, provider in provider_calls),
        )
        for source_id, results, error in responses:
            if error:
                failures.append(f"{source_id}:{error}")
            else:
                successful_sources.append(source_id)
                provider_results.extend(results)

        biquote_results = await self._search_biquote_instruments(cleaned_query, clamped_limit)
        if biquote_results:
            successful_sources.append("biquote_public")
            provider_results.extend(biquote_results)

        deduplicated: Dict[Tuple[str, str, Optional[str]], InstrumentSearchResult] = {}
        for result in provider_results:
            key = (result.source_id, result.source_symbol, result.exchange)
            deduplicated.setdefault(key, result)
        ordered = sorted(
            deduplicated.values(),
            key=lambda item: (*self._search_rank(cleaned_query, item)[:1], self._quote_priority(item.symbol), item.symbol.casefold()),
        )[:clamped_limit]
        if ordered:
            status = "READY"
            reason = None
        elif successful_sources:
            status = "NO_MATCH"
            reason = "NO_VERIFIED_INSTRUMENT_MATCH"
        else:
            status = "UNAVAILABLE"
            reason = "SEARCH_PROVIDERS_UNAVAILABLE"
        return {
            "status": status,
            "reason": reason,
            "query": cleaned_query,
            "results": [result.as_dict() for result in ordered],
            "sources": successful_sources,
            "provider_failures": failures,
        }

    async def _run_instrument_search_provider(
        self,
        source_id: str,
        provider: Any,
        query: str,
        limit: int,
    ) -> Tuple[str, List[InstrumentSearchResult], Optional[str]]:
        try:
            return source_id, await provider(query, limit), None
        except Exception as exc:
            logger.warning("[PUBLIC-FETCHER] Instrument search failed for %s: %s", source_id, exc)
            return source_id, [], type(exc).__name__

    @staticmethod
    def _iso_from_timestamp_ms(timestamp_ms: Any) -> Optional[str]:
        try:
            timestamp = float(timestamp_ms) / 1000.0
            if not math.isfinite(timestamp) or timestamp <= 0:
                return None
            return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    @staticmethod
    def _unavailable_quote(
        requested_symbol: str,
        reason: str,
        *,
        source_id: Optional[str] = None,
        source_symbol: Optional[str] = None,
    ) -> PublicQuote:
        return PublicQuote(
            requested_symbol=requested_symbol,
            source_id=source_id,
            source_symbol=source_symbol,
            price=None,
            status="UNAVAILABLE",
            price_kind=None,
            observed_at=None,
            reason=reason,
        )

    @classmethod
    def _quote_candle_values(cls, candle: Dict[str, Any]) -> Optional[Tuple[float, str]]:
        """Return a finite positive close and timestamp suitable for provenance."""
        try:
            price = float(candle["close"])
        except (KeyError, TypeError, ValueError):
            return None
        observed_at = cls._iso_from_timestamp_ms(candle.get("timestamp"))
        if not math.isfinite(price) or price <= 0 or observed_at is None:
            return None
        return price, observed_at

    @staticmethod
    def _macro_key(symbol: str) -> Optional[str]:
        raw = str(symbol or "").strip().upper()
        if raw in MACRO_SYMBOL_MAP:
            return raw
        compact = re.sub(r"\s+", "", raw)
        return compact if compact in MACRO_SYMBOL_MAP else None

    async def fetch_tracking_quote(self, source: str, symbol: str) -> Dict[str, Any]:
        """Exact recent trade with provider event time, never request/candle time.

        Other public adapters currently cannot attest <=60s event freshness and
        remain display-only for automatic local tracking. No source fallback.
        """
        if not re.fullmatch(r"[A-Z0-9]{2,40}", symbol) or source not in {"binance_public", "bybit_public"}:
            return {"status": "UNAVAILABLE", "source_id": source, "source_symbol": symbol,
                    "reason": "PROVIDER_EVENT_TIME_UNAVAILABLE"}
        binance = source == "binance_public"
        url = ("https://data-api.binance.vision/api/v3/trades" if binance
               else "https://api.bybit.com/v5/market/recent-trade")
        params = {"symbol": symbol, "limit": 1}
        if not binance:
            params["category"] = "spot"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params, headers=self._get_headers())
        if response.status_code in {418, 429}:
            try:
                delay = max(60, float(response.headers.get("Retry-After", "60")))
                if not math.isfinite(delay):
                    delay = 3600
            except ValueError:
                delay = 3600
            raise TrackingQuoteRateLimit(delay)
        response.raise_for_status()
        body = response.json()
        if not binance and body.get("retCode") != 0:
            raise ValueError("Provider rejected quote")
        rows = body if binance else body.get("result", {}).get("list", [])
        if not isinstance(rows, list) or not rows:
            raise ValueError("Missing recent provider trade")
        row = rows[-1] if binance else rows[0]
        if not binance and row.get("symbol") != symbol:
            raise ValueError("Provider symbol mismatch")
        price = float(row["price"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid provider price")
        observed = datetime.fromtimestamp(int(row["time"]) / 1000, timezone.utc).isoformat()
        return {"source_id": source, "source_symbol": symbol, "price": str(row["price"]),
                "observed_at": observed, "status": "LIVE", "timestamp_basis": "PROVIDER_EVENT",
                "provider_event_id": str(row["id"] if binance else row["execId"])}

    async def fetch_quote(self, symbol: str, source: str = "auto") -> PublicQuote:
        """Resolve one free public quote without changing instrument identity.

        ``auto`` has a deterministic source order.  A source failure returns an
        explicit ``UNAVAILABLE`` result after the allowed free candidates have
        been tried; it never produces a simulated or cross-instrument price.
        """

        requested = str(symbol or "").strip().upper()
        if not requested:
            return self._unavailable_quote("", "SYMBOL_REQUIRED")
        if len(requested) > 128 or any(ord(character) < 32 for character in requested):
            return self._unavailable_quote(requested, "SYMBOL_INVALID")

        normalized_source = str(source or "auto").strip().lower()
        if normalized_source != "auto" and normalized_source not in FREE_QUOTE_SOURCES:
            return self._unavailable_quote(requested, "UNSUPPORTED_OR_PAID_SOURCE")

        macro_key = self._macro_key(requested)
        if macro_key is not None:
            return await self._fetch_macro_quote(
                requested_symbol=requested,
                macro_key=macro_key,
                source=normalized_source,
            )
        if self._crypto_pair_symbol(requested) is not None:
            return await self._fetch_crypto_quote(
                requested_symbol=requested,
                source=normalized_source,
            )
        return await self._fetch_generic_quote(
            requested_symbol=requested,
            source=normalized_source,
        )

    @staticmethod
    def _crypto_pair_symbol(symbol: str) -> Optional[str]:
        """Return a normalized crypto pair only when the quote currency is explicit.

        A bare ticker such as ``MSFT`` or ``GOOG`` must not be rewritten to a
        fictitious ``MSFTUSDT`` pair.  The journal accepts those symbols as
        generic assets and lets exact Yahoo/Stooq lookup decide availability.
        """
        raw = str(symbol or "").strip().upper()
        compact = re.sub(r"[\s/_\-]+", "", raw)
        if any(
            compact.endswith(quote) and len(compact) > len(quote)
            for quote in KNOWN_QUOTE_CURRENCIES
        ):
            return compact
        return None

    async def _fetch_macro_quote(
        self,
        *,
        requested_symbol: str,
        macro_key: str,
        source: str,
    ) -> PublicQuote:
        yahoo_ticker, stooq_ticker = MACRO_SYMBOL_MAP[macro_key]
        failures: List[str] = []

        # XAU/USD has no reliable Yahoo spot ticker in the free public path.
        # Biquote is an exact XAUUSD public source; it is preferred for this
        # instrument and never changes the requested asset into a token or a
        # futures contract.
        biquote_symbol = BIQUOTE_SYMBOL_MAP.get(macro_key)
        if source in {"auto", "biquote_public"} and biquote_symbol:
            candles = await self._fetch_biquote_candles(biquote_symbol, interval="1h", limit=1)
            if candles:
                latest = candles[-1]
                values = self._quote_candle_values(latest)
                if values is not None:
                    price, observed_at = values
                    return PublicQuote(
                        requested_symbol=requested_symbol,
                        source_id="biquote_public",
                        source_symbol=biquote_symbol,
                        price=price,
                        status="LIVE",
                        price_kind="LAST",
                        observed_at=observed_at,
                    )
            failures.append("BIQUOTE_QUOTE_UNAVAILABLE")
            if source == "biquote_public":
                return self._unavailable_quote(
                    requested_symbol,
                    ";".join(failures),
                    source_id="biquote_public",
                    source_symbol=biquote_symbol,
                )

        if source == "biquote_public":
            return self._unavailable_quote(requested_symbol, "SOURCE_NOT_APPLICABLE_TO_SYMBOL")

        candidates = ("yahoo_public", "stooq_public") if source == "auto" else (source,)

        if "yahoo_public" in candidates:
            try:
                params = {
                    "interval": "1m",
                    "range": "1d",
                    "includePrePost": "false",
                    "events": "div|split",
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.YAHOO_CHART_URL.format(ticker=yahoo_ticker),
                        params=params,
                        headers=self._get_headers(),
                    )
                if response.status_code == 200:
                    candles = self._parse_yahoo_chart(response.json())
                    if candles:
                        latest = candles[-1]
                        values = self._quote_candle_values(latest)
                        if values is not None:
                            price, observed_at = values
                            return PublicQuote(
                                requested_symbol=requested_symbol,
                                source_id="yahoo_public",
                                source_symbol=yahoo_ticker,
                                price=price,
                                status="DELAYED",
                                price_kind="CLOSE",
                                observed_at=observed_at,
                            )
                failures.append("YAHOO_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Yahoo quote failed for %s", yahoo_ticker)
                failures.append("YAHOO_QUOTE_UNAVAILABLE")

        if "stooq_public" in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.STOOQ_CSV_URL.format(ticker=stooq_ticker),
                        headers=self._get_headers(),
                    )
                if response.status_code == 200 and "Date" in response.text:
                    candles = self._parse_stooq_csv(response.text)
                    if candles:
                        latest = candles[-1]
                        values = self._quote_candle_values(latest)
                        if values is not None:
                            price, observed_at = values
                            return PublicQuote(
                                requested_symbol=requested_symbol,
                                source_id="stooq_public",
                                source_symbol=stooq_ticker,
                                price=price,
                                status="EOD",
                                price_kind="CLOSE",
                                observed_at=observed_at,
                            )
                failures.append("STOOQ_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Stooq quote failed for %s", stooq_ticker)
                failures.append("STOOQ_QUOTE_UNAVAILABLE")

        return self._unavailable_quote(
            requested_symbol,
            ";".join(failures) or "NO_FREE_QUOTE_SOURCE",
            source_id=source if source != "auto" else None,
            source_symbol=yahoo_ticker if source == "yahoo_public" else stooq_ticker if source == "stooq_public" else None,
        )

    async def _fetch_generic_quote(self, *, requested_symbol: str, source: str) -> PublicQuote:
        """Fetch an exact generic ticker without changing its asset identity.

        This path is for free-source-supported assets outside the curated
        macro map (for example ``GOOG``).  It deliberately never appends a
        crypto quote currency or adds an exchange suffix.  If a free source
        cannot resolve the exact ticker, the caller receives ``UNAVAILABLE``
        and can enter the actual journal price manually.
        """
        if source not in {"auto", "yahoo_public", "stooq_public"}:
            return self._unavailable_quote(
                requested_symbol,
                "SOURCE_NOT_APPLICABLE_TO_GENERIC_SYMBOL",
            )

        failures: List[str] = []
        candidates = ("yahoo_public", "stooq_public") if source == "auto" else (source,)
        if "yahoo_public" in candidates:
            try:
                params = {
                    "interval": "1d",
                    "range": "5d",
                    "includePrePost": "false",
                    "events": "div|split",
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.YAHOO_CHART_URL.format(ticker=url_quote(requested_symbol, safe="")),
                        params=params,
                        headers=self._get_headers(),
                    )
                if response.status_code == 200:
                    candles = self._parse_yahoo_chart(response.json())
                    if candles:
                        latest = candles[-1]
                        values = self._quote_candle_values(latest)
                        if values is not None:
                            price, observed_at = values
                            return PublicQuote(
                                requested_symbol=requested_symbol,
                                source_id="yahoo_public",
                                source_symbol=requested_symbol,
                                price=price,
                                status="DELAYED",
                                price_kind="CLOSE",
                                observed_at=observed_at,
                            )
                failures.append("YAHOO_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Yahoo generic quote failed for %s", requested_symbol)
                failures.append("YAHOO_QUOTE_UNAVAILABLE")

        if "stooq_public" in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.STOOQ_CSV_URL.format(ticker=url_quote(requested_symbol.lower(), safe="")),
                        headers=self._get_headers(),
                    )
                if response.status_code == 200 and "Date" in response.text:
                    candles = self._parse_stooq_csv(response.text)
                    if candles:
                        latest = candles[-1]
                        values = self._quote_candle_values(latest)
                        if values is not None:
                            price, observed_at = values
                            return PublicQuote(
                                requested_symbol=requested_symbol,
                                source_id="stooq_public",
                                source_symbol=requested_symbol.lower(),
                                price=price,
                                status="EOD",
                                price_kind="CLOSE",
                                observed_at=observed_at,
                            )
                failures.append("STOOQ_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Stooq generic quote failed for %s", requested_symbol)
                failures.append("STOOQ_QUOTE_UNAVAILABLE")

        return self._unavailable_quote(
            requested_symbol,
            ";".join(failures) or "NO_FREE_QUOTE_SOURCE",
            source_id=source if source != "auto" else None,
            source_symbol=requested_symbol if source == "yahoo_public" else requested_symbol.lower() if source == "stooq_public" else None,
        )

    async def _fetch_crypto_quote(self, *, requested_symbol: str, source: str) -> PublicQuote:
        normalized_symbol = normalize_crypto_symbol(requested_symbol)
        failures: List[str] = []
        candidates = ("binance_public", "bybit_public") if source == "auto" else (source,)

        if "binance_public" in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.BINANCE_TICKER_URL,
                        params={"symbol": normalized_symbol},
                        headers=self._get_headers(),
                    )
                if response.status_code == 200:
                    payload = response.json()
                    price = float(payload.get("price"))
                    if math.isfinite(price) and price > 0:
                        return PublicQuote(
                            requested_symbol=requested_symbol,
                            source_id="binance_public",
                            source_symbol=normalized_symbol,
                            price=price,
                            status="LIVE",
                            price_kind="LAST",
                            observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        )
                failures.append("BINANCE_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Binance quote failed for %s", normalized_symbol)
                failures.append("BINANCE_QUOTE_UNAVAILABLE")

        if "bybit_public" in candidates:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self.BYBIT_TICKER_URL,
                        params={"category": "spot", "symbol": normalized_symbol},
                        headers=self._get_headers(),
                    )
                if response.status_code == 200:
                    payload = response.json()
                    rows = payload.get("result", {}).get("list", [])
                    if rows and isinstance(rows[0], dict):
                        price = float(rows[0].get("lastPrice"))
                        if math.isfinite(price) and price > 0:
                            return PublicQuote(
                                requested_symbol=requested_symbol,
                                source_id="bybit_public",
                                source_symbol=normalized_symbol,
                                price=price,
                                status="LIVE",
                                price_kind="LAST",
                                observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            )
                failures.append("BYBIT_QUOTE_UNAVAILABLE")
            except Exception:
                logger.warning("[PUBLIC-FETCHER] Bybit quote failed for %s", normalized_symbol)
                failures.append("BYBIT_QUOTE_UNAVAILABLE")

        return self._unavailable_quote(
            requested_symbol,
            ";".join(failures) or "NO_FREE_QUOTE_SOURCE",
            source_id=source if source != "auto" else None,
            source_symbol=normalized_symbol,
        )

    def _map_yahoo_interval_and_range(self, interval: str, period: Optional[str] = None) -> Tuple[str, str]:
        """Maps standard interval to Yahoo interval and appropriate query range."""
        norm_int = normalize_interval(interval)
        if norm_int == "1m":
            return "1m", period or "1d"
        elif norm_int in ("3m", "5m"):
            return "5m", period or "5d"
        elif norm_int == "15m":
            return "15m", period or "5d"
        elif norm_int == "30m":
            return "30m", period or "1mo"
        elif norm_int in ("1h", "60m"):
            return "60m", period or "1mo"
        elif norm_int in ("2h", "4h", "6h", "8h", "12h"):
            return "60m", period or "3mo"
        elif norm_int in ("1d", "1D", "d", "3d"):
            return "1d", period or "1y"
        elif norm_int in ("1w", "1W", "w"):
            return "1wk", period or "2y"
        elif norm_int in ("1M", "M"):
            return "1mo", period or "5y"
        return "1d", period or "1mo"

    async def _fetch_yahoo_candles(
        self,
        ticker: str,
        *,
        interval: str = "1d",
        period: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Single-source Yahoo Finance fetch; never falls back to another provider."""

        yahoo_interval, auto_range = self._map_yahoo_interval_and_range(interval, period)
        url = self.YAHOO_CHART_URL.format(ticker=ticker)
        if start_time is not None:
            end_ms = int(end_time) if end_time is not None else int(time.time() * 1000)
            clamped_start = self._clamp_yahoo_period1(yahoo_interval, int(start_time), end_ms)
            params = {
                "interval": yahoo_interval,
                "period1": clamped_start // 1000,
                "period2": max(end_ms // 1000, clamped_start // 1000 + 1),
                "includePrePost": "false",
                "events": "div|split",
            }
        else:
            params = {
                "interval": yahoo_interval,
                "range": auto_range,
                "includePrePost": "false",
                "events": "div|split",
            }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(url, params=params, headers=self._get_headers())
        if res.status_code != 200:
            return []
        return self._parse_yahoo_chart(res.json())

    async def _fetch_stooq_candles(self, ticker: str) -> List[Dict[str, Any]]:
        """Single-source Stooq fetch; never falls back to another provider."""

        stooq_url = self.STOOQ_CSV_URL.format(ticker=ticker)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(stooq_url, headers=self._get_headers())
        if res.status_code != 200 or "Date" not in res.text:
            return []
        return self._parse_stooq_csv(res.text)

    async def _fetch_binance_klines_once(
        self, symbol: str, *, interval: str = "1h", limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Single Binance klines page; no Bybit fallback on this path."""

        params = {"symbol": symbol, "interval": normalize_interval(interval),
                  "limit": max(1, min(self.BINANCE_PAGE_LIMIT, int(limit)))}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(self.BINANCE_KLINES_URL, params=params, headers=self._get_headers())
        if res.status_code != 200:
            return []
        return self._parse_binance_klines(res.json())

    async def _fetch_bybit_klines_once(
        self, symbol: str, *, interval: str = "1h", limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Single Bybit klines page; no Binance fallback on this path."""

        bybit_params = {
            "category": "spot", "symbol": symbol,
            "interval": BYBIT_INTERVAL_MAP.get(normalize_interval(interval), "60"),
            "limit": max(1, min(1000, int(limit))),
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(self.BYBIT_KLINES_URL, params=bybit_params, headers=self._get_headers())
        if res.status_code != 200:
            return []
        return self._parse_bybit_klines(res.json())

    async def fetch_declared_provider_candles(
        self,
        provider: str,
        provider_symbol: str,
        *,
        interval: str = "1m",
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Fetch candles ONLY from the declared provider and instrument.

        No silent fallback is permitted: if the declared provider fails, cannot
        serve the instrument, or the provider's own symbol mapping would change
        the product (for example ``GOLD`` mapped to the ``GC=F`` future), this
        raises :class:`ProviderFetchError` with an explicit reason instead.
        """

        declared = str(provider or "").strip().lower()
        symbol = str(provider_symbol or "").strip().upper()
        if declared not in FREE_QUOTE_SOURCES:
            raise ProviderFetchError("PROVIDER_NOT_SUPPORTED", "The declared quote provider is not a supported free public source.")
        if not symbol:
            raise ProviderFetchError("PROVIDER_NOT_DECLARED", "The trade has no declared provider instrument symbol.")

        candles: List[Dict[str, Any]] = []
        resolved_symbol = symbol
        if declared in {"binance_public", "bybit_public"}:
            if symbol in MACRO_SYMBOL_MAP:
                raise ProviderFetchError("PROVIDER_INSTRUMENT_UNSUPPORTED", "The declared provider does not serve this instrument.")
            resolved_symbol = normalize_crypto_symbol(symbol)
            if declared == "binance_public":
                candles = await self._fetch_binance_klines_once(resolved_symbol, interval=interval, limit=limit)
            else:
                candles = await self._fetch_bybit_klines_once(resolved_symbol, interval=interval, limit=limit)
        elif declared == "biquote_public":
            resolved_symbol = BIQUOTE_SYMBOL_MAP.get(symbol)
            if not resolved_symbol:
                raise ProviderFetchError("PROVIDER_INSTRUMENT_UNSUPPORTED", "The declared provider does not serve this instrument.")
            candles = await self._fetch_biquote_candles(resolved_symbol, interval=interval, limit=limit)
        elif declared == "yahoo_public":
            if symbol in MACRO_SYMBOL_MAP and MACRO_SYMBOL_MAP[symbol][0] != symbol:
                raise ProviderFetchError(
                    "PROVIDER_INSTRUMENT_UNSUPPORTED",
                    "The declared symbol maps to a different product on this provider and will not be substituted.",
                )
            candles = await self._fetch_yahoo_candles(resolved_symbol, interval=interval)
        elif declared == "stooq_public":
            if symbol in MACRO_SYMBOL_MAP and MACRO_SYMBOL_MAP[symbol][1] != symbol.lower():
                raise ProviderFetchError(
                    "PROVIDER_INSTRUMENT_UNSUPPORTED",
                    "The declared symbol maps to a different product on this provider and will not be substituted.",
                )
            candles = await self._fetch_stooq_candles(resolved_symbol.lower())
        if not candles:
            raise ProviderFetchError("PROVIDER_FETCH_FAILED", "The declared provider did not return candles; nothing was substituted.")
        return {
            "provider": declared,
            "provider_symbol": resolved_symbol,
            "candles": candles,
            "interval": normalize_interval(interval),
            "fetched_at": self._now_iso(),
        }

    async def fetch_crypto_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches historical OHLCV crypto candles from public Binance REST endpoint.
        Falls back automatically to Bybit public API if Binance encounters rate limiting or downtime.
        If symbol is in MACRO_SYMBOL_MAP, routes automatically to fetch_macro_candles.
        """
        clean_sym = symbol.upper().strip()
        if clean_sym in MACRO_SYMBOL_MAP or symbol in MACRO_SYMBOL_MAP:
            return await self.fetch_macro_candles(symbol=clean_sym, interval=interval)

        norm_sym = normalize_crypto_symbol(symbol)
        norm_int = normalize_interval(interval)
        clamped_limit = max(1, min(1000, limit))

        # 1. Attempt Binance Public Spot Klines.  A history request
        # (``start_time``) walks backwards page by page within a bounded cap so
        # the chart can load older bars without hammering the provider.
        try:
            page_limit = min(self.BINANCE_PAGE_LIMIT, max(1, clamped_limit))
            collected: Dict[int, Dict[str, Any]] = {}
            cursor_end = int(end_time) if end_time is not None else None
            pages = 0
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                while pages < (self.MAX_HISTORY_PAGES if start_time is not None else 1):
                    params: Dict[str, Any] = {
                        "symbol": norm_sym,
                        "interval": norm_int,
                        "limit": page_limit if start_time is not None else clamped_limit,
                    }
                    if start_time is not None:
                        params["startTime"] = int(start_time)
                    if cursor_end is not None:
                        params["endTime"] = cursor_end

                    res = await client.get(self.BINANCE_KLINES_URL, params=params, headers=self._get_headers())
                    if res.status_code == 429:
                        logger.warning(f"[PUBLIC-FETCHER] Binance Public API rate limited (429). Falling back to Bybit...")
                        break
                    if res.status_code != 200:
                        logger.warning(f"[PUBLIC-FETCHER] Binance Public API returned status {res.status_code} for {norm_sym}: {res.text[:100]}")
                        break
                    page = self._parse_binance_klines(res.json())
                    if not page:
                        break
                    before = len(collected)
                    for candle in page:
                        collected[candle["timestamp"]] = candle
                    pages += 1
                    oldest = min(candle["timestamp"] for candle in page)
                    if len(collected) == before:
                        break
                    if len(page) < (page_limit if start_time is not None else clamped_limit):
                        break
                    if start_time is not None and oldest <= int(start_time):
                        break
                    cursor_end = oldest - 1
            if collected:
                candles = [collected[key] for key in sorted(collected)]
                logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} candles for {norm_sym} ({norm_int}) via Binance Public.")
                return candles
        except Exception as e:
            logger.warning(f"[PUBLIC-FETCHER] Binance fetch error for {norm_sym}: {e}. Triggering Bybit fallback...")

        # 2. Fallback: Bybit Public V5 Market Klines
        try:
            bybit_int = BYBIT_INTERVAL_MAP.get(norm_int, "60")
            bybit_params: Dict[str, Any] = {
                "category": "spot",
                "symbol": norm_sym,
                "interval": bybit_int,
                "limit": clamped_limit
            }
            if start_time is not None:
                bybit_params["start"] = int(start_time)
            if end_time is not None:
                bybit_params["end"] = int(end_time)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.BYBIT_KLINES_URL, params=bybit_params, headers=self._get_headers())
                if res.status_code == 200:
                    payload = res.json()
                    candles = self._parse_bybit_klines(payload)
                    if candles:
                        logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} candles for {norm_sym} ({norm_int}) via Bybit Fallback.")
                        return candles
                logger.warning(f"[PUBLIC-FETCHER] Bybit returned status {res.status_code} for {norm_sym}")
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Bybit fallback error for {norm_sym}: {e}")

        # 3. Fallback: Binance Futures Public Klines
        try:
            fapi_params: Dict[str, Any] = {
                "symbol": norm_sym,
                "interval": norm_int,
                "limit": clamped_limit
            }
            if start_time is not None:
                fapi_params["startTime"] = int(start_time)
            if end_time is not None:
                fapi_params["endTime"] = int(end_time)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.BINANCE_FUTURES_URL, params=fapi_params, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    candles = self._parse_binance_klines(data)
                    if candles:
                        logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} candles for {norm_sym} ({norm_int}) via Binance Futures Public.")
                        return candles
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Binance Futures fallback error for {norm_sym}: {e}")

        logger.error(f"[PUBLIC-FETCHER] All public endpoints failed to fetch candles for {norm_sym} ({norm_int}).")
        return []

    def _parse_binance_klines(self, raw_klines: List[List[Any]]) -> List[Dict[str, Any]]:
        """Parses Binance standard kline format into normalized OHLCV records."""
        candles: List[Dict[str, Any]] = []
        for k in raw_klines:
            try:
                candle = {
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                }
                candles.append(candle)
            except (ValueError, IndexError, TypeError):
                continue
        # Ensure ascending sort
        candles.sort(key=lambda c: c["timestamp"])
        return candles

    def _parse_bybit_klines(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses Bybit V5 kline payload (list of [startTime, open, high, low, close, volume, turnover])."""
        result = payload.get("result", {})
        raw_list = result.get("list", [])
        candles: List[Dict[str, Any]] = []
        for k in raw_list:
            try:
                candle = {
                    "timestamp": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5])
                }
                candles.append(candle)
            except (ValueError, IndexError, TypeError):
                continue
        # Bybit returns newest first, sort ascending
        candles.sort(key=lambda c: c["timestamp"])
        return candles

    @classmethod
    def _clamp_yahoo_period1(cls, interval: str, start_ms: int, end_ms: int) -> int:
        """Clamp a requested start to Yahoo's documented intraday window."""

        lookback = cls.YAHOO_INTRADAY_LOOKBACK_MS.get(str(interval))
        if lookback is None:
            return max(0, int(start_ms))
        return max(int(start_ms), int(end_ms) - lookback)

    async def fetch_macro_candles(
        self,
        symbol: str,
        interval: str = "1d",
        period: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches historical macro/forex/indices candles from free public sources.
        XAUUSD uses the exact Biquote XAUUSD path before Yahoo/Stooq fallback.
        Zero API keys required.  A source failure never falls back to a
        materially different instrument such as PAXGUSDT or GC=F for spot gold.
        """
        clean_sym = symbol.upper().strip()
        yahoo_ticker, stooq_ticker = MACRO_SYMBOL_MAP.get(clean_sym, (clean_sym, clean_sym.lower()))

        yahoo_interval, auto_range = self._map_yahoo_interval_and_range(interval, period)

        # Prefer the exact free XAU/USD path. Yahoo's XAUUSD=X endpoint is not
        # consistently available, while a futures/token substitute would
        # silently change the instrument identity.
        biquote_symbol = BIQUOTE_SYMBOL_MAP.get(clean_sym)
        if biquote_symbol:
            candles = await self._fetch_biquote_candles(
                biquote_symbol,
                interval=interval,
                limit=500,
            )
            if candles:
                logger.info(
                    "[PUBLIC-FETCHER] Successfully fetched %s exact %s candles via Biquote.",
                    len(candles),
                    biquote_symbol,
                )
                return candles

        # 1. Try Yahoo Finance Chart API.  An explicit start_time switches to
        # period1/period2 so the chart can walk years back for daily+ bars; the
        # provider's intraday window is honored by clamping, never invented.
        try:
            candles = await self._fetch_yahoo_candles(
                yahoo_ticker, interval=interval, period=period,
                start_time=start_time, end_time=end_time,
            )
            if candles:
                logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} macro candles for {clean_sym} ({yahoo_ticker}) via Yahoo Finance.")
                return candles
            logger.warning(f"[PUBLIC-FETCHER] Yahoo Finance returned no candles for {yahoo_ticker}")
        except Exception as e:
            logger.warning(f"[PUBLIC-FETCHER] Yahoo Finance fetch error for {clean_sym} ({yahoo_ticker}): {e}")

        # 2. Try the same-instrument Stooq Public CSV fallback.
        try:
            candles = await self._fetch_stooq_candles(stooq_ticker)
            if candles:
                logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} macro candles for {clean_sym} ({stooq_ticker}) via Stooq.")
                return candles
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Stooq fallback error for {clean_sym}: {e}")

        logger.error(f"[PUBLIC-FETCHER] Failed to fetch macro candles for {clean_sym}.")
        return []

    async def _fetch_biquote_candles(
        self,
        symbol: str,
        *,
        interval: str = "1h",
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Fetch exact XAU/USD OHLC from the free, keyless Biquote endpoint."""
        clean_symbol = str(symbol or "").strip().upper()
        if clean_symbol not in BIQUOTE_SYMBOL_MAP.values():
            return []
        normalized_interval = normalize_interval(interval)
        biquote_interval = BIQUOTE_INTERVAL_MAP.get(normalized_interval)
        if biquote_interval is None:
            return []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.BIQUOTE_OHLC_URL.format(symbol=clean_symbol),
                    params={
                        "interval": biquote_interval,
                        "limit": max(1, min(500, int(limit))),
                    },
                    headers=self._get_headers(),
                )
            if response.status_code != 200:
                logger.warning(
                    "[PUBLIC-FETCHER] Biquote returned status %s for %s.",
                    response.status_code,
                    clean_symbol,
                )
                return []
            return self._parse_biquote_ohlc(response.json())
        except Exception as exc:
            logger.warning("[PUBLIC-FETCHER] Biquote fetch failed for %s: %s", clean_symbol, exc)
            return []

    @staticmethod
    def _timestamp_ms(value: Any) -> Optional[int]:
        """Normalize an ISO-8601 or epoch timestamp into milliseconds."""
        try:
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                numeric = float(value)
                return int(numeric * 1000 if numeric < 10_000_000_000 else numeric)
            if isinstance(value, str) and value.strip():
                normalized = value.strip().replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return int(parsed.timestamp() * 1000)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
        return None

    def _parse_biquote_ohlc(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Biquote bars while retaining zero volume for spot metals."""
        if not isinstance(payload, dict) or not isinstance(payload.get("bars"), list):
            return []

        candles: List[Dict[str, Any]] = []
        for bar in payload["bars"]:
            if not isinstance(bar, dict):
                continue
            timestamp = self._timestamp_ms(bar.get("openTime"))
            try:
                open_price = float(bar["open"])
                high = float(bar["high"])
                low = float(bar["low"])
                close = float(bar["close"])
                volume = float(bar.get("volume", 0) or 0)
            except (KeyError, TypeError, ValueError):
                continue
            prices = (open_price, high, low, close)
            if (
                timestamp is None
                or timestamp <= 0
                or not all(math.isfinite(price) and price > 0 for price in prices)
                or not math.isfinite(volume)
                or volume < 0
                or high < max(open_price, low, close)
                or low > min(open_price, high, close)
            ):
                continue
            candles.append({
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            })
        candles.sort(key=lambda candle: candle["timestamp"])
        return candles

    def _parse_yahoo_chart(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parses Yahoo Finance v8 chart JSON response."""
        try:
            chart = payload.get("chart", {})
            result_list = chart.get("result", [])
            if not result_list:
                return []
            result = result_list[0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {})
            quote_list = indicators.get("quote", [])
            if not quote_list:
                return []
            quote = quote_list[0]

            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            candles: List[Dict[str, Any]] = []
            for i, ts in enumerate(timestamps):
                if (
                    i < len(opens) and opens[i] is not None
                    and i < len(highs) and highs[i] is not None
                    and i < len(lows) and lows[i] is not None
                    and i < len(closes) and closes[i] is not None
                ):
                    vol = float(volumes[i]) if (i < len(volumes) and volumes[i] is not None) else 0.0
                    candles.append({
                        "timestamp": int(ts) * 1000,  # Convert seconds to ms
                        "open": round(float(opens[i]), 4),
                        "high": round(float(highs[i]), 4),
                        "low": round(float(lows[i]), 4),
                        "close": round(float(closes[i]), 4),
                        "volume": round(vol, 4)
                    })
            candles.sort(key=lambda c: c["timestamp"])
            return candles
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Error parsing Yahoo chart: {e}")
            return []

    def _parse_stooq_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """Parses Stooq CSV export into standardized OHLCV dictionaries."""
        candles: List[Dict[str, Any]] = []
        try:
            f = io.StringIO(csv_text)
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_str = row.get("Date", "").strip()
                    if not date_str or date_str == "Date":
                        continue
                    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    ts_ms = int(dt.timestamp() * 1000)

                    c_open = float(row.get("Open", 0.0))
                    c_high = float(row.get("High", 0.0))
                    c_low = float(row.get("Low", 0.0))
                    c_close = float(row.get("Close", 0.0))
                    c_vol = float(row.get("Volume", 0.0) or 0.0)

                    candles.append({
                        "timestamp": ts_ms,
                        "open": c_open,
                        "high": c_high,
                        "low": c_low,
                        "close": c_close,
                        "volume": c_vol
                    })
                except (ValueError, KeyError):
                    continue
            candles.sort(key=lambda c: c["timestamp"])
            return candles
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Error parsing Stooq CSV: {e}")
            return []


# Global Singleton Instance
public_market_fetcher = PublicMarketDataFetcher()
