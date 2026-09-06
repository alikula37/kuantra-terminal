"""Coverage-gated trade read adapter.

The SQLite ``trades`` table remains a compatibility write/read model while
legacy data is being backfilled.  Once the typed evidence projection covers the
same IDs exactly, selected product reads switch to the projection.  The adapter
never mixes a partial projection with legacy rows, which would make the journal
silently incomplete.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver, sqlite_driver

logger = logging.getLogger(__name__)


class TradeReadAdapter:
    """Read trades from the typed projection only after an exact coverage gate."""

    def __init__(
        self,
        *,
        legacy_driver: Optional[SQLiteDriver] = None,
        projection_repo: Optional[EvidenceTradeProjectionRepository] = None,
        account_id: str = "local-journal",
        venue: str = "local-journal",
        projection_venues: Optional[Sequence[str]] = None,
    ) -> None:
        self.legacy_driver = legacy_driver or sqlite_driver
        self.projection_repo = projection_repo or EvidenceTradeProjectionRepository(
            self.legacy_driver.db_path
        )
        self.ledger_repo = EvidenceLedgerRepository(self.legacy_driver.db_path)
        self.account_id = account_id
        self.venue = venue
        # ``legacy`` is the explicit venue used by the P1-WP01 backfill.  It is
        # still the same local journal account, so migration reads may accept
        # both venues while requiring exact one-to-one trade ID coverage.
        self.projection_venues = tuple(
            projection_venues
            if projection_venues is not None
            else ((venue, "legacy") if venue == "local-journal" else (venue,))
        )

    def coverage(self) -> Dict[str, Any]:
        return self.projection_repo.coverage(
            account_id=self.account_id,
            venue=self.venue,
            venues=self.projection_venues,
        )

    def _projection_ready(self) -> bool:
        coverage = self.coverage()
        if not coverage["ready"]:
            logger.debug(
                "Trade projection not ready; using compatibility reads: %s",
                coverage,
            )
        return bool(coverage["ready"])

    def list_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        order_by_utc: bool = False,
    ) -> List[Dict[str, Any]]:
        if not self._projection_ready():
            return self.legacy_driver.list_trades(
                limit=limit,
                offset=offset,
                symbol=symbol,
                status=status,
                order_by_utc=order_by_utc,
            )
        return self.projection_repo.list_trade_snapshots(
            limit=limit,
            offset=offset,
            symbol=symbol,
            status=status,
            order_by_utc=order_by_utc,
            account_id=self.account_id,
            venue=self.venue,
            venues=self.projection_venues,
        )

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        if not self._projection_ready():
            return self.legacy_driver.get_trade(trade_id)
        return self.projection_repo.get_trade_snapshot(
            trade_id,
            account_id=self.account_id,
            venue=self.venue,
            venues=self.projection_venues,
        )

    def get_open_trades(self) -> List[Dict[str, Any]]:
        if not self._projection_ready():
            return self.legacy_driver.get_open_trades()
        return self.projection_repo.list_trade_snapshots(
            limit=100000,
            status="OPEN",
            account_id=self.account_id,
            venue=self.venue,
            venues=self.projection_venues,
        )

    def get_evidence_pack(self, trade_id: str) -> Dict[str, Any]:
        """Build a read-only, source-linked evidence pack for one trade."""

        coverage = self.coverage()
        trade = self.get_trade(trade_id)
        events = self.ledger_repo.list_events_for_trade(
            trade_id,
            account_id=self.account_id,
            venues=self.projection_venues,
        )
        integrity = self.ledger_repo.verify_chain(account_id=self.account_id)
        safe_events = []
        for event in events:
            safe_events.append({
                key: event.get(key)
                for key in (
                    "event_id", "event_type", "account_id", "venue", "occurred_at_utc",
                    "received_at_utc", "chain_date_utc", "chain_sequence", "schema_version",
                    "adapter_version", "correlation_id", "causation_id", "idempotency_key",
                    "raw_payload_sha256", "normalized_payload", "provenance", "prev_hash",
                    "event_hash",
                )
            })
        return {
            "trade_id": trade_id,
            "trade": trade,
            "read_source": "typed_projection" if coverage["ready"] else "compatibility_legacy",
            "coverage": coverage,
            "ledger_integrity": {
                "valid": integrity["valid"],
                "checked_events": integrity["checked_events"],
                "errors": integrity["errors"],
            },
            "events": safe_events,
            "event_count": len(safe_events),
        }


trade_read_adapter = TradeReadAdapter()
