"""004_trade_quote_provenance

Additive journal metadata for external trade records and free quote provenance.
Existing rows remain explicitly unknown; no historical source or price status is
inferred during this migration.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "004_trade_quote_provenance"
down_revision: Union[str, None] = "003_trade_projection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        row[1]
        for row in bind.exec_driver_sql("PRAGMA table_info(trades)").fetchall()
    }
    columns = {
        "record_mode": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
        "execution_venue": "TEXT",
        "price_source": "TEXT NOT NULL DEFAULT 'unknown'",
        "price_source_symbol": "TEXT",
        "price_status": "TEXT NOT NULL DEFAULT 'UNAVAILABLE'",
        "price_observed_at": "TEXT",
        "price_origin": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
    }
    for name, definition in columns.items():
        if name not in existing:
            op.execute(f"ALTER TABLE trades ADD COLUMN {name} {definition}")


def downgrade() -> None:
    raise RuntimeError("Trade quote provenance downgrade is destructive and unsupported")
