"""Coverage-gated trade read adapter.

The SQLite ``trades`` table remains a compatibility write/read model while
legacy data is being backfilled.  Once the typed evidence projection covers the
same IDs exactly, selected product reads switch to the projection.  The adapter
never mixes a partial projection with legacy rows, which would make the journal
silently incomplete.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository
from app.db.sqlite_driver import SQLiteDriver, sqlite_driver

logger = logging.getLogger(__name__)

_COVERAGE_STATES = frozenset({"COMPLETE", "PARTIAL", "UNKNOWN", "NOT_AVAILABLE"})


def _coverage_state(value: Any, *, default: str = "UNKNOWN") -> str:
    text = str(value or "").strip().upper()
    return text if text in _COVERAGE_STATES else default


def _explicit_coverage(mapping: Any, keys: Sequence[str]) -> str:
    declared = _declared_coverage(mapping, keys)
    return declared if declared is not None else "NOT_AVAILABLE"


def _declared_coverage(mapping: Any, keys: Sequence[str]) -> Optional[str]:
    """Return an explicitly declared state, including NOT_AVAILABLE.

    None means that the source did not declare any of the requested keys.
    This distinction matters for a source that explicitly says
    trade_snapshot=NOT_AVAILABLE: the presence of a compatibility row must
    not silently upgrade that claim to COMPLETE.
    """

    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        if key in mapping:
            value = mapping.get(key)
            if isinstance(value, str) and value.strip().upper() in _COVERAGE_STATES:
                return value.strip().upper()
            if isinstance(value, bool):
                return "COMPLETE" if value else _coverage_state(mapping.get("status"), default="UNKNOWN")
        complete = mapping.get(f"{key}_complete")
        if complete is True:
            return "COMPLETE"
        if complete is False:
            return _coverage_state(mapping.get("status"), default="UNKNOWN")
    return None


def _market_context_coverage(market_context: Any) -> str:
    if not isinstance(market_context, Mapping):
        return "NOT_AVAILABLE"
    status = str(market_context.get("status") or "").strip().upper()
    if status == "READY":
        provenance = market_context.get("provenance")
        return "COMPLETE" if isinstance(provenance, Mapping) and provenance.get("source_verified") is True else "PARTIAL"
    if status in {"NO_DATA", "UNAVAILABLE"}:
        return "NOT_AVAILABLE"
    return _coverage_state(status, default="UNKNOWN")


def _coverage_summary(
    *,
    trade: Any,
    events: Sequence[Mapping[str, Any]],
    import_review: Any,
    reconciliation_review: Any,
    account_coverage: Any,
    market_context: Any,
) -> Dict[str, str]:
    import_coverage = import_review.get("coverage") if isinstance(import_review, Mapping) else None
    reconciliation_coverage = (
        reconciliation_review.get("coverage")
        if isinstance(reconciliation_review, Mapping)
        else None
    )
    fee_sources = (import_coverage, reconciliation_coverage, account_coverage)
    fees = next(
        (
            _explicit_coverage(source, ("commission", "fees", "fee"))
            for source in fee_sources
            if isinstance(source, Mapping)
            and _explicit_coverage(source, ("commission", "fees", "fee")) != "NOT_AVAILABLE"
        ),
        "NOT_AVAILABLE",
    )
    funding_transfer = next(
        (
            _explicit_coverage(source, ("funding_transfer", "funding", "transfers"))
            for source in fee_sources
            if isinstance(source, Mapping)
            and _explicit_coverage(source, ("funding_transfer", "funding", "transfers")) != "NOT_AVAILABLE"
        ),
        "NOT_AVAILABLE",
    )
    account_events = next(
        (
            _explicit_coverage(source, ("account_events", "events_complete"))
            for source in (account_coverage, import_coverage, reconciliation_coverage)
            if isinstance(source, Mapping)
            and _explicit_coverage(source, ("account_events", "events_complete")) != "NOT_AVAILABLE"
        ),
        "NOT_AVAILABLE",
    )
    realized_pnl = next(
        (
            _explicit_coverage(source, ("realized_pnl", "pnl"))
            for source in (import_coverage, reconciliation_coverage, account_coverage)
            if isinstance(source, Mapping)
            and _explicit_coverage(source, ("realized_pnl", "pnl")) != "NOT_AVAILABLE"
        ),
        "NOT_AVAILABLE",
    )
    trade_snapshot = next(
        (
            declared
            for source in (import_coverage, reconciliation_coverage, account_coverage)
            for declared in [_declared_coverage(source, ("trade_snapshot",))]
            if declared is not None
        ),
        "COMPLETE" if isinstance(trade, Mapping) else "NOT_AVAILABLE",
    )
    market = _market_context_coverage(market_context)
    declared_statuses = tuple(
        declared
        for source in (import_coverage, reconciliation_coverage, account_coverage)
        for declared in [_declared_coverage(source, ("status",))]
        if declared is not None
    )
    states = (
        trade_snapshot,
        realized_pnl,
        fees,
        funding_transfer,
        account_events,
        market,
        *declared_statuses,
    )
    if not trade and not events:
        overall = "NOT_AVAILABLE"
    elif not trade and events:
        overall = "PARTIAL"
    elif "UNKNOWN" in states:
        overall = "UNKNOWN"
    elif any(state in {"PARTIAL", "NOT_AVAILABLE"} for state in states):
        overall = "PARTIAL"
    else:
        overall = "COMPLETE"
    return {
        "overall": overall,
        "trade_snapshot": trade_snapshot,
        "realized_pnl": realized_pnl,
        "fees": fees,
        "funding_transfer": funding_transfer,
        "account_events": account_events,
        "market_context": market,
    }


def _applicable_rules(events: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    references: List[Dict[str, str]] = []
    for event in events:
        payload = event.get("normalized_payload")
        provenance = event.get("provenance")
        payload = payload if isinstance(payload, Mapping) else {}
        provenance = provenance if isinstance(provenance, Mapping) else {}
        sources = [
            value
            for value in (
                payload.get("decision"),
                payload.get("risk_policy"),
                payload.get("playbook_version"),
                provenance,
            )
            if isinstance(value, Mapping)
        ]
        risk_source = next((value for value in sources if value.get("policy_id")), None)
        playbook_source = next((value for value in sources if value.get("playbook_id")), None)
        if risk_source is not None:
            references.append({
                "kind": "risk",
                "rule_id": str(risk_source.get("policy_id")),
                "version": str(risk_source.get("policy_version") or risk_source.get("version") or "—"),
                "snapshot_sha256": str(
                    risk_source.get("policy_snapshot_sha256")
                    or risk_source.get("snapshot_sha256")
                    or ""
                ),
                "event_id": str(event.get("event_id") or ""),
                "event_hash": str(event.get("event_hash") or ""),
            })
        elif playbook_source is not None:
            references.append({
                "kind": "playbook",
                "rule_id": str(playbook_source.get("playbook_id")),
                "version": str(playbook_source.get("playbook_version") or playbook_source.get("version") or "—"),
                "snapshot_sha256": str(
                    playbook_source.get("playbook_snapshot_sha256")
                    or playbook_source.get("snapshot_sha256")
                    or ""
                ),
                "event_id": str(event.get("event_id") or ""),
                "event_hash": str(event.get("event_hash") or ""),
            })
    return references


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
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        if not self._projection_ready():
            legacy_kwargs = {
                "limit": limit,
                "offset": offset,
                "symbol": symbol,
                "status": status,
                "order_by_utc": order_by_utc,
            }
            if resource_check is not None:
                legacy_kwargs["resource_check"] = resource_check
            return self.legacy_driver.list_trades(
                **legacy_kwargs,
            )
        projection_kwargs = {
            "limit": limit,
            "offset": offset,
            "symbol": symbol,
            "status": status,
            "order_by_utc": order_by_utc,
            "account_id": self.account_id,
            "venue": self.venue,
            "venues": self.projection_venues,
        }
        if resource_check is not None:
            projection_kwargs["resource_check"] = resource_check
        return self.projection_repo.list_trade_snapshots(
            **projection_kwargs,
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

    def get_evidence_pack(
        self,
        trade_id: str,
        *,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Build a read-only, source-linked evidence pack for one trade."""

        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        def check_resources(phase: str) -> None:
            if resource_check is not None:
                resource_check(phase)

        coverage = self.coverage()
        check_resources("after_coverage")
        trade = self.get_trade(trade_id)
        check_resources("after_trade")
        events = self.ledger_repo.list_events_for_trade(
            trade_id,
            account_id=self.account_id,
            venues=self.projection_venues,
        )
        check_resources("after_events")
        integrity = self.ledger_repo.verify_chain(
            account_id=self.account_id,
            resource_check=resource_check,
        )
        check_resources("after_ledger_integrity")
        market_context = self.get_market_context(trade_id)
        check_resources("after_market_context")
        safe_events = []
        latest_economic_evidence = None
        economic_revisions = []
        latest_import_review = None
        import_review_history = []
        latest_reconciliation_review = None
        reconciliation_review_history = []
        for event in events:
            check_resources("before_evidence_event")
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
            check_resources("after_evidence_event")
        pack = {
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
            "coverage_summary": _coverage_summary(
                trade=trade,
                events=safe_events,
                import_review=latest_import_review,
                reconciliation_review=latest_reconciliation_review,
                account_coverage=(
                    latest_economic_evidence.get("account_coverage")
                    if isinstance(latest_economic_evidence, dict)
                    else None
                ),
                market_context=market_context,
            ),
            "applicable_rules": _applicable_rules(safe_events),
            "market_context": market_context,
        }
        pack["snapshot_sha256"] = hashlib.sha256(
            canonical_json(pack).encode("utf-8")
        ).hexdigest()
        check_resources("before_pack_return")
        return pack

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
