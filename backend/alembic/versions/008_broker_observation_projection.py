"""Additive broker observation projection (A1.1).

Creates the rebuildable broker observation projection and its projection state
table.  No existing table or row is modified; the projection is rebuildable from
the append-only evidence ledger.
"""

from alembic import op

from app.db.broker_observation_schema import initialize_broker_observation_schema

revision = "008_broker_observation_projection"
down_revision = "007_trade_qty_unit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    initialize_broker_observation_schema(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Broker observation projection downgrade is destructive and unsupported")
