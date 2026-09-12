import sqlite3
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional, Sequence
from app.core.paths import get_sqlite_path
from app.core.position_type import normalize_position_type
from app.db.evidence_schema import initialize_evidence_schema
from app.db.projection_schema import initialize_trade_projection_schema

logger = logging.getLogger(__name__)


class SQLiteOperationCancelled(RuntimeError):
    """A cooperative write operation was cancelled before commit."""


class SQLiteOperationResourceLimit(RuntimeError):
    """A cooperative resource check rejected an operation."""


class SQLiteDriver:
    """OLTP SQLite Database Driver configured with WAL mode and robust schema."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        transaction_hook: Optional[Callable[[str, sqlite3.Connection], None]] = None,
    ):
        self.db_path = db_path or get_sqlite_path()
        # Test-only crash/failure injection. Production callers leave this unset;
        # it makes the commit/ack boundary observable without adding persistence
        # state or changing the ledger event contract.
        self._transaction_hook = transaction_hook
        self._init_db()

    def _notify_transaction_hook(self, phase: str, conn: sqlite3.Connection) -> None:
        if self._transaction_hook is not None:
            self._transaction_hook(phase, conn)

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
                    record_mode TEXT NOT NULL DEFAULT 'EXTERNAL',
                    position_type TEXT NOT NULL DEFAULT 'UNKNOWN',
                    execution_venue TEXT,
                    price_source TEXT NOT NULL DEFAULT 'unknown',
                    price_source_symbol TEXT,
                    price_status TEXT NOT NULL DEFAULT 'UNAVAILABLE',
                    price_observed_at TEXT,
                    price_origin TEXT NOT NULL DEFAULT 'UNKNOWN',
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
            self._ensure_legacy_trade_columns(cursor)
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

    @staticmethod
    def _ensure_legacy_trade_columns(cursor: sqlite3.Cursor) -> None:
        """Add only the additive compatibility columns used by current writes.

        Alembic revision 001 databases predate ``commission`` and
        ``updated_at``.  The canonical trade identity and snapshot fields are
        not inferable, so a database missing one of those fields remains
        unsupported instead of being guessed into a new schema.
        """

        columns = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(trades)").fetchall()
        }
        required = {
            "id",
            "symbol",
            "side",
            "entry_price",
            "qty",
            "entry_time",
            "status",
        }
        missing_required = sorted(required - columns)
        if missing_required:
            raise RuntimeError(
                "unsupported trades schema; missing required columns: "
                + ", ".join(missing_required)
            )

        additive_columns = {
            "exit_price": "REAL",
            "stop_loss": "REAL",
            "take_profit": "REAL",
            "exit_time": "TEXT",
            "pnl": "REAL DEFAULT 0.0",
            "r_multiple": "REAL",
            "commission": "REAL DEFAULT 0.0",
            "notes": "TEXT DEFAULT ''",
            # Existing rows predate quote provenance.  UNKNOWN/UNAVAILABLE
            # are deliberately explicit and are never backfilled as success.
            "record_mode": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "position_type": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "execution_venue": "TEXT",
            "price_source": "TEXT NOT NULL DEFAULT 'unknown'",
            "price_source_symbol": "TEXT",
            "price_status": "TEXT NOT NULL DEFAULT 'UNAVAILABLE'",
            "price_observed_at": "TEXT",
            "price_origin": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        }
        for name, definition in additive_columns.items():
            if name not in columns:
                cursor.execute(f"ALTER TABLE trades ADD COLUMN {name} {definition}")

        cursor.execute(
            "UPDATE trades SET created_at = datetime('now') "
            "WHERE created_at IS NULL OR created_at = ''"
        )
        cursor.execute(
            "UPDATE trades SET updated_at = created_at "
            "WHERE updated_at IS NULL OR updated_at = ''"
        )

    _TRADE_SNAPSHOT_FIELDS = (
        "id", "symbol", "side", "entry_price", "exit_price", "qty",
        "stop_loss", "take_profit", "entry_time", "exit_time", "status", "pnl",
        "r_multiple", "commission", "notes", "record_mode", "execution_venue",
        "price_source", "price_source_symbol", "price_status", "price_observed_at",
        "price_origin", "position_type",
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
            "record_mode": str(trade.get("record_mode", "UNKNOWN")).upper(),
            "position_type": normalize_position_type(trade.get("position_type"), trade.get("side", "BUY")),
            "execution_venue": trade.get("execution_venue"),
            "price_source": str(trade.get("price_source", "unknown")).lower(),
            "price_source_symbol": trade.get("price_source_symbol"),
            "price_status": str(trade.get("price_status", "UNAVAILABLE")).upper(),
            "price_observed_at": trade.get("price_observed_at"),
            "price_origin": str(trade.get("price_origin", "UNKNOWN")).upper(),
            "created_at": trade.get("created_at") or now,
            "updated_at": trade.get("updated_at") or now,
        }

    @classmethod
    def _upsert_trade_on_connection(cls, conn: sqlite3.Connection, trade: Dict[str, Any]) -> None:
        conn.execute("""
                INSERT INTO trades (
                    id, symbol, side, entry_price, exit_price, qty,
                    stop_loss, take_profit, entry_time, exit_time,
                    status, pnl, r_multiple, commission, notes, record_mode,
                    execution_venue, price_source, price_source_symbol, price_status,
                    price_observed_at, price_origin, created_at, updated_at, position_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record_mode = excluded.record_mode,
                    position_type = excluded.position_type,
                    execution_venue = excluded.execution_venue,
                    price_source = excluded.price_source,
                    price_source_symbol = excluded.price_source_symbol,
                    price_status = excluded.price_status,
                    price_observed_at = excluded.price_observed_at,
                    price_origin = excluded.price_origin,
                    updated_at = excluded.updated_at
            """, tuple(trade[field] for field in (
                "id", "symbol", "side", "entry_price", "exit_price", "qty",
                "stop_loss", "take_profit", "entry_time", "exit_time", "status",
                "pnl", "r_multiple", "commission", "notes", "record_mode",
                "execution_venue", "price_source", "price_source_symbol", "price_status",
                "price_observed_at", "price_origin", "created_at", "updated_at", "position_type",
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
        received_at: Optional[str] = None,
        causation_id: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        raw_payload: Any = None,
        event_id: Optional[str] = None,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Persist a journal mutation and its evidence event atomically.

        The compatibility ``trades`` row is retained for existing analytics, but
        its write acknowledgement is coupled to the append-only ledger.  If the
        event is invalid, conflicting, or cannot be appended, the trade mutation
        is rolled back and the caller receives an error.
        """

        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository

        resolved_id = str(trade.get("id") or f"TRD-{int(datetime.utcnow().timestamp()*1000)}")
        ledger = EvidenceLedgerRepository(self.db_path)
        projection = EvidenceTradeProjectionRepository(self.db_path)
        conn = self.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            if resource_check is not None:
                resource_check("before_trade_upsert")
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
            if resource_check is not None:
                resource_check("after_trade_upsert")
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
                causation_id=causation_id,
                provenance=provenance or {"source": "journal"},
                received_at=received_at,
                event_id=event_id,
            )
            self._notify_transaction_hook("after_canonical_event", conn)
            if resource_check is not None:
                resource_check("after_canonical_event")
            # Keep the typed read model current in the same transaction as the
            # compatibility row and canonical ledger event.  A projection
            # validation/constraint error must roll back the whole journal write.
            projection.upsert_event_in_transaction(conn, event)
            self._notify_transaction_hook("after_projection_update", conn)
            if resource_check is not None:
                resource_check("after_projection_update")
            self._notify_transaction_hook("before_commit", conn)
            if resource_check is not None:
                resource_check("before_commit")
            conn.commit()
            self._notify_transaction_hook("after_commit_before_ack", conn)
            return dict(stored)
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def record_grouped_evidence_batch(
        self,
        commands: Sequence[Dict[str, Any]],
        *,
        cancel_check: Optional[Callable[[], bool]] = None,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Persist economic-group journal/evidence commands in one transaction.

        Each command carries a validated trade snapshot and its normalized
        economic evidence context.  The compatibility row, canonical ledger
        append and typed projection are deliberately coupled; a failure for any
        command rolls back the complete bounded batch.  ``cancel_check`` is an
        optional cooperative boundary for callers that can cancel before the
        transaction is committed; a requested cancellation rolls back the
        entire batch instead of returning a partial success.
        """

        if not commands:
            return []
        if cancel_check is not None and not callable(cancel_check):
            raise TypeError("cancel_check must be callable")
        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
        from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository

        ledger = EvidenceLedgerRepository(self.db_path)
        projection = EvidenceTradeProjectionRepository(self.db_path)
        conn = self.get_connection()
        persisted: List[Dict[str, Any]] = []
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            for command in commands:
                if resource_check is not None:
                    resource_check("before_command")
                if cancel_check is not None and cancel_check():
                    raise SQLiteOperationCancelled(
                        "grouped evidence batch cancelled before commit"
                    )
                if not isinstance(command, dict):
                    raise TypeError("grouped evidence command must be an object")
                trade = command.get("trade")
                if not isinstance(trade, dict):
                    raise ValueError("grouped evidence command trade must be an object")
                resolved_id = str(trade.get("id") or "").strip()
                if not resolved_id:
                    raise ValueError("grouped evidence trade id is required")

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
                    prepared = self._prepare_trade(
                        {**trade, "id": resolved_id},
                        trade_id=resolved_id,
                    )

                self._upsert_trade_on_connection(conn, prepared)
                stored = conn.execute(
                    "SELECT * FROM trades WHERE id = ?", (resolved_id,)
                ).fetchone()
                if stored is None:
                    raise RuntimeError("Grouped trade write is not readable inside its transaction")
                snapshot = {
                    field: stored[field] for field in self._TRADE_SNAPSHOT_FIELDS
                }

                normalized_payload = command.get("normalized_payload")
                if not isinstance(normalized_payload, dict):
                    raise ValueError("grouped evidence normalized_payload must be an object")
                normalized_payload = dict(normalized_payload)
                payload_trade = normalized_payload.get("trade")
                if not isinstance(payload_trade, dict):
                    raise ValueError("grouped evidence normalized_payload.trade is required")
                payload_trade = dict(payload_trade)
                payload_trade.update(snapshot)
                normalized_payload["trade"] = payload_trade
                # The source rows are intentionally never copied into the
                # ledger.  Use the final normalized snapshot for the digest so
                # deterministic replays cannot conflict on an intermediate
                # pre-normalization object.
                raw_payload = normalized_payload

                event = ledger.append_event_in_transaction(
                    conn,
                    event_type=command["event_type"],
                    account_id=command["account_id"],
                    venue=command["venue"],
                    idempotency_key=command["idempotency_key"],
                    normalized_payload=normalized_payload,
                    raw_payload=raw_payload,
                    occurred_at=command.get("occurred_at"),
                    received_at=command.get("received_at"),
                    schema_version=command.get("schema_version", "1"),
                    adapter_version=command.get("adapter_version", "unknown"),
                    correlation_id=command.get("correlation_id") or resolved_id,
                    causation_id=command.get("causation_id"),
                    provenance=command.get("provenance") or {},
                    event_id=command.get("event_id"),
                )
                self._notify_transaction_hook("after_canonical_event", conn)
                if resource_check is not None:
                    resource_check("after_canonical_event")
                projection.upsert_event_in_transaction(conn, event)
                self._notify_transaction_hook("after_projection_update", conn)
                if resource_check is not None:
                    resource_check("after_projection_update")
                persisted.append({"trade": dict(stored), "event": event})
            if cancel_check is not None and cancel_check():
                raise SQLiteOperationCancelled(
                    "grouped evidence batch cancelled before commit"
                )
            if resource_check is not None:
                resource_check("before_commit")
            self._notify_transaction_hook("before_commit", conn)
            conn.commit()
            self._notify_transaction_hook("after_commit_before_ack", conn)
            return persisted
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

    def list_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        order_by_utc: bool = False,
        resource_check: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        if resource_check is not None and not callable(resource_check):
            raise TypeError("resource_check must be callable")

        def check_resources(phase: str) -> None:
            if resource_check is not None:
                resource_check(phase)

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
            check_resources("before_trade_query")
            cursor.execute(query, params)
            result = []
            for row in cursor:
                check_resources("before_trade_row")
                result.append(dict(row))
            check_resources("after_trade_query")
            return result

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
