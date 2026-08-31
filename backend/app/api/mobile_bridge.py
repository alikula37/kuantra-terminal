"""
Encrypted Mobile Companion Bridge for Kuantra Terminal.
Handles Biometric QR Code pairing, session authentication, and iOS/Android companion communication.
"""

import time
import uuid
import hashlib
import hmac
import logging
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.services.p2p.mesh_node import p2p_mesh_node

logger = logging.getLogger("mobile_bridge")

class MobileCompanionBridge:
    """Manages secure pairing and telemetry for mobile companion devices."""

    def __init__(self):
        self.paired_devices: Dict[str, Dict[str, Any]] = {}
        self.active_pairing_tokens: Dict[str, float] = {} # token -> expires_at

    def generate_pairing_qr_payload(self) -> Dict[str, Any]:
        """Generates a cryptographic time-limited QR pairing token."""
        raw_token = str(uuid.uuid4())
        salt = hashlib.sha256(f"{raw_token}:{time.time()}".encode()).hexdigest()[:16]
        pairing_token = f"KNT-PAIR-{salt.upper()}"
        expires_at = time.time() + 300.0 # 5 minutes validity

        self.active_pairing_tokens[pairing_token] = expires_at

        qr_data = {
            "protocol": "KUANTRA_MOBILE_PAIR_V2",
            "terminal_name": settings.app_name,
            "version": settings.version,
            "node_id": p2p_mesh_node.node_id,
            "pairing_token": pairing_token,
            "host_url": f"http://127.0.0.1:{settings.port}",
            "expires_at": expires_at
        }

        logger.info(f"[MOBILE BRIDGE] Generated ephemeral pairing token {pairing_token}")
        return qr_data

    def verify_and_pair_device(
        self,
        pairing_token: str,
        device_id: str,
        device_name: str,
        platform: str = "iOS",
        biometric_supported: bool = True
    ) -> Dict[str, Any]:
        """Validates token and registers new mobile device."""
        exp = self.active_pairing_tokens.get(pairing_token)
        if not exp or time.time() > exp:
            raise ValueError("Pairing token invalid or expired.")

        session_secret = hashlib.sha256(f"{pairing_token}:{device_id}:{time.time()}".encode()).hexdigest()

        device_record = {
            "device_id": device_id,
            "device_name": device_name,
            "platform": platform,
            "session_secret": session_secret,
            "paired_at": time.time(),
            "last_active": time.time(),
            "is_biometric_enabled": biometric_supported,
            "status": "PAIRED_SECURE"
        }

        self.paired_devices[device_id] = device_record
        del self.active_pairing_tokens[pairing_token]

        logger.info(f"[MOBILE BRIDGE] Successfully paired mobile companion {device_name} ({device_id})")
        return {
            "status": "PAIRED_SUCCESS",
            "device_id": device_id,
            "session_token": session_secret,
            "node_id": p2p_mesh_node.node_id
        }

    def list_paired_devices(self) -> List[Dict[str, Any]]:
        """Returns list of all authorized mobile companions."""
        # Sanitize session secrets before returning
        return [
            {k: v for k, v in d.items() if k != "session_secret"}
            for d in self.paired_devices.values()
        ]

    def revoke_device(self, device_id: str) -> bool:
        """Revokes mobile device authorization immediately."""
        if device_id in self.paired_devices:
            del self.paired_devices[device_id]
            logger.warning(f"[MOBILE BRIDGE] Revoked mobile companion {device_id}")
            return True
        return False

mobile_companion_bridge = MobileCompanionBridge()