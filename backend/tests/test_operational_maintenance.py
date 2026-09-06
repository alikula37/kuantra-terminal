import os
import time
import gzip
import tempfile
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from main import create_app
from app.services.maintenance.log_sanitizer import (
    sanitize_log_message,
    PIISecretSanitizerFilter,
    LogRotationManager
)
from app.services.maintenance.db_maintenance import (
    DatabaseMaintenanceEngine,
    db_maintenance_engine
)
from app.services.maintenance.worker import MaintenanceWorker
from app.cli import create_parser, handle_maintenance, handle_repair_db, handle_vault_audit, handle_storage_stats
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

class TestOperationalMaintenanceAndSanitizer:
    """Test suite for Log Sanitizer, WAL Checkpointing, Parquet Archival, and Maintenance CLI."""

    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_log_sanitizer_redacts_sensitive_tokens(self):
        # 1. API Key redaction
        raw_msg_1 = "Connected to Binance API: api_key=\"AKIAIOSFODNN7EXAMPLE\" and secret_key=\"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\""
        sanitized_1 = sanitize_log_message(raw_msg_1)
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_1
        assert "[REDACTED_SECRET]" in sanitized_1

        # 2. Bearer token redaction
        raw_msg_2 = "Authorization Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozG"
        sanitized_2 = sanitize_log_message(raw_msg_2)
        assert "eyJhbGci" not in sanitized_2
        assert "Bearer [REDACTED_SECRET]" in sanitized_2 or "[REDACTED_SECRET]" in sanitized_2

        # 3. Private Key redaction
        raw_msg_3 = "Loading private_key=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d for execution"
        sanitized_3 = sanitize_log_message(raw_msg_3)
        assert "0x4f3edf983ac6" not in sanitized_3
        assert "[REDACTED_SECRET]" in sanitized_3

        # 4. Passkey signature redaction
        raw_msg_4 = "FIDO2 attestation received: WEBAUTHN_ENCLAVE_SIGNATURE_99482103847582"
        sanitized_4 = sanitize_log_message(raw_msg_4)
        assert "WEBAUTHN_ENCLAVE_SIGNATURE_99482103847582" not in sanitized_4
        assert "[REDACTED_SECRET]" in sanitized_4

    def test_log_rotation_and_ttl_pruning(self, tmp_path):
        logs_dir = tmp_path / "logs"
        rotator = LogRotationManager(logs_dir=str(logs_dir))

        # Create a mock oversized log file (>25MB threshold override for test)
        rotator.MAX_FILE_SIZE_BYTES = 1024 # 1 KB for test
        test_log = logs_dir / "kuantra_app.log"
        with open(test_log, "w", encoding="utf-8") as f:
            f.write("A" * 2048) # 2 KB

        archived = rotator.rotate_file_if_needed(test_log)
        assert archived is not None
        assert archived.exists()
        assert archived.name.endswith(".log.gz")

        # Verify gz content can be decompressed
        with gzip.open(archived, "rt", encoding="utf-8") as f_gz:
            data = f_gz.read()
            assert len(data) > 0

        # Test TTL Pruning of archives (>14 days)
        # Artificially set old mtime on archive file (15 days ago)
        old_time = time.time() - (15 * 86400)
        os.utime(archived, (old_time, old_time))

        pruned = rotator.prune_expired_archives(max_age_days=14)
        assert archived.name in pruned
        assert not archived.exists()

    def test_sqlite_wal_checkpoint_and_backup(self, tmp_path):
        backup_dir = tmp_path / "backups"
        engine = DatabaseMaintenanceEngine(backup_dir=str(backup_dir))

        # 1. WAL Checkpoint
        chk = engine.run_sqlite_checkpoint(truncate=True)
        assert chk["status"] == "SUCCESS"
        assert "checkpointed_frames" in chk

        # 2. SQLite Integrity Check
        integrity = engine.run_sqlite_integrity_check()
        assert integrity["status"] == "HEALTHY"

        # 3. Non-blocking Shadow Backup
        backup_res = engine.create_sqlite_shadow_backup(max_retention_days=30)
        assert backup_res["status"] == "SUCCESS"
        assert backup_res["size_bytes"] > 0
        assert os.path.exists(backup_res["backup_path"])

    def test_duckdb_cold_storage_parquet_export(self, tmp_path):
        cold_dir = tmp_path / "cold_storage"
        engine = DatabaseMaintenanceEngine(cold_storage_dir=str(cold_dir))

        # Insert old synthetic candles (>10 days ago) into DuckDB
        conn = duckdb_driver.get_connection()
        try:
            conn.execute("""
                INSERT INTO market_candles (
                    symbol, timeframe, timestamp, open, high, low, close, volume, trades_count
                ) VALUES
                ('BTCUSDT', '1m', '2020-01-01 10:00:00', 7000.0, 7050.0, 6990.0, 7020.0, 10.5, 100),
                ('BTCUSDT', '1m', '2020-01-01 10:01:00', 7020.0, 7080.0, 7010.0, 7075.0, 12.0, 120);
            """)
        finally:
            conn.close()

        # Execute Parquet archival (>7 days old)
        arc_res = engine.archive_old_ticks_to_parquet(retention_days=7)
        assert arc_res["status"] == "SUCCESS"
        assert arc_res["archived_records"] >= 2
        assert arc_res["parquet_file"] is not None

        # Verify generated Parquet file exists
        parquet_file = cold_dir / arc_res["parquet_file"]
        assert parquet_file.exists()
        assert parquet_file.stat().st_size > 0

    def test_maintenance_cli_and_rest_endpoints(self, client):
        # 1. CLI Parser & Handler execution
        parser = create_parser()
        args = parser.parse_args(["maintenance", "--checkpoint-wal", "--prune-logs"])
        assert args.command == "maintenance"
        assert args.checkpoint_wal is True

        repair_res = handle_repair_db(args)
        assert repair_res["status"] == "HEALTHY"

        vault_res = handle_vault_audit(args)
        assert vault_res["status"] == "VERIFIED_SECURE"

        stats_cli = handle_storage_stats(args)
        assert "sqlite_db_size_mb" in stats_cli
        assert "duckdb_size_mb" in stats_cli

        # 2. REST Endpoints
        # Heartbeat
        res_hb = client.get("/api/v1/system/health/heartbeat")
        assert res_hb.status_code == 200
        hb_data = res_hb.json()
        assert hb_data["status"] == "HEALTHY"
        assert hb_data["ipc_alive"] is True
        assert "uptime_seconds" in hb_data

        # Storage Stats
        res_st = client.get("/api/v1/system/storage/stats")
        assert res_st.status_code == 200
        st_data = res_st.json()
        assert "sqlite_db_size_mb" in st_data
        assert "duckdb_size_mb" in st_data

        # Run Maintenance Endpoint
        res_maint = client.post("/api/v1/system/maintenance/run", json={
            "checkpoint_wal": True,
            "compact_duckdb": True,
            "prune_logs": True
        })
        assert res_maint.status_code == 200
        maint_data = res_maint.json()
        assert "wal_checkpoint" in maint_data
