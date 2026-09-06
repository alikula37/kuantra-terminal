"""Coverage-gated trade read adapter.

The SQLite ``trades`` table remains a compatibility write/read model while
legacy data is being backfilled.  Once the typed evidence projection covers the
same IDs exactly, selected product reads switch to the projection.  The adapter
never mixes a partial projection with legacy rows, which would make the journal
silently incomplete.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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
    ) -> None:
        self.legacy_driver = legacy_driver or sqlite_driver
        self.projection_repo = projection_repo or EvidenceTradeProjectionRepository(
            self.legacy_driver.db_path
        )
        self.account_id = account_id
        self.venue = venue

    def coverage(self) -> Dict[str, Any]:
        return self.projection_repo.coverage(
            account_id=self.account_id,
            venue=self.venue,
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
        )

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        if not self._projection_ready():
            return self.legacy_driver.get_trade(trade_id)
        return self.projection_repo.get_trade_snapshot(
            trade_id,
            account_id=self.account_id,
            venue=self.venue,
        )

    def get_open_trades(self) -> List[Dict[str, Any]]:
        if not self._projection_ready():
            return self.legacy_driver.get_open_trades()
        return self.projection_repo.list_trade_snapshots(
            limit=100000,
            status="OPEN",
            account_id=self.account_id,
            venue=self.venue,
        )


trade_read_adapter = TradeReadAdapter()

