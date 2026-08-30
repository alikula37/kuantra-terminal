"""
Background Async Maintenance Scheduler Worker for Kuantra Terminal.
Executes non-blocking periodic maintenance cycles (hourly WAL checkpoints and daily cold storage archival)
without interrupting real-time market tick ingestion or high-frequency order execution.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

from app.services.maintenance.log_sanitizer import log_sanitizer_engine
from app.services.maintenance.db_maintenance import db_maintenance_engine

logger = logging.getLogger("maintenance_worker")

class MaintenanceWorker:
    """Async Background Worker managing storage hygiene and operational stability."""

    def __init__(self, hourly_interval_sec: int = 3600, daily_interval_sec: int = 86400):
        self.hourly_interval = hourly_interval_sec
        self.daily_interval = daily_interval_sec
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.last_hourly_run: float = 0.0
        self.last_daily_run: float = 0.0
        self.stats = {
            "total_checkpoints": 0,
            "total_backups": 0,
            "total_archivals": 0,
            "worker_status": "IDLE"
        }

    async def start(self):
        """Starts the async background loop."""
        if self._running:
            return
        self._running = True
        self.stats["worker_status"] = "RUNNING"
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[MAINTENANCE-WORKER] Background maintenance worker started.")

    async def stop(self):
        """Stops the async background loop gracefully."""
        if not self._running:
            return
        self._running = False
        self.stats["worker_status"] = "STOPPED"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[MAINTENANCE-WORKER] Background maintenance worker stopped.")

    async def _run_loop(self):
        """Main async monitoring & maintenance tick loop."""
        while self._running:
            try:
                now = time.time()

                # 1. Hourly Maintenance Checkpoint (WAL Checkpoint & Log Check)
                if now - self.last_hourly_run >= self.hourly_interval:
                    self.execute_hourly_maintenance()
                    self.last_hourly_run = now

                # 2. Daily Maintenance (Log Rotation, Cold Parquet Archival, Shadow Backup)
                if now - self.last_daily_run >= self.daily_interval:
                    self.execute_daily_maintenance()
                    self.last_daily_run = now

                # Sleep in short increments for responsive shutdown
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MAINTENANCE-WORKER] Unhandled error in maintenance loop: {e}")
                await asyncio.sleep(30)

    def execute_hourly_maintenance(self) -> Dict[str, Any]:
        """Executes lightweight hourly SQLite WAL checkpoint and DuckDB memory check."""
        logger.info("[MAINTENANCE-WORKER] Executing Hourly Maintenance...")
        chk_res = db_maintenance_engine.run_sqlite_checkpoint(truncate=False)
        mem_res = db_maintenance_engine.enforce_duckdb_memory_limit(2048)
        self.stats["total_checkpoints"] += 1
        return {
            "checkpoint": chk_res,
            "memory": mem_res,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    def execute_daily_maintenance(self) -> Dict[str, Any]:
        """Executes full daily maintenance suite: WAL Truncate, Backup, Parquet Archival, Log Rotation."""
        logger.info("[MAINTENANCE-WORKER] Executing Daily Maintenance...")
        
        # 1. Truncate WAL
        chk_res = db_maintenance_engine.run_sqlite_checkpoint(truncate=True)
        # 2. SQLite Shadow Snapshot
        bk_res = db_maintenance_engine.create_sqlite_shadow_backup(max_retention_days=30)
        # 3. DuckDB Cold Storage Parquet Archival (>7 days old)
        arc_res = db_maintenance_engine.archive_old_ticks_to_parquet(retention_days=7)
        # 4. Log Sanitization & Rotation
        log_res = log_sanitizer_engine.run_full_log_maintenance()

        self.stats["total_checkpoints"] += 1
        self.stats["total_backups"] += 1
        self.stats["total_archivals"] += 1

        return {
            "wal_checkpoint": chk_res,
            "shadow_backup": bk_res,
            "cold_parquet_archival": arc_res,
            "log_rotation": log_res,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

maintenance_worker = MaintenanceWorker()