"""Canonical append-only evidence ledger repository.

The repository is deliberately independent from the journal CRUD and from the
DuckDB projection.  It records facts; later work packages may project those
facts into analytics, replay, or execution views.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional, Tuple

from app.core.paths import get_sqlite_path
from app.db.evidence_schema import EVENT_TYPES, initialize_evidence_schema


GENESIS_HASH = "0" * 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "api_secret",
    "apisecret",
    "secret",
    "password",
    "passphrase",
    "private_key",
    "privatekey",
    "authorization",
    "access_token",
    "accesstoken",
    "refresh_token",
    "refreshtoken",
    "client_secret",
    "clientsecret",
    "credential",
    "credentials",
}


class EvidenceLedgerError(Exception):
    """Base class for fail-closed ledger errors."""


class EvidenceValidationError(EvidenceLedgerError, ValueError):
    """An event command is invalid or contains prohibited data."""


class EvidenceIdentityConflict(EvidenceLedgerError):
    """An idempotency identity was reused with different immutable content."""


class EvidenceLedgerIntegrityError(EvidenceLedgerError):
    """Reserved for callers that choose to raise on a failed verification."""


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically and reject non-standard numeric values."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceValidationError(f"Payload is not canonical JSON: {exc}") from exc


def _decode_json_value(value: Any, field_name: str) -> Any:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EvidenceValidationError(f"{field_name} must be UTF-8 JSON") from exc
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise EvidenceValidationError(f"{field_name} must contain valid JSON") from exc
    return value


def _assert_no_secret_keys(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _SECRET_KEYS:
                raise EvidenceValidationError(
                    f"{path}.{key} is a secret-bearing field and cannot enter the ledger"
                )
            _assert_no_secret_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_secret_keys(child, f"{path}[{index}]")


def _canonical_payload(value: Any, field_name: str) -> str:
    decoded = _decode_json_value(value, field_name)
    _assert_no_secret_keys(decoded, field_name)
    return canonical_json(decoded)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _raw_payload_bytes(raw_payload: Any, normalized_payload_json: str) -> bytes:
    if raw_payload is None:
        return normalized_payload_json.encode("utf-8")
    if isinstance(raw_payload, bytes):
        return raw_payload
    if isinstance(raw_payload, str):
        try:
            decoded = json.loads(raw_payload)
        except json.JSONDecodeError:
            decoded = None
        if decoded is not None:
            _assert_no_secret_keys(decoded, "raw_payload")
        return raw_payload.encode("utf-8")
    decoded = _decode_json_value(raw_payload, "raw_payload")
    _assert_no_secret_keys(decoded, "raw_payload")
    return canonical_json(decoded).encode("utf-8")


def _utc_iso(value: Any, field_name: str) -> Tuple[str, str]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise EvidenceValidationError(f"{field_name} cannot be empty")
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise EvidenceValidationError(f"{field_name} must be ISO-8601") from exc
    else:
        raise EvidenceValidationError(f"{field_name} must be datetime or ISO-8601 text")

    if parsed.tzinfo is None:
        # Legacy journal rows are historically naive and documented as UTC.
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed_utc = parsed.astimezone(timezone.utc)
    normalized = parsed_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return normalized, parsed_utc.date().isoformat()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_identifier(value: Any, field_name: str) -> str:
    if value is None:
        raise EvidenceValidationError(f"{field_name} is required")
    text = str(value).strip()
    if not text:
        raise EvidenceValidationError(f"{field_name} cannot be empty")
    return text


def _validate_sha256(value: str, field_name: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise EvidenceValidationError(f"{field_name} must be a lowercase SHA-256 digest")


class EvidenceLedgerRepository:
    """Append-only canonical evidence ledger backed by one SQLite file."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        failure_injector: Optional[Callable[[sqlite3.Connection], None]] = None,
    ) -> None:
        self.db_path = str(db_path or get_sqlite_path())
        # This hook exists only for transaction rollback tests; production code
        # never supplies it.
        self._failure_injector = failure_injector
        self._ensure_schema()

    def _connect(self, *, write: bool = False) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=FULL" if write else "PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect(write=False)
        try:
            initialize_evidence_schema(conn)
        finally:
            conn.close()

    @staticmethod
    def _identity_where() -> str:
        return "account_id = ? AND venue = ? AND event_type = ? AND idempotency_key = ?"

    @staticmethod
    def _row_to_dict(row: sqlite3.Row, *, created: bool) -> Dict[str, Any]:
        result = dict(row)
        try:
            result["normalized_payload"] = json.loads(result["normalized_payload_json"])
            result["provenance"] = json.loads(result["provenance_json"])
        except (KeyError, json.JSONDecodeError):
            # Verifier, rather than read paths, owns the invalid-payload report.
            pass
        result["created"] = created
        return result

    @staticmethod
    def _request_fingerprint(fields: Dict[str, Any]) -> str:
        fingerprint_body = {
            "event_type": fields["event_type"],
            "account_id": fields["account_id"],
            "venue": fields["venue"],
            "occurred_at_utc": fields["occurred_at_utc"],
            "schema_version": fields["schema_version"],
            "adapter_version": fields["adapter_version"],
            "correlation_id": fields["correlation_id"],
            "causation_id": fields["causation_id"],
            "idempotency_key": fields["idempotency_key"],
            "raw_payload_sha256": fields["raw_payload_sha256"],
            "normalized_payload_json": fields["normalized_payload_json"],
            "provenance_json": fields["provenance_json"],
        }
        return _sha256_bytes(canonical_json(fingerprint_body).encode("utf-8"))

    @classmethod
    def _event_hash_body(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "account_id": row["account_id"],
            "venue": row["venue"],
            "occurred_at_utc": row["occurred_at_utc"],
            "received_at_utc": row["received_at_utc"],
            "chain_date_utc": row["chain_date_utc"],
            "chain_sequence": row["chain_sequence"],
            "schema_version": row["schema_version"],
            "adapter_version": row["adapter_version"],
            "correlation_id": row["correlation_id"],
            "causation_id": row["causation_id"],
            "idempotency_key": row["idempotency_key"],
            "request_fingerprint_sha256": row["request_fingerprint_sha256"],
            "raw_payload_sha256": row["raw_payload_sha256"],
            "normalized_payload_json": row["normalized_payload_json"],
            "provenance_json": row["provenance_json"],
            "prev_hash": row["prev_hash"],
        }

    @classmethod
    def _event_hash(cls, row: Dict[str, Any]) -> str:
        return _sha256_bytes(canonical_json(cls._event_hash_body(row)).encode("utf-8"))

    @staticmethod
    def _same_semantic_event(existing: sqlite3.Row, candidate: Dict[str, Any]) -> bool:
        # event_id and received_at are local acceptance details.  A retry may
        # arrive with a new generated id or receipt timestamp but must resolve
        # to the first canonical event instead of creating a conflict.
        compared_fields = (
            "event_type",
            "account_id",
            "venue",
            "occurred_at_utc",
            "schema_version",
            "adapter_version",
            "correlation_id",
            "causation_id",
            "idempotency_key",
            "request_fingerprint_sha256",
            "raw_payload_sha256",
            "normalized_payload_json",
            "provenance_json",
        )
        return all(existing[field] == candidate[field] for field in compared_fields)

    @classmethod
    def _build_candidate(
        cls,
        *,
        event_type: str,
        account_id: str,
        venue: str,
        idempotency_key: str,
        normalized_payload: Any,
        raw_payload: Any = None,
        occurred_at: Any = None,
        received_at: Any = None,
        schema_version: Any = "1",
        adapter_version: str = "unknown",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        provenance: Any = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        event_type = _require_identifier(event_type, "event_type")
        if event_type not in EVENT_TYPES:
            raise EvidenceValidationError(f"Unsupported evidence event type: {event_type}")
        account_id = _require_identifier(account_id, "account_id")
        venue = _require_identifier(venue, "venue")
        idempotency_key = _require_identifier(idempotency_key, "idempotency_key")
        adapter_version = _require_identifier(adapter_version, "adapter_version")
        schema_version = _require_identifier(schema_version, "schema_version")
        if not schema_version.isdigit() or int(schema_version) < 1:
            raise EvidenceValidationError("schema_version must be a positive integer")
        event_id = _require_identifier(event_id or str(uuid.uuid4()), "event_id")
        occurred_at_utc, chain_date_utc = _utc_iso(occurred_at or _now_utc(), "occurred_at")
        received_at_utc, _ = _utc_iso(received_at or _now_utc(), "received_at")
        correlation_id = _require_identifier(correlation_id or event_id, "correlation_id")
        causation_id = str(causation_id).strip() if causation_id is not None else None
        normalized_payload_json = _canonical_payload(normalized_payload, "normalized_payload")
        provenance_json = _canonical_payload(provenance or {}, "provenance")
        raw_payload_sha256 = _sha256_bytes(
            _raw_payload_bytes(raw_payload, normalized_payload_json)
        )

        candidate: Dict[str, Any] = {
            "event_id": event_id,
            "event_type": event_type,
            "account_id": account_id,
            "venue": venue,
            "occurred_at_utc": occurred_at_utc,
            "received_at_utc": received_at_utc,
            "chain_date_utc": chain_date_utc,
            "schema_version": schema_version,
            "adapter_version": adapter_version,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "idempotency_key": idempotency_key,
            "raw_payload_sha256": raw_payload_sha256,
            "normalized_payload_json": normalized_payload_json,
            "provenance_json": provenance_json,
        }
        candidate["request_fingerprint_sha256"] = cls._request_fingerprint(candidate)
        return candidate

    def _append_candidate(
        self, conn: sqlite3.Connection, candidate: Dict[str, Any]
    ) -> Tuple[sqlite3.Row, bool]:
        """Append one prepared command inside an already-open transaction."""
        event_id = candidate["event_id"]
        existing_by_id = conn.execute(
            "SELECT * FROM evidence_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        existing_by_identity = conn.execute(
            f"SELECT * FROM evidence_events WHERE {self._identity_where()}",
            (
                candidate["account_id"],
                candidate["venue"],
                candidate["event_type"],
                candidate["idempotency_key"],
            ),
        ).fetchone()
        existing = existing_by_id or existing_by_identity
        if existing is not None:
            if self._same_semantic_event(existing, candidate):
                return existing, False
            raise EvidenceIdentityConflict(
                "Event identity already exists with different immutable content"
            )

        previous = conn.execute(
            """
            SELECT chain_sequence, event_hash
            FROM evidence_events
            WHERE account_id = ? AND chain_date_utc = ?
            ORDER BY chain_sequence DESC
            LIMIT 1
            """,
            (candidate["account_id"], candidate["chain_date_utc"]),
        ).fetchone()
        candidate["chain_sequence"] = int(previous["chain_sequence"]) + 1 if previous else 1
        candidate["prev_hash"] = previous["event_hash"] if previous else GENESIS_HASH
        candidate["event_hash"] = self._event_hash(candidate)

        columns = (
            "event_id", "event_type", "account_id", "venue", "occurred_at_utc",
            "received_at_utc", "chain_date_utc", "chain_sequence", "schema_version",
            "adapter_version", "correlation_id", "causation_id", "idempotency_key",
            "request_fingerprint_sha256", "raw_payload_sha256", "normalized_payload_json",
            "provenance_json", "prev_hash", "event_hash",
        )
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO evidence_events ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(candidate[column] for column in columns),
        )
        stored = conn.execute(
            "SELECT * FROM evidence_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if stored is None:
            raise EvidenceLedgerError("Ledger insert is not readable inside its transaction")
        return stored, True

    def append_event(
        self,
        *,
        event_type: str,
        account_id: str,
        venue: str,
        idempotency_key: str,
        normalized_payload: Any,
        raw_payload: Any = None,
        occurred_at: Any = None,
        received_at: Any = None,
        schema_version: Any = "1",
        adapter_version: str = "unknown",
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        provenance: Any = None,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        candidate = self._build_candidate(
            event_type=event_type,
            account_id=account_id,
            venue=venue,
            idempotency_key=idempotency_key,
            normalized_payload=normalized_payload,
            raw_payload=raw_payload,
            occurred_at=occurred_at,
            received_at=received_at,
            schema_version=schema_version,
            adapter_version=adapter_version,
            correlation_id=correlation_id,
            causation_id=causation_id,
            provenance=provenance,
            event_id=event_id,
        )
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            stored, created = self._append_candidate(conn, candidate)
            if self._failure_injector is not None and created:
                self._failure_injector(conn)
            conn.commit()
            return self._row_to_dict(stored, created=created)
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def append_events(self, commands: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Append a bounded batch atomically while preserving per-event ordering.

        This is primarily useful for deterministic backfills and replay fixtures;
        each event still uses the same validation, identity, hash, and append-only
        path as ``append_event``.
        """
        candidates = [self._build_candidate(**command) for command in commands]
        if not candidates:
            return []
        conn = self._connect(write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            results: List[Dict[str, Any]] = []
            for candidate in candidates:
                stored, created = self._append_candidate(conn, candidate)
                results.append(self._row_to_dict(stored, created=created))
                if self._failure_injector is not None and created:
                    self._failure_injector(conn)
            conn.commit()
            return results
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect(write=False)
        try:
            row = conn.execute("SELECT * FROM evidence_events WHERE event_id = ?", (event_id,)).fetchone()
            return self._row_to_dict(row, created=False) if row else None
        finally:
            conn.close()

    def get_event_by_identity(
        self, account_id: str, venue: str, event_type: str, idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        conn = self._connect(write=False)
        try:
            row = conn.execute(
                f"SELECT * FROM evidence_events WHERE {self._identity_where()}",
                (account_id, venue, event_type, idempotency_key),
            ).fetchone()
            return self._row_to_dict(row, created=False) if row else None
        finally:
            conn.close()

    def count_events(self) -> int:
        conn = self._connect(write=False)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM evidence_events").fetchone()[0])
        finally:
            conn.close()

    def export_events(
        self,
        *,
        account_id: Optional[str] = None,
        chain_date_utc: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Yield immutable ledger rows in deterministic chain order."""

        conn = self._connect(write=False)
        try:
            query = "SELECT * FROM evidence_events WHERE 1 = 1"
            params: List[Any] = []
            if account_id is not None:
                query += " AND account_id = ?"
                params.append(account_id)
            if chain_date_utc is not None:
                query += " AND chain_date_utc = ?"
                params.append(chain_date_utc)
            query += " ORDER BY account_id ASC, chain_date_utc ASC, chain_sequence ASC"
            for row in conn.execute(query, params):
                yield self._row_to_dict(row, created=False)
        finally:
            conn.close()

    def export_jsonl(
        self,
        *,
        account_id: Optional[str] = None,
        chain_date_utc: Optional[str] = None,
    ) -> str:
        rows = list(self.export_events(account_id=account_id, chain_date_utc=chain_date_utc))
        return "\n".join(canonical_json({key: value for key, value in row.items() if key != "created"}) for row in rows)

    def verify_chain(
        self,
        *,
        account_id: Optional[str] = None,
        chain_date_utc: Optional[str] = None,
    ) -> Dict[str, Any]:
        rows = list(self.export_events(account_id=account_id, chain_date_utc=chain_date_utc))
        errors: List[str] = []
        seen_identities = set()
        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault((row["account_id"], row["chain_date_utc"]), []).append(row)
            identity = (row["account_id"], row["venue"], row["event_type"], row["idempotency_key"])
            if identity in seen_identities:
                errors.append(f"duplicate identity: {identity}")
            seen_identities.add(identity)

        for (row_account, row_date), chain_rows in grouped.items():
            expected_sequence = 1
            expected_prev_hash = GENESIS_HASH
            for row in chain_rows:
                raw_sequence = row.get("chain_sequence")
                prefix = f"{row_account}/{row_date}/{raw_sequence}"
                try:
                    sequence = int(raw_sequence)
                except (TypeError, ValueError):
                    sequence = None
                    errors.append(f"{prefix}: chain sequence is not an integer")
                if row["event_type"] not in EVENT_TYPES:
                    errors.append(f"{prefix}: unsupported event type")
                if row["chain_date_utc"] != row_date:
                    errors.append(f"{prefix}: chain date scope mismatch")
                if sequence != expected_sequence:
                    errors.append(
                        f"{prefix}: expected sequence {expected_sequence}, got {raw_sequence}"
                    )
                if sequence is not None:
                    expected_sequence = sequence + 1
                try:
                    occurred_normalized, occurred_date = _utc_iso(
                        row["occurred_at_utc"], "occurred_at_utc"
                    )
                    if occurred_normalized != row["occurred_at_utc"]:
                        errors.append(f"{prefix}: occurred_at_utc is not normalized UTC")
                    if occurred_date != row["chain_date_utc"]:
                        errors.append(f"{prefix}: occurred_at_utc/day scope mismatch")
                except EvidenceValidationError as exc:
                    errors.append(f"{prefix}: invalid occurred_at_utc ({exc})")
                try:
                    received_normalized, _ = _utc_iso(
                        row["received_at_utc"], "received_at_utc"
                    )
                    if received_normalized != row["received_at_utc"]:
                        errors.append(f"{prefix}: received_at_utc is not normalized UTC")
                except EvidenceValidationError as exc:
                    errors.append(f"{prefix}: invalid received_at_utc ({exc})")
                if row["prev_hash"] != expected_prev_hash:
                    errors.append(f"{prefix}: prev_hash mismatch")
                if not _SHA256_RE.fullmatch(row["prev_hash"] or ""):
                    errors.append(f"{prefix}: invalid prev_hash")
                for digest_field in (
                    "request_fingerprint_sha256",
                    "raw_payload_sha256",
                    "event_hash",
                ):
                    if not _SHA256_RE.fullmatch(row[digest_field] or ""):
                        errors.append(f"{prefix}: invalid {digest_field}")
                try:
                    parsed_payload = json.loads(row["normalized_payload_json"])
                    if canonical_json(parsed_payload) != row["normalized_payload_json"]:
                        errors.append(f"{prefix}: normalized payload is not canonical JSON")
                    _assert_no_secret_keys(parsed_payload, "normalized_payload")
                    parsed_provenance = json.loads(row["provenance_json"])
                    if canonical_json(parsed_provenance) != row["provenance_json"]:
                        errors.append(f"{prefix}: provenance is not canonical JSON")
                    _assert_no_secret_keys(parsed_provenance, "provenance")
                except (EvidenceValidationError, json.JSONDecodeError, TypeError) as exc:
                    errors.append(f"{prefix}: invalid JSON payload ({exc})")
                try:
                    fingerprint = self._request_fingerprint(row)
                    if fingerprint != row["request_fingerprint_sha256"]:
                        errors.append(f"{prefix}: request fingerprint mismatch")
                    event_hash = self._event_hash(row)
                    if event_hash != row["event_hash"]:
                        errors.append(f"{prefix}: event hash mismatch")
                except (KeyError, EvidenceValidationError, TypeError) as exc:
                    errors.append(f"{prefix}: hash recomputation failed ({exc})")
                expected_prev_hash = row["event_hash"]

        return {
            "valid": not errors,
            "checked_events": len(rows),
            "scopes": [f"{account}/{day}" for account, day in sorted(grouped)],
            "errors": errors,
        }

    def backfill_legacy_trades(
        self,
        *,
        dry_run: bool = True,
        account_id: str = "local-journal",
        venue: str = "legacy",
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Import immutable snapshots of legacy trades without mutating trades."""

        account_id = _require_identifier(account_id, "account_id")
        venue = _require_identifier(venue, "venue")
        conn = self._connect(write=False)
        try:
            query = "SELECT * FROM trades ORDER BY id ASC"
            params: List[Any] = []
            if limit is not None:
                if isinstance(limit, bool) or limit < 1:
                    raise EvidenceValidationError("limit must be a positive integer")
                query += " LIMIT ?"
                params.append(limit)
            try:
                source_rows = [dict(row) for row in conn.execute(query, params)]
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    source_rows = []
                else:
                    raise
        finally:
            conn.close()

        report: Dict[str, Any] = {
            "dry_run": dry_run,
            "source_count": len(source_rows),
            "would_append": 0,
            "appended": 0,
            "duplicates": 0,
            "errors": [],
        }
        for trade in source_rows:
            source_id = _require_identifier(trade.get("id"), "trade.id")
            idempotency_key = f"legacy-trade:{source_id}"
            payload = {
                "source_table": "trades",
                "source_id": source_id,
                "trade": self._redact_legacy_trade(trade),
            }
            occurred_at = trade.get("entry_time") or trade.get("created_at") or _now_utc()
            existing = self.get_event_by_identity(
                account_id, venue, "LegacyTradeImported", idempotency_key
            )
            if existing is not None:
                report["duplicates"] += 1
                continue
            report["would_append"] += 1
            if dry_run:
                continue
            try:
                result = self.append_event(
                    event_type="LegacyTradeImported",
                    account_id=account_id,
                    venue=venue,
                    idempotency_key=idempotency_key,
                    normalized_payload=payload,
                    raw_payload=payload,
                    occurred_at=occurred_at,
                    adapter_version="legacy-trades-v1",
                    correlation_id=f"legacy-trade:{source_id}",
                    provenance={"source_table": "trades", "source_id": source_id},
                )
                if result["created"]:
                    report["appended"] += 1
                else:
                    report["duplicates"] += 1
            except EvidenceLedgerError as exc:
                report["errors"].append({"source_id": source_id, "error": str(exc)})
        return report

    @staticmethod
    def _redact_legacy_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
        # Keep the source snapshot useful while ensuring accidental credential
        # columns cannot become permanent evidence payload.
        redacted: Dict[str, Any] = {}
        for key, value in trade.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _SECRET_KEYS:
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = value
        return redacted
