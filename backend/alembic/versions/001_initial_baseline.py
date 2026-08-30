"""001_initial_baseline

Revision ID: 001_initial_baseline
Revises: 
Create Date: 2026-08-30 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Trades table
    op.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            qty REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            pnl REAL,
            r_multiple REAL,
            mae REAL,
            mfe REAL,
            exit_efficiency REAL,
            status TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 2. Playbooks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbooks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            timeframe TEXT,
            target_rr REAL,
            min_discipline_score REAL DEFAULT 80.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 3. Playbook Rules table
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbook_rules (
            id TEXT PRIMARY KEY,
            playbook_id TEXT NOT NULL,
            rule_text TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            is_mandatory INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE CASCADE
        )
    """)

    # 4. Trade Rule Checks audit table
    op.execute("""
        CREATE TABLE IF NOT EXISTS trade_rule_checks (
            id TEXT PRIMARY KEY,
            trade_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            is_checked INTEGER NOT NULL DEFAULT 0,
            checked_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
            FOREIGN KEY (rule_id) REFERENCES playbook_rules(id) ON DELETE CASCADE
        )
    """)

    # 5. User Settings & Audit Log table
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trade_rule_checks")
    op.execute("DROP TABLE IF EXISTS playbook_rules")
    op.execute("DROP TABLE IF EXISTS playbooks")
    op.execute("DROP TABLE IF EXISTS user_settings")
    op.execute("DROP TABLE IF EXISTS trades")