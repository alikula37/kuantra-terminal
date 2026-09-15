"""
Emergency panic kill-switch & terminal lockdown engine for Kuantra Terminal.

The kill switch only changes the local operational state to lockdown.  Kuantra
has no order authority, so it never fabricates fills or closes and never writes
invented exit prices into the journal or the evidence ledger.
"""

import hmac
import os
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("panic_switch")

DISARM_SECRET_ENV = "KUANTRA_PANIC_DISARM_SECRET"


class PanicKillSwitchEngine:
    """Institutional circuit-breaker and emergency risk shutdown coordinator."""

    def __init__(self):
        self.is_locked_down: bool = False
        self.lockdown_reason: Optional[str] = None
        self.lockdown_timestamp: Optional[float] = None
        self.panic_events: List[Dict[str, Any]] = []

    def trigger_emergency_kill_switch(
        self,
        source: str = "WEARABLE_APPLE_WATCH",
        reason: str = "Trader manual 1-tap panic activation"
    ) -> Dict[str, Any]:
        """
        Enters READ_ONLY_LOCKDOWN and records the event.

        No positions are closed or written: Kuantra has no order authority and
        must never record a fill that a broker did not report.  Existing open
        journal positions remain untouched until the user (or a future
        broker-verified sync) records a real close.
        """
        t_now = time.time()
        self.is_locked_down = True
        self.lockdown_reason = reason
        self.lockdown_timestamp = t_now

        event = {
            "event_id": f"PANIC-{int(t_now * 1000)}",
            "source": source,
            "reason": reason,
            "flattened_positions_count": 0,
            "flattened_details": [],
            "flattening": "DISABLED_NO_ORDER_AUTHORITY",
            "timestamp": t_now,
            "status": "TERMINAL_LOCKED_DOWN"
        }
        self.panic_events.append(event)

        logger.critical(
            "[PANIC KILL-SWITCH] Lockdown activated from %s. No positions were "
            "closed or written (no order authority).", source,
        )
        return event

    def disarm_lockdown(self, pin_or_passkey: str) -> Dict[str, Any]:
        """Disarms the lockdown only with the owner-configured disarm secret."""
        if not self.is_locked_down:
            return {"status": "ALREADY_ARMED", "message": "Terminal is not in lockdown."}

        secret = str(os.environ.get(DISARM_SECRET_ENV) or "").strip()
        if not secret:
            raise ValueError(
                f"PANIC_DISARM_UNCONFIGURED: set {DISARM_SECRET_ENV} to allow disarming."
            )
        provided = str(pin_or_passkey or "")
        if not hmac.compare_digest(provided.encode("utf-8"), secret.encode("utf-8")):
            raise ValueError("Invalid disarm secret.")

        self.is_locked_down = False
        self.lockdown_reason = None
        self.lockdown_timestamp = None
        logger.info("[PANIC KILL-SWITCH] Terminal DISARMED with the configured secret.")
        return {"status": "DISARMED", "message": "Operational state restored."}

    def get_lockdown_status(self) -> Dict[str, Any]:
        """Returns active terminal lockdown status and panic history."""
        return {
            "is_locked_down": self.is_locked_down,
            "lockdown_reason": self.lockdown_reason,
            "lockdown_timestamp": self.lockdown_timestamp,
            "panic_events_count": len(self.panic_events),
            "recent_event": self.panic_events[-1] if self.panic_events else None
        }

panic_kill_switch = PanicKillSwitchEngine()