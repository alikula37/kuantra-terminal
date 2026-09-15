"""Journal trust fields: declared leverage, revision and time/close source.

All columns are additive and nullable/defaulted so existing trades keep their
original meaning: no leverage is invented, the first revision stays 1, and a
time/close source stays UNKNOWN until the user supplies one.
"""

from alembic import op

revision = "006_trade_time_edit_sizing"
down_revision = "005_trade_position_type"
branch_labels = None
depends_on = None

_ADDITIVE_COLUMNS = (
    ("leverage", "REAL"),
    ("revision", "INTEGER NOT NULL DEFAULT 1"),
    ("entry_time_source", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
    ("close_source", "TEXT"),
    ("tracking_started_at", "TEXT"),
)


def upgrade() -> None:
    columns = {row[1] for row in op.get_bind().exec_driver_sql("PRAGMA table_info(trades)")}
    for name, definition in _ADDITIVE_COLUMNS:
        if name not in columns:
            op.execute(f"ALTER TABLE trades ADD COLUMN {name} {definition}")


def downgrade() -> None:
    raise RuntimeError("Journal trust fields downgrade is destructive and unsupported")
