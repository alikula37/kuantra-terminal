"""Deterministic, bounded columnar-row contract for market event envelopes.

This is the adapter boundary before an Arrow/Parquet sink.  It performs no disk
I/O and intentionally stores decimal prices/quantities as canonical strings so
the eventual columnar schema cannot silently introduce float drift.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.db.repositories.evidence_ledger_repo import canonical_json

from .market_event_envelope import MarketEventEnvelope, validate_market_event_envelope


BATCH_SCHEMA_VERSION = "MARKET_EVENT_BATCH_V1"


class MarketEventBatchError(ValueError):
    """Raised when a batch exceeds bounds or contains an invalid envelope."""


@dataclass(frozen=True)
class MarketEventBatch:
    schema_version: str
    event_rows: tuple[dict[str, Any], ...]
    level_rows: tuple[dict[str, Any], ...]
    first_chain_sequence: int | None
    last_chain_sequence: int | None
    source_verified: bool
    batch_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_rows": [dict(row) for row in self.event_rows],
            "level_rows": [dict(row) for row in self.level_rows],
            "first_chain_sequence": self.first_chain_sequence,
            "last_chain_sequence": self.last_chain_sequence,
            "source_verified": self.source_verified,
            "batch_sha256": self.batch_sha256,
        }

    def to_jsonl(self) -> str:
        """Return deterministic event rows as newline-delimited JSON."""

        return "".join(canonical_json(row) + "\n" for row in self.event_rows)


class MarketEventBatchProjector:
    """Project verified envelope structure into bounded analytical rows."""

    def __init__(self, *, max_events: int = 10_000, max_levels: int = 500_000):
        if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
            raise ValueError("max_events must be a positive integer")
        if isinstance(max_levels, bool) or not isinstance(max_levels, int) or max_levels <= 0:
            raise ValueError("max_levels must be a positive integer")
        self.max_events = max_events
        self.max_levels = max_levels

    def project(self, envelopes: Iterable[MarketEventEnvelope]) -> MarketEventBatch:
        event_rows: list[dict[str, Any]] = []
        level_rows: list[dict[str, Any]] = []
        previous_sequence: int | None = None
        previous_hash: str | None = None
        for index, envelope in enumerate(envelopes, start=1):
            if index > self.max_events:
                raise MarketEventBatchError("event batch exceeds max_events; truncation is disabled")
            try:
                validate_market_event_envelope(envelope)
            except ValueError as exc:
                raise MarketEventBatchError(str(exc)) from exc
            if previous_sequence is not None:
                if envelope.chain_sequence != previous_sequence + 1:
                    raise MarketEventBatchError("envelope chain sequence is not contiguous")
                if envelope.prev_hash != previous_hash:
                    raise MarketEventBatchError("envelope prev_hash does not match batch predecessor")
            previous_sequence = envelope.chain_sequence
            previous_hash = envelope.event_hash

            row = self._event_row(envelope)
            event_rows.append(row)
            level_rows.extend(self._level_rows(envelope))
            if len(level_rows) > self.max_levels:
                raise MarketEventBatchError("level batch exceeds max_levels; truncation is disabled")

        return self._build(tuple(event_rows), tuple(level_rows))

    @staticmethod
    def _event_row(envelope: MarketEventEnvelope) -> dict[str, Any]:
        return {
            "schema_version": BATCH_SCHEMA_VERSION,
            "event_id": envelope.event_id,
            "event_type": envelope.event_type,
            "source_identity": envelope.source_identity,
            "symbol": envelope.symbol,
            "venue": envelope.venue,
            "feed": envelope.feed,
            "first_update_id": envelope.first_update_id,
            "final_update_id": envelope.final_update_id,
            "previous_update_id": envelope.previous_update_id,
            "chain_sequence": envelope.chain_sequence,
            "prev_hash": envelope.prev_hash,
            "payload_sha256": envelope.payload_sha256,
            "event_hash": envelope.event_hash,
            "source_verified": False,
            "normalized_payload_json": canonical_json(envelope.normalized_payload),
            "provenance_json": canonical_json(envelope.provenance),
        }

    @staticmethod
    def _level_rows(envelope: MarketEventEnvelope) -> list[dict[str, Any]]:
        payload = envelope.normalized_payload
        side_keys = (("BID", "bids" if envelope.event_type == "DEPTH_SNAPSHOT" else "b"), ("ASK", "asks" if envelope.event_type == "DEPTH_SNAPSHOT" else "a"))
        rows: list[dict[str, Any]] = []
        for side, key in side_keys:
            levels = payload.get(key, [])
            if not isinstance(levels, list):
                raise MarketEventBatchError(f"{key} payload must be an array")
            for level_index, level in enumerate(levels):
                if not isinstance(level, list) or len(level) != 2 or not all(isinstance(value, str) for value in level):
                    raise MarketEventBatchError(f"{key}[{level_index}] must contain canonical decimal strings")
                rows.append({
                    "schema_version": BATCH_SCHEMA_VERSION,
                    "event_id": envelope.event_id,
                    "event_type": envelope.event_type,
                    "symbol": envelope.symbol,
                    "venue": envelope.venue,
                    "chain_sequence": envelope.chain_sequence,
                    "final_update_id": envelope.final_update_id,
                    "side": side,
                    "level_index": level_index,
                    "price_text": level[0],
                    "quantity_text": level[1],
                    "source_verified": False,
                    "event_hash": envelope.event_hash,
                })
        return rows

    @staticmethod
    def _build(event_rows: tuple[dict[str, Any], ...], level_rows: tuple[dict[str, Any], ...]) -> MarketEventBatch:
        stable = {
            "schema_version": BATCH_SCHEMA_VERSION,
            "event_rows": list(event_rows),
            "level_rows": list(level_rows),
        }
        digest = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
        sequences = [row["chain_sequence"] for row in event_rows]
        return MarketEventBatch(
            schema_version=BATCH_SCHEMA_VERSION,
            event_rows=event_rows,
            level_rows=level_rows,
            first_chain_sequence=min(sequences) if sequences else None,
            last_chain_sequence=max(sequences) if sequences else None,
            source_verified=False,
            batch_sha256=digest,
        )


__all__ = ["BATCH_SCHEMA_VERSION", "MarketEventBatch", "MarketEventBatchError", "MarketEventBatchProjector"]
