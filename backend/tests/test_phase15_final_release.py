import pytest
from app.api.mobile_bridge import mobile_companion_bridge, MobileCompanionBridge
from app.services.biometrics.panic_switch import panic_kill_switch, PanicKillSwitchEngine
from app.services.security.passkey_vault import webauthn_passkey_vault, WebAuthnPasskeyVault
from app.services.execution.order_router import order_router
from app.services.execution.risk_interceptor import risk_interceptor
from app.services.biometrics.watch_bridge import biometric_watch_bridge
from app.core.config import settings

class TestPhase15MobileAndFinalRelease:
    """Test suite for Mobile Companion, Emergency Panic Kill-Switch, WebAuthn Passkeys, and v2.0 Production Release."""

    @pytest.fixture
    def compliant_account(self, monkeypatch):
        """Keep the happy-path router test independent from persistent journal state."""
        compliant = {
            "overall_status": "COMPLIANT",
            "daily_loss_pct_of_account": 0.0,
            "daily_loss_limit_pct": 5.0,
            "rules": [{"rule": "Daily Max Loss", "utilization_pct": 0.0}],
        }
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.compliance_engine.evaluate_compliance",
            lambda *args, **kwargs: compliant,
        )
        monkeypatch.setattr(
            "app.quant.risk_guard.compliance_engine.evaluate_compliance",
            lambda *args, **kwargs: compliant,
        )

    def test_mobile_companion_pairing_and_revocation(self):
        bridge = MobileCompanionBridge()
        # 1. Generate QR
        qr_data = bridge.generate_pairing_qr_payload()
        token = qr_data["pairing_token"]
        assert token.startswith("KNT-PAIR-")
        assert qr_data["expires_at"] > 0

        # 2. Pair Device
        pair_res = bridge.verify_and_pair_device(
            pairing_token=token,
            device_id="DEV-UNITTEST-IPHONE",
            device_name="Trader iPhone Test",
            platform="iOS"
        )
        assert pair_res["status"] == "PAIRED_SUCCESS"
        assert pair_res["device_id"] == "DEV-UNITTEST-IPHONE"

        # 3. List and Revoke
        devs = bridge.list_paired_devices()
        assert any(d["device_id"] == "DEV-UNITTEST-IPHONE" for d in devs)

        revoked = bridge.revoke_device("DEV-UNITTEST-IPHONE")
        assert revoked is True
        assert not any(d["device_id"] == "DEV-UNITTEST-IPHONE" for d in bridge.list_paired_devices())

    def test_wearable_emergency_panic_kill_switch_lifecycle(self):
        engine = PanicKillSwitchEngine()
        assert engine.is_locked_down is False

        # 1. Trigger Panic Kill Switch
        event = engine.trigger_emergency_kill_switch(
            source="WEARABLE_APPLE_WATCH",
            reason="Acute Volatility Spike"
        )
        assert event["status"] == "TERMINAL_LOCKED_DOWN"
        assert engine.is_locked_down is True

        st = engine.get_lockdown_status()
        assert st["is_locked_down"] is True
        assert st["lockdown_reason"] == "Acute Volatility Spike"

        # 2. Disarm with invalid PIN
        with pytest.raises(ValueError, match="Invalid Disarm PIN"):
            engine.disarm_lockdown("wrong_pin")

        # 3. Disarm with valid PIN
        disarm_res = engine.disarm_lockdown("1234")
        assert disarm_res["status"] == "DISARMED"
        assert engine.is_locked_down is False

    def test_webauthn_hardware_passkey_enclave_and_high_value_gate(self):
        vault = WebAuthnPasskeyVault(high_value_threshold_usd=50000.0)
        # 1. Registration
        reg = vault.register_passkey(
            credential_id="CRED-YUBIKEY-TEST",
            public_key="pubkey-test-fido2",
            device_name="YubiKey 5C NFC"
        )
        assert reg["status"] == "ACTIVE_HARDWARE_ENCLAVE"

        # 2. Challenge & Assertion
        ch = vault.generate_auth_challenge("HIGH_VALUE_ORDER")
        assert len(ch["challenge"]) == 64

        valid = vault.verify_passkey_assertion(
            challenge=ch["challenge"],
            credential_id="CRED-YUBIKEY-TEST",
            assertion_signature="valid-assertion-signature-string"
        )
        assert valid is True

        # 3. High-Value Gate Check
        assert vault.is_passkey_required_for_order(qty=1.0, price=65000.0) is True
        assert vault.is_passkey_required_for_order(qty=0.5, price=65000.0) is False

    def test_end_to_end_institutional_order_routing_pipeline(self, compliant_account):
        # Ensure calm biometrics and psychology tilt
        biometric_watch_bridge.update_telemetry(bpm=58.0, hrv=85.0)
        orig_tilt_limit = risk_interceptor.max_allowed_tilt_score
        risk_interceptor.max_allowed_tilt_score = 95.0

        try:
            # Dispatch standard order
            order_res = order_router.route_order({
                "symbol": "BTCUSDT",
                "side": "BUY",
                "qty": 0.5,
                "price": 64800.0,
                "exchange": "BINANCE",
                "stop_loss": 63800.0,
                "take_profit": 67000.0
            })
            assert order_res["status"] == "EXECUTED"
            assert order_res["order"]["exchange"] == "BINANCE"
        finally:
            risk_interceptor.max_allowed_tilt_score = orig_tilt_limit

    def test_final_production_pyinstaller_release_spec(self):
        import pathlib
        repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
        spec_path = repo_root / "packaging" / "kuantra.spec"
        assert spec_path.exists(), "packaging/kuantra.spec must exist"

        spec_source = spec_path.read_text(encoding="utf-8")
        assert 'APP_NAME = "Kuantra Terminal"' in spec_source
        assert "com.kuantra.terminal" in spec_source
