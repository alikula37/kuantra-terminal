"""Deterministic weekly review projection over canonical evidence.

The review is deliberately a read projection.  It stores completion or reopen
decisions through the existing ``JournalReviewAdded`` event and never adds a
weekly-review table, a funding/transfer event, or a financial success verdict.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json


_COVERAGE_STATES = frozenset({"COMPLETE", "PARTIAL", "UNKNOWN", "NOT_AVAILABLE"})
_DECISIONS = {"COMPLETE": "COMPLETED", "COMPLETED": "COMPLETED", "REOPEN": "REOPENED", "REOPENED": "REOPENED"}


class WeeklyReviewError(ValueError):
    """Raised when a weekly review cannot be built or recorded safely."""


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise WeeklyReviewError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise WeeklyReviewError(f"{field} must be an ISO date") from exc


def _parse_as_of(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise WeeklyReviewError("as_of_utc is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise WeeklyReviewError("as_of_utc must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None:
        raise WeeklyReviewError("as_of_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def _event_time(event: Mapping[str, Any]) -> Optional[datetime]:
    value = event.get("occurred_at_utc")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _received_time(event: Mapping[str, Any]) -> Optional[datetime]:
    value = event.get("received_at_utc")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_review_event(event: Mapping[str, Any]) -> bool:
    payload = event.get("normalized_payload")
    provenance = event.get("provenance")
    return (
        isinstance(payload, Mapping) and payload.get("review_kind") == "WEEKLY_REVIEW"
    ) or (
        isinstance(provenance, Mapping) and provenance.get("source") == "weekly_review"
    )


def _coverage_state(value: Any, *, default: str = "UNKNOWN") -> str:
    text = str(value or "").strip().upper()
    return text if text in _COVERAGE_STATES else default


def _explicit_coverage(mapping: Any, keys: Sequence[str]) -> Optional[str]:
    if not isinstance(mapping, Mapping):
        return None
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip().upper() in _COVERAGE_STATES:
            return value.strip().upper()
        if isinstance(value, bool):
            return "COMPLETE" if value else _coverage_state(mapping.get("status"), default="UNKNOWN")
        if mapping.get(f"{key}_complete") is True:
            return "COMPLETE"
        if mapping.get(f"{key}_complete") is False:
            return _coverage_state(mapping.get("status"), default="UNKNOWN")
    return None


def _merge_coverage(values: Sequence[str]) -> str:
    if not values:
        return "NOT_AVAILABLE"
    if "UNKNOWN" in values:
        return "UNKNOWN"
    if "PARTIAL" in values:
        return "PARTIAL"
    if all(value == "COMPLETE" for value in values):
        return "COMPLETE"
    return "NOT_AVAILABLE"


def _trade_id(event: Mapping[str, Any]) -> Optional[str]:
    payload = event.get("normalized_payload")
    trade = payload.get("trade") if isinstance(payload, Mapping) else None
    if not isinstance(trade, Mapping):
        return None
    value = str(trade.get("id") or "").strip()
    return value or None


def _rule_reference(event: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
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
    risk = next((value for value in sources if value.get("policy_id")), None)
    playbook = next((value for value in sources if value.get("playbook_id")), None)
    source = risk or playbook
    if source is None:
        return None
    kind = "risk" if risk is not None else "playbook"
    if kind == "risk":
        rule_id = str(source.get("policy_id"))
        version = str(source.get("policy_version") or source.get("version") or "—")
        snapshot = str(source.get("policy_snapshot_sha256") or source.get("snapshot_sha256") or "")
    else:
        rule_id = str(source.get("playbook_id"))
        version = str(source.get("playbook_version") or source.get("version") or "—")
        snapshot = str(source.get("playbook_snapshot_sha256") or source.get("snapshot_sha256") or "")
    effective = source.get("effective_at_utc") or source.get("effective_at")
    return {
        "kind": kind,
        "rule_id": rule_id,
        "version": version,
        "snapshot_sha256": snapshot,
        "effective_at_utc": str(effective) if effective else None,
        "effective_time_status": "EXPLICIT" if effective else "NOT_AVAILABLE",
        "event_id": str(event.get("event_id") or ""),
        "event_hash": str(event.get("event_hash") or ""),
    }


class WeeklyReviewService:
    """Build and record a deterministic review without widening the ledger schema."""

    def __init__(self, *, ledger_repo: Optional[EvidenceLedgerRepository] = None):
        self.ledger_repo = ledger_repo or EvidenceLedgerRepository()

    @staticmethod
    def _period(
        period_start: str,
        period_end: str,
        timezone_name: str,
    ) -> Dict[str, Any]:
        start_date = _parse_date(period_start, "period_start")
        end_date = _parse_date(period_end, "period_end")
        if end_date <= start_date:
            raise WeeklyReviewError("period_end must be after period_start")
        if (end_date - start_date).days > 366:
            raise WeeklyReviewError("review period cannot exceed 366 days")
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise WeeklyReviewError("timezone is required")
        try:
            zone = ZoneInfo(timezone_name.strip())
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise WeeklyReviewError("timezone is unsupported") from exc
        start_local = datetime.combine(start_date, time.min, tzinfo=zone)
        end_local = datetime.combine(end_date, time.min, tzinfo=zone)
        return {
            "start_local": start_local.isoformat(),
            "end_local": end_local.isoformat(),
            "start_utc": _utc_text(start_local),
            "end_utc": _utc_text(end_local),
            "timezone": timezone_name.strip(),
        }

    @staticmethod
    def _coverage(events: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
        fields = {
            "realized_pnl": ("realized_pnl", "pnl"),
            "fees": ("commission", "fees", "fee"),
            "funding_transfer": ("funding_transfer", "funding", "transfers"),
            "market_context": ("market_context",),
            "account_events": ("account_events", "events_complete"),
        }
        collected: Dict[str, List[str]] = {key: [] for key in fields}
        for event in events:
            provenance = event.get("provenance")
            provenance = provenance if isinstance(provenance, Mapping) else {}
            payload = event.get("normalized_payload")
            trade = payload.get("trade") if isinstance(payload, Mapping) else None
            economic = trade.get("economic_evidence") if isinstance(trade, Mapping) else None
            sources = [
                provenance.get("import_review", {}).get("coverage")
                if isinstance(provenance.get("import_review"), Mapping)
                else None,
                provenance.get("reconciliation_review", {}).get("coverage")
                if isinstance(provenance.get("reconciliation_review"), Mapping)
                else None,
                economic.get("account_coverage") if isinstance(economic, Mapping) else None,
            ]
            for key, aliases in fields.items():
                for source in sources:
                    value = _explicit_coverage(source, aliases)
                    if value is not None:
                        collected[key].append(value)
        summary = {key: _merge_coverage(values) for key, values in collected.items()}
        if not events:
            summary["overall"] = "NOT_AVAILABLE"
        elif "UNKNOWN" in summary.values():
            summary["overall"] = "UNKNOWN"
        elif any(value in {"PARTIAL", "NOT_AVAILABLE"} for value in summary.values()):
            summary["overall"] = "PARTIAL"
        else:
            summary["overall"] = "COMPLETE"
        return summary

    @staticmethod
    def _rules(events: Sequence[Mapping[str, Any]], as_of: datetime) -> tuple[List[Dict[str, Any]], int, bool]:
        rules: List[Dict[str, Any]] = []
        excluded_future = 0
        missing_effective_time = False
        for event in events:
            reference = _rule_reference(event)
            if reference is None:
                continue
            effective = reference.get("effective_at_utc")
            if effective:
                try:
                    effective_dt = datetime.fromisoformat(str(effective).replace("Z", "+00:00"))
                    if effective_dt.tzinfo is None:
                        raise ValueError
                    if effective_dt.astimezone(timezone.utc) > as_of:
                        excluded_future += 1
                        continue
                    reference["effective_at_utc"] = _utc_text(effective_dt)
                except ValueError:
                    reference["effective_time_status"] = "MALFORMED"
                    missing_effective_time = True
            else:
                missing_effective_time = True
            rules.append(reference)
        deduped: Dict[str, Dict[str, Any]] = {}
        for rule in rules:
            deduped[canonical_json(rule)] = rule
        return [deduped[key] for key in sorted(deduped)], excluded_future, missing_effective_time

    @staticmethod
    def _review_decision(events: Iterable[Mapping[str, Any]], review_id: str) -> Optional[Dict[str, Any]]:
        decisions = []
        for event in events:
            if not _is_review_event(event):
                continue
            payload = event.get("normalized_payload")
            if not isinstance(payload, Mapping) or payload.get("review_id") != review_id:
                continue
            decisions.append((str(event.get("occurred_at_utc") or ""), str(event.get("event_id") or ""), payload, event))
        if not decisions:
            return None
        _time, _event_id, payload, event = sorted(decisions)[-1]
        return {
            "decision": payload.get("decision"),
            "note": payload.get("decision_note"),
            "event_id": event.get("event_id"),
            "event_hash": event.get("event_hash"),
            "reviewed_at_utc": event.get("occurred_at_utc"),
        }

    def build_review(
        self,
        *,
        period_start: str,
        period_end: str,
        timezone_name: str,
        as_of_utc: str,
    ) -> Dict[str, Any]:
        period = self._period(period_start, period_end, timezone_name)
        as_of = _parse_as_of(as_of_utc)
        start_utc = datetime.fromisoformat(period["start_utc"].replace("Z", "+00:00"))
        end_utc = datetime.fromisoformat(period["end_utc"].replace("Z", "+00:00"))
        if as_of < start_utc:
            raise WeeklyReviewError("as_of_utc cannot be before period_start")

        all_events = list(self.ledger_repo.export_events())
        evidence_events: List[Mapping[str, Any]] = []
        late_event_count = 0
        malformed_event_count = 0
        for event in all_events:
            if _is_review_event(event):
                continue
            occurred = _event_time(event)
            if occurred is None:
                malformed_event_count += 1
                continue
            if start_utc <= occurred < end_utc:
                received = _received_time(event)
                # The as-of projection contains only facts known by the
                # cutoff.  A correction can retain an in-period occurred_at
                # while arriving later, so received_at is part of this gate.
                if occurred <= as_of and (received is None or received <= as_of):
                    evidence_events.append(event)
                else:
                    late_event_count += 1

        source_event_hashes = sorted(
            str(event.get("event_hash"))
            for event in evidence_events
            if event.get("event_hash")
        )
        trade_ids = sorted({trade_id for event in evidence_events if (trade_id := _trade_id(event))})
        applicable_rules, excluded_future_rule_count, missing_effective_time = self._rules(evidence_events, as_of)
        coverage = self._coverage(evidence_events)
        review_identity = {
            "period": period,
            "as_of_utc": _utc_text(as_of),
            "source_event_hashes": source_event_hashes,
            "applicable_rules": applicable_rules,
            "excluded_future_rule_count": excluded_future_rule_count,
        }
        review_id = "WR-" + hashlib.sha256(canonical_json(review_identity).encode("utf-8")).hexdigest()[:24].upper()
        snapshot_body = {
            "review_id": review_id,
            **review_identity,
            "event_count": len(evidence_events),
            "trade_ids": trade_ids,
            "coverage": coverage,
            "late_event_count": late_event_count,
            "malformed_event_count": malformed_event_count,
        }
        snapshot_sha256 = hashlib.sha256(canonical_json(snapshot_body).encode("utf-8")).hexdigest()
        warnings: List[str] = []
        if not evidence_events:
            warnings.append("NO_EVIDENCE_IN_PERIOD")
        if late_event_count:
            warnings.append("LATE_EVENT_AFTER_AS_OF")
        if malformed_event_count:
            warnings.append("MALFORMED_EVENT_EXCLUDED")
        for field in ("fees", "funding_transfer", "market_context"):
            if coverage[field] != "COMPLETE":
                warnings.append(f"{field.upper()}_{coverage[field]}")
        if missing_effective_time:
            warnings.append("RULE_EFFECTIVE_TIME_NOT_AVAILABLE")
        if excluded_future_rule_count:
            warnings.append("FUTURE_RULE_EXCLUDED")

        if not evidence_events:
            status = "NOT_READY"
        elif late_event_count:
            status = "STALE_REVIEW"
        elif coverage["overall"] == "COMPLETE" and not missing_effective_time and not excluded_future_rule_count:
            status = "READY"
        else:
            status = "LIMITED"
        decision = self._review_decision(all_events, review_id)
        completion = decision if decision and decision.get("decision") in {"COMPLETED", "REOPENED"} else None
        if completion and completion["decision"] == "COMPLETED" and status != "STALE_REVIEW":
            status = "COMPLETED"
        return {
            "review_id": review_id,
            "review_status": status,
            "completion_allowed": bool(evidence_events) and status not in {"STALE_REVIEW", "NOT_READY"},
            "is_pass": False,
            "period": period,
            "as_of_utc": _utc_text(as_of),
            "snapshot_sha256": snapshot_sha256,
            "source_event_hashes": source_event_hashes,
            "trade_ids": trade_ids,
            "trade_count": len(trade_ids),
            "event_count": len(evidence_events),
            "late_event_count": late_event_count,
            "malformed_event_count": malformed_event_count,
            "excluded_future_rule_count": excluded_future_rule_count,
            "coverage": coverage,
            "applicable_rules": applicable_rules,
            "warnings": warnings,
            "completion": completion,
        }

    def record_decision(self, review: Mapping[str, Any], *, decision: str, note: Optional[str] = None) -> Dict[str, Any]:
        normalized = str(decision or "").strip().upper().replace("-", "_")
        target = _DECISIONS.get(normalized)
        if target is None:
            raise WeeklyReviewError("decision must be COMPLETE or REOPEN")
        if review.get("review_status") in {"NOT_READY", "STALE_REVIEW"} or not review.get("completion_allowed"):
            raise WeeklyReviewError("review is not ready for a completion decision")
        if note is not None:
            note = str(note).strip()
            if len(note) > 500:
                raise WeeklyReviewError("review note exceeds the bounded limit")
            if any(ord(character) < 32 and character not in "\t\n\r" for character in note):
                raise WeeklyReviewError("review note contains a control character")
        note = note or None
        digest = hashlib.sha256(canonical_json({"decision": target, "note": note}).encode("utf-8")).hexdigest()[:24]
        idempotency_key = f"weekly-review:{review['review_id']}:{target}:{digest}"
        existing = self.ledger_repo.get_event_by_identity(
            "local-journal", "local-journal", "JournalReviewAdded", idempotency_key
        )
        if existing is not None:
            return {
                "review_id": review["review_id"],
                "decision": target,
                "event_id": existing["event_id"],
                "event_hash": existing["event_hash"],
                "created": False,
            }
        payload = {
            "review_kind": "WEEKLY_REVIEW",
            "review_id": review["review_id"],
            "decision": target,
            "period": review["period"],
            "as_of_utc": review["as_of_utc"],
            "snapshot_sha256": review["snapshot_sha256"],
            "source_event_hashes": review["source_event_hashes"],
            "coverage": review["coverage"],
            "is_pass": False,
        }
        if note:
            payload["decision_note"] = note
        event = self.ledger_repo.append_event(
            event_type="JournalReviewAdded",
            account_id="local-journal",
            venue="local-journal",
            idempotency_key=idempotency_key,
            normalized_payload=payload,
            raw_payload=payload,
            occurred_at=_utc_text(datetime.now(timezone.utc)),
            adapter_version="weekly-review-v1",
            correlation_id=review["review_id"],
            provenance={
                "source": "weekly_review",
                "review_id": review["review_id"],
                "snapshot_sha256": review["snapshot_sha256"],
            },
        )
        return {
            "review_id": review["review_id"],
            "decision": target,
            "event_id": event["event_id"],
            "event_hash": event["event_hash"],
            "created": bool(event.get("created")),
        }


weekly_review_service = WeeklyReviewService()


__all__ = ["WeeklyReviewError", "WeeklyReviewService", "weekly_review_service"]
