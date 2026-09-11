import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import create_app
from app.services.market_data.public_fetcher import (
    PublicMarketDataFetcher,
    public_market_fetcher,
    normalize_crypto_symbol,
    normalize_interval
)
from app.db.repositories.candles_repo import CandlesRepository, candles_repo


class TestPublicMarketDataFetcherAndCache:
    """Comprehensive test suite for zero-auth public market data & SQLite cache."""

    @pytest.fixture
    def temp_repo(self):
        """Creates an isolated temporary SQLite database for testing candle caching."""
        fd, db_path = tempfile.mkstemp(suffix="_test_candles.db")
        os.close(fd)
        repo = CandlesRepository(db_path=db_path)
        yield repo
        try:
            if os.path.exists(db_path):
                os.remove(db_path)
        except Exception:
            pass

    def test_symbol_and_interval_normalization(self):
        """Verifies symbol and interval normalization handles varied formats."""
        assert normalize_crypto_symbol("BTC/USDT") == "BTCUSDT"
        assert normalize_crypto_symbol("eth_usdt") == "ETHUSDT"
        assert normalize_crypto_symbol("SOL-USDC") == "SOLUSDC"
        assert normalize_crypto_symbol("BTC") == "BTCUSDT"
        assert normalize_crypto_symbol("eth") == "ETHUSDT"
        assert normalize_crypto_symbol("BNBBTC") == "BNBBTC"
        assert normalize_crypto_symbol("") == "BTCUSDT"

        assert normalize_interval("1h") == "1h"
        assert normalize_interval("60m") == "1h"
        assert normalize_interval("1D") == "1d"
        assert normalize_interval("d") == "1d"
        assert normalize_interval("4h") == "4h"
        assert normalize_interval("240m") == "4h"
        assert normalize_interval("1W") == "1w"

    def test_binance_klines_parsing(self):
        """Verifies parsing of raw Binance public kline JSON arrays."""
        fetcher = PublicMarketDataFetcher()
        raw_binance_data = [
            [1700000000000, "65000.50", "65500.00", "64800.00", "65200.25", "124.550", 1700003599999, "8100000.0", 500],
            [1700003600000, "65200.25", "65800.00", "65100.00", "65750.00", "89.200", 1700007199999, "5800000.0", 350]
        ]
        parsed = fetcher._parse_binance_klines(raw_binance_data)
        assert len(parsed) == 2
        assert parsed[0]["timestamp"] == 1700000000000
        assert parsed[0]["open"] == 65000.50
        assert parsed[0]["high"] == 65500.00
        assert parsed[0]["low"] == 64800.00
        assert parsed[0]["close"] == 65200.25
        assert parsed[0]["volume"] == 124.550
        assert parsed[1]["timestamp"] == 1700003600000
        assert parsed[1]["close"] == 65750.00

    def test_bybit_klines_parsing(self):
        """Verifies parsing of Bybit V5 public kline responses."""
        fetcher = PublicMarketDataFetcher()
        raw_bybit_payload = {
            "result": {
                "list": [
                    ["1700003600000", "65200.25", "65800.00", "65100.00", "65750.00", "89.200", "5800000.0"],
                    ["1700000000000", "65000.50", "65500.00", "64800.00", "65200.25", "124.550", "8100000.0"]
                ]
            }
        }
        parsed = fetcher._parse_bybit_klines(raw_bybit_payload)
        assert len(parsed) == 2
        # Bybit list is reversed to ensure ascending chronological order
        assert parsed[0]["timestamp"] == 1700000000000
        assert parsed[0]["open"] == 65000.50
        assert parsed[1]["timestamp"] == 1700003600000
        assert parsed[1]["close"] == 65750.00

    def test_yahoo_chart_parsing(self):
        """Verifies parsing of Yahoo Finance v8 chart JSON."""
        fetcher = PublicMarketDataFetcher()
        raw_yahoo = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1700000000, 1700086400],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [1.0850, 1.0920],
                                    "high": [1.0890, 1.0960],
                                    "low": [1.0820, 1.0900],
                                    "close": [1.0875, 1.0945],
                                    "volume": [15000, 18000]
                                }
                            ]
                        }
                    }
                ]
            }
        }
        parsed = fetcher._parse_yahoo_chart(raw_yahoo)
        assert len(parsed) == 2
        assert parsed[0]["timestamp"] == 1700000000000  # Converted to ms
        assert parsed[0]["open"] == 1.0850
        assert parsed[0]["close"] == 1.0875
        assert parsed[1]["timestamp"] == 1700086400000

    def test_stooq_csv_parsing(self):
        """Verifies parsing of Stooq CSV daily data."""
        fetcher = PublicMarketDataFetcher()
        sample_csv = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-08-28,450.50,455.00,449.00,453.20,1200000\n"
            "2026-08-29,453.20,458.10,452.00,457.50,1450000\n"
        )
        parsed = fetcher._parse_stooq_csv(sample_csv)
        assert len(parsed) == 2
        assert parsed[0]["open"] == 450.50
        assert parsed[0]["close"] == 453.20
        assert parsed[1]["high"] == 458.10

    @pytest.mark.asyncio
    async def test_fetch_crypto_candles_with_failover(self):
        """Tests that fetch_crypto_candles falls back to Bybit when Binance is simulated to fail."""
        fetcher = PublicMarketDataFetcher()

        mock_binance_response = MagicMock()
        mock_binance_response.status_code = 429  # Simulate rate limiting

        mock_bybit_response = MagicMock()
        mock_bybit_response.status_code = 200
        mock_bybit_response.json.return_value = {
            "result": {
                "list": [
                    ["1700000000000", "60000.0", "61000.0", "59500.0", "60500.0", "50.0", "3000000.0"]
                ]
            }
        }

        async def mock_get(url, *args, **kwargs):
            if "binance" in url:
                return mock_binance_response
            elif "bybit" in url:
                return mock_bybit_response
            raise ValueError("Unknown URL")

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            candles = await fetcher.fetch_crypto_candles("BTCUSDT", interval="1h", limit=1)
            assert len(candles) == 1
            assert candles[0]["open"] == 60000.0
            assert candles[0]["close"] == 60500.0

    def test_candles_sqlite_caching_and_deduplication(self, temp_repo):
        """Verifies SQLite cache batch insert, deduplication via INSERT OR IGNORE, and range queries."""
        sample_candles = [
            {"timestamp": 1000, "open": 100.0, "high": 105.0, "low": 99.0, "close": 102.0, "volume": 10.0},
            {"timestamp": 2000, "open": 102.0, "high": 107.0, "low": 101.0, "close": 106.0, "volume": 15.0},
            {"timestamp": 3000, "open": 106.0, "high": 108.0, "low": 104.0, "close": 105.0, "volume": 12.0}
        ]

        # 1. Initial Insert
        inserted = temp_repo.save_candles_batch(sample_candles, symbol="BTCUSDT", timeframe="1h")
        assert inserted == 3

        # 2. Duplicate Insert - Should insert 0 new records due to unique constraint
        re_inserted = temp_repo.save_candles_batch(sample_candles, symbol="BTCUSDT", timeframe="1h")
        assert re_inserted == 0

        # 3. Query All
        cached = temp_repo.get_cached_candles(symbol="BTCUSDT", timeframe="1h")
        assert len(cached) == 3
        assert cached[0]["timestamp"] == 1000
        assert cached[2]["timestamp"] == 3000

        # 4. Range Query
        bounded = temp_repo.get_cached_candles(symbol="BTCUSDT", timeframe="1h", start_ts=1500, end_ts=2500)
        assert len(bounded) == 1
        assert bounded[0]["timestamp"] == 2000

        # 5. Limit Query
        limited = temp_repo.get_cached_candles(symbol="BTCUSDT", timeframe="1h", limit=2)
        assert len(limited) == 2
        assert limited[0]["timestamp"] == 2000
        assert limited[1]["timestamp"] == 3000

        # 6. Cache Stats
        stats = temp_repo.get_cache_stats()
        assert stats["total_records"] == 3
        assert stats["symbols_count"] == 1
        assert "BTCUSDT" in stats["symbols"]
        assert stats["oldest_timestamp"] == 1000
        assert stats["newest_timestamp"] == 3000

        # 7. Clear Cache
        cleared = temp_repo.clear_cache(symbol="BTCUSDT")
        assert cleared == 3
        assert temp_repo.get_cache_stats()["total_records"] == 0

    @pytest.mark.asyncio
    async def test_get_or_fetch_candles_cache_hit_and_miss(self, temp_repo):
        """Tests that get_or_fetch_candles utilizes cache on hit and fetches on miss."""
        mock_candles = [
            {"timestamp": 1700000000000, "open": 50000.0, "high": 51000.0, "low": 49000.0, "close": 50500.0, "volume": 100.0},
            {"timestamp": 1700003600000, "open": 50500.0, "high": 52000.0, "low": 50000.0, "close": 51500.0, "volume": 120.0}
        ]

        with patch.object(public_market_fetcher, "fetch_crypto_candles", AsyncMock(return_value=mock_candles)) as mock_fetch:
            # 1. First Call: Cache MISS -> Should call fetcher
            res1 = await temp_repo.get_or_fetch_candles(symbol="ETHUSDT", timeframe="1h", limit=2)
            assert len(res1) == 2
            assert mock_fetch.call_count == 1

            # 2. Second Call: Cache HIT -> Should NOT call fetcher
            res2 = await temp_repo.get_or_fetch_candles(symbol="ETHUSDT", timeframe="1h", limit=2)
            assert len(res2) == 2
            assert mock_fetch.call_count == 1  # Still 1, no second call!

            # 3. Third Call with force_refresh=True -> Should call fetcher again
            res3 = await temp_repo.get_or_fetch_candles(symbol="ETHUSDT", timeframe="1h", limit=2, force_refresh=True)
            assert len(res3) == 2
            assert mock_fetch.call_count == 2

    def test_market_data_api_endpoints(self):
        """Tests FastAPI REST endpoints for /api/v1/market-data/candles and /api/v1/market-data/status."""
        app = create_app()
        client = TestClient(app)

        mock_candles = [
            {"timestamp": 1700000000000, "open": 65000.0, "high": 66000.0, "low": 64500.0, "close": 65500.0, "volume": 80.0}
        ]

        with patch.object(candles_repo, "get_or_fetch_candles", AsyncMock(return_value=mock_candles)):
            # 1. GET /api/v1/market-data/candles
            res = client.get("/api/v1/market-data/candles?symbol=BTCUSDT&timeframe=1h&limit=10")
            assert res.status_code == 200
            data = res.json()
            assert data["symbol"] == "BTCUSDT"
            assert data["timeframe"] == "1h"
            assert data["count"] == 1
            assert len(data["candles"]) == 1
            assert data["candles"][0]["open"] == 65000.0

        # 2. GET /api/v1/market-data/status
        res_status = client.get("/api/v1/market-data/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["status"] == "HEALTHY"
        assert status_data["auth_required"] is False
        assert "binance_public" in status_data["supported_exchanges"]

        # 3. POST /api/v1/market-data/cache/clear
        res_clear = client.post("/api/v1/market-data/cache/clear?symbol=BTCUSDT")
        assert res_clear.status_code == 200
        clear_data = res_clear.json()
        assert clear_data["status"] == "CLEARED"

    @pytest.mark.asyncio
    async def test_macro_symbol_routing_and_fetch(self):
        """Verifies macro symbols (XAUUSD, EURUSD, SPY, NVDA) are mapped and routed to fetch_macro_candles."""
        fetcher = PublicMarketDataFetcher()
        mock_macro_candles = [
            {"timestamp": 1700000000000, "open": 2000.0, "high": 2010.0, "low": 1995.0, "close": 2005.0, "volume": 500.0}
        ]

        with patch.object(fetcher, "fetch_macro_candles", AsyncMock(return_value=mock_macro_candles)) as mock_macro:
            # When requesting XAUUSD, fetch_crypto_candles should delegate to fetch_macro_candles
            res = await fetcher.fetch_crypto_candles("XAUUSD", interval="15m")
            assert len(res) == 1
            assert res[0]["close"] == 2005.0
            mock_macro.assert_called_once_with(symbol="XAUUSD", interval="15m")

    @pytest.mark.asyncio
    async def test_gold_does_not_fallback_to_a_different_instrument_when_yahoo_fails(self):
        """Gold stays unavailable if every exact free source is unavailable."""
        fetcher = PublicMarketDataFetcher()

        # Simulate Yahoo HTTP 403 and a final Stooq failure. There must be no
        # Binance PAXGUSDT request because it is not the requested instrument.
        mock_yahoo_fail = MagicMock(status_code=403)

        async def mock_get(url, *args, **kwargs):
            if "yahoo.com" in url:
                return mock_yahoo_fail
            return MagicMock(status_code=404)

        with patch("httpx.AsyncClient.get", side_effect=mock_get):
            candles = await fetcher.fetch_macro_candles("XAUUSD", interval="15m")
            assert candles == []

    @pytest.mark.asyncio
    async def test_xauusd_uses_exact_keyless_biquote_ohlc_before_unreliable_fallbacks(self):
        """Spot gold can use an exact XAUUSD source without becoming GC=F/PAXG."""
        fetcher = PublicMarketDataFetcher()
        biquote = MagicMock(status_code=200)
        biquote.json.return_value = {
            "symbol": "XAUUSD",
            "interval": "15m",
            "bars": [{
                "openTime": "2026-09-11T16:30:00Z",
                "open": 4355.08,
                "high": 4363.149,
                "low": 4353.344,
                "close": 4362.537,
                "volume": 0,
            }],
        }

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=biquote)) as get:
            candles = await fetcher.fetch_macro_candles("XAUUSD", interval="15m")

        assert candles == [{
            "timestamp": 1789144200000,
            "open": 4355.08,
            "high": 4363.149,
            "low": 4353.344,
            "close": 4362.537,
            "volume": 0.0,
        }]
        request_url = get.await_args.args[0]
        assert request_url == "https://biquote.io/api/XAUUSD/ohlc"
        assert get.await_args.kwargs["params"] == {"interval": "15m", "limit": 500}

    @pytest.mark.asyncio
    async def test_xauusd_quote_reports_exact_biquote_provenance(self):
        fetcher = PublicMarketDataFetcher()
        biquote = MagicMock(status_code=200)
        biquote.json.return_value = {
            "symbol": "XAUUSD",
            "bars": [{
                "openTime": "2026-09-11T16:30:00Z",
                "open": 4355.08,
                "high": 4363.149,
                "low": 4353.344,
                "close": 4362.537,
                "volume": 0,
            }],
        }

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=biquote)):
            quote = await fetcher.fetch_quote("XAUUSD")

        assert quote.source_id == "biquote_public"
        assert quote.source_symbol == "XAUUSD"
        assert quote.price == 4362.537
        assert quote.status == "LIVE"
