"""
Secure Exchange API Credentials & Key Management Service for Kuantra Terminal.
Stores AES-256-GCM encrypted API keys, secrets, and passphrases in SQLite.
Enforces zero-plaintext logging and machine-derived authentication keys.
"""

import os
import platform
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import ccxt
from app.core.security import StrongholdVault, vault
from app.db.sqlite_driver import sqlite_driver

logger = logging.getLogger("exchange_credentials")


class ExchangeCredentialsManager:
    """Manages encrypted exchange credentials and connection handshakes."""

    SUPPORTED_EXCHANGES = {
        "binance_spot": {"name": "Binance Spot", "ccxt_id": "binance", "requires_passphrase": False},
        "binance_futures": {"name": "Binance USDⓈ-M Futures", "ccxt_id": "binanceusdm", "requires_passphrase": False},
        "okx": {"name": "OKX V5 Unified", "ccxt_id": "okx", "requires_passphrase": True},
    }

    def __init__(self):
        self._encryption_passphrase = self._derive_system_passphrase()

    @staticmethod
    def _derive_system_passphrase() -> str:
        """Derives machine-tied encryption passphrase for local credential protection."""
        env_key = os.environ.get("KUANTRA_MASTER_KEY")
        if env_key:
            return env_key
        node = platform.node() or "kuantra-default-node"
        sys_id = f"kuantra-vault-aes256-{node}-{platform.system()}"
        return sys_id

    @staticmethod
    def mask_key(key: Optional[str]) -> str:
        """Masks API key for safe UI rendering (e.g. abcd...1234)."""
        if not key:
            return ""
        if len(key) <= 8:
            return "********"
        return f"{key[:4]}...{key[-4:]}"

    def save_credentials(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        passphrase: Optional[str] = None,
        name: Optional[str] = None,
        is_testnet: bool = False,
        is_active: bool = True
    ) -> Dict[str, Any]:
        """Encrypts and persists exchange credentials into SQLite."""
        exchange_id = exchange_id.lower().strip()
        if exchange_id not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange '{exchange_id}'. Must be one of {list(self.SUPPORTED_EXCHANGES.keys())}")

        if not api_key or not api_secret:
            raise ValueError("API Key and API Secret are strictly required.")

        display_name = name or self.SUPPORTED_EXCHANGES[exchange_id]["name"]

        # Encrypt secrets with AES-256-GCM
        api_key_enc = StrongholdVault.encrypt_payload(api_key.strip(), self._encryption_passphrase)
        api_secret_enc = StrongholdVault.encrypt_payload(api_secret.strip(), self._encryption_passphrase)
        passphrase_enc = (
            StrongholdVault.encrypt_payload(passphrase.strip(), self._encryption_passphrase)
            if passphrase and passphrase.strip()
            else None
        )

        now_ts = datetime.now(timezone.utc).isoformat()

        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO exchange_credentials (
                    exchange_id, name, api_key_encrypted, api_secret_encrypted,
                    passphrase_encrypted, is_testnet, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exchange_id,
                display_name,
                api_key_enc,
                api_secret_enc,
                passphrase_enc,
                1 if is_testnet else 0,
                1 if is_active else 0,
                now_ts,
                now_ts
            ))
            conn.commit()

        # Cache in memory vault for active session
        vault.store_secret(f"{exchange_id.upper()}_API_KEY", api_key.strip())
        vault.store_secret(f"{exchange_id.upper()}_API_SECRET", api_secret.strip())
        if passphrase:
            vault.store_secret(f"{exchange_id.upper()}_API_PASSPHRASE", passphrase.strip())

        logger.info(f"[EXCHANGE-CREDENTIALS] Encrypted credentials saved for '{exchange_id}' ({display_name}).")

        return {
            "exchange_id": exchange_id,
            "name": display_name,
            "api_key_masked": self.mask_key(api_key),
            "has_passphrase": bool(passphrase),
            "is_testnet": bool(is_testnet),
            "is_active": bool(is_active),
            "updated_at": now_ts
        }

    def get_decrypted_credentials(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves and decrypts exchange credentials."""
        exchange_id = exchange_id.lower().strip()
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
            row = cur.fetchone()
            if not row:
                return None

            data = dict(row)

        try:
            api_key = StrongholdVault.decrypt_payload(data["api_key_encrypted"], self._encryption_passphrase)
            api_secret = StrongholdVault.decrypt_payload(data["api_secret_encrypted"], self._encryption_passphrase)
            passphrase = (
                StrongholdVault.decrypt_payload(data["passphrase_encrypted"], self._encryption_passphrase)
                if data.get("passphrase_encrypted")
                else None
            )

            return {
                "exchange_id": exchange_id,
                "name": data["name"],
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": passphrase,
                "is_testnet": bool(data["is_testnet"]),
                "is_active": bool(data["is_active"]),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"]
            }
        except Exception as e:
            logger.error(f"[EXCHANGE-CREDENTIALS] Decryption failure for '{exchange_id}': {e}")
            return None

    def list_configured_exchanges(self) -> List[Dict[str, Any]]:
        """Lists all supported exchanges with their configuration and encrypted status."""
        configured_map = {}
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM exchange_credentials")
            for row in cur.fetchall():
                d = dict(row)
                configured_map[d["exchange_id"]] = d

        result = []
        for ex_id, meta in self.SUPPORTED_EXCHANGES.items():
            if ex_id in configured_map:
                row = configured_map[ex_id]
                # Decrypt key only for masking
                try:
                    decrypted_key = StrongholdVault.decrypt_payload(row["api_key_encrypted"], self._encryption_passphrase)
                    masked = self.mask_key(decrypted_key)
                except Exception:
                    masked = "CORRUPT_KEY"

                result.append({
                    "exchange_id": ex_id,
                    "name": row["name"],
                    "is_configured": True,
                    "api_key_masked": masked,
                    "requires_passphrase": meta["requires_passphrase"],
                    "has_passphrase": bool(row.get("passphrase_encrypted")),
                    "is_testnet": bool(row["is_testnet"]),
                    "is_active": bool(row["is_active"]),
                    "updated_at": row["updated_at"]
                })
            else:
                result.append({
                    "exchange_id": ex_id,
                    "name": meta["name"],
                    "is_configured": False,
                    "api_key_masked": "",
                    "requires_passphrase": meta["requires_passphrase"],
                    "has_passphrase": False,
                    "is_testnet": False,
                    "is_active": False,
                    "updated_at": None
                })

        return result

    def delete_credentials(self, exchange_id: str) -> bool:
        """Removes credentials from SQLite and in-memory vault."""
        exchange_id = exchange_id.lower().strip()
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
            deleted = cur.rowcount > 0
            conn.commit()

        vault.delete_secret(f"{exchange_id.upper()}_API_KEY")
        vault.delete_secret(f"{exchange_id.upper()}_API_SECRET")
        vault.delete_secret(f"{exchange_id.upper()}_API_PASSPHRASE")

        logger.info(f"[EXCHANGE-CREDENTIALS] Credentials deleted for '{exchange_id}'.")
        return deleted

    def test_connection(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        is_testnet: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Genuinely verifies exchange API connectivity via CCXT fetch_balance().
        Propagates authentic network & authentication errors without mocking.
        """
        exchange_id = exchange_id.lower().strip()
        if exchange_id not in self.SUPPORTED_EXCHANGES:
            return {"success": False, "error": f"Unsupported exchange '{exchange_id}'"}

        # If credentials not passed directly, look up decrypted storage
        if not api_key or not api_secret:
            stored = self.get_decrypted_credentials(exchange_id)
            if not stored:
                return {"success": False, "error": f"No credentials configured for '{exchange_id}'"}
            api_key = stored["api_key"]
            api_secret = stored["api_secret"]
            passphrase = stored.get("passphrase")
            if is_testnet is None:
                is_testnet = stored.get("is_testnet", False)

        ccxt_id = self.SUPPORTED_EXCHANGES[exchange_id]["ccxt_id"]
        exchange_class = getattr(ccxt, ccxt_id, None)
        if not exchange_class:
            return {"success": False, "error": f"CCXT driver class '{ccxt_id}' not found."}

        config = {
            "apiKey": api_key.strip(),
            "secret": api_secret.strip(),
            "enableRateLimit": True,
            "timeout": 10000,
        }
        if passphrase:
            config["password"] = passphrase.strip()

        try:
            exchange_instance = exchange_class(config)
            if is_testnet:
                exchange_instance.set_sandbox_mode(True)

            balance = exchange_instance.fetch_balance()
            free_usdt = balance.get("free", {}).get("USDT", 0.0) or balance.get("free", {}).get("USD", 0.0) or 0.0
            total_usdt = balance.get("total", {}).get("USDT", 0.0) or balance.get("total", {}).get("USD", 0.0) or 0.0

            return {
                "success": True,
                "exchange_id": exchange_id,
                "exchange_name": self.SUPPORTED_EXCHANGES[exchange_id]["name"],
                "is_testnet": bool(is_testnet),
                "message": f"Successfully authenticated with {self.SUPPORTED_EXCHANGES[exchange_id]['name']}.",
                "free_quote_balance": float(free_usdt),
                "total_quote_balance": float(total_usdt),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except ccxt.AuthenticationError as e:
            logger.warning(f"[EXCHANGE-TEST] Authentication failed for '{exchange_id}': {e}")
            return {
                "success": False,
                "error_type": "AUTHENTICATION_ERROR",
                "message": f"Exchange rejected API Key / Secret signature: {str(e)}"
            }
        except ccxt.NetworkError as e:
            logger.warning(f"[EXCHANGE-TEST] Network error reaching '{exchange_id}': {e}")
            return {
                "success": False,
                "error_type": "NETWORK_ERROR",
                "message": f"Network error connecting to exchange: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[EXCHANGE-TEST] Unexpected error testing '{exchange_id}': {e}")
            return {
                "success": False,
                "error_type": "UNEXPECTED_ERROR",
                "message": str(e)
            }


exchange_credentials_manager = ExchangeCredentialsManager()
