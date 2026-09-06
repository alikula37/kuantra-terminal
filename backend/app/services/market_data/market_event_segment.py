"""Single-writer, fsync-backed JSONL segment for market event envelopes.

This is a deliberately small durability boundary.  It is not a Parquet
warehouse, does not coordinate multiple processes, and never truncates a
corrupt file automatically.  A future sink can consume only a segment whose
recovery report is valid.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.db.repositories.evidence_ledger_repo import canonical_json

from .market_event_envelope import (
    GENESIS_HASH,
    MarketEventEnvelope,
    MarketEventEnvelopeError,
    MarketEventIdentityConflict,
    envelope_from_dict,
    validate_market_event_envelope,
)


class MarketEventSegmentRecoveryError(MarketEventEnvelopeError):
    """A segment contains an invalid or incomplete line and cannot be trusted."""


class MarketEventSegmentWriter:
    """Append validated envelopes to one local JSONL file with fsync."""

    def __init__(self, path: str | Path, *, strict: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[MarketEventEnvelope] = []
        self._by_source_identity: dict[str, MarketEventEnvelope] = {}
        self._recovery_errors: list[str] = []
        self._load_existing()
        if strict and self._recovery_errors:
            raise MarketEventSegmentRecoveryError("; ".join(self._recovery_errors))

    @property
    def events(self) -> tuple[MarketEventEnvelope, ...]:
        return tuple(self._events)

    @property
    def head_hash(self) -> str:
        return self._events[-1].event_hash if self._events else GENESIS_HASH

    @property
    def last_sequence(self) -> int:
        return self._events[-1].chain_sequence if self._events else 0

    def append(self, envelope: MarketEventEnvelope) -> MarketEventEnvelope:
        """Append one envelope only when its chain position is exactly next."""

        if self._recovery_errors:
            raise MarketEventSegmentRecoveryError("segment recovery is invalid; no append is allowed")
        validate_market_event_envelope(envelope)
        existing = self._by_source_identity.get(envelope.source_identity)
        if existing is not None:
            if existing.payload_sha256 == envelope.payload_sha256:
                return existing
            raise MarketEventIdentityConflict(
                f"source identity {envelope.source_identity} was reused with different content"
            )
        expected_sequence = self.last_sequence + 1
        if envelope.chain_sequence != expected_sequence:
            raise MarketEventSegmentRecoveryError(
                f"expected chain_sequence {expected_sequence}, got {envelope.chain_sequence}"
            )
        if envelope.prev_hash != self.head_hash:
            raise MarketEventSegmentRecoveryError("envelope prev_hash does not match segment head")

        line = (canonical_json(envelope.as_dict()) + "\n").encode("utf-8")
        with self.path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._events.append(envelope)
        self._by_source_identity[envelope.source_identity] = envelope
        return envelope

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "path": str(self.path),
            "event_count": len(self._events),
            "last_sequence": self.last_sequence,
            "head_hash": self.head_hash,
            "errors": list(self._recovery_errors),
        }

    def _load_existing(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            self._recovery_errors.append(f"read failed: {exc}")
            return
        if not raw:
            return
        if not raw.endswith(b"\n"):
            self._recovery_errors.append("final line is incomplete; automatic truncation is disabled")
        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            try:
                decoded = json.loads(raw_line.decode("utf-8"))
                envelope = envelope_from_dict(decoded)
                self._validate_position(envelope)
                if envelope.source_identity in self._by_source_identity:
                    raise MarketEventIdentityConflict(
                        f"duplicate source identity at line {line_number}: {envelope.source_identity}"
                    )
            except (UnicodeDecodeError, json.JSONDecodeError, MarketEventEnvelopeError, OSError, TypeError) as exc:
                self._recovery_errors.append(f"line {line_number}: {exc}")
                break
            self._events.append(envelope)
            self._by_source_identity[envelope.source_identity] = envelope

    def _validate_position(self, envelope: MarketEventEnvelope) -> None:
        expected_sequence = self.last_sequence + 1
        if envelope.chain_sequence != expected_sequence:
            raise MarketEventSegmentRecoveryError(
                f"expected chain_sequence {expected_sequence}, got {envelope.chain_sequence}"
            )
        if envelope.prev_hash != self.head_hash:
            raise MarketEventSegmentRecoveryError("prev_hash does not match previous segment event")


__all__ = ["MarketEventSegmentRecoveryError", "MarketEventSegmentWriter"]
