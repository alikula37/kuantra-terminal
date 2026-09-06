"""SQLite schema primitives for rebuildable trade projections.

The projection is intentionally mutable and disposable.  The evidence ledger
remains the source of record; this table is only a typed read model rebuilt from
validated ledger events.
"""

from typing import Any, Iterable


PROJECTION_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS evidence_trade_projections (
        account_id TEXT NOT NULL,
        venue TEXT NOT NULL,
        trade_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        qty REAL NOT NULL,
        stop_loss REAL,
        take_profit REAL,
        entry_time TEXT NOT NULL,
        exit_time TEXT,
        status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED', 'CANCELED')),
        pnl REAL NOT NULL,
        r_multiple REAL,
        commission REAL NOT NULL,
        notes TEXT NOT NULL,
        source_event_id TEXT NOT NULL,
        source_event_type TEXT NOT NULL,
        source_event_hash TEXT NOT NULL,
        occurred_at_utc TEXT NOT NULL,
        received_at_utc TEXT NOT NULL,
        is_tombstone INTEGER NOT NULL CHECK(is_tombstone IN (0, 1)),
        snapshot_json TEXT NOT NULL,
        projected_at_utc TEXT NOT NULL,
        PRIMARY KEY (account_id, venue, trade_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_trade_projections_status
    ON evidence_trade_projections(account_id, status, entry_time)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_evidence_trade_projections_event
    ON evidence_trade_projections(source_event_id)
    """,
)


def initialize_trade_projection_schema(connection: Any) -> None:
    """Create the rebuildable projection schema for SQLite or Alembic binds."""

    executescript = getattr(connection, "executescript", None)
    if callable(executescript):
        executescript(";\n".join(PROJECTION_SCHEMA_STATEMENTS) + ";")
        return

    exec_driver_sql = getattr(connection, "exec_driver_sql", None)
    if callable(exec_driver_sql):
        for statement in PROJECTION_SCHEMA_STATEMENTS:
            exec_driver_sql(statement)
        return

    execute = getattr(connection, "execute", None)
    if callable(execute):
        for statement in PROJECTION_SCHEMA_STATEMENTS:
            execute(statement)
        return

    raise TypeError("Connection must provide executescript, exec_driver_sql, or execute")


def iter_projection_schema_statements() -> Iterable[str]:
    return iter(PROJECTION_SCHEMA_STATEMENTS)
