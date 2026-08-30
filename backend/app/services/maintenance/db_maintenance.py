"""
Dual-Storage Maintenance & Parquet Cold Storage Archival Engine for Kuantra Terminal.
Executes non-blocking SQLite WAL checkpoints, shadow VACUUM snapshots,
DuckDB memory limits, and ZSTD-compressed Parquet cold storage tiering.
"""

import os
import sys
import time
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from app.core.paths import get_sqlite_path, get_duckdb_path, DATA_DIR
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver

logger = logging.getLogger("db_maintenance")

class DatabaseMaintenanceEngine:
    """Enterprise Storage Lifecycle & Cold Archival Controller."""

    def __init__(
        self,
        sqlite_path: Optional[str] = None,
        duckdb_path: Optional[str] = None,
        backup_dir: Optional[str] = None,
        cold_storage_dir: Optional[str] = None
    ):
        self.sqlite_path = Path(sqlite_path) if sqlite_path else Path(get_sqlite_path())
        self.duckdb_path = Path(duckdb_path) if duckdb_path else Path(get_duckdb_path())
        self.backup_dir = Path(backup_dir) if backup_dir else DATA_DIR / "backups"
        self.cold_storage_dir = Path(cold_storage_dir) if cold_storage_dir else DATA_DIR / "cold_storage"

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.cold_storage_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. SQLite WAL Checkpointing & Shadow Snapshots
    # =========================================================================
    def run_sqlite_checkpoint(self, truncate: bool = True) -> Dict[str, Any]:
        """
        Executes PRAGMA wal_checkpoint(TRUNCATE / PASSIVE) to merge WAL journal into main DB.
        """
        mode = "TRUNCATE" if truncate else "PASSIVE"
        try:
            with sqlite_driver.get_connection() as conn:
                cursor = conn.cursor()
                res = cursor.execute(f"PRAGMA wal_checkpoint({mode});").fetchone()
                busy, log_frames, checkpointed_frames = res[0], res[1], res[2]
                
            logger.info(f"[SQLITE-MAINTENANCE] WAL Checkpoint ({mode}): Busy={busy}, Log={log_frames}, Checkpointed={checkpointed_frames}")
            return {
                "status": "SUCCESS",
                "mode": mode,
                "busy": busy,
                "log_frames": log_frames,
                "checkpointed_frames": checkpointed_frames,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as e:
            logger.error(f"[SQLITE-MAINTENANCE] WAL checkpoint failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    def run_sqlite_integrity_check(self) -> Dict[str, Any]:
        """Executes PRAGMA integrity_check and PRAGMA optimize for query indexing."""
        try:
            with sqlite_driver.get_connection() as conn:
                cursor = conn.cursor()
                check_result = cursor.execute("PRAGMA integrity_check;").fetchall()
                cursor.execute("PRAGMA optimize;")

            messages = [r[0] for r in check_result]
            is_ok = messages == ["ok"]
            return {
                "status": "HEALTHY" if is_ok else "CORRUPTED",
                "integrity_output": messages,
                "optimized": True
            }
        except Exception as e:
            logger.error(f"[SQLITE-MAINTENANCE] Integrity check error: {e}")
            return {"status": "ERROR", "error": str(e)}

    def create_sqlite_shadow_backup(self, max_retention_days: int = 30) -> Dict[str, Any]:
        """
        Executes non-blocking online VACUUM INTO snapshot and cleans up backups older than 30 days.
        """
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        backup_filename = f"kuantra_user_data_{timestamp_str}.db"
        target_backup_path = self.backup_dir / backup_filename

        try:
            with sqlite_driver.get_connection() as conn:
                # Online non-blocking shadow copy
                conn.execute(f"VACUUM INTO '{target_backup_path.as_posix()}';")

            size_bytes = target_backup_path.stat().st_size
            logger.info(f"[SQLITE-BACKUP] Created shadow backup: {backup_filename} ({size_bytes} bytes)")

            # Prune old backups
            pruned_backups = self._prune_old_backups(max_retention_days)

            return {
                "status": "SUCCESS",
                "backup_file": backup_filename,
                "backup_path": str(target_backup_path),
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 3),
                "pruned_backups": pruned_backups,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as e:
            logger.error(f"[SQLITE-BACKUP] Shadow backup failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    def _prune_old_backups(self, max_days: int) -> List[str]:
        """Deletes database backups older than max_days."""
        ttl_seconds = max_days * 86400.0
        now = time.time()
        deleted = []
        for bk in self.backup_dir.glob("*.db"):
            try:
                if now - bk.stat().st_mtime > ttl_seconds:
                    bk.unlink()
                    deleted.append(bk.name)
            except Exception as e:
                logger.warning(f"Failed to prune backup {bk.name}: {e}")
        return deleted

    # =========================================================================
    # 2. DuckDB Memory Guard & Cold Parquet Archival
    # =========================================================================
    def enforce_duckdb_memory_limit(self, max_memory_mb: int = 2048) -> Dict[str, Any]:
        """Sets max memory ceiling (e.g. 2GB) on DuckDB to prevent unbounded RAM usage."""
        conn = duckdb_driver.get_connection()
        try:
            mem_str = f"{max_memory_mb}MB"
            conn.execute(f"SET max_memory = '{mem_str}';")
            logger.info(f"[DUCKDB-MAINTENANCE] Enforced max memory ceiling: {mem_str}")
            return {"status": "SUCCESS", "max_memory": mem_str}
        except Exception as e:
            logger.error(f"[DUCKDB-MAINTENANCE] Failed to set memory ceiling: {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            conn.close()

    def archive_old_ticks_to_parquet(self, retention_days: int = 7) -> Dict[str, Any]:
        """
        Exports market candles / ticks older than retention_days to ZSTD Parquet cold storage,
        deletes archived rows from active tables, and executes DuckDB CHECKPOINT.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_str = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        parquet_filename = f"ticks_archive_{timestamp_str}.parquet"
        parquet_path = self.cold_storage_dir / parquet_filename

        conn = duckdb_driver.get_connection()
        try:
            # Check row count to archive
            count_res = conn.execute(
                f"SELECT count(*) FROM market_candles WHERE timestamp < '{cutoff_str}'"
            ).fetchone()
            rows_to_archive = count_res[0] if count_res else 0

            exported_file = None
            if rows_to_archive > 0:
                # Export to ZSTD compressed Parquet
                export_sql = f"""
                    COPY (SELECT * FROM market_candles WHERE timestamp < '{cutoff_str}')
                    TO '{parquet_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD);
                """
                conn.execute(export_sql)
                exported_file = parquet_filename

                # Delete archived rows from active table
                conn.execute(f"DELETE FROM market_candles WHERE timestamp < '{cutoff_str}';")
                conn.execute("CHECKPOINT;")
                logger.info(f"[DUCKDB-COLD-STORAGE] Exported {rows_to_archive} records to {parquet_filename}")
            else:
                logger.info("[DUCKDB-COLD-STORAGE] No expired tick records found beyond retention window.")

            return {
                "status": "SUCCESS",
                "cutoff_date": cutoff_str,
                "archived_records": rows_to_archive,
                "parquet_file": exported_file,
                "cold_storage_dir": str(self.cold_storage_dir),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        except Exception as e:
            logger.error(f"[DUCKDB-COLD-STORAGE] Parquet archival error: {e}")
            return {"status": "ERROR", "error": str(e)}
        finally:
            conn.close()

    # =========================================================================
    # 3. Overall Storage Telemetry
    # =========================================================================
    def get_storage_telemetry(self) -> Dict[str, Any]:
        """Returns comprehensive storage metrics across SQLite, DuckDB, Logs, and Cold Storage."""
        # SQLite size
        sqlite_db_size = self.sqlite_path.stat().st_size if self.sqlite_path.exists() else 0
        wal_path = Path(str(self.sqlite_path) + "-wal")
        sqlite_wal_size = wal_path.stat().st_size if wal_path.exists() else 0

        # DuckDB size
        duckdb_size = self.duckdb_path.stat().st_size if self.duckdb_path.exists() else 0
        duckdb_wal_path = Path(str(self.duckdb_path) + ".wal")
        duckdb_wal_size = duckdb_wal_path.stat().st_size if duckdb_wal_path.exists() else 0

        # Logs total size
        logs_dir = DATA_DIR / "logs"
        logs_total_size = sum(f.stat().st_size for f in logs_dir.glob("**/*") if f.is_file()) if logs_dir.exists() else 0

        # Cold storage size
        cold_storage_size = sum(f.stat().st_size for f in self.cold_storage_dir.glob("*.parquet")) if self.cold_storage_dir.exists() else 0

        # Backups count
        active_backups = len(list(self.backup_dir.glob("*.db"))) if self.backup_dir.exists() else 0

        return {
            "sqlite_db_size_mb": round(sqlite_db_size / (1024 * 1024), 3),
            "sqlite_wal_size_mb": round(sqlite_wal_size / (1024 * 1024), 3),
            "duckdb_size_mb": round((duckdb_size + duckdb_wal_size) / (1024 * 1024), 3),
            "logs_total_size_mb": round(logs_total_size / (1024 * 1024), 3),
            "cold_storage_size_mb": round(cold_storage_size / (1024 * 1024), 3),
            "active_backups_count": active_backups,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

db_maintenance_engine = DatabaseMaintenanceEngine()