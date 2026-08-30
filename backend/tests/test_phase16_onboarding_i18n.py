import os
import json
import pytest
from app.services.settings_service import settings_service, SettingsService
from app.db.sqlite_driver import sqlite_driver
from app.core.security import vault

class TestPhase16OnboardingAndI18n:
    """Test suite for Onboarding Wizard, Theme Engine, i18n Dictionary Parity, and Stronghold Ingestion."""

    def test_onboarding_wizard_flag_persistence(self):
        # 1. Reset state
        sqlite_driver.set_setting("first_boot_completed", "false")
        st = settings_service.get_settings()
        assert st["first_boot_completed"] is False

        # 2. Complete Onboarding with custom settings
        updated = settings_service.update_settings({
            "first_boot_completed": True,
            "trading_mode": "paper",
            "paper_balance": 150000.0,
            "active_theme": "light",
            "active_locale": "tr",
            "ai_mode": "local_gguf"
        })

        assert updated["first_boot_completed"] is True
        assert updated["trading_mode"] == "paper"
        assert updated["paper_balance"] == 150000.0
        assert updated["active_theme"] == "light"
        assert updated["active_locale"] == "tr"

        # Verify DB directly
        assert sqlite_driver.get_setting("first_boot_completed") == "true"
        assert sqlite_driver.get_setting("active_theme") == "light"

    def test_locale_dictionary_integrity(self):
        frontend_locales_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "frontend", "src", "locales"
        )
        assert os.path.exists(frontend_locales_dir)

        en_path = os.path.join(frontend_locales_dir, "en.json")
        tr_path = os.path.join(frontend_locales_dir, "tr.json")
        de_path = os.path.join(frontend_locales_dir, "de.json")

        assert os.path.exists(en_path)
        assert os.path.exists(tr_path)
        assert os.path.exists(de_path)

        with open(en_path, "r", encoding="utf-8") as f:
            en_dict = json.load(f)
        with open(tr_path, "r", encoding="utf-8") as f:
            tr_dict = json.load(f)
        with open(de_path, "r", encoding="utf-8") as f:
            de_dict = json.load(f)

        def extract_leaf_paths(d, prefix=""):
            paths = set()
            for k, v in d.items():
                p = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    paths.update(extract_leaf_paths(v, p))
                else:
                    paths.add(p)
            return paths

        en_keys = extract_leaf_paths(en_dict)
        tr_keys = extract_leaf_paths(tr_dict)
        de_keys = extract_leaf_paths(de_dict)

        # Validate 1:1 key parity
        missing_in_tr = en_keys - tr_keys
        extra_in_tr = tr_keys - en_keys
        missing_in_de = en_keys - de_keys
        extra_in_de = de_keys - en_keys

        assert not missing_in_tr, f"TR dictionary missing keys: {missing_in_tr}"
        assert not extra_in_tr, f"TR dictionary has extra keys: {extra_in_tr}"
        assert not missing_in_de, f"DE dictionary missing keys: {missing_in_de}"
        assert not extra_in_de, f"DE dictionary has extra keys: {extra_in_de}"

        # Ensure essential namespaces are present
        required_namespaces = ["nav", "onboarding", "dashboard", "orderflow", "metrics", "vault", "settings", "alerts"]
        for ns in required_namespaces:
            assert ns in en_dict
            assert ns in tr_dict
            assert ns in de_dict

    def test_theme_and_color_palette_tokens(self):
        # Test Dark Theme persistence
        dark_res = settings_service.update_settings({"active_theme": "dark"})
        assert dark_res["active_theme"] == "dark"

        # Test Light Theme persistence
        light_res = settings_service.update_settings({"active_theme": "light"})
        assert light_res["active_theme"] == "light"

        # Reset back to dark
        settings_service.update_settings({"active_theme": "dark"})

    def test_vault_credentials_encryption_onboarding(self):
        # Ingest credentials as done during onboarding Step 2
        credentials_to_store = {
            "TWELVEDATA_API_KEY": "td_secret_key_998877",
            "POLYGON_API_KEY": "poly_secret_key_112233",
            "BINANCE_API_KEY": "bin_api_key_445566",
            "BINANCE_API_SECRET": "bin_sec_key_778899",
            "OKX_API_KEY": "okx_api_key_001122"
        }

        for k, v in credentials_to_store.items():
            settings_service.store_vault_secret(k, v)

        # Verify encryption: raw memory secrets must not equal plaintext
        for k, plaintext_val in credentials_to_store.items():
            ciphertext = vault._secrets.get(k)
            assert ciphertext is not None
            assert ciphertext != plaintext_val.encode("utf-8")

            # Decrypted secret matches original plaintext
            decrypted = vault.get_secret(k)
            assert decrypted == plaintext_val