"""Canonical, hash-linked market event envelopes.

The envelope is the boundary between an in-memory market-data adapter and a
future append-only/Parquet writer.  It is intentionally storage-free in this
package: the chain proves deterministic identity and ordering without claiming
that a live feed or durable market-data recorder is already connected.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.db.repositories.evidence_ledger_repo import canonical_json

from .binance_depth_payload import NormalizedDepthSnapshot, NormalizedDepthUpdate
from .binance_depth_sequence import DepthSequenceDecision, DepthSequenceResult


GENESIS_HASH = "0" * 64
MARKET_EVENT_SCHEMA_VERSION = "MARKET_EVENT_V1"


class MarketEventEnvelopeError(ValueError):
    """Base class for invalid market event envelope commands."""


class MarketEventIdentityConflict(MarketEventEnvelopeError):
    """A source identity was reused with different normalized content."""


@dataclass(frozen=True)
class MarketEventEnvelope:
    schema_version: str
    event_type: str
    source_identity: str
    event_id: str
    symbol: str
    venue: str
    feed: str
    first_update_id: Optional[int]
    final_update_id: int
    previous_update_id: Optional[int]
    normalized_payload: Dict[str, Any]
    provenance: Dict[str, Any]
    chain_sequence: int
    prev_hash: str
    payload_sha256: str
    event_hash: str

    def stable_payload(self) -> Dict[str, Any]:
        """Return the content-addressed portion, excluding chain position."""

        return {
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "source_identity": self.source_identity,
            "event_id": self.event_id,
            "symbol": self.symbol,
            "venue": self.venue,
            "feed": self.feed,
            "first_update_id": self.first_update_id,
            "final_update_id": self.final_update_id,
            "previous_update_id": self.previous_update_id,
            "normalized_payload": self.normalized_payload,
            "provenance": self.provenance,
            "payload_sha256": self.payload_sha256,
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            **self.stable_payload(),
            "chain_sequence": self.chain_sequence,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
        }


class MarketEventChain:
    """In-memory append-only chain for normalized Binance depth observations."""

    def __init__(self, *, venue: str = "BINANCE"):
        normalized_venue = str(venue).strip().upper()
        if not normalized_venue:
            raise ValueError("venue must be non-empty")
        self.venue = normalized_venue
        self._events: list[MarketEventEnvelope] = []
        self._by_source_identity: dict[str, MarketEventEnvelope] = {}

    @property
    def events(self) -> tuple[MarketEventEnvelope, ...]:
        return tuple(self._events)

    @property
    def head_hash(self) -> str:
        return self._events[-1].event_hash if self._events else GENESIS_HASH

    def append_snapshot(self, snapshot: NormalizedDepthSnapshot) -> MarketEventEnvelope:
        source_identity = f"{self.venue}:{snapshot.symbol}:DEPTH_SNAPSHOT:{snapshot.last_update_id}"
        return self._append(
            event_type="DEPTH_SNAPSHOT",
            source_identity=source_identity,
            symbol=snapshot.symbol,
            feed="BINANCE_REST_DEPTH_SNAPSHOT",
            first_update_id=None,
            final_update_id=snapshot.last_update_id,
            previous_update_id=None,
            normalized_payload=snapshot.as_dict(),
            provenance={
                "source": "BINANCE_REST_DEPTH_SNAPSHOT",
                "venue": self.venue,
                "source_verified": False,
                "sequence_decision": "SNAPSHOT_ACCEPTED",
            },
        )

    def append_update(
        self,
        update: NormalizedDepthUpdate,
        sequence: DepthSequenceResult,
    ) -> MarketEventEnvelope:
        """Append only a sequence-approved update; gaps are never canonicalized."""

        if sequence.decision is not DepthSequenceDecision.APPLIED:
            raise MarketEventEnvelopeError("only APPLIED sequence decisions may enter the canonical chain")
        if sequence.event_final_update_id != update.final_update_id:
            raise MarketEventEnvelopeError("sequence decision does not match normalized update")
        source_identity = (
            f"{self.venue}:{update.symbol}:DEPTH_UPDATE:"
            f"{update.first_update_id}:{update.final_update_id}:{update.previous_update_id}"
        )
        return self._append(
            event_type="DEPTH_UPDATE",
            source_identity=source_identity,
            symbol=update.symbol,
            feed="BINANCE_WS_DEPTH",
            first_update_id=update.first_update_id,
            final_update_id=update.final_update_id,
            previous_update_id=update.previous_update_id,
            normalized_payload=update.as_dict(),
            provenance={
                "source": "BINANCE_WS_DEPTH",
                "venue": self.venue,
                "source_verified": False,
                "sequence_decision": sequence.decision.value,
                "sequence_reason_code": sequence.reason_code,
            },
        )

    def verify(self) -> Dict[str, Any]:
        """Recompute the in-memory chain without mutating it."""

        errors: list[str] = []
        expected_sequence = 1
        expected_previous = GENESIS_HASH
        for event in self._events:
            try:
                validate_market_event_envelope(event)
            except MarketEventEnvelopeError as exc:
                errors.append(f"envelope validation failed at {event.event_id}: {exc}")
            if event.chain_sequence != expected_sequence:
                errors.append(f"chain_sequence mismatch at {event.event_id}")
            if event.prev_hash != expected_previous:
                errors.append(f"prev_hash mismatch at {event.event_id}")
            expected_payload_hash = _payload_hash(event.normalized_payload)
            if event.payload_sha256 != expected_payload_hash:
                errors.append(f"payload_sha256 mismatch at {event.event_id}")
            expected_event_hash = _event_hash(event)
            if event.event_hash != expected_event_hash:
                errors.append(f"event_hash mismatch at {event.event_id}")
            expected_sequence += 1
            expected_previous = event.event_hash
        return {
            "valid": not errors,
            "event_count": len(self._events),
            "head_hash": self.head_hash,
            "errors": errors,
        }

    def _append(
        self,
        *,
        event_type: str,
        source_identity: str,
        symbol: str,
        feed: str,
        first_update_id: Optional[int],
        final_update_id: int,
        previous_update_id: Optional[int],
        normalized_payload: Dict[str, Any],
        provenance: Dict[str, Any],
    ) -> MarketEventEnvelope:
        payload_sha256 = _payload_hash(normalized_payload)
        event_id = f"{source_identity}:{payload_sha256[:16]}"
        existing = self._by_source_identity.get(source_identity)
        if existing is not None:
            if existing.payload_sha256 == payload_sha256:
                return existing
            raise MarketEventIdentityConflict(
                f"source identity {source_identity} was reused with different content"
            )

        chain_sequence = len(self._events) + 1
        draft = MarketEventEnvelope(
            schema_version=MARKET_EVENT_SCHEMA_VERSION,
            event_type=event_type,
            source_identity=source_identity,
            event_id=event_id,
            symbol=symbol,
            venue=self.venue,
            feed=feed,
            first_update_id=first_update_id,
            final_update_id=final_update_id,
            previous_update_id=previous_update_id,
            normalized_payload=normalized_payload,
            provenance=provenance,
            chain_sequence=chain_sequence,
            prev_hash=self.head_hash,
            payload_sha256=payload_sha256,
            event_hash="0" * 64,
        )
        envelope = MarketEventEnvelope(**{**draft.__dict__, "event_hash": _event_hash(draft)})
        self._events.append(envelope)
        self._by_source_identity[source_identity] = envelope
        return envelope


def envelope_from_dict(payload: Any) -> MarketEventEnvelope:
    """Decode and validate one persisted JSON envelope without repairing it."""

    if not isinstance(payload, dict):
        raise MarketEventEnvelopeError("envelope must be an object")
    required = {
        "schema_version",
        "event_type",
        "source_identity",
        "event_id",
        "symbol",
        "venue",
        "feed",
        "first_update_id",
        "final_update_id",
        "previous_update_id",
        "normalized_payload",
        "provenance",
        "chain_sequence",
        "prev_hash",
        "payload_sha256",
        "event_hash",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise MarketEventEnvelopeError(f"envelope is missing fields: {', '.join(missing)}")
    try:
        envelope = MarketEventEnvelope(
            schema_version=payload["schema_version"],
            event_type=payload["event_type"],
            source_identity=payload["source_identity"],
            event_id=payload["event_id"],
            symbol=payload["symbol"],
            venue=payload["venue"],
            feed=payload["feed"],
            first_update_id=payload["first_update_id"],
            final_update_id=payload["final_update_id"],
            previous_update_id=payload["previous_update_id"],
            normalized_payload=payload["normalized_payload"],
            provenance=payload["provenance"],
            chain_sequence=payload["chain_sequence"],
            prev_hash=payload["prev_hash"],
            payload_sha256=payload["payload_sha256"],
            event_hash=payload["event_hash"],
        )
    except (KeyError, TypeError) as exc:
        raise MarketEventEnvelopeError("envelope fields have invalid types") from exc
    validate_market_event_envelope(envelope)
    return envelope


def validate_market_event_envelope(envelope: MarketEventEnvelope) -> None:
    """Validate content and hashes of one envelope without changing it."""

    if not isinstance(envelope, MarketEventEnvelope):
        raise MarketEventEnvelopeError("value is not a MarketEventEnvelope")
    if envelope.schema_version != MARKET_EVENT_SCHEMA_VERSION:
        raise MarketEventEnvelopeError("unsupported market event schema version")
    for field_name in ("event_type", "source_identity", "event_id", "symbol", "venue", "feed", "prev_hash", "payload_sha256", "event_hash"):
        if not isinstance(getattr(envelope, field_name), str) or not getattr(envelope, field_name):
            raise MarketEventEnvelopeError(f"{field_name} must be a non-empty string")
    for field_name in ("chain_sequence", "final_update_id"):
        value = getattr(envelope, field_name)
        if isinstance(value, bool) or not isinstance(value, int) or value < (1 if field_name == "chain_sequence" else 0):
            raise MarketEventEnvelopeError(f"{field_name} must be a non-negative integer")
    for field_name in ("first_update_id", "previous_update_id"):
        value = getattr(envelope, field_name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise MarketEventEnvelopeError(f"{field_name} must be null or a non-negative integer")
    if not isinstance(envelope.normalized_payload, dict) or not isinstance(envelope.provenance, dict):
        raise MarketEventEnvelopeError("normalized_payload and provenance must be objects")
    for field_name in ("prev_hash", "payload_sha256", "event_hash"):
        value = getattr(envelope, field_name)
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise MarketEventEnvelopeError(f"{field_name} must be a lowercase SHA-256 digest")
    expected_payload = _payload_hash(envelope.normalized_payload)
    if envelope.payload_sha256 != expected_payload:
        raise MarketEventEnvelopeError("payload_sha256 does not match normalized_payload")
    expected_event = _event_hash(envelope)
    if envelope.event_hash != expected_event:
        raise MarketEventEnvelopeError("event_hash does not match envelope content")


def _payload_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _event_hash(event: MarketEventEnvelope) -> str:
    body = {
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "source_identity": event.source_identity,
        "event_id": event.event_id,
        "symbol": event.symbol,
        "venue": event.venue,
        "feed": event.feed,
        "first_update_id": event.first_update_id,
        "final_update_id": event.final_update_id,
        "previous_update_id": event.previous_update_id,
        "normalized_payload": event.normalized_payload,
        "provenance": event.provenance,
        "chain_sequence": event.chain_sequence,
        "prev_hash": event.prev_hash,
        "payload_sha256": event.payload_sha256,
    }
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


__all__ = [
    "GENESIS_HASH",
    "MARKET_EVENT_SCHEMA_VERSION",
    "MarketEventChain",
    "MarketEventEnvelope",
    "MarketEventEnvelopeError",
    "MarketEventIdentityConflict",
    "envelope_from_dict",
    "validate_market_event_envelope",
]
