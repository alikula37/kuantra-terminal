"""Server-verified instrument catalog for base-unit monetary math.

The backend fetches the provider's own public instrument metadata (Binance spot
``exchangeInfo``, Bybit spot ``instruments-info``) and caches the exact result.
A symbol only counts as verified when *this server-side lookup* confirms it as
a trading spot instrument; client-supplied labels or a symbol suffix never do.

Verified rows are cached in SQLite so reads stay offline-friendly.  A row is
refreshed from the provider after 24 hours and is treated as no longer verified
after 7 days (an instrument can be delisted), instead of being assumed valid
forever.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.paths import get_sqlite_path

logger = logging.getLogger(__name__)

REFRESH_AFTER_SECONDS = 24 * 3_600
VALID_FOR_SECONDS = 7 * 86_400
BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InstrumentCatalog:
    def __init__(self, fetcher: Any = None, db_path: Optional[str] = None):
        if fetcher is None:
            from app.services.market_data.public_fetcher import public_market_fetcher

            fetcher = public_market_fetcher
        self.fetcher = fetcher
        self.db_path = str(db_path or get_sqlite_path())
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verified_instruments (
                    symbol TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    base_asset TEXT NOT NULL,
                    quote_asset TEXT NOT NULL,
                    contract_size REAL NOT NULL DEFAULT 1.0,
                    verified_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _row_age_seconds(row: Dict[str, Any], now: Optional[float] = None) -> Optional[float]:
        raw = row.get("verified_at")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        reference = now if now is not None else time.time()
        return reference - parsed.timestamp()

    def get(self, symbol: str) -> Optional[Dict[str, Any]]:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM verified_instruments WHERE symbol = ?", (normalized,)
            ).fetchone()
        return dict(row) if row is not None else None

    def is_verified(self, symbol: str) -> bool:
        """Offline read: a recent server-verified row counts as verified."""

        row = self.get(symbol)
        if row is None:
            return False
        age = self._row_age_seconds(row)
        return age is not None and age <= VALID_FOR_SECONDS

    def _store(
        self,
        symbol: str,
        *,
        provider: str,
        base_asset: str,
        quote_asset: str,
        contract_size: float = 1.0,
    ) -> Dict[str, Any]:
        normalized = symbol.strip().upper()
        row = {
            "symbol": normalized,
            "provider": provider,
            "base_asset": base_asset.upper(),
            "quote_asset": quote_asset.upper(),
            "contract_size": float(contract_size),
            "verified_at": _now_iso(),
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO verified_instruments "
                "(symbol, provider, base_asset, quote_asset, contract_size, verified_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET provider=excluded.provider, "
                "base_asset=excluded.base_asset, quote_asset=excluded.quote_asset, "
                "contract_size=excluded.contract_size, verified_at=excluded.verified_at",
                (
                    row["symbol"],
                    row["provider"],
                    row["base_asset"],
                    row["quote_asset"],
                    row["contract_size"],
                    row["verified_at"],
                ),
            )
            conn.commit()
        return row

    async def _verify_binance_spot(self, symbol: str) -> Optional[Dict[str, Any]]:
        instruments = await self.fetcher._load_binance_instruments()
        for instrument in instruments or []:
            if str(instrument.get("symbol") or "").upper() != symbol.upper():
                continue
            base = instrument.get("baseAsset")
            quote = instrument.get("quoteAsset")
            if not base or not quote:
                return None
            if str(instrument.get("status") or "TRADING").upper() != "TRADING":
                return None
            if instrument.get("isSpotTradingAllowed") is False:
                return None
            return self._store(
                symbol,
                provider="binance_spot",
                base_asset=str(base),
                quote_asset=str(quote),
            )
        return None

    async def _verify_bybit_spot(self, symbol: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                BYBIT_INSTRUMENTS_URL,
                params={"category": "spot", "symbol": symbol.upper()},
                headers=self.fetcher._get_headers(),
            )
        if response.status_code != 200:
            return None
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            return None
        rows = (payload.get("result") or {}).get("list")
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0]
        if not isinstance(row, dict):
            return None
        if str(row.get("symbol") or "").upper() != symbol.upper():
            return None
        if str(row.get("status") or "").lower() != "trading":
            return None
        base = row.get("baseCoin")
        quote = row.get("quoteCoin")
        if not base or not quote:
            return None
        return self._store(
            symbol,
            provider="bybit_spot",
            base_asset=str(base),
            quote_asset=str(quote),
        )

    async def ensure_verified(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Verify ``symbol`` against provider metadata, using the cache when fresh.

        Provider failures are contained: an unverifiable symbol simply stays
        unverified and never enables monetary math or raises to the caller.
        """

        normalized = str(symbol or "").strip().upper()
        if not normalized or len(normalized) > 64:
            return None
        cached = self.get(normalized)
        if cached is not None:
            age = self._row_age_seconds(cached)
            if age is not None and age <= REFRESH_AFTER_SECONDS:
                return cached
        for verifier in (self._verify_binance_spot, self._verify_bybit_spot):
            try:
                verified = await verifier(normalized)
            except Exception as exc:  # noqa: BLE001 - provider failures stay bounded
                logger.warning(
                    "[INSTRUMENT-CATALOG] %s verification failed for %s: %s",
                    verifier.__name__,
                    normalized,
                    exc,
                )
                verified = None
            if verified is not None:
                return verified
        if cached is not None:
            age = self._row_age_seconds(cached)
            if age is not None and age <= VALID_FOR_SECONDS:
                return cached
        return None

    async def describe(self, symbol: str) -> Dict[str, Any]:
        row = await self.ensure_verified(symbol)
        if row is None:
            return {
                "symbol": str(symbol or "").strip().upper(),
                "status": "UNVERIFIED",
                "provider": None,
                "base_asset": None,
                "quote_asset": None,
                "contract_size": None,
                "verified_at": None,
            }
        return {
            "symbol": row["symbol"],
            "status": "VERIFIED",
            "provider": row["provider"],
            "base_asset": row["base_asset"],
            "quote_asset": row["quote_asset"],
            "contract_size": row["contract_size"],
            "verified_at": row["verified_at"],
        }


instrument_catalog = InstrumentCatalog()
