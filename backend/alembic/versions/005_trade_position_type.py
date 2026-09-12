"""Explicit journal position kind; historical trades remain UNKNOWN."""

from alembic import op

revision = "005_trade_position_type"
down_revision = "004_trade_quote_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {row[1] for row in op.get_bind().exec_driver_sql("PRAGMA table_info(trades)")}
    if "position_type" not in columns:
        op.execute("ALTER TABLE trades ADD COLUMN position_type TEXT NOT NULL DEFAULT 'UNKNOWN'")


def downgrade() -> None:
    raise RuntimeError("Position type downgrade is destructive and unsupported")
