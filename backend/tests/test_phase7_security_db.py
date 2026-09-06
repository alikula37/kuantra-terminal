import time
import os
import sys
import pytest
from app.core.security import StrongholdVault, vault
from app.db.sqlite_driver import SQLiteDriver, sqlite_driver
from app.db.duckdb_hydrator import DuckDBHydrator, duckdb_hydrator
from app.db.sync_pipeline import SyncPipeline
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.repositories.evidence_projection_repo import EvidenceTradeProjectionRepository

class TestPhase7SecurityAndDbHydration:
    """Test suite for Stronghold Vault, Alembic SQLite migrations, and DuckDB Shadow Hydration."""

    def test_stronghold_vault_encryption_decryption_lifecycle(self):
        v = StrongholdVault("test-master-passphrase-999")
        v.store_secret("API_KEY", "kuantra_super_secret_token_12345")
        v.store_secret("SECRET_KEY", "kuantra_private_hmac_secret_67890")

        assert v.get_secret("API_KEY") == "kuantra_super_secret_token_12345"
        assert v.get_secret("SECRET_KEY") == "kuantra_private_hmac_secret_67890"
        assert set(v.list_keys()) == {"API_KEY", "SECRET_KEY"}

        assert v.delete_secret("API_KEY") is True
        assert v.get_secret("API_KEY") is None
        assert v.delete_secret("NON_EXISTENT") is False

        v.clear()
        assert len(v.list_keys()) == 0

    def test_stateless_payload_encryption(self):
        plaintext = "secret_binance_api_key_value"
        password = "ultra_strong_pin_8877"

        encrypted = StrongholdVault.encrypt_payload(plaintext, password)
        assert isinstance(encrypted, str)
        assert encrypted != plaintext

        decrypted = StrongholdVault.decrypt_payload(encrypted, password)
        assert decrypted == plaintext

        # Test wrong password fails gracefully
        with pytest.raises(Exception):
            StrongholdVault.decrypt_payload(encrypted, "wrong_password")

    def test_alembic_sqlite_migrations_and_wal_mode(self):
        migrated = sqlite_driver.run_migrations("head")
        assert migrated is True

        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            assert mode.upper() == "WAL"

    def test_duckdb_shadow_hydration_integrity_and_recovery(self):
        # Insert a sample trade into SQLite OLTP
        test_trade = {
            "id": f"TRD-HYDRATE-{int(time.time()*1000)}",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 65000.0,
            "exit_price": 67000.0,
            "qty": 1.0,
            "stop_loss": 64000.0,
            "take_profit": 67000.0,
            "entry_time": "2026-08-30T14:00:00",
            "exit_time": "2026-08-30T14:30:00",
            "status": "CLOSED",
            "pnl": 2000.0,
            "r_multiple": 2.0,
            "notes": "Hydration integrity test"
        }
        # Hydration is intentionally evidence-gated; direct compatibility CRUD
        # rows are not accepted as an OLAP source without explicit backfill.
        SyncPipeline.record_and_sync_trade(test_trade, source="manual")

        res = duckdb_hydrator.hydrate_from_sqlite(force_rebuild=False)
        assert res["status"] == "HYDRATED"
        assert res["recovered_trades_count"] >= 1
        assert duckdb_hydrator.check_integrity() is True

    def test_duckdb_hydrator_blocks_unverified_legacy_rows(self, tmp_path):
        sqlite_path = tmp_path / "legacy.sqlite"
        duckdb_path = tmp_path / "legacy.duckdb"
        legacy_driver = SQLiteDriver(str(sqlite_path))
        legacy_driver.insert_trade({
            "id": "UNVERIFIED-1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "entry_price": 100.0,
            "qty": 1.0,
            "entry_time": "2026-08-30T14:00:00Z",
            "status": "OPEN",
        })

        hydrator = DuckDBHydrator(
            duckdb_path=str(duckdb_path),
            sqlite_path=str(sqlite_path),
        )
        result = hydrator.hydrate_from_sqlite(force_rebuild=True)

        assert result["status"] == "BLOCKED"
        assert result["reason"] == "PROJECTION_COVERAGE_INCOMPLETE"
        assert result["coverage"]["missing_count"] == 1
        assert not duckdb_path.exists()

        EvidenceLedgerRepository(str(sqlite_path)).backfill_legacy_trades(
            dry_run=False,
            venue="local-journal",
        )
        EvidenceTradeProjectionRepository(str(sqlite_path)).rebuild(dry_run=False)
        hydrated = hydrator.hydrate_from_sqlite(force_rebuild=True)
        assert hydrated["status"] == "HYDRATED"
        assert hydrated["source"] == "evidence_trade_projection"

    def test_duckdb_hydrator_corrupted_file_recovery(self):
        duck_path = duckdb_hydrator.duckdb_path
        # Corrupt DuckDB file by writing invalid garbage bytes
        with open(duck_path, "wb") as f:
            f.write(b"CORRUPTED_GARBAGE_DATA_1234567890_HEADER_OVERWRITE")

        # Hydrator should detect corruption and self-heal from SQLite
        res = duckdb_hydrator.hydrate_from_sqlite(force_rebuild=False)
        assert res["status"] == "HYDRATED"
        assert res["is_reconstituted"] is True
        assert duckdb_hydrator.check_integrity() is True
