"""Broker observation identity, account-scope state and deterministic builder.

This module is the A1.1 foundation for broker-sourced records.  It is pure: it
takes validated ledger events and produces a canonical, order-independent
snapshot.  Nothing here converts a broker observation into a journal trade,
writes to the compatibility ``trades`` table or feeds portfolio PnL.

Account-scope contract:

* the caller-declared local bucket (``account_id``) is a local evidence bucket,
  not a broker-verified account identity; being in the same bucket or carrying
  the same symbol/fill id never proves account equality and a file hash never
  substitutes for it;
* current producers provide no persistent, verifiable account namespace, so
  every observation is projected with ``account_scope_state = UNVERIFIED``;
* while the account scope is unverified, observations are preserved
  individually - no economic merge, no repeat/dedup and no content conflict are
  declared across observations.  Duplicate claims on the same declared scope
  are surfaced through counters with their lineage instead;
* source-level idempotency (re-sending the same document) stays a ledger
  property, separate from cross-document economic dedup;
* order and fill records have separate source identities; a fill identity is
  the source fill/deal id and is never substituted with the order id, the
  ledger event id or a content hash.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

ACCOUNT_ENVIRONMENTS = ("UNKNOWN", "DEMO", "LIVE")
ACCOUNT_CONTEXTS = ("UNKNOWN", "PERSONAL", "PROP")
ACCOUNT_SCOPE_SOURCES = ("UNKNOWN", "USER_DECLARED", "BROKER_VERIFIED")

# The account scope available today is the caller-declared local evidence bucket
# (``account_id`` from the import/sync call), not a broker-verified account
# namespace.  A broker-verified account identity and server namespace are an
# A1.2 producer obligation; until then they are never inferred.
ACCOUNT_SCOPE_BASIS = "CALLER_DECLARED"

ACCOUNT_SCOPE_STATE_UNVERIFIED = "UNVERIFIED"
ACCOUNT_SCOPE_STATE_VERIFIED = "VERIFIED"
ACCOUNT_SCOPE_REASON_NOT_PROVIDED = "ACCOUNT_SCOPE_NOT_PROVIDED_BY_PRODUCER"

# Environment/context are changeable classification metadata, not identity:
# learning that an account is LIVE/DEMO or PERSONAL/PROP must never create a
# second economic record for the same source fill.  No producer supplies these
# values today, so stored metadata stays UNKNOWN and is never inferred.
ACCOUNT_METADATA_BASIS = "NOT_PROVIDED_BY_PRODUCER"

PROJECTION_ID = "broker_observations"

RECORD_TYPES = ("order", "fill")
_BROKER_LIFECYCLE_EVENT_TYPES = {
    "fill": frozenset({"FillRecorded"}),
    "order": frozenset({"VenueAck", "VenueReject"}),
}
_REQUIRED_TEXT_FIELDS = ("occurred_at", "symbol", "side", "status")


class BrokerObservationError(ValueError):
    """Raised when a broker lifecycle event cannot be represented fail-closed."""


def validate_account_scope(
    environment: str = "UNKNOWN",
    context: str = "UNKNOWN",
    source: str = "UNKNOWN",
) -> Dict[str, str]:
    """Validate the independent account dimensions.

    Environment and account context are separate dimensions, so every
    combination - including ``PROP`` + ``DEMO`` and ``PROP`` + ``LIVE`` - is
    valid.  Values are never inferred; an unknown source stays ``UNKNOWN``.
    """

    normalized_environment = str(environment or "UNKNOWN").strip().upper()
    normalized_context = str(context or "UNKNOWN").strip().upper()
    normalized_source = str(source or "UNKNOWN").strip().upper()
    if normalized_environment not in ACCOUNT_ENVIRONMENTS:
        raise BrokerObservationError(
            f"unsupported account environment: {environment}"
        )
    if normalized_context not in ACCOUNT_CONTEXTS:
        raise BrokerObservationError(f"unsupported account context: {context}")
    if normalized_source not in ACCOUNT_SCOPE_SOURCES:
        raise BrokerObservationError(f"unsupported account scope source: {source}")
    return {
        "environment": normalized_environment,
        "context": normalized_context,
        "source": normalized_source,
    }


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_text(body: Dict[str, Any], field: str) -> str:
    value = body.get(field)
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise BrokerObservationError(f"broker_lifecycle payload requires {field}")
    return text


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _canonical_decimal(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise BrokerObservationError(f"broker_lifecycle {field} must be a decimal value")
    text = str(value).strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise BrokerObservationError(
            f"broker_lifecycle {field} must be a decimal value"
        ) from exc
    if not number.is_finite():
        raise BrokerObservationError(
            f"broker_lifecycle {field} must be a finite decimal value"
        )
    if number == 0:
        return "0"
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _load_payload(event: Dict[str, Any]) -> Any:
    try:
        return json.loads(event["normalized_payload_json"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BrokerObservationError(
            f"event {event.get('event_id', '<unknown>')} has invalid normalized payload"
        ) from exc


def _load_provenance(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get("provenance_json")
    if not raw:
        return {}
    try:
        provenance = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BrokerObservationError(
            f"event {event.get('event_id', '<unknown>')} has invalid provenance"
        ) from exc
    if not isinstance(provenance, dict):
        raise BrokerObservationError(
            f"event {event.get('event_id', '<unknown>')} has invalid provenance"
        )
    return provenance


@dataclass(frozen=True)
class BrokerObservation:
    """One validated broker lifecycle observation."""

    event_id: str
    event_hash: str
    account_id: str
    venue: str
    received_at_utc: str
    record_type: str
    external_identity: Optional[str]
    related_order_id: Optional[str]
    occurred_at_utc: str
    symbol: str
    side: str
    status: str
    semantics: Dict[str, Any]
    semantic_sha256: str
    source_exchange_id: Optional[str]
    market_type: Optional[str]
    environment: str
    context: str
    unresolved_reason: Optional[str]
    source_document_sha256: Optional[str]
    source_row_number: Optional[int]

    @property
    def account_scope_state(self) -> str:
        return ACCOUNT_SCOPE_STATE_UNVERIFIED

    @property
    def account_scope_reason(self) -> str:
        return ACCOUNT_SCOPE_REASON_NOT_PROVIDED

    @property
    def claim_key(self) -> Optional[Tuple[str, ...]]:
        """Declared-scope claim identity used only for duplicate-claim counters.

        It is deliberately not an economic identity: the account scope is
        unverified, so two observations sharing this key are never merged.
        Environment/context metadata is excluded.
        """

        if self.unresolved_reason is not None or self.external_identity is None:
            return None
        return (
            self.account_id,
            self.venue,
            self.source_exchange_id or "UNKNOWN_SOURCE",
            self.market_type or "UNKNOWN_MARKET",
            self.record_type,
            self.external_identity,
        )

    def lineage_ref(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_hash": self.event_hash,
            "occurred_at_utc": self.occurred_at_utc,
            "received_at_utc": self.received_at_utc,
            "semantic_sha256": self.semantic_sha256,
            "source_document_sha256": self.source_document_sha256,
            "source_row_number": self.source_row_number,
        }


def _observation_from_event(event: Dict[str, Any]) -> Optional[BrokerObservation]:
    payload = _load_payload(event)
    if not isinstance(payload, dict):
        return None
    body = payload.get("broker_lifecycle")
    if body is None:
        return None
    if not isinstance(body, dict):
        raise BrokerObservationError("broker_lifecycle payload must be an object")
    if "account_event" in payload:
        raise BrokerObservationError("conflicting lifecycle payload contracts")

    record_type = str(body.get("record_type") or "").strip().lower()
    if record_type not in RECORD_TYPES:
        raise BrokerObservationError(f"unsupported broker record_type: {body.get('record_type')}")
    event_type = str(event.get("event_type") or "").strip()
    if event_type not in _BROKER_LIFECYCLE_EVENT_TYPES[record_type]:
        raise BrokerObservationError(
            f"broker_lifecycle {record_type} is not valid for {event_type or 'unknown'} events"
        )

    venue = _require_text(body, "venue")
    event_venue = str(event.get("venue") or "").strip()
    if venue.upper() != event_venue.upper():
        raise BrokerObservationError("broker_lifecycle venue disagrees with the event venue")
    for field in _REQUIRED_TEXT_FIELDS:
        _require_text(body, field)

    occurred_at = _require_text(body, "occurred_at")
    symbol = _require_text(body, "symbol")
    side = _require_text(body, "side")
    status = _require_text(body, "status")

    if record_type == "fill":
        external_identity = _require_text(body, "external_fill_id")
        related_order_id = _optional_text(body.get("external_order_id"))
        filled_qty = _canonical_decimal(body.get("filled_qty"), "filled_qty")
        if filled_qty is None:
            raise BrokerObservationError("broker_lifecycle payload requires filled_qty")
        price = _canonical_decimal(body.get("price"), "price")
        if price is None:
            raise BrokerObservationError("broker_lifecycle payload requires price")
        order_qty = None
        avg_price = _canonical_decimal(body.get("avg_price"), "avg_price")
    else:
        external_identity = _require_text(body, "external_order_id")
        related_order_id = None
        order_qty = _canonical_decimal(body.get("order_qty"), "order_qty")
        if order_qty is None:
            raise BrokerObservationError("broker_lifecycle payload requires order_qty")
        filled_qty = _canonical_decimal(body.get("filled_qty"), "filled_qty")
        price = _canonical_decimal(body.get("price"), "price")
        avg_price = _canonical_decimal(body.get("avg_price"), "avg_price")

    semantics = {
        "symbol": symbol,
        "side": side,
        "status": status,
    }
    for field, value in (
        ("order_qty", order_qty),
        ("filled_qty", filled_qty),
        ("price", price),
        ("avg_price", avg_price),
        ("fee", _canonical_decimal(body.get("fee"), "fee")),
        ("fee_currency", _optional_text(body.get("fee_currency"))),
    ):
        if value is not None:
            semantics[field] = value

    account_id = str(event.get("account_id") or "").strip()
    if not account_id:
        raise BrokerObservationError("broker observation requires an account scope")

    provenance = _load_provenance(event)
    source_exchange_id = _optional_text(provenance.get("source_exchange_id"))
    source_exchange_id = source_exchange_id.lower() if source_exchange_id else None
    market_type = _optional_text(provenance.get("market_type"))
    market_type = market_type.lower() if market_type else None
    unresolved_reason = None
    if source_exchange_id is None or market_type is None:
        unresolved_reason = "MISSING_SOURCE_SCOPE"

    scope = validate_account_scope("UNKNOWN", "UNKNOWN", "UNKNOWN")
    source_row_number = provenance.get("source_row_number")
    if isinstance(source_row_number, bool) or not isinstance(source_row_number, int):
        source_row_number = None

    return BrokerObservation(
        event_id=str(event.get("event_id") or ""),
        event_hash=str(event.get("event_hash") or ""),
        account_id=account_id,
        venue=venue,
        received_at_utc=str(event.get("received_at_utc") or ""),
        record_type=record_type,
        external_identity=external_identity,
        related_order_id=related_order_id,
        occurred_at_utc=occurred_at,
        symbol=symbol,
        side=side,
        status=status,
        semantics=semantics,
        semantic_sha256=_sha256_text(_canonical_json(semantics)),
        source_exchange_id=source_exchange_id,
        market_type=market_type,
        environment=scope["environment"],
        context=scope["context"],
        unresolved_reason=unresolved_reason,
        source_document_sha256=_optional_text(provenance.get("source_file_sha256")),
        source_row_number=source_row_number,
    )


def _sort_key(observation: BrokerObservation) -> Tuple[str, str, str]:
    return (observation.occurred_at_utc, observation.received_at_utc, observation.event_id)


def _observation_record(observation: BrokerObservation) -> Dict[str, Any]:
    return {
        "account_id": observation.account_id,
        "account_scope_state": observation.account_scope_state,
        "account_scope_reason": observation.account_scope_reason,
        "account_environment": observation.environment,
        "account_context": observation.context,
        "venue": observation.venue,
        "source_exchange_id": observation.source_exchange_id or "UNKNOWN_SOURCE",
        "market_type": observation.market_type or "UNKNOWN_MARKET",
        "record_type": observation.record_type,
        "external_identity": observation.external_identity,
        "related_order_id": observation.related_order_id,
        "symbol": observation.symbol,
        "side": observation.side,
        "status": observation.status,
        "occurred_at_utc": observation.occurred_at_utc,
        "semantics": observation.semantics,
        "semantics_sha256": observation.semantic_sha256,
        "source_event_id": observation.event_id,
        "source_event_hash": observation.event_hash,
        "received_at_utc": observation.received_at_utc,
        "lineage": [observation.lineage_ref()],
    }


def build_broker_observation_snapshot(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the deterministic, account-scope-explicit observation snapshot.

    The same evidence set produces the same records, counters and
    ``snapshot_sha256`` regardless of the input iteration order.  Operational
    values such as the rebuild timestamp are deliberately out of scope.
    """

    observations: List[BrokerObservation] = []
    for event in events:
        observation = _observation_from_event(event)
        if observation is not None:
            observations.append(observation)

    projected: List[BrokerObservation] = []
    unresolved: List[BrokerObservation] = []
    for observation in observations:
        if observation.unresolved_reason is not None:
            unresolved.append(observation)
        else:
            projected.append(observation)

    claim_groups: Dict[Tuple[str, ...], List[BrokerObservation]] = {}
    for observation in projected:
        key = observation.claim_key
        assert key is not None  # source scope is resolved for projected rows
        claim_groups.setdefault(key, []).append(observation)

    duplicate_claim_count = sum(len(group) - 1 for group in claim_groups.values())
    duplicate_identity_count = sum(1 for group in claim_groups.values() if len(group) > 1)

    records = [_observation_record(observation) for observation in sorted(projected, key=_sort_key)]

    unresolved_reasons: Dict[str, int] = {}
    for observation in unresolved:
        reason = observation.unresolved_reason or "UNKNOWN"
        unresolved_reasons[reason] = unresolved_reasons.get(reason, 0) + 1

    counters = {
        "accepted_observation_count": len(observations),
        "verified_account_scope_observation_count": 0,
        "unverified_account_scope_observation_count": len(projected),
        "unresolved_source_scope_observation_count": len(unresolved),
        "unverified_duplicate_claim_count": duplicate_claim_count,
        "unverified_duplicate_identity_count": duplicate_identity_count,
        "unresolved_reasons": unresolved_reasons,
    }
    if counters["accepted_observation_count"] != (
        counters["verified_account_scope_observation_count"]
        + counters["unverified_account_scope_observation_count"]
        + counters["unresolved_source_scope_observation_count"]
    ):
        raise BrokerObservationError("broker observation counters are inconsistent")

    unresolved_refs = [
        {
            "event_id": observation.event_id,
            "event_hash": observation.event_hash,
            "account_id": observation.account_id,
            "venue": observation.venue,
            "record_type": observation.record_type,
            "external_identity": observation.external_identity,
            "reason": observation.unresolved_reason,
        }
        for observation in sorted(unresolved, key=lambda item: item.event_id)
    ]

    snapshot_sha256 = _sha256_text(_canonical_json({
        "projection_id": PROJECTION_ID,
        "records": records,
        "unresolved": unresolved_refs,
        "counters": counters,
    }))

    return {
        "projection_id": PROJECTION_ID,
        "records": records,
        "unresolved": unresolved_refs,
        "counters": counters,
        "snapshot_sha256": snapshot_sha256,
    }
