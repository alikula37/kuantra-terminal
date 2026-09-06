"""Manifest-backed rotation for durable market-event JSONL segments."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from app.db.repositories.evidence_ledger_repo import canonical_json

from .market_event_envelope import (
    GENESIS_HASH,
    MarketEventEnvelope,
    MarketEventEnvelopeError,
    MarketEventIdentityConflict,
    validate_market_event_envelope,
)
from .market_event_segment import MarketEventSegmentRecoveryError, MarketEventSegmentWriter


MANIFEST_SCHEMA_VERSION = "MARKET_SEGMENT_MANIFEST_V1"
_SEGMENT_NAME_RE = re.compile(r"^segment-[0-9]{6}\.jsonl$")


class MarketEventSegmentSetRecoveryError(MarketEventSegmentRecoveryError):
    """A manifest or one of its referenced segments is not trustworthy."""


class MarketEventSegmentSet:
    """Rotate single-writer JSONL segments while preserving one global chain."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_events_per_segment: int = 100_000,
        venue: str = "BINANCE",
        strict: bool = True,
    ):
        if isinstance(max_events_per_segment, bool) or not isinstance(max_events_per_segment, int):
            raise ValueError("max_events_per_segment must be a positive integer")
        if max_events_per_segment <= 0:
            raise ValueError("max_events_per_segment must be a positive integer")
        normalized_venue = str(venue).strip().upper()
        if not normalized_venue:
            raise ValueError("venue must be non-empty")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self.max_events_per_segment = max_events_per_segment
        self.venue = normalized_venue
        self._writers: list[MarketEventSegmentWriter] = []
        self._by_source_identity: dict[str, MarketEventEnvelope] = {}
        self._recovery_errors: list[str] = []
        self._load_manifest()
        if strict and self._recovery_errors:
            raise MarketEventSegmentSetRecoveryError("; ".join(self._recovery_errors))

    @property
    def events(self) -> tuple[MarketEventEnvelope, ...]:
        return tuple(event for writer in self._writers for event in writer.events)

    @property
    def event_count(self) -> int:
        return sum(len(writer.events) for writer in self._writers)

    @property
    def last_sequence(self) -> int:
        return self._writers[-1].last_sequence if self._writers else 0

    @property
    def head_hash(self) -> str:
        return self._writers[-1].head_hash if self._writers else GENESIS_HASH

    @property
    def segment_count(self) -> int:
        return len(self._writers)

    def append(self, envelope: MarketEventEnvelope) -> MarketEventEnvelope:
        if self._recovery_errors:
            raise MarketEventSegmentSetRecoveryError("segment-set recovery is invalid; no append is allowed")
        validate_market_event_envelope(envelope)
        if envelope.venue != self.venue:
            raise MarketEventEnvelopeError("envelope venue does not match segment-set venue")
        existing = self._by_source_identity.get(envelope.source_identity)
        if existing is not None:
            if existing.payload_sha256 == envelope.payload_sha256:
                return existing
            raise MarketEventIdentityConflict(
                f"source identity {envelope.source_identity} was reused with different content"
            )

        writer = self._current_writer()
        created = False
        if writer is None or len(writer.events) >= self.max_events_per_segment:
            base_sequence = self.last_sequence
            base_prev_hash = self.head_hash
            path = self.root / f"segment-{len(self._writers) + 1:06d}.jsonl"
            writer = MarketEventSegmentWriter(
                path,
                base_sequence=base_sequence,
                base_prev_hash=base_prev_hash,
            )
            self._writers.append(writer)
            created = True
        try:
            appended = writer.append(envelope)
        except Exception:
            if created and not writer.events:
                self._writers.pop()
            raise
        self._by_source_identity[appended.source_identity] = appended
        self._write_manifest()
        return appended

    def recovery_report(self) -> dict[str, Any]:
        return {
            "valid": not self._recovery_errors,
            "root": str(self.root),
            "manifest": str(self.manifest_path),
            "venue": self.venue,
            "event_count": self.event_count,
            "segment_count": self.segment_count,
            "last_sequence": self.last_sequence,
            "head_hash": self.head_hash,
            "errors": list(self._recovery_errors),
        }

    def _current_writer(self) -> MarketEventSegmentWriter | None:
        return self._writers[-1] if self._writers else None

    def _load_manifest(self) -> None:
        if not self.manifest_path.exists():
            orphan_segments = sorted(self.root.glob("segment-*.jsonl"))
            if orphan_segments:
                self._recovery_errors.append("segment files exist without manifest.json")
            return
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self._validate_manifest(manifest)
            previous_sequence = 0
            previous_hash = GENESIS_HASH
            for descriptor in manifest["segments"]:
                name = descriptor["file"]
                if not isinstance(name, str) or not _SEGMENT_NAME_RE.fullmatch(name):
                    raise MarketEventSegmentSetRecoveryError("manifest contains an unsafe segment filename")
                writer = MarketEventSegmentWriter(
                    self.root / name,
                    base_sequence=previous_sequence,
                    base_prev_hash=previous_hash,
                )
                report = writer.recovery_report()
                if not report["valid"]:
                    raise MarketEventSegmentSetRecoveryError("; ".join(report["errors"]))
                if not writer.events:
                    raise MarketEventSegmentSetRecoveryError(f"segment {name} is empty")
                self._validate_descriptor(descriptor, writer)
                for event in writer.events:
                    if event.venue != self.venue:
                        raise MarketEventSegmentSetRecoveryError("segment event venue mismatch")
                    if event.source_identity in self._by_source_identity:
                        raise MarketEventSegmentIdentityConflict("duplicate source identity across segments")
                    self._by_source_identity[event.source_identity] = event
                self._writers.append(writer)
                previous_sequence = writer.last_sequence
                previous_hash = writer.head_hash
            if manifest["event_count"] != self.event_count:
                raise MarketEventSegmentSetRecoveryError("manifest event_count does not match segments")
            if manifest["last_sequence"] != self.last_sequence or manifest["head_hash"] != self.head_hash:
                raise MarketEventSegmentSetRecoveryError("manifest head does not match segments")
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError, MarketEventEnvelopeError) as exc:
            self._recovery_errors.append(str(exc))

    def _validate_manifest(self, manifest: Any) -> None:
        if not isinstance(manifest, dict):
            raise MarketEventSegmentSetRecoveryError("manifest must be an object")
        required = {"schema_version", "venue", "max_events_per_segment", "segments", "event_count", "last_sequence", "head_hash", "manifest_sha256"}
        missing = required.difference(manifest)
        if missing:
            raise MarketEventSegmentSetRecoveryError(f"manifest is missing fields: {', '.join(sorted(missing))}")
        if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise MarketEventSegmentSetRecoveryError("unsupported manifest schema version")
        if manifest["venue"] != self.venue:
            raise MarketEventSegmentSetRecoveryError("manifest venue does not match requested venue")
        if manifest["max_events_per_segment"] != self.max_events_per_segment:
            raise MarketEventSegmentSetRecoveryError("max_events_per_segment differs from manifest")
        if not isinstance(manifest["segments"], list):
            raise MarketEventSegmentSetRecoveryError("manifest segments must be an array")
        stable = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        expected = hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()
        if manifest["manifest_sha256"] != expected:
            raise MarketEventSegmentSetRecoveryError("manifest_sha256 does not match manifest content")

    @staticmethod
    def _validate_descriptor(descriptor: Any, writer: MarketEventSegmentWriter) -> None:
        if not isinstance(descriptor, dict):
            raise MarketEventSegmentSetRecoveryError("segment descriptor must be an object")
        events = writer.events
        expected = {
            "file": descriptor.get("file"),
            "first_sequence": events[0].chain_sequence,
            "last_sequence": events[-1].chain_sequence,
            "event_count": len(events),
            "first_hash": events[0].event_hash,
            "last_hash": events[-1].event_hash,
        }
        for key, value in expected.items():
            if descriptor.get(key) != value:
                raise MarketEventSegmentSetRecoveryError(f"segment descriptor {key} does not match file")

    def _write_manifest(self) -> None:
        descriptors = []
        for index, writer in enumerate(self._writers, start=1):
            events = writer.events
            descriptors.append(
                {
                    "file": f"segment-{index:06d}.jsonl",
                    "first_sequence": events[0].chain_sequence,
                    "last_sequence": events[-1].chain_sequence,
                    "event_count": len(events),
                    "first_hash": events[0].event_hash,
                    "last_hash": events[-1].event_hash,
                }
            )
        stable = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "venue": self.venue,
            "max_events_per_segment": self.max_events_per_segment,
            "segments": descriptors,
            "event_count": self.event_count,
            "last_sequence": self.last_sequence,
            "head_hash": self.head_hash,
        }
        manifest = {
            **stable,
            "manifest_sha256": hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest(),
        }
        temporary = self.manifest_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(manifest) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.manifest_path)


__all__ = ["MANIFEST_SCHEMA_VERSION", "MarketEventSegmentSet", "MarketEventSegmentSetRecoveryError"]
