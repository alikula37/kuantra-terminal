"""Explicit quantity-unit contract for verified base-unit math.

``qty_unit`` is additive and defaults to UNKNOWN so existing trades never gain a
unit claim they did not declare.
"""

from alembic import op

revision = "007_trade_qty_unit"
down_revision = "006_trade_time_edit_sizing"
branch_labels = None
depends_on = None

_ADDITIVE_COLUMNS = (
    ("qty_unit", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
)


def upgrade() -> None:
    columns = {row[1] for row in op.get_bind().exec_driver_sql("PRAGMA table_info(trades)")}
    for name, definition in _ADDITIVE_COLUMNS:
        if name not in columns:
            op.execute(f"ALTER TABLE trades ADD COLUMN {name} {definition}")


def downgrade() -> None:
    raise RuntimeError("Quantity-unit downgrade is destructive and unsupported")
