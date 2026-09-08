"""Deterministic P1-WP21 propagation from economic groups to evidence.

Economic observations are not complete trades.  This service therefore accepts
only an explicit, already-accounted trade snapshot for each confirmed economic
group.  It enriches that snapshot with source lineage and account coverage,
then writes the compatibility journal, canonical ledger and typed projection in
one SQLite transaction.  Missing accounting facts remain missing; they are
never represented as zero or ``COMPLETE``.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.db.repositories.evidence_ledger_repo import (
    EvidenceLedgerRepository,
    canonical_json,
)
from app.db.sqlite_driver import SQLiteDriver, sqlite_driver


_ALLOWED_COVERAGE_STATUSES = frozenset({"COMPLETE", "PARTIAL", "UNKNOWN", "NOT_AVAILABLE"})
_UNSUPPORTED_COVERAGE_MARKERS = frozenset({
    "UNSUPPORTED_ACCOUNT_EVENT",
    "EVENT_STORAGE_SCHEMA_PENDING",
    "SCHEMA_EVENT_TYPE_PENDING",
})
_REQUIRED_TRADE_FIELDS = frozenset({
    "id", "symbol", "side", "entry_price", "qty", "entry_time", "status", "pnl", "commission",
})


class EconomicEvidencePropagationError(ValueError):
    """Raised when an economic group cannot be propagated without invention."""


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EconomicEvidencePropagationError(f"{field} is required")
    return text


def _decimal(value: Any, field: str) -> Decimal:
    if value is None:
        raise EconomicEvidencePropagationError(f"{field} is required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise EconomicEvidencePropagationError(f"{field} must be a finite number") from exc
    if not result.is_finite():
        raise EconomicEvidencePropagationError(f"{field} must be a finite number")
    return result


def _copy_json(value: Any, field: str) -> Any:
    try:
        copied = deepcopy(value)
        canonical_json(copied)
        return copied
    except Exception as exc:
        raise EconomicEvidencePropagationError(f"{field} must be canonical JSON") from exc


def _coverage_for_account(
    account_coverage: Mapping[str, Any],
    account_id: str,
) -> Dict[str, Any]:
    if not isinstance(account_coverage, Mapping):
        raise EconomicEvidencePropagationError("account_coverage must be an object")
    raw = account_coverage.get(account_id)
    if raw is None and "status" in account_coverage:
        raw = account_coverage
    if not isinstance(raw, Mapping):
        raise EconomicEvidencePropagationError(
            f"account coverage is required for account {account_id}"
        )

    raw = _copy_json(dict(raw), "account_coverage")
    raw_markers = {
        str(reason).upper()
        for reason in raw.get("reasons", [])
    }
    if isinstance(raw.get("discrepancies"), list):
        raw_markers.update(
            str(item.get("type")).upper()
            for item in raw["discrepancies"]
            if isinstance(item, Mapping) and item.get("type")
        )
    if int(raw.get("unsupported_event_count", 0) or 0) > 0:
        raw_markers.add("UNSUPPORTED_ACCOUNT_EVENT")
    nested = raw.get("coverage")
    if isinstance(nested, Mapping):
        coverage = _copy_json(dict(nested), "account_coverage.coverage")
        status = str(raw.get("status") or coverage.get("status") or "UNKNOWN").upper()
        coverage["status"] = status
        coverage["reconciliation_status"] = str(raw.get("status") or status).upper()
        for key in ("realized_pnl", "unrealized_pnl"):
            if key in raw:
                coverage[key] = raw[key]
    else:
        coverage = raw
        status = str(coverage.get("status") or "UNKNOWN").upper()
        coverage["status"] = status

    if status not in _ALLOWED_COVERAGE_STATUSES:
        raise EconomicEvidencePropagationError(
            f"unsupported account coverage status: {status}"
        )
    markers = {str(reason).upper() for reason in coverage.get("reasons", [])}
    discrepancies = coverage.get("discrepancies", [])
    if isinstance(discrepancies, list):
        markers.update(
            str(item.get("type")).upper()
            for item in discrepancies
            if isinstance(item, Mapping) and item.get("type")
        )
    if int(coverage.get("unsupported_event_count", 0) or 0) > 0:
        markers.add("UNSUPPORTED_ACCOUNT_EVENT")
    if (markers | raw_markers) & _UNSUPPORTED_COVERAGE_MARKERS:
        raise EconomicEvidencePropagationError(
            "unsupported or schema-pending account event cannot enter trade evidence"
        )
    return coverage


def _source_documents(group: Mapping[str, Any]) -> List[str]:
    values = {
        str(item.get("source_document_sha256"))
        for item in group.get("source_lineage", [])
        if isinstance(item, Mapping) and item.get("source_document_sha256")
    }
    return sorted(values)


def _event_time(group: Mapping[str, Any]) -> str:
    correction_lineage = group.get("correction_lineage") or []
    if correction_lineage:
        latest = correction_lineage[-1]
        if isinstance(latest, Mapping) and latest.get("effective_at"):
            return _required_text(latest["effective_at"], "correction_lineage.effective_at")
    return _required_text(group.get("occurred_at"), "group.occurred_at")


class EconomicEvidencePropagationService:
    """Propagate complete trade snapshots with deterministic group context."""

    def __init__(
        self,
        driver: Optional[SQLiteDriver] = None,
        *,
        ledger_repo: Optional[EvidenceLedgerRepository] = None,
    ) -> None:
        self.driver = driver or sqlite_driver
        self.ledger_repo = ledger_repo or EvidenceLedgerRepository(self.driver.db_path)

    @staticmethod
    def _validate_group(group: Mapping[str, Any]) -> Tuple[str, str, str, str, Decimal, Decimal]:
        if not isinstance(group, Mapping):
            raise EconomicEvidencePropagationError("economic group must be an object")
        group_id = _required_text(group.get("economic_group_id"), "economic_group_id")
        account_id = _required_text(group.get("account_id"), "group.account_id")
        venue = _required_text(group.get("venue"), "group.venue")
        status = _required_text(group.get("status"), "group.status").upper()
        if status != "CONFIRMED":
            raise EconomicEvidencePropagationError(
                f"economic group {group_id} is not confirmed: {status}"
            )
        quantity = _decimal(group.get("quantity"), f"group {group_id}.quantity")
        price = _decimal(group.get("price"), f"group {group_id}.price")
        if quantity <= 0:
            raise EconomicEvidencePropagationError(f"group {group_id}.quantity must be positive")
        if price <= 0:
            raise EconomicEvidencePropagationError(f"group {group_id}.price must be positive")
        _required_text(group.get("symbol"), f"group {group_id}.symbol")
        _required_text(group.get("side"), f"group {group_id}.side")
        if not isinstance(group.get("source_lineage"), list) or not group["source_lineage"]:
            raise EconomicEvidencePropagationError(
                f"group {group_id}.source_lineage is required"
            )
        return (
            group_id,
            account_id,
            venue,
            status,
            quantity,
            price,
        )

    @classmethod
    def _validate_trade_snapshot(
        cls,
        group: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> Dict[str, Any]:
        group_id = str(group["economic_group_id"])
        if not isinstance(snapshot, Mapping):
            raise EconomicEvidencePropagationError(
                f"trade snapshot is required for economic group {group_id}"
            )
        missing = sorted(_REQUIRED_TRADE_FIELDS - set(snapshot))
        if missing:
            raise EconomicEvidencePropagationError(
                f"trade snapshot for {group_id} is missing {', '.join(missing)}"
            )
        trade = _copy_json(dict(snapshot), f"trade snapshot {group_id}")
        trade_id = _required_text(trade.get("id"), f"trade snapshot {group_id}.id")
        symbol = _required_text(trade.get("symbol"), f"trade snapshot {trade_id}.symbol").upper()
        side = _required_text(trade.get("side"), f"trade snapshot {trade_id}.side").upper()
        if symbol != str(group["symbol"]).upper():
            raise EconomicEvidencePropagationError(
                f"trade snapshot {trade_id} symbol disagrees with group {group_id}"
            )
        if side != str(group["side"]).upper():
            raise EconomicEvidencePropagationError(
                f"trade snapshot {trade_id} side disagrees with group {group_id}"
            )
        if _decimal(trade.get("qty"), f"trade snapshot {trade_id}.qty") != _decimal(group["quantity"], "group.quantity"):
            raise EconomicEvidencePropagationError(
                f"trade snapshot {trade_id}.qty disagrees with group {group_id}"
            )
        if _decimal(trade.get("entry_price"), f"trade snapshot {trade_id}.entry_price") != _decimal(group["price"], "group.price"):
            raise EconomicEvidencePropagationError(
                f"trade snapshot {trade_id}.entry_price disagrees with group {group_id}"
            )
        status = _required_text(trade.get("status"), f"trade snapshot {trade_id}.status").upper()
        if status not in {"OPEN", "CLOSED", "CANCELED"}:
            raise EconomicEvidencePropagationError(
                f"trade snapshot {trade_id}.status is unsupported"
            )
        _required_text(trade.get("entry_time"), f"trade snapshot {trade_id}.entry_time")
        _decimal(trade.get("pnl"), f"trade snapshot {trade_id}.pnl")
        _decimal(trade.get("commission"), f"trade snapshot {trade_id}.commission")
        # These keys are intentionally normalized here, while pnl and
        # commission remain explicit input requirements rather than defaults.
        trade.update({"id": trade_id, "symbol": symbol, "side": side, "status": status})
        return trade

    @staticmethod
    def _base_evidence(
        report: Mapping[str, Any],
        group: Mapping[str, Any],
        coverage: Mapping[str, Any],
    ) -> Dict[str, Any]:
        group_id = str(group["economic_group_id"])
        return {
            "schema_version": "P1-WP21-EVIDENCE-V1",
            "economic_group_id": group_id,
            "economic_group_key": group.get("economic_group_key"),
            "group_status": group.get("status"),
            "grouping_status": report.get("status"),
            "source_observation_count": group.get("source_observation_count"),
            "source_lineage": _copy_json(group.get("source_lineage"), f"group {group_id}.source_lineage"),
            "correction_lineage": _copy_json(group.get("correction_lineage") or [], f"group {group_id}.correction_lineage"),
            "correction_count": int(group.get("correction_count", 0) or 0),
            "external_order_ids": sorted(str(value) for value in group.get("external_order_ids", [])),
            "external_fill_ids": sorted(str(value) for value in group.get("external_fill_ids", [])),
            "discrepancies": _copy_json(group.get("discrepancies") or [], f"group {group_id}.discrepancies"),
            "grouping_discrepancies": _copy_json(report.get("discrepancies") or [], "grouping.discrepancies"),
            "account_coverage": _copy_json(dict(coverage), "account_coverage"),
            "source_documents": _source_documents(group),
        }

    @staticmethod
    def _fingerprint(trade: Mapping[str, Any], evidence: Mapping[str, Any]) -> str:
        body = {"trade": dict(trade), "economic_evidence": dict(evidence)}
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()

    @staticmethod
    def _event_id(idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return f"p1-wp21-{digest}"

    @staticmethod
    def _revision_from_event(event: Mapping[str, Any]) -> int:
        payload = event.get("normalized_payload")
        trade = payload.get("trade") if isinstance(payload, Mapping) else None
        evidence = trade.get("economic_evidence") if isinstance(trade, Mapping) else None
        revision = evidence.get("revision") if isinstance(evidence, Mapping) else None
        try:
            return int(revision.get("revision_number", 1)) if isinstance(revision, Mapping) else 1
        except (TypeError, ValueError):
            raise EconomicEvidencePropagationError("previous economic evidence revision is invalid")

    def _build_command(
        self,
        report: Mapping[str, Any],
        group: Mapping[str, Any],
        trade: Mapping[str, Any],
        coverage: Mapping[str, Any],
    ) -> Dict[str, Any]:
        group_id, account_id, venue, _, _, _ = self._validate_group(group)
        evidence = self._base_evidence(report, group, coverage)
        fingerprint = self._fingerprint(trade, evidence)
        correction_count = int(group.get("correction_count", 0) or 0)
        event_type = "TradeCorrected" if correction_count else "FillRecorded"
        idempotency_key = f"economic-group:{group_id}:{event_type}:{fingerprint}"
        existing = self.ledger_repo.get_event_by_identity(
            account_id, venue, event_type, idempotency_key
        )
        if existing is not None:
            # Replays reuse the exact immutable command, including its
            # deterministic receipt time and payload.
            payload = existing.get("normalized_payload")
            if not isinstance(payload, Mapping):
                raise EconomicEvidencePropagationError("existing economic evidence payload is invalid")
            return {
                "trade": dict(trade),
                "event_type": event_type,
                "idempotency_key": idempotency_key,
                "event_id": existing["event_id"],
                "account_id": account_id,
                "venue": venue,
                "occurred_at": existing["occurred_at_utc"],
                "received_at": existing["received_at_utc"],
                "schema_version": "1",
                "adapter_version": "economic-group-propagation-v1",
                "correlation_id": str(trade["id"]),
                "causation_id": existing.get("causation_id"),
                "provenance": existing.get("provenance") or {},
                "normalized_payload": payload,
                "raw_payload": payload,
            }

        history = self.ledger_repo.list_events_for_economic_group(
            group_id,
            account_id=account_id,
            venue=venue,
        )
        causation_id = None
        if correction_count:
            if not history:
                raise EconomicEvidencePropagationError(
                    f"correction for economic group {group_id} has no prior immutable event"
                )
            previous = history[-1]
            previous_trade = (previous.get("normalized_payload") or {}).get("trade")
            if not isinstance(previous_trade, Mapping) or str(previous_trade.get("id")) != str(trade["id"]):
                raise EconomicEvidencePropagationError(
                    f"correction for economic group {group_id} changes trade identity"
                )
            causation_id = previous["event_id"]
            evidence["revision"] = {
                "revision_number": self._revision_from_event(previous) + 1,
                "previous_event_id": previous["event_id"],
                "previous_event_hash": previous["event_hash"],
                "as_of_event_type": event_type,
            }
        elif history:
            raise EconomicEvidencePropagationError(
                f"economic group {group_id} already exists; a changed import requires correction lineage"
            )
        else:
            evidence["revision"] = {
                "revision_number": 1,
                "previous_event_id": None,
                "previous_event_hash": None,
                "as_of_event_type": event_type,
            }

        evidence["propagation_fingerprint"] = fingerprint
        payload_trade = dict(trade)
        payload_trade["economic_evidence"] = evidence
        normalized_payload = {"trade": payload_trade, "source_id": group_id}
        source_documents = evidence["source_documents"]
        provenance = {
            "source": "economic_trade_grouping",
            "propagation_version": "P1-WP21-V1",
            "economic_group_id": group_id,
            "source_documents": source_documents,
            "account_coverage_status": coverage.get("status", "UNKNOWN"),
        }
        return {
            "trade": payload_trade,
            "event_type": event_type,
            "idempotency_key": idempotency_key,
            "event_id": self._event_id(idempotency_key),
            "account_id": account_id,
            "venue": venue,
            "occurred_at": _event_time(group),
            "received_at": _event_time(group),
            "schema_version": "1",
            "adapter_version": "economic-group-propagation-v1",
            "correlation_id": str(trade["id"]),
            "causation_id": causation_id,
            "provenance": provenance,
            "normalized_payload": normalized_payload,
            "raw_payload": normalized_payload,
        }

    def propagate(
        self,
        grouping_report: Mapping[str, Any],
        *,
        trade_snapshots: Mapping[str, Mapping[str, Any]],
        account_coverage: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Write a validated group batch atomically and return immutable evidence."""

        if not isinstance(grouping_report, Mapping):
            raise EconomicEvidencePropagationError("grouping_report must be an object")
        if not isinstance(trade_snapshots, Mapping):
            raise EconomicEvidencePropagationError("trade_snapshots must be an object")
        report_status = _required_text(grouping_report.get("status"), "grouping_report.status").upper()
        if report_status == "UNRESOLVED":
            raise EconomicEvidencePropagationError("unresolved economic grouping cannot be propagated")
        groups = grouping_report.get("groups")
        if not isinstance(groups, list):
            raise EconomicEvidencePropagationError("grouping_report.groups must be an array")
        if not groups:
            return {"created_count": 0, "duplicate_count": 0, "events": [], "trades": []}

        integrity = self.ledger_repo.verify_chain()
        if not integrity["valid"]:
            raise EconomicEvidencePropagationError(
                "ledger is invalid; economic evidence propagation is fail-closed"
            )

        commands: List[Dict[str, Any]] = []
        seen_group_ids = set()
        for group in sorted(groups, key=lambda item: str(item.get("economic_group_id", ""))):
            group_id, _, _, _, _, _ = self._validate_group(group)
            if group_id in seen_group_ids:
                raise EconomicEvidencePropagationError(f"duplicate economic group: {group_id}")
            seen_group_ids.add(group_id)
            snapshot = trade_snapshots.get(group_id)
            trade = self._validate_trade_snapshot(group, snapshot)
            coverage = _coverage_for_account(account_coverage, str(group["account_id"]))
            commands.append(self._build_command(grouping_report, group, trade, coverage))

        commands.sort(
            key=lambda command: (
                str(command.get("occurred_at") or ""),
                str(command.get("account_id") or ""),
                str(command.get("venue") or ""),
                str(command.get("idempotency_key") or ""),
            )
        )
        persisted = self.driver.record_grouped_evidence_batch(commands)
        events = [item["event"] for item in persisted]
        return {
            "created_count": sum(1 for event in events if event.get("created")),
            "duplicate_count": sum(1 for event in events if not event.get("created")),
            "event_ids": [event["event_id"] for event in events],
            "events": [
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "account_id": event["account_id"],
                    "venue": event["venue"],
                    "occurred_at_utc": event["occurred_at_utc"],
                    "received_at_utc": event["received_at_utc"],
                    "causation_id": event["causation_id"],
                    "idempotency_key": event["idempotency_key"],
                    "raw_payload_sha256": event["raw_payload_sha256"],
                    "normalized_payload": event["normalized_payload"],
                    "provenance": event["provenance"],
                    "prev_hash": event["prev_hash"],
                    "event_hash": event["event_hash"],
                }
                for event in events
            ],
            "trades": [item["trade"] for item in persisted],
        }


economic_evidence_propagation_service = EconomicEvidencePropagationService()
