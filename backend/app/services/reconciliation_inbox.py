"""Evidence-backed reconciliation inbox and explicit user decision boundary.

The inbox is a projection of existing immutable ledger provenance.  It does not
introduce a reconciliation table or a new funding/transfer event type.  Review
decisions use the existing ``JournalReviewAdded`` event and an actual trade
correction uses the existing ``TradeCorrected`` contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.db.repositories.evidence_ledger_repo import (
    EvidenceLedgerRepository,
    canonical_json,
)
from app.db.sqlite_driver import SQLiteDriver, sqlite_driver


DECISION_STATES = frozenset({"UNRESOLVED", "ACKNOWLEDGED", "REJECTED", "CORRECTED"})
_DECISION_TARGETS = {
    "ACKNOWLEDGE": "ACKNOWLEDGED",
    "ACKNOWLEDGED": "ACKNOWLEDGED",
    "REJECT": "REJECTED",
    "REJECTED": "REJECTED",
    "CORRECT": "CORRECTED",
    "CORRECTED": "CORRECTED",
}
_TERMINAL_STATES = frozenset({"ACKNOWLEDGED", "REJECTED", "CORRECTED"})
_CORRECTION_FIELDS = frozenset({
    "entry_price",
    "exit_price",
    "qty",
    "stop_loss",
    "take_profit",
    "entry_time",
    "exit_time",
    "status",
    "pnl",
    "r_multiple",
    "commission",
    "notes",
})
# (lower, upper, zero_allowed) for every numeric correction field.
_CORRECTION_NUMERIC_BOUNDS = {
    "entry_price": (0.0, 1e15, False),
    "exit_price": (0.0, 1e15, False),
    "qty": (0.0, 1e15, False),
    "stop_loss": (0.0, 1e15, False),
    "take_profit": (0.0, 1e15, False),
    "pnl": (-1e15, 1e15, True),
    "r_multiple": (-1e6, 1e6, True),
    "commission": (-1e15, 1e15, True),
}


def _bounded_correction_number(key: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReconciliationInboxError(f"correction field {key} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ReconciliationInboxError(f"correction field {key} must be finite")
    lower, upper, zero_allowed = _CORRECTION_NUMERIC_BOUNDS[key]
    if number < lower or number > upper or (number == 0 and not zero_allowed):
        raise ReconciliationInboxError(
            f"correction field {key} is outside the allowed range"
        )
    return number
_DISCREPANCY_FIELDS = frozenset({
    "type",
    "fields",
    "source_row_number",
    "source_row_sha256",
    "external_order_id",
    "external_fill_id",
    "record_type",
    "count",
    "warning_count",
    "order_filled_qty",
    "fill_qty",
    "order_avg_price",
    "fill_weighted_price",
    "order_fee",
    "fill_fee",
    "fee_currency",
    "currencies",
    "reason",
})
_SECRET_KEY_PARTS = frozenset({
    "api_key",
    "api_secret",
    "password",
    "passphrase",
    "credential",
    "token",
    "private_key",
})


class ReconciliationInboxError(ValueError):
    """Base class for bounded inbox validation errors."""


class ReconciliationReviewNotFound(ReconciliationInboxError):
    """Raised when a review id is not derived from immutable source evidence."""


class ReconciliationDecisionConflict(ReconciliationInboxError):
    """Raised when a terminal review is given a different decision."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _bounded_text(value: Any, *, limit: int = 512) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > limit:
        raise ReconciliationInboxError("review text exceeds the bounded limit")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in text):
        raise ReconciliationInboxError("review text contains a control character")
    return text


def _safe_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ReconciliationInboxError("review value must be finite")
        return value
    return str(value)


