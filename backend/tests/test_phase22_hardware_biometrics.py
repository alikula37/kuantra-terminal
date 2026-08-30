import pytest
from app.services.biometrics.hardware_driver import (
    hardware_biometrics_driver,
    HardwareBiometricDriver,
    BLEGATTPacketDecoder,
    SignalQualityFilter
)
from app.services.biometrics.stress_interceptor import (
    stress_interceptor,
    HardwareStressInterceptor,
    HRVMathEngine
)

class TestPhase22HardwareBiometricsAndLockout:
    """Test suite for Wearables BLE/HID Drivers, HRV/EDA Math, and Biometric Trading Lockout."""

    def test_ble_sensor_telemetry_and_sqi(self):
        # 1. Decode 8-bit Heart Rate with RR Interval
        # Flags = 0x10 (has RR), BPM = 72, RR = 850ms (850*1024/1000 = 870 = 0x0366)
        raw_gatt = bytes([0x10, 72, 0x66, 0x03])
        res = BLEGATTPacketDecoder.decode_heart_rate_measurement(raw_gatt)
        assert res["bpm"] == 72
        assert len(res["rr_intervals_ms"]) == 1
        assert 840.0 <= res["rr_intervals_ms"][0] <= 860.0

        # 2. Signal Quality Index (Clean Signal)
        sqi, is_valid = SignalQualityFilter.calculate_sqi(
            bpm=70.0,
            rr_intervals_ms=[850.0, 840.0, 860.0],
            eda_us=2.5
        )
        assert sqi >= 85.0
        assert is_valid is True

        # 3. Noisy Artifact Signal
        sqi_noisy, is_valid_noisy = SignalQualityFilter.calculate_sqi(
            bpm=240.0, # Unphysiological
            rr_intervals_ms=[150.0, 2500.0], # Severe artifacts
            eda_us=65.0
        )
        assert sqi_noisy < 60.0
        assert is_valid_noisy is False

    def test_hrv_rmssd_and_eda_stress_math(self):
        rr_series = [800.0, 850.0, 820.0, 880.0, 840.0, 860.0]
        metrics = HRVMathEngine.compute_time_domain_metrics(rr_series)
        assert metrics["rmssd_ms"] > 0
        assert metrics["sdnn_ms"] > 0
        assert metrics["pnn50_pct"] >= 0

        # Composite S_bio calculation (Calm State)
        calm_sbio = HRVMathEngine.compute_composite_s_bio(bpm=62.0, rmssd_ms=55.0, eda_us=1.8)
        assert calm_sbio["s_bio"] < 60.0
        assert calm_sbio["hrv_stress_component"] < 40.0

        # Composite S_bio calculation (High Stress State)
        stressed_sbio = HRVMathEngine.compute_composite_s_bio(bpm=120.0, rmssd_ms=12.0, eda_us=18.0)
        assert stressed_sbio["s_bio"] >= 75.0

    def test_stress_interceptor_lockout_and_veto(self):
        interceptor = HardwareStressInterceptor()

        # 1. Nominal State
        nom_state = interceptor.evaluate_live_state(manual_bpm=65.0, manual_eda=2.0)
        assert nom_state["lockout_state"] == "NOMINAL"
        gate_nom = interceptor.evaluate_order_gate(requested_size=2.0, live_state=nom_state)
        assert gate_nom["decision"] == "APPROVED_UNRESTRICTED"
        assert gate_nom["approved_size"] == 2.0

        # 2. Elevated Stress State (60 <= S_bio < 75)
        elev_state = interceptor.evaluate_live_state(manual_bpm=88.0, manual_eda=7.5)
        assert elev_state["lockout_state"] == "ELEVATED_STRESS"
        gate_elev = interceptor.evaluate_order_gate(requested_size=2.0, live_state=elev_state)
        assert gate_elev["decision"] == "APPROVED_CLAMPED_50_PERCENT"
        assert gate_elev["approved_size"] == 1.0  # Clamped to 50%

        # 3. Critical Tilt Lockout State (S_bio >= 75)
        tilt_state = interceptor.evaluate_live_state(manual_bpm=125.0, manual_eda=22.0)
        assert tilt_state["lockout_state"] in ("CRITICAL_TILT_LOCKOUT", "PANIC_EMERGENCY")
        assert tilt_state["lockout_remaining_seconds"] > 0

        gate_tilt = interceptor.evaluate_order_gate(requested_size=2.0, live_state=tilt_state)
        assert gate_tilt["decision"] == "VETO_BIOMETRIC_LOCKOUT_ACTIVE"
        assert gate_tilt["approved_size"] == 0.0

    def test_fido2_lockout_override(self):
        interceptor = HardwareStressInterceptor()
        # Force Critical Tilt Lockout
        interceptor.evaluate_live_state(manual_bpm=130.0, manual_eda=25.0)
        assert interceptor.lockout_state in ("CRITICAL_TILT_LOCKOUT", "PANIC_EMERGENCY")

        # Attempt invalid signature override
        bad_res = interceptor.override_lockout_fido2(challenge_signature="short")
        assert bad_res["status"] == "OVERRIDE_REJECTED"

        # Valid FIDO2 hardware passkey override
        good_res = interceptor.override_lockout_fido2(
            challenge_signature="WEBAUTHN_AUTHENTICATOR_VALID_ATTESTATION_SIG990123",
            passkey_user_id="TRADER_ADMIN"
        )
        assert good_res["status"] == "LOCKOUT_OVERRIDDEN_SUCCESS"
        assert good_res["new_state"] == "NOMINAL"
        assert len(interceptor.override_audit_trail) > 0

    def test_biometrics_api_endpoints(self):
        driver = HardwareBiometricDriver()
        devices = driver.scan_devices()
        assert len(devices) >= 4

        conn = driver.connect_device("GARMIN-DUAL-4421", "BLE")
        assert conn["status"] == "CONNECTED"
        assert conn["device_id"] == "GARMIN-DUAL-4421"

        telemetry = driver.get_live_raw_telemetry()
        assert telemetry["bpm"] > 0
        assert "signal_quality_index_pct" in telemetry