"""
Opt-In Privacy Telemetry & Offline Crash Spooler for Kuantra Terminal.
Zero-tracking by default; handles offline exception queueing and anonymized crash spooling.
"""

import os
import sys
import json
import time
import logging
from typing import Dict, Any, List, Optional
from app.core.paths import DATA_DIR
from app.db.sqlite_driver import sqlite_driver
from app.core.logging_config import redact_sensitive_text

logger = logging.getLogger("telemetry")

QUEUE_FILE_PATH = DATA_DIR / "telemetry_queue.json"

class PrivacyTelemetryManager:
    """Manages explicit user consent, Sentry gating, and offline crash spooling."""

    def __init__(self):
        self.queue_file = QUEUE_FILE_PATH

    def is_opted_in(self) -> bool:
        """Checks if user has explicitly enabled anonymous crash telemetry (default False)."""
        val = sqlite_driver.get_setting("telemetry_opt_in")
        if val is None:
            return False
        return str(val).lower() in ("true", "1", '"true"')

    def set_opt_in(self, enabled: bool) -> None:
        """Persists user consent choice in encrypted/secure settings."""
        sqlite_driver.set_setting("telemetry_opt_in", "true" if enabled else "false")
        logger.info(f"Telemetry opt-in status updated to: {enabled}")

    def spool_crash(self, error_type: str, message: str, stack_trace: str) -> bool:
        """
        Stores crash report in local spool queue.
        Always scrubs all PII/secrets before queueing to disk.
        """
        clean_message = redact_sensitive_text(message)
        clean_stack = redact_sensitive_text(stack_trace)

        record = {
            "timestamp": time.time(),
            "error_type": error_type,
            "message": clean_message,
            "stack_trace": clean_stack,
            "os": sys.platform,
        }

        queue = self._load_queue()
        queue.append(record)
        self._save_queue(queue)
        logger.info(f"Crash spooled to local queue: {error_type}")
        return True

    def flush_queue(self) -> Dict[str, Any]:
        """Flushes queued crash reports if opted-in and clears local spool file."""
        if not self.is_opted_in():
            return {"status": "SKIPPED_OPT_OUT", "flushed_count": 0}

        queue = self._load_queue()
        flushed_count = len(queue)
        
        # Simulate / dispatch to anonymous telemetry endpoint
        if flushed_count > 0:
            logger.info(f"Flushing {flushed_count} anonymous crash reports...")
            self._save_queue([]) # Clear queue

        return {"status": "SUCCESS", "flushed_count": flushed_count}

    def get_queued_crashes_count(self) -> int:
        """Returns number of spooled crash logs currently stored locally."""
        return len(self._load_queue())

    def _load_queue(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.queue_file):
            return []
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_queue(self, queue: List[Dict[str, Any]]) -> None:
        try:
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving crash queue: {e}")

telemetry_manager = PrivacyTelemetryManager()