def _safe_discrepancy(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ReconciliationInboxError("discrepancy must be an object")
    safe: Dict[str, Any] = {}
    for key in _DISCREPANCY_FIELDS:
        if key not in value:
            continue
        normalized_key = str(key).lower()
        if any(part in normalized_key for part in _SECRET_KEY_PARTS):
            continue
        child = value[key]
        if isinstance(child, list):
            safe[key] = [_safe_scalar(item) for item in child[:32]]
        elif isinstance(child, dict):
            safe[key] = {
                str(child_key): _safe_scalar(child_value)
                for child_key, child_value in list(child.items())[:32]
                if not any(part in str(child_key).lower() for part in _SECRET_KEY_PARTS)
            }
        else:
            safe[key] = _safe_scalar(child)
    if not safe.get("type"):
        raise ReconciliationInboxError("discrepancy type is required")
    return safe


def _safe_review_fragment(value: Any) -> Any:
    """Copy bounded review metadata without exposing raw source payloads."""

    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            normalized = key_text.lower()
            if normalized in {"raw_payload", "payload", "errors", "rejected_rows"}:
                continue
            if any(part in normalized for part in _SECRET_KEY_PARTS):
                continue
            result[key_text] = _safe_review_fragment(child)
        return result
    if isinstance(value, list):
        return [_safe_review_fragment(child) for child in value[:64]]
    if isinstance(value, str):
        return _bounded_text(value, limit=1024) or ""
    return _safe_scalar(value)


def _decision_target(value: Any) -> str:
    normalized = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    target = _DECISION_TARGETS.get(normalized)
    if target is None:
        raise ReconciliationInboxError(
            "decision must be ACKNOWLEDGE, REJECT, or CORRECT"
        )
    return target


class ReconciliationInboxService:
    """Derive and append reconciliation decisions from canonical evidence."""

    def __init__(
        self,
        *,
        ledger_repo: Optional[EvidenceLedgerRepository] = None,
        legacy_driver: Optional[SQLiteDriver] = None,
    ) -> None:
        self.ledger_repo = ledger_repo or EvidenceLedgerRepository()
        self.legacy_driver = legacy_driver or (
            sqlite_driver if self.ledger_repo.db_path == sqlite_driver.db_path
            else SQLiteDriver(self.ledger_repo.db_path)
        )

    @staticmethod
    def _trade_context(event: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        payload = event.get("normalized_payload")
        if not isinstance(payload, dict):
            return None, None
        trade = payload.get("trade")
        if not isinstance(trade, dict):
            return None, None
        trade_id = str(trade.get("id") or "").strip() or None
        economic = trade.get("economic_evidence")
        group_id = (
            str(economic.get("economic_group_id") or "").strip() or None
            if isinstance(economic, dict)
            else None
        )
        return trade_id, group_id

    @staticmethod
    def _source_ref(event: Dict[str, Any]) -> Dict[str, Any]:
        provenance = event.get("provenance") if isinstance(event.get("provenance"), dict) else {}
        source: Dict[str, Any] = {
            "event_id": event.get("event_id"),
            "event_hash": event.get("event_hash"),
            "event_type": event.get("event_type"),
            "account_id": event.get("account_id"),
            "venue": event.get("venue"),
            "occurred_at_utc": event.get("occurred_at_utc"),
        }
        for key in ("source_file_sha256", "source_row_number", "source_row_sha256"):
            if provenance.get(key) is not None:
                source[key] = provenance[key]
        return source

    @staticmethod
    def _review_group_key(event: Dict[str, Any], review_key: str) -> str:
        provenance = event.get("provenance") if isinstance(event.get("provenance"), dict) else {}
        return str(
            provenance.get("source_file_sha256")
            or event.get("event_id")
            or "unknown-source"
        )

    @classmethod
    def _review_discrepancies(
        cls,
        review_key: str,
        review: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raw = review.get("discrepancies")
        raw_items = raw if isinstance(raw, list) else []
        discrepancies = [
            _safe_discrepancy(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        if discrepancies:
            return discrepancies

        status = str(review.get("status") or "").upper()
        decision = str(review.get("decision") or "").upper()
        next_action = str(review.get("next_action") or "").strip()
        if review_key == "import_review" and status == "READY" and decision == "IMPORT_ALLOWED":
            return []
        if review_key == "reconciliation_review" or status not in {"READY", "IMPORT_ALLOWED"}:
            return [{
                "type": "USER_DECISION_REQUIRED",
                "reason": next_action or "RECONCILIATION_REVIEW_REQUIRED",
            }]
        return []

    @classmethod
    def _candidate_items(cls, events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        sorted_events = sorted(
            events,
            key=lambda event: (
                str(event.get("occurred_at_utc") or ""),
                str(event.get("event_id") or ""),
            ),
        )
        for event in sorted_events:
            provenance = event.get("provenance")
            if not isinstance(provenance, dict):
                continue
            if provenance.get("source") in {"reconciliation_inbox", "reconciliation_correction"}:
                continue
            for review_key in ("import_review", "reconciliation_review"):
                review = provenance.get(review_key)
                if not isinstance(review, dict):
                    continue
                group_key = cls._review_group_key(event, review_key)
                for index, discrepancy in enumerate(cls._review_discrepancies(review_key, review)):
                    discrepancy_key = canonical_json(discrepancy)
                    dedup_key = (review_key, group_key, discrepancy_key)
                    if dedup_key in candidates:
                        continue
                    review_id = "RCN-" + hashlib.sha256(
                        canonical_json({
                            "review_key": review_key,
                            "group_key": group_key,
                            "discrepancy": discrepancy,
                        }).encode("utf-8")
                    ).hexdigest()[:24].upper()
                    trade_id, economic_group_id = cls._trade_context(event)
                    candidates[dedup_key] = {
                        "review_id": review_id,
                        "status": "UNRESOLVED",
                        "decision": "UNRESOLVED",
                        "trade_id": trade_id,
                        "economic_group_id": economic_group_id,
                        "source": cls._source_ref(event),
                        "discrepancy": discrepancy,
                        "discrepancy_index": index,
                        "coverage": _safe_review_fragment(review.get("coverage") or {}),
                        "reconciliation": _safe_review_fragment(review.get("reconciliation") or {
                            "status": review.get("reconciliation_status") or "UNKNOWN",
                        }),
                        "source_review": _safe_review_fragment({
                            key: review.get(key)
                            for key in (
                                "status", "decision", "source_type", "detected_format",
                                "next_action", "discrepancy_types",
                            )
                            if review.get(key) is not None
                        }),
                        "detected_at_utc": event.get("occurred_at_utc"),
                    }
        return sorted(
            candidates.values(),
            key=lambda item: (
                str(item.get("detected_at_utc") or ""),
                str(item["source"].get("event_id") or ""),
                item["review_id"],
            ),
        )

    @staticmethod
    def _decision_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = event.get("normalized_payload")
        provenance = event.get("provenance")
        decision = None
        if isinstance(payload, dict) and payload.get("review_kind") == "RECONCILIATION_DECISION":
            decision = payload
        elif isinstance(provenance, dict) and isinstance(provenance.get("reconciliation_decision"), dict):
            decision = provenance["reconciliation_decision"]
        if not isinstance(decision, dict) or not decision.get("review_id"):
            return None
        return {
            **_safe_review_fragment(decision),
            "event_id": event.get("event_id"),
            "event_hash": event.get("event_hash"),
            "occurred_at_utc": event.get("occurred_at_utc"),
            "source_event_hash": decision.get("source_event_hash"),
        }

    @classmethod
    def _apply_decisions(
        cls,
        items: List[Dict[str, Any]],
        events: Iterable[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        by_review_id = {item["review_id"]: item for item in items}
        decisions: Dict[str, Dict[str, Any]] = {}
        for event in events:
            decision = cls._decision_from_event(event)
            if decision is None:
                continue
            review_id = str(decision["review_id"])
            item = by_review_id.get(review_id)
            if item is None:
                continue
            if decision.get("source_event_hash") != item["source"].get("event_hash"):
                item["decision_error"] = "SOURCE_EVENT_HASH_MISMATCH"
                continue
            decisions[review_id] = decision

        for item in items:
            decision = decisions.get(item["review_id"])
            if decision is None:
                continue
            state = str(decision.get("decision") or "").upper()
            if state not in _TERMINAL_STATES:
                item["decision_error"] = "UNSUPPORTED_DECISION_STATE"
                continue
            item.update({
                "status": state,
                "decision": state,
                "decision_event_id": decision.get("event_id"),
                "decision_event_hash": decision.get("event_hash"),
                "decision_at_utc": decision.get("occurred_at_utc"),
            })
            if decision.get("decision_note"):
                item["decision_note"] = decision["decision_note"]
        return items

    def list_items(self, *, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ReconciliationInboxError("limit must be between 1 and 1000")
        requested_status = str(status or "").strip().upper() or None
        if requested_status and requested_status not in DECISION_STATES:
            raise ReconciliationInboxError(
                "status must be UNRESOLVED, ACKNOWLEDGED, REJECTED, or CORRECTED"
            )
        events = list(self.ledger_repo.export_events())
        items = self._candidate_items(events)
        self._apply_decisions(items, events)
        if requested_status:
            items = [item for item in items if item["status"] == requested_status]
        return items[:limit]

    def get_item(self, review_id: str) -> Dict[str, Any]:
        normalized = _bounded_text(review_id, limit=128)
        for item in self.list_items(limit=1000):
            if item["review_id"] == normalized:
                return item
        raise ReconciliationReviewNotFound(f"reconciliation review not found: {review_id}")

    @staticmethod
    def _validate_correction(correction: Any) -> Dict[str, Any]:
        if not isinstance(correction, dict) or not correction:
            raise ReconciliationInboxError(
                "CORRECT requires an explicit non-empty correction object"
            )
        unknown = sorted(set(str(key) for key in correction) - _CORRECTION_FIELDS)
        if unknown:
            raise ReconciliationInboxError(
                f"unsupported correction field: {unknown[0]}"
            )
        validated: Dict[str, Any] = {}
        for key, value in correction.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ReconciliationInboxError(f"correction field {key} must be finite")
            if key == "notes":
                validated[key] = _bounded_text(value, limit=2000) or ""
            elif key == "status":
                normalized_status = str(value or "").strip().upper()
                if normalized_status not in {"OPEN", "CLOSED", "CANCELED"}:
                    raise ReconciliationInboxError("correction status is unsupported")
                validated[key] = normalized_status
            elif key in _CORRECTION_NUMERIC_BOUNDS:
                validated[key] = _bounded_correction_number(key, value)
            else:
                validated[key] = value
        return validated

    @staticmethod
    def _decision_payload(
        item: Dict[str, Any],
        *,
        decision: str,
        note: Optional[str],
        correction_fields: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "review_kind": "RECONCILIATION_DECISION",
            "review_id": item["review_id"],
            "decision": decision,
            "source_event_id": item["source"]["event_id"],
            "source_event_hash": item["source"]["event_hash"],
            "trade_id": item.get("trade_id"),
            "economic_group_id": item.get("economic_group_id"),
            "discrepancy": item["discrepancy"],
            "coverage": item["coverage"],
        }
        if note:
            payload["decision_note"] = note
        if correction_fields:
            payload["correction_fields"] = sorted(str(field) for field in correction_fields)
        return payload

    def record_decision(
        self,
        review_id: str,
        decision: str,
        *,
        note: Optional[str] = None,
        correction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        item = self.get_item(review_id)
        target = _decision_target(decision)
        bounded_note = _bounded_text(note, limit=500)
        validated_correction = self._validate_correction(correction) if target == "CORRECTED" else None
        if target != "CORRECTED" and correction is not None:
            raise ReconciliationInboxError("correction is only accepted with decision CORRECT")

        correction_digest = hashlib.sha256(
            canonical_json(validated_correction or {}).encode("utf-8")
        ).hexdigest()[:24]
        event_type = "TradeCorrected" if target == "CORRECTED" else "JournalReviewAdded"
        idempotency_key = f"reconciliation:{item['review_id']}:{target}:{correction_digest}"
        existing = self.ledger_repo.get_event_by_identity(
            "local-journal", "local-journal", event_type, idempotency_key
        )
        if existing is not None:
            return {
                "review_id": item["review_id"],
                "status": target,
                "decision": target,
                "event_id": existing["event_id"],
                "event_hash": existing["event_hash"],
                "created": False,
            }
        if item["status"] in _TERMINAL_STATES:
            raise ReconciliationDecisionConflict(
                f"review {item['review_id']} already has terminal decision {item['status']}"
            )

        payload = self._decision_payload(
            item,
            decision=target,
            note=bounded_note,
            correction_fields=list(validated_correction or {}),
        )
        if target == "CORRECTED":
            trade_id = item.get("trade_id")
            if not trade_id:
                raise ReconciliationInboxError(
                    "CORRECT requires a source-linked journal trade"
                )
            trade = self.legacy_driver.get_trade(trade_id)
            if trade is None:
                raise ReconciliationInboxError("CORRECT target trade is not available")
            provenance = {
                "source": "reconciliation_correction",
                "review_id": item["review_id"],
                "source_event_id": item["source"]["event_id"],
                "source_event_hash": item["source"]["event_hash"],
                "reconciliation_decision": payload,
            }
            saved = self.legacy_driver.record_trade_with_evidence(
                {"id": trade_id, **validated_correction},
                event_type="TradeCorrected",
                idempotency_key=idempotency_key,
                account_id="local-journal",
                venue="local-journal",
                occurred_at=_now_utc(),
                causation_id=item["source"]["event_id"],
                provenance=provenance,
            )
            event = self.ledger_repo.get_event_by_identity(
                "local-journal", "local-journal", "TradeCorrected", idempotency_key
            )
            if event is None:
                raise ReconciliationInboxError("correction evidence was not persisted")
            return {
                "review_id": item["review_id"],
                "status": target,
                "decision": target,
                "event_id": event["event_id"],
                "event_hash": event["event_hash"],
                "created": bool(event.get("created", True)),
                "trade": saved,
            }

        event = self.ledger_repo.append_event(
            event_type="JournalReviewAdded",
            account_id="local-journal",
            venue="local-journal",
            idempotency_key=idempotency_key,
            normalized_payload=payload,
            raw_payload=payload,
            occurred_at=_now_utc(),
            adapter_version="reconciliation-review-v1",
            correlation_id=item.get("trade_id") or item["review_id"],
            provenance={
                "source": "reconciliation_inbox",
                "review_id": item["review_id"],
                "source_event_id": item["source"]["event_id"],
                "source_event_hash": item["source"]["event_hash"],
                "decision": target,
            },
        )
        return {
            "review_id": item["review_id"],
            "status": target,
            "decision": target,
            "event_id": event["event_id"],
            "event_hash": event["event_hash"],
            "created": bool(event.get("created")),
        }


reconciliation_inbox_service = ReconciliationInboxService()


__all__ = [
    "DECISION_STATES",
    "ReconciliationDecisionConflict",
    "ReconciliationInboxError",
    "ReconciliationInboxService",
    "ReconciliationReviewNotFound",
    "reconciliation_inbox_service",
]
