"""
Bluetooth LE Biometric Wearable Stress Interceptor for Kuantra Terminal.
Listens to real-time BPM & HRV from Apple Watch / Garmin / Whoop and computes Biometric Tilt Score.
"""

import time
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("watch_bridge")

class BiometricWatchBridge:
    """Processes live physiological data and detects acute emotional tilt."""

    def __init__(self):
        self.device_name: str = "Apple Watch Ultra / BLE Bridge"
        self.is_connected: bool = True
        self.current_bpm: float = 72.0
        self.current_hrv: float = 65.0 # Higher is better (parasympathetic tone)
        self.last_update_time: float = time.time()
        self.stress_threshold: float = 75.0

    @classmethod
    def calculate_biometric_tilt_score(cls, bpm: float, hrv: float) -> float:
        """
        Biometric Tilt Score Formula:
        S_bio = (BPM / 1.5) + ((100 - HRV) * 0.6)
        Normalized to 0.0 .. 100.0
        """
        clamped_bpm = max(40.0, min(200.0, bpm))
        clamped_hrv = max(5.0, min(100.0, hrv))
        
        raw_score = (clamped_bpm / 1.5) + ((100.0 - clamped_hrv) * 0.6)
        return round(max(0.0, min(100.0, raw_score)), 1)

    def update_telemetry(self, bpm: float, hrv: float, device_name: Optional[str] = None) -> Dict[str, Any]:
        """Updates internal physiological state from wearable BLE stream."""
        self.current_bpm = float(bpm)
        self.current_hrv = float(hrv)
        if device_name:
            self.device_name = device_name
        self.is_connected = True
        self.last_update_time = time.time()

        tilt_score = self.calculate_biometric_tilt_score(self.current_bpm, self.current_hrv)
        category, _ = self._get_category(tilt_score)

        if tilt_score >= self.stress_threshold:
            logger.warning(
                f"[BIOMETRICS] ACUTE PHYSIOLOGICAL STRESS DETECTED! "
                f"BPM: {self.current_bpm}, HRV: {self.current_hrv}ms, Tilt: {tilt_score}/100"
            )

        return self.get_biometric_state()

    def get_biometric_state(self) -> Dict[str, Any]:
        tilt_score = self.calculate_biometric_tilt_score(self.current_bpm, self.current_hrv)
        category, risk_level = self._get_category(tilt_score)

        return {
            "device_name": self.device_name,
            "is_connected": self.is_connected,
            "bpm": round(self.current_bpm, 1),
            "hrv_ms": round(self.current_hrv, 1),
            "biometric_tilt_score": tilt_score,
            "stress_category": category,
            "risk_level": risk_level,
            "is_stress_critical": tilt_score >= self.stress_threshold,
            "last_update_timestamp": self.last_update_time
        }

    def is_stress_critical(self) -> bool:
        """Returns True if biometric tilt exceeds safety threshold (>75)."""
        tilt = self.calculate_biometric_tilt_score(self.current_bpm, self.current_hrv)
        return tilt >= self.stress_threshold

    @staticmethod
    def _get_category(tilt_score: float) -> Tuple[str, str]:
        if tilt_score >= 75.0:
            return "ACUTE_PANIC_TILT", "CRITICAL_VETO"
        elif tilt_score >= 50.0:
            return "ELEVATED_STRESS", "WARNING"
        return "CALM_FLOW_STATE", "NORMAL"

biometric_watch_bridge = BiometricWatchBridge()