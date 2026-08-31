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
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("public_market_fetcher")

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
    "XAUUSD": ("GC=F", "xauusd"),
    "GOLD": ("GC=F", "xauusd"),
    "XAGUSD": ("SI=F", "xagusd"),
    "SILVER": ("SI=F", "xagusd"),
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


class PublicMarketDataFetcher:
    """
    Zero-auth public market data fetcher with high-availability failover.
    Fetches spot/futures klines and macro/forex candles directly from free public endpoints.
    """

    BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
    BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
    BYBIT_KLINES_URL = "https://api.bybit.com/v5/market/kline"
    YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={ticker}&i=d"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache"
        }

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

        # 1. Attempt Binance Public Spot Klines
        try:
            params: Dict[str, Any] = {
                "symbol": norm_sym,
                "interval": norm_int,
                "limit": clamped_limit
            }
            if start_time is not None:
                params["startTime"] = int(start_time)
            if end_time is not None:
                params["endTime"] = int(end_time)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(self.BINANCE_KLINES_URL, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    candles = self._parse_binance_klines(data)
                    if candles:
                        logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} candles for {norm_sym} ({norm_int}) via Binance Public.")
                        return candles
                elif res.status_code == 429:
                    logger.warning(f"[PUBLIC-FETCHER] Binance Public API rate limited (429). Falling back to Bybit...")
                else:
                    logger.warning(f"[PUBLIC-FETCHER] Binance Public API returned status {res.status_code} for {norm_sym}: {res.text[:100]}")
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

    async def fetch_macro_candles(
        self,
        symbol: str,
        interval: str = "1d",
        period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches historical macro/forex/indices candles from public Yahoo Finance v8 or Stooq.
        Includes automatic fallback to Binance PAXGUSDT for gold (XAUUSD/GOLD).
        Zero API keys required.
        """
        clean_sym = symbol.upper().strip()
        yahoo_ticker, stooq_ticker = MACRO_SYMBOL_MAP.get(clean_sym, (clean_sym, clean_sym.lower()))

        yahoo_interval, auto_range = self._map_yahoo_interval_and_range(interval, period)

        # 1. Try Yahoo Finance Chart API
        try:
            url = self.YAHOO_CHART_URL.format(ticker=yahoo_ticker)
            params = {
                "interval": yahoo_interval,
                "range": auto_range,
                "includePrePost": "false",
                "events": "div|split"
            }
            headers = self._get_headers()

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    candles = self._parse_yahoo_chart(data)
                    if candles:
                        logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} macro candles for {clean_sym} ({yahoo_ticker}) via Yahoo Finance.")
                        return candles
                logger.warning(f"[PUBLIC-FETCHER] Yahoo Finance returned status {res.status_code} for {yahoo_ticker}")
        except Exception as e:
            logger.warning(f"[PUBLIC-FETCHER] Yahoo Finance fetch error for {clean_sym} ({yahoo_ticker}): {e}")

        # 2. Fallback for Gold (XAUUSD / GOLD): Binance PAXGUSDT
        if clean_sym in ("XAUUSD", "GOLD"):
            try:
                logger.info(f"[PUBLIC-FETCHER] Attempting Binance PAXGUSDT fallback for {clean_sym}...")
                norm_int = normalize_interval(interval)
                params = {
                    "symbol": "PAXGUSDT",
                    "interval": norm_int,
                    "limit": 500
                }
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(self.BINANCE_KLINES_URL, params=params, headers=self._get_headers())
                    if res.status_code == 200:
                        candles = self._parse_binance_klines(res.json())
                        if candles:
                            logger.info(f"[PUBLIC-FETCHER] Binance PAXGUSDT fallback succeeded for {clean_sym} ({len(candles)} candles).")
                            return candles
            except Exception as e:
                logger.warning(f"[PUBLIC-FETCHER] Binance PAXGUSDT fallback error for {clean_sym}: {e}")

        # 3. Try Stooq Public CSV Fallback
        try:
            stooq_url = self.STOOQ_CSV_URL.format(ticker=stooq_ticker)
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(stooq_url, headers=self._get_headers())
                if res.status_code == 200 and "Date" in res.text:
                    candles = self._parse_stooq_csv(res.text)
                    if candles:
                        logger.info(f"[PUBLIC-FETCHER] Successfully fetched {len(candles)} macro candles for {clean_sym} ({stooq_ticker}) via Stooq.")
                        return candles
        except Exception as e:
            logger.error(f"[PUBLIC-FETCHER] Stooq fallback error for {clean_sym}: {e}")

        logger.error(f"[PUBLIC-FETCHER] Failed to fetch macro candles for {clean_sym}.")
        return []

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
