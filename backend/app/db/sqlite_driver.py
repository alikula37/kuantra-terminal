import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.paths import get_sqlite_path
from app.db.evidence_schema import initialize_evidence_schema
from app.db.projection_schema import initialize_trade_projection_schema

logger = logging.getLogger(__name__)

class SQLiteDriver:
    """OLTP SQLite Database Driver configured with WAL mode and robust schema."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_sqlite_path()
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL', 'LONG', 'SHORT')),
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    qty REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT,
                    status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED', 'CANCELED')),
                    pnl REAL DEFAULT 0.0,
                    r_multiple REAL,
                    commission REAL DEFAULT 0.0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color TEXT DEFAULT '#38bdf8'
                );

                CREATE TABLE IF NOT EXISTS trade_tags (
                    trade_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (trade_id, tag_id),
                    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_candles_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS exchange_credentials (
                    exchange_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    api_key_encrypted TEXT NOT NULL,
                    api_secret_encrypted TEXT NOT NULL,
                    passphrase_encrypted TEXT,
                    is_testnet INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- Secret values live in the OS credential manager. This table contains
                -- only stable keychain account references and non-secret metadata.
                CREATE TABLE IF NOT EXISTS exchange_credential_refs (
                    exchange_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    api_key_ref TEXT NOT NULL,
                    api_secret_ref TEXT NOT NULL,
                    passphrase_ref TEXT,
                    permission_scope TEXT NOT NULL DEFAULT 'READ_ONLY',
                    is_testnet INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
                CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_candles_sym_tf_time ON market_candles_cache(symbol, timeframe, timestamp);
                CREATE INDEX IF NOT EXISTS idx_candles_lookup ON market_candles_cache(symbol, timeframe, timestamp ASC);
            """)
            # The keychain reference table predates the read-only broker sync
            # boundary.  Keep the migration additive so existing desktop
            # databases become explicitly read-only without touching secrets.
            credential_columns = {
                row["name"] for row in cursor.execute(
                    "PRAGMA table_info(exchange_credential_refs)"
                ).fetchall()
            }
            if "permission_scope" not in credential_columns:
                cursor.execute(
                    "ALTER TABLE exchange_credential_refs "
                    "ADD COLUMN permission_scope TEXT NOT NULL DEFAULT 'READ_ONLY'"
                )
            # Use the same idempotent schema primitive as Alembic revision
            # 002 so a fresh desktop database has the ledger before any
            # explicit migration command is invoked.
            initialize_evidence_schema(conn)
            initialize_trade_projection_schema(conn)
            conn.commit()
            logger.info("SQLite OLTP schema initialized with WAL mode and candle cache.")

    _TRADE_SNAPSHOT_FIELDS = (
        "id", "symbol", "side", "entry_price", "exit_price", "qty",
        "stop_loss", "take_profit", "entry_time", "exit_time", "status", "pnl",
        "r_multiple", "commission", "notes",
    )

    @staticmethod
    def _prepare_trade(trade: Dict[str, Any], *, trade_id: Optional[str] = None,
                       now: Optional[str] = None) -> Dict[str, Any]:
        now = now or datetime.utcnow().isoformat()
        resolved_id = str(trade.get("id") or trade_id or f"TRD-{int(datetime.utcnow().timestamp()*1000)}")
        return {
            "id": resolved_id,
            "symbol": str(trade["symbol"]).upper(),
            "side": str(trade.get("side", "BUY")).upper(),
            "entry_price": float(trade["entry_price"]),
            "exit_price": float(trade["exit_price"]) if trade.get("exit_price") is not None else None,
            "qty": float(trade["qty"]),
            "stop_loss": float(trade["stop_loss"]) if trade.get("stop_loss") is not None else None,
            "take_profit": float(trade["take_profit"]) if trade.get("take_profit") is not None else None,
            "entry_time": trade.get("entry_time") or now,
            "exit_time": trade.get("exit_time"),
            "status": str(trade.get("status", "OPEN")).upper(),
            "pnl": float(trade.get("pnl", 0.0)),
            "r_multiple": float(trade["r_multiple"]) if trade.get("r_multiple") is not None else None,
            "commission": float(trade.get("commission", 0.0)),
            "notes": trade.get("notes", ""),
            "created_at": trade.get("created_at") or now,
            "updated_at": trade.get("updated_at") or now,
        }

    @classmethod
    def _upsert_trade_on_connection(cls, conn: sqlite3.Connection, trade: Dict[str, Any]) -> None:
        conn.execute("""
                INSERT INTO trades (
                    id, symbol, side, entry_price, exit_price, qty,
                    stop_loss, take_profit, entry_time, exit_time,
                    status, pnl, r_multiple, commission, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol = excluded.symbol,
                    side = excluded.side,
                    entry_price = excluded.entry_price,
                    exit_price = excluded.exit_price,
                    qty = excluded.qty,
                    stop_loss = excluded.stop_loss,
                    take_profit = excluded.take_profit,
                    entry_time = excluded.entry_time,
                    exit_time = excluded.exit_time,
                    status = excluded.status,
                    pnl = excluded.pnl,
                    r_multiple = excluded.r_multiple,
                    commission = excluded.commission,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
            """, tuple(trade[field] for field in (
                "id", "symbol", "side", "entry_price", "exit_price", "qty",
                "stop_loss", "take_profit", "entry_time", "exit_time", "status",
                "pnl", "r_multiple", "commission", "notes", "created_at", "updated_at",
            )))

    def insert_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        prepared = self._prepare_trade(trade)
        with self.get_connection() as conn:
            self._upsert_trade_on_connection(conn, prepared)
            conn.commit()
        return self.get_trade(prepared["id"])

    def record_trade_with_evidence(
        self,
        trade: Dict[str, Any],
        *,
        event_type: str,
        idempotency_key: str,
        account_id: str = "local-journal",
        venue: str = "local-journal",
        occurred_at: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        raw_payload: Any = None,
    ) -> Dict[str, Any]:
        """Persist a journal mutation and its evidence event atomically.

        The compatibility ``trades`` row is retained for existing analytics, but
        its write acknowledgement is coupled to the append-only ledger.  If the
        event is invalid, conflicting, or cannot be appended, the trade mutation
        is rolled back and the caller receives an error.
        """

        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository

        resolved_id = str(trade.get("id") or f"TRD-{int(datetime.utcnow().timestamp()*1000)}")
        ledger = EvidenceLedgerRepository(self.db_path)
        projection = EvidenceTradeProjectionRepository(self.db_path)
        conn = self.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM trades WHERE id = ?", (resolved_id,)
            ).fetchone()
            if existing is not None:
                merged = dict(existing)
                merged.update({key: value for key, value in trade.items() if key != "id"})
                merged["id"] = resolved_id
                merged["created_at"] = existing["created_at"]
                merged["updated_at"] = datetime.utcnow().isoformat()
                prepared = self._prepare_trade(
                    merged, trade_id=resolved_id, now=merged["updated_at"]
                )
            else:
                prepared = self._prepare_trade({**trade, "id": resolved_id}, trade_id=resolved_id)

            self._upsert_trade_on_connection(conn, prepared)
            stored = conn.execute(
                "SELECT * FROM trades WHERE id = ?", (resolved_id,)
            ).fetchone()
            if stored is None:
                raise RuntimeError("Trade write is not readable inside its transaction")

            snapshot = {
                field: stored[field] for field in self._TRADE_SNAPSHOT_FIELDS
            }
            event = ledger.append_event_in_transaction(
                conn,
                event_type=event_type,
                account_id=account_id,
                venue=venue,
                idempotency_key=idempotency_key,
                normalized_payload={"trade": snapshot},
                raw_payload=raw_payload if raw_payload is not None else {"trade": snapshot},
                occurred_at=occurred_at or snapshot["exit_time"] or snapshot["entry_time"],
                schema_version="1",
                adapter_version="journal-write-v1",
                correlation_id=resolved_id,
                provenance=provenance or {"source": "journal"},
            )
            # Keep the typed read model current in the same transaction as the
            # compatibility row and canonical ledger event.  A projection
            # validation/constraint error must roll back the whole journal write.
            projection.upsert_event_in_transaction(conn, event)
            conn.commit()
            return dict(stored)
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def update_trade(self, trade_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.get_trade(trade_id)
        if not existing:
            return None

        update_data["updated_at"] = datetime.utcnow().isoformat()
        fields = []
        values = []
        for k, v in update_data.items():
            if k != "id":
                fields.append(f"{k} = ?")
                values.append(v)
        values.append(trade_id)

        query = f"UPDATE trades SET {', '.join(fields)} WHERE id = ?"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
        return self.get_trade(trade_id)

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def list_trades(self, limit: int = 100, offset: int = 0, symbol: Optional[str] = None, status: Optional[str] = None, order_by_utc: bool = False) -> List[Dict[str, Any]]:
        query = "SELECT * FROM trades WHERE 1=1"
        params: List[Any] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper())
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        # Evidence sampling must not rank offset ISO timestamps lexically.
        # Preserve legacy ordering for other callers; no stored data is changed.
        query += " ORDER BY julianday(entry_time) DESC, id DESC LIMIT ? OFFSET ?" if order_by_utc else " ORDER BY entry_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_open_trades(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM trades WHERE status = 'OPEN' ORDER BY entry_time DESC")
            return [dict(row) for row in cursor.fetchall()]

    def delete_trade(self, trade_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
            conn.commit()
            return cursor.rowcount > 0

    def set_setting(self, key: str, value: Any) -> None:
        val_str = json.dumps(value) if not isinstance(value, str) else value
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, val_str, now))
            conn.commit()

    def get_setting(self, key: str) -> Optional[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row["value"]
        return None

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}


    def run_migrations(self, target_version: str = "head") -> bool:
        """Executes Alembic migrations programmatically on SQLite database."""
        try:
            import os
            from alembic.config import Config
            from alembic import command

            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ini_path = os.path.join(backend_dir, "alembic.ini")
            if os.path.exists(ini_path):
                alembic_cfg = Config(ini_path)
                alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
                alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
                command.upgrade(alembic_cfg, target_version)
                logger.info(f"SQLite Alembic migrations applied successfully to '{target_version}'.")
                return True
        except Exception as e:
            logger.warning(f"Alembic migration runner fallback: {e}")
        return False

sqlite_driver = SQLiteDriver()
