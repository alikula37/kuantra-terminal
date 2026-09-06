"""SQLite schema primitives for the canonical evidence ledger.

This module deliberately has no dependency on the SQLite driver.  The runtime
bootstrap and the Alembic revision both call the same schema initializer so a
new desktop database and an upgraded database cannot silently drift apart.
"""

from typing import Any, Iterable


EVENT_TYPES = (
    "IntentRecorded",
    "RiskEvaluated",
    "OrderSubmitRequested",
    "VenueAck",
    "VenueReject",
    "FillRecorded",
    "CancelRequested",
    "CancelAck",
    "CancelReject",
    "FeeAdjusted",
    "TradeCorrected",
    "PositionProjectionUpdated",
    "JournalReviewAdded",
    "LegacyTradeImported",
)

_EVENT_TYPE_SQL = ", ".join(f"'{event_type}'" for event_type in EVENT_TYPES)

EVIDENCE_SCHEMA_STATEMENTS = (
    f"""
    CREATE TABLE IF NOT EXISTS evidence_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL CHECK (event_type IN ({_EVENT_TYPE_SQL})),
        account_id TEXT NOT NULL,
        venue TEXT NOT NULL,
        occurred_at_utc TEXT NOT NULL,
        received_at_utc TEXT NOT NULL,
        chain_date_utc TEXT NOT NULL,
        chain_sequence INTEGER NOT NULL CHECK (chain_sequence > 0),
        schema_version TEXT NOT NULL,
        adapter_version TEXT NOT NULL,
        correlation_id TEXT NOT NULL,
        causation_id TEXT,
        idempotency_key TEXT NOT NULL,
        request_fingerprint_sha256 TEXT NOT NULL,
        raw_payload_sha256 TEXT NOT NULL,
        normalized_payload_json TEXT NOT NULL,
        provenance_json TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_events_identity
    ON evidence_events(account_id, venue, event_type, idempotency_key)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_events_chain_sequence
    ON evidence_events(account_id, chain_date_utc, chain_sequence)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_events_chain_hash
    ON evidence_events(account_id, chain_date_utc, event_hash)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_events_chain_lookup
    ON evidence_events(account_id, chain_date_utc, chain_sequence)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_events_export
    ON evidence_events(account_id, occurred_at_utc, chain_sequence)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_events_correlation
    ON evidence_events(correlation_id)
    """,
    """
    CREATE TRIGGER IF NOT EXISTS evidence_events_no_update
    BEFORE UPDATE ON evidence_events
    BEGIN
        SELECT RAISE(ABORT, 'evidence_events is append-only');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS evidence_events_no_delete
    BEFORE DELETE ON evidence_events
    BEGIN
        SELECT RAISE(ABORT, 'evidence_events is append-only');
    END
    """,
)


def initialize_evidence_schema(connection: Any) -> None:
    """Create the ledger schema and append-only guards idempotently.

    ``sqlite3.Connection`` exposes ``executescript`` while the Alembic bind
    exposes ``exec_driver_sql``.  Supporting both keeps this module the single
    schema authority without coupling application code to SQLAlchemy.
    """

    executescript = getattr(connection, "executescript", None)
    if callable(executescript):
        executescript(";\n".join(EVIDENCE_SCHEMA_STATEMENTS) + ";")
        return

    exec_driver_sql = getattr(connection, "exec_driver_sql", None)
    if callable(exec_driver_sql):
        for statement in EVIDENCE_SCHEMA_STATEMENTS:
            exec_driver_sql(statement)
        return

    execute = getattr(connection, "execute", None)
    if callable(execute):
        for statement in EVIDENCE_SCHEMA_STATEMENTS:
            execute(statement)
        return

    raise TypeError("Connection must provide executescript, exec_driver_sql, or execute")


def iter_schema_statements() -> Iterable[str]:
    """Expose a read-only iterator for migration and schema inspection tests."""

    return iter(EVIDENCE_SCHEMA_STATEMENTS)
