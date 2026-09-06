"""002_evidence_ledger

Canonical append-only evidence ledger schema.  The DDL is shared with the
runtime SQLite bootstrap so migration and fresh-install paths cannot diverge.
"""

from typing import Sequence, Union

from alembic import op

from app.db.evidence_schema import initialize_evidence_schema


revision: str = "002_evidence_ledger"
down_revision: Union[str, None] = "001_initial_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    initialize_evidence_schema(op.get_bind())


def downgrade() -> None:
    # Evidence is an audit record.  A destructive downgrade would violate the
    # ledger's append-only contract and is intentionally not supported.
    raise RuntimeError("Evidence ledger downgrade is destructive and unsupported")
