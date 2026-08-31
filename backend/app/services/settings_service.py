"""
Runtime UI & System Settings Service for Kuantra Terminal.
Provides persistent state management for Theme, i18n Locales, Paper Balance, and Trading Modes.
"""

import json
import logging
from typing import Dict, Any, Optional
from app.db.sqlite_driver import sqlite_driver
from app.core.security import vault

logger = logging.getLogger("settings_service")

class SettingsService:
    """Manages persistent terminal configuration in SQLite user_settings."""

    DEFAULT_SETTINGS = {
        "first_boot_completed": False,
        "active_theme": "dark",
        "active_locale": "en",
        "trading_mode": "paper",
        "user_initial_balance": 0.0,
        "initial_balance": 0.0,
        "paper_balance": 0.0,
        "ai_mode": "local_gguf"
    }

    def get_settings(self) -> Dict[str, Any]:
        """Retrieves and normalizes all terminal configuration settings."""
        settings = dict(self.DEFAULT_SETTINGS)
        raw_settings = sqlite_driver.get_all_settings()

        for k, v in raw_settings.items():
            if k == "first_boot_completed":
                settings["first_boot_completed"] = str(v).lower() in ("true", "1", '"true"')
            elif k in ("user_initial_balance", "initial_balance", "paper_balance"):
                try:
                    settings[k] = float(v)
                except (ValueError, TypeError):
                    settings[k] = 0.0
            elif k in self.DEFAULT_SETTINGS:
                try:
                    # Parse json if stored with quotes
                    parsed = json.loads(v)
                    settings[k] = parsed
                except Exception:
                    settings[k] = v
            else:
                settings[k] = v

        return settings

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a single setting key with fallback."""
        settings = self.get_settings()
        return settings.get(key, default)

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Persists updated configuration into SQLite user_settings."""
        for key, value in updates.items():
            if value is not None:
                if isinstance(value, bool):
                    sqlite_driver.set_setting(key, "true" if value else "false")
                else:
                    sqlite_driver.set_setting(key, str(value))

        logger.info(f"[SETTINGS] Updated settings keys: {list(updates.keys())}")
        return self.get_settings()

    def store_vault_secret(self, key: str, value: str) -> None:
        """Encrypts API key with Argon2id / AES-256-GCM and stores in Stronghold Vault."""
        normalized_key = key.strip().upper()
        vault.store_secret(normalized_key, value.strip())
        logger.info(f"[VAULT] Securely stored credential for {normalized_key}")

settings_service = SettingsService()