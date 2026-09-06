"""003_trade_projection

Rebuildable typed projection sourced from the append-only evidence ledger.
"""

from typing import Sequence, Union

from alembic import op

from app.db.projection_schema import initialize_trade_projection_schema


revision: str = "003_trade_projection"
down_revision: Union[str, None] = "002_evidence_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    initialize_trade_projection_schema(op.get_bind())


def downgrade() -> None:
    raise RuntimeError("Trade projection downgrade is destructive and unsupported")
