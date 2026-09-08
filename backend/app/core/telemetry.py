"""
Opt-In Privacy Telemetry & Offline Crash Spooler for Kuantra Terminal.
Zero-tracking by default; handles offline exception queueing and anonymized crash spooling.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional
from app.core.paths import DATA_DIR, ensure_private_directory, ensure_private_file
from app.db.sqlite_driver import sqlite_driver
from app.core.logging_config import redact_sensitive_text

logger = logging.getLogger("telemetry")

QUEUE_FILE_PATH = DATA_DIR / "telemetry_queue.json"
MAX_QUEUE_RECORDS = 100
MAX_ERROR_TYPE_LENGTH = 128
MAX_MESSAGE_LENGTH = 4000
MAX_STACK_TRACE_LENGTH = 12000

FlushTransport = Callable[[List[Dict[str, Any]]], bool]

class PrivacyTelemetryManager:
    """Manages explicit user consent, Sentry gating, and offline crash spooling."""

    def __init__(
        self,
        queue_file: Optional[Path] = None,
        flush_transport: Optional[FlushTransport] = None,
        max_queue_records: int = MAX_QUEUE_RECORDS,
    ):
        self.queue_file = Path(queue_file or QUEUE_FILE_PATH)
        ensure_private_directory(self.queue_file.parent)
        self.flush_transport = flush_transport
        self.max_queue_records = max(1, int(max_queue_records))

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
            "error_type": redact_sensitive_text(str(error_type))[:MAX_ERROR_TYPE_LENGTH],
            "message": clean_message[:MAX_MESSAGE_LENGTH],
            "stack_trace": clean_stack[:MAX_STACK_TRACE_LENGTH],
            "os": sys.platform,
        }

        queue = self._load_queue()
        queue = (queue + [record])[-self.max_queue_records :]
        self._save_queue(queue)
        logger.info(f"Crash spooled to local queue: {error_type}")
        return True

    def flush_queue(self) -> Dict[str, Any]:
        """Flush queued reports only after an injected transport acknowledges delivery."""
        if not self.is_opted_in():
            return {"status": "SKIPPED_OPT_OUT", "flushed_count": 0}

        queue = self._load_queue()
        if not queue:
            return {"status": "NOTHING_TO_FLUSH", "flushed_count": 0}

        if self.flush_transport is None:
            return {"status": "NO_TRANSPORT", "flushed_count": 0}

        try:
            delivered = bool(self.flush_transport(list(queue)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telemetry transport failed; retaining local queue: %s", exc)
            return {"status": "TRANSPORT_ERROR", "flushed_count": 0}

        if not delivered:
            return {"status": "TRANSPORT_REJECTED", "flushed_count": 0}

        logger.info("Flushed %s anonymous crash reports after transport acknowledgement.", len(queue))
        self._save_queue([])

        return {"status": "SUCCESS", "flushed_count": len(queue)}

    def get_queued_crashes_count(self) -> int:
        """Returns number of spooled crash logs currently stored locally."""
        return len(self._load_queue())

    def delivery_status(self) -> str:
        """Describe delivery truth without attempting a network operation."""

        if not self.is_opted_in():
            return "OPT_OUT"
        if not self._load_queue():
            return "IDLE"
        if self.flush_transport is None:
            return "NO_TRANSPORT"
        return "READY_TO_FLUSH"

    def _load_queue(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.queue_file):
            return []
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, list):
                return []
            return loaded[-self.max_queue_records :]
        except Exception:
            return []

    def _save_queue(self, queue: List[Dict[str, Any]]) -> None:
        temporary = self.queue_file.with_name(f".{self.queue_file.name}.tmp")
        try:
            ensure_private_file(temporary)
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2)
            ensure_private_file(temporary)
            os.replace(temporary, self.queue_file)
            ensure_private_file(self.queue_file)
        except Exception as e:
            logger.error(f"Error saving crash queue: {e}")
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

telemetry_manager = PrivacyTelemetryManager()
