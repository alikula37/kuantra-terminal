"""SQLite schema primitives for the rebuildable broker observation projection.

The projection is mutable and disposable; the evidence ledger remains the source
of record.  Nothing in this table creates a journal trade or portfolio PnL.
Rows carry an explicit ``account_scope_state``: while the source account scope
is unverified (no producer supplies a persistent account namespace), each
observation is stored individually and is never economically merged with
another observation.  The schema is additive (revision ``008``) and behaves
like the existing trade projection: ``CREATE TABLE IF NOT EXISTS`` on both
SQLite and Alembic binds.
"""

from typing import Any, Iterable

BROKER_OBSERVATION_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS broker_observation_log (
        account_id TEXT NOT NULL,
        account_scope_state TEXT NOT NULL DEFAULT 'UNVERIFIED'
            CHECK(account_scope_state IN ('UNVERIFIED', 'VERIFIED')),
        account_scope_reason TEXT NOT NULL,
        account_environment TEXT NOT NULL DEFAULT 'UNKNOWN'
            CHECK(account_environment IN ('UNKNOWN', 'DEMO', 'LIVE')),
        account_context TEXT NOT NULL DEFAULT 'UNKNOWN'
            CHECK(account_context IN ('UNKNOWN', 'PERSONAL', 'PROP')),
        venue TEXT NOT NULL,
        source_exchange_id TEXT NOT NULL,
        market_type TEXT NOT NULL,
        record_type TEXT NOT NULL CHECK(record_type IN ('order', 'fill')),
        external_identity TEXT NOT NULL,
        related_order_id TEXT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        status TEXT NOT NULL,
        occurred_at_utc TEXT NOT NULL,
        semantics_json TEXT NOT NULL,
        semantics_sha256 TEXT NOT NULL,
        source_event_id TEXT NOT NULL,
        source_event_hash TEXT NOT NULL,
        received_at_utc TEXT NOT NULL,
        lineage_json TEXT NOT NULL,
        projected_at_utc TEXT NOT NULL,
        PRIMARY KEY (
            account_id, source_exchange_id, market_type, record_type,
            external_identity, source_event_id
        )
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_broker_observation_log_symbol
    ON broker_observation_log(record_type, symbol, occurred_at_utc)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_broker_observation_log_event
    ON broker_observation_log(source_event_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS broker_projection_state (
        projection_id TEXT PRIMARY KEY,
        snapshot_sha256 TEXT,
        evidence_sha256 TEXT,
        scanned_event_count INTEGER,
        processed_through_event_id TEXT,
        processed_through_event_hash TEXT,
        processed_through_received_at_utc TEXT,
        counters_json TEXT,
        last_success_at_utc TEXT,
        last_attempt_at_utc TEXT NOT NULL,
        last_attempt_status TEXT NOT NULL CHECK(last_attempt_status IN ('SUCCESS', 'FAILED')),
        last_failure_reason TEXT
    )
    """,
)


def initialize_broker_observation_schema(connection: Any) -> None:
    """Create the broker observation projection schema for SQLite or Alembic binds."""

    executescript = getattr(connection, "executescript", None)
    if callable(executescript):
        executescript(";\n".join(BROKER_OBSERVATION_SCHEMA_STATEMENTS) + ";")
        return

    exec_driver_sql = getattr(connection, "exec_driver_sql", None)
    if callable(exec_driver_sql):
        for statement in BROKER_OBSERVATION_SCHEMA_STATEMENTS:
            exec_driver_sql(statement)
        return

    execute = getattr(connection, "execute", None)
    if callable(execute):
        for statement in BROKER_OBSERVATION_SCHEMA_STATEMENTS:
            execute(statement)
        return

    raise TypeError("Connection must provide executescript, exec_driver_sql, or execute")


def iter_broker_observation_schema_statements() -> Iterable[str]:
    return iter(BROKER_OBSERVATION_SCHEMA_STATEMENTS)
