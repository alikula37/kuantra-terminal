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
        market_context = self.get_market_context(trade_id)
        safe_events = []
        latest_economic_evidence = None
        economic_revisions = []
        latest_import_review = None
        import_review_history = []
        latest_reconciliation_review = None
        reconciliation_review_history = []
        for event in events:
            payload = event.get("normalized_payload")
            trade_payload = payload.get("trade") if isinstance(payload, dict) else None
            provenance = event.get("provenance")
            if isinstance(provenance, dict):
                import_review = provenance.get("import_review")
                if isinstance(import_review, dict):
                    review_view = dict(import_review)
                    review_view.update({
                        "event_id": event.get("event_id"),
                        "event_hash": event.get("event_hash"),
                    })
                    latest_import_review = review_view
                    import_review_history.append(review_view)
                reconciliation_review = provenance.get("reconciliation_review")
                if isinstance(reconciliation_review, dict):
                    review_view = dict(reconciliation_review)
                    review_view.update({
                        "event_id": event.get("event_id"),
                        "event_hash": event.get("event_hash"),
                    })
                    latest_reconciliation_review = review_view
                    reconciliation_review_history.append(review_view)
            economic_evidence = (
                trade_payload.get("economic_evidence")
                if isinstance(trade_payload, dict)
                else None
            )
            if isinstance(economic_evidence, dict):
                latest_economic_evidence = economic_evidence
                revision = economic_evidence.get("revision")
                if isinstance(revision, dict):
                    revision_view = dict(revision)
                else:
                    revision_view = {}
                revision_view.update({
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "event_hash": event.get("event_hash"),
                    "causation_id": event.get("causation_id"),
                })
                economic_revisions.append(revision_view)
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
            "economic_evidence": latest_economic_evidence,
            "economic_revisions": economic_revisions,
            "import_review": latest_import_review,
            "import_review_history": import_review_history,
            "reconciliation_review": latest_reconciliation_review,
            "reconciliation_review_history": reconciliation_review_history,
            "account_coverage": (
                latest_economic_evidence.get("account_coverage")
                if isinstance(latest_economic_evidence, dict)
                else None
            ),
            "market_context": market_context,
        }

    def get_market_context(
        self,
        trade_id: str,
        *,
        lookback_bars: int = 30,
        lookforward_bars: int = 20,
    ) -> Dict[str, Any]:
        """Attach bounded, deterministic recorded-bar context to a trade."""

        trade = self.get_trade(trade_id)
        if trade is None:
            return {
                "status": "NO_DATA",
                "reason": "TRADE_NOT_FOUND",
                "message": "The recorded trade was not found.",
                "trade_id": trade_id,
                "market_context": None,
                "candles": [],
            }
        from app.quant.candle_evidence import EvidenceError, load_candle_evidence, provenance

        try:
            evidence = load_candle_evidence(
                trade,
                lookback_bars=lookback_bars,
                lookforward_bars=lookforward_bars,
            )
        except EvidenceError as error:
            return {
                **error.to_dict(),
                "trade_id": trade_id,
                "market_context": None,
                "candles": [],
            }
        return {
            "status": "READY",
            "reason": None,
            "message": None,
            "trade_id": trade_id,
            "provenance": provenance(),
            "market_context": evidence.market_context,
            "candles": evidence.candles,
        }


trade_read_adapter = TradeReadAdapter()
