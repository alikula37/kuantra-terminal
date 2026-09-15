"""OS-keychain-backed exchange credential service for Kuantra Terminal.

SQLite stores only non-secret metadata and keychain account references. Secret values
are never persisted in SQLite and are never logged.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import ccxt
from app.db.sqlite_driver import sqlite_driver
from app.services.security.credential_store import (
    CredentialStoreUnavailable,
    credential_store,
)

logger = logging.getLogger("exchange_credentials")


def _safe_exchange_error_message(error_type: str) -> str:
    """Generic, secret-free connection error text; never echoes upstream data."""
    return {
        "AUTHENTICATION_ERROR": "The exchange rejected the API credentials.",
        "NETWORK_ERROR": "Network error while connecting to the exchange.",
        "UNEXPECTED_ERROR": "Unexpected error while testing the exchange connection.",
    }.get(error_type, "The exchange connection could not be verified.")


class ExchangeCredentialsManager:
    """Manages OS-keychain-backed exchange credentials and connection handshakes.

    SQLite stores only metadata and keychain account references. Legacy encrypted
    ``exchange_credentials`` rows are deliberately not decrypted by this manager; users
    must re-enter those credentials into the OS credential manager.
    """

    SUPPORTED_EXCHANGES = {
        "binance_spot": {"name": "Binance Spot", "ccxt_id": "binance", "requires_passphrase": False},
        "binance_futures": {"name": "Binance USDⓈ-M Futures", "ccxt_id": "binanceusdm", "requires_passphrase": False},
        "okx": {"name": "OKX V5 Unified", "ccxt_id": "okx", "requires_passphrase": True},
    }
    # Phase 1 only permits credentials to be used for evidence ingestion and
    # connectivity checks.  A future Phase 4 write-capable credential must be
    # an explicit, separately reviewed capability; it is not accepted here.
    READ_ONLY_SCOPE = "READ_ONLY"

    @staticmethod
    def _credential_ref(exchange_id: str, field: str) -> str:
        """Build a stable account name; the value is stored only by the OS keychain."""

        return f"exchange/{exchange_id}/{field}"

    @staticmethod
    def _require_credential_store() -> None:
        # The factory permits an explicit ``memory-test`` provider only under
        # KUANTRA_TEST_MODE; normal application processes can only receive an
        # unavailable store or a persistent OS keychain here.
        if not credential_store.status.available:
            raise CredentialStoreUnavailable(
                credential_store.status.reason
                or "An OS credential manager is required before credentials can be saved."
            )

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
        is_active: bool = True,
        permission_scope: str = READ_ONLY_SCOPE,
    ) -> Dict[str, Any]:
        """Stores secret values in the OS keychain and only refs/metadata in SQLite."""
        exchange_id = exchange_id.lower().strip()
        if exchange_id not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange '{exchange_id}'. Must be one of {list(self.SUPPORTED_EXCHANGES.keys())}")

        api_key = (api_key or "").strip()
        api_secret = (api_secret or "").strip()
        passphrase = passphrase.strip() if passphrase else None
        if not api_key or not api_secret:
            raise ValueError("API Key and API Secret are strictly required.")

        permission_scope = str(permission_scope or "").strip().upper()
        if permission_scope != self.READ_ONLY_SCOPE:
            raise ValueError(
                "Only READ_ONLY credential scope is available before Phase 4 execution gates."
            )

        self._require_credential_store()

        display_name = name or self.SUPPORTED_EXCHANGES[exchange_id]["name"]
        now_ts = datetime.now(timezone.utc).isoformat()
        refs = {
            "api_key": self._credential_ref(exchange_id, "api_key"),
            "api_secret": self._credential_ref(exchange_id, "api_secret"),
            "passphrase": self._credential_ref(exchange_id, "passphrase") if passphrase else None,
        }
        written_refs: List[str] = []

        try:
            for field, value in (("api_key", api_key), ("api_secret", api_secret), ("passphrase", passphrase)):
                ref = refs[field]
                if value and ref:
                    credential_store.set_secret(ref, value)
                    written_refs.append(ref)

            with sqlite_driver.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO exchange_credential_refs (
                        exchange_id, name, api_key_ref, api_secret_ref, passphrase_ref,
                        permission_scope, is_testnet, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(exchange_id) DO UPDATE SET
                        name = excluded.name,
                        api_key_ref = excluded.api_key_ref,
                        api_secret_ref = excluded.api_secret_ref,
                        passphrase_ref = excluded.passphrase_ref,
                        permission_scope = excluded.permission_scope,
                        is_testnet = excluded.is_testnet,
                        is_active = excluded.is_active,
                        updated_at = excluded.updated_at
                """, (
                    exchange_id,
                    display_name,
                    refs["api_key"],
                    refs["api_secret"],
                    refs["passphrase"],
                    permission_scope,
                    1 if is_testnet else 0,
                    1 if is_active else 0,
                    now_ts,
                    now_ts,
                ))
                # A replaced credential must not leave a decryptable legacy copy in SQLite.
                cur.execute("DELETE FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
                conn.commit()
        except Exception:
            for ref in written_refs:
                try:
                    credential_store.delete_secret(ref)
                except Exception:  # noqa: BLE001
                    logger.error("[EXCHANGE-CREDENTIALS] Failed to roll back keychain account %s", ref)
            raise

        logger.info("[EXCHANGE-CREDENTIALS] OS-keychain credentials saved for '%s' (%s).", exchange_id, display_name)

        return {
            "exchange_id": exchange_id,
            "name": display_name,
            "api_key_masked": self.mask_key(api_key),
            "has_passphrase": bool(passphrase),
            "is_testnet": bool(is_testnet),
            "is_active": bool(is_active),
            "storage_backend": credential_store.status.backend,
            "updated_at": now_ts
        }

    def get_decrypted_credentials(self, exchange_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves secret values from the OS keychain; never decrypts legacy SQLite rows."""
        exchange_id = exchange_id.lower().strip()
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
            legacy_row = cur.fetchone()
            cur.execute("SELECT * FROM exchange_credential_refs WHERE exchange_id = ?", (exchange_id,))
            row = cur.fetchone()
        if not row:
            if legacy_row:
                logger.warning("[EXCHANGE-CREDENTIALS] Legacy SQLite credential ignored for '%s'; re-enter it in Settings.", exchange_id)
            return None

        data = dict(row)
        try:
            api_key = credential_store.get_secret(data["api_key_ref"])
            api_secret = credential_store.get_secret(data["api_secret_ref"])
            passphrase = credential_store.get_secret(data["passphrase_ref"]) if data.get("passphrase_ref") else None
            if not api_key or not api_secret:
                logger.error("[EXCHANGE-CREDENTIALS] Keychain entries missing for '%s'.", exchange_id)
                return None
            return {
                "exchange_id": exchange_id,
                "name": data["name"],
                "api_key": api_key,
                "api_secret": api_secret,
                "passphrase": passphrase,
                "permission_scope": str(data.get("permission_scope") or self.READ_ONLY_SCOPE).upper(),
                "is_testnet": bool(data["is_testnet"]),
                "is_active": bool(data["is_active"]),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
                "storage_backend": credential_store.status.backend,
            }
        except CredentialStoreUnavailable as exc:
            logger.error("[EXCHANGE-CREDENTIALS] Keychain unavailable for '%s': %s", exchange_id, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("[EXCHANGE-CREDENTIALS] Keychain read failure for '%s': %s", exchange_id, exc)
            return None

    def list_configured_exchanges(self) -> List[Dict[str, Any]]:
        """Lists supported exchanges without returning any secret value."""
        configured_map = {}
        legacy_map = {}
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM exchange_credential_refs")
            for row in cur.fetchall():
                d = dict(row)
                configured_map[d["exchange_id"]] = d
            cur.execute("SELECT exchange_id FROM exchange_credentials")
            legacy_map = {row["exchange_id"] for row in cur.fetchall()}

        result = []
        for ex_id, meta in self.SUPPORTED_EXCHANGES.items():
            if ex_id in configured_map:
                row = configured_map[ex_id]
                try:
                    key_value = credential_store.get_secret(row["api_key_ref"])
                    masked = self.mask_key(key_value) if key_value else "KEYCHAIN_ENTRY_MISSING"
                    available = bool(key_value)
                except CredentialStoreUnavailable:
                    masked = "KEYCHAIN_UNAVAILABLE"
                    available = False

                result.append({
                    "exchange_id": ex_id,
                    "name": row["name"],
                    "is_configured": True,
                    "credentials_available": available,
                    "api_key_masked": masked,
                    "requires_passphrase": meta["requires_passphrase"],
                    "has_passphrase": bool(row.get("passphrase_ref")),
                    "permission_scope": str(row.get("permission_scope") or self.READ_ONLY_SCOPE).upper(),
                    "is_testnet": bool(row["is_testnet"]),
                    "is_active": bool(row["is_active"]),
                    "storage_backend": credential_store.status.backend,
                    "legacy_detected": False,
                    "updated_at": row["updated_at"]
                })
            else:
                result.append({
                    "exchange_id": ex_id,
                    "name": meta["name"],
                    "is_configured": False,
                    "credentials_available": False,
                    "api_key_masked": "",
                    "requires_passphrase": meta["requires_passphrase"],
                    "has_passphrase": False,
                    "permission_scope": self.READ_ONLY_SCOPE,
                    "is_testnet": False,
                    "is_active": False,
                    "storage_backend": "LEGACY_SQLITE_DISABLED" if ex_id in legacy_map else "OS_KEYCHAIN_REQUIRED",
                    "legacy_detected": ex_id in legacy_map,
                    "updated_at": None
                })

        return result

    def delete_credentials(self, exchange_id: str) -> bool:
        """Removes keychain entries and non-secret metadata."""
        exchange_id = exchange_id.lower().strip()
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT api_key_ref, api_secret_ref, passphrase_ref FROM exchange_credential_refs WHERE exchange_id = ?", (exchange_id,))
            ref_row = cur.fetchone()
            cur.execute("SELECT 1 FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
            legacy_row = cur.fetchone()

        # A legacy row has no keychain account to clean. Allow explicit purge even when
        # the current machine has no OS keychain, so an upgrade can remove old ciphertext.
        if not ref_row and legacy_row:
            with sqlite_driver.get_connection() as conn:
                deleted = conn.execute("DELETE FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,)).rowcount > 0
                conn.commit()
            logger.info("[EXCHANGE-CREDENTIALS] Legacy credentials purged for '%s'.", exchange_id)
            return deleted

        self._require_credential_store()

        if ref_row:
            for ref in (ref_row["api_key_ref"], ref_row["api_secret_ref"], ref_row["passphrase_ref"]):
                if ref:
                    credential_store.delete_secret(ref)

        # Delete metadata only after keychain deletion succeeds; otherwise a failed
        # keychain operation would orphan a still-live secret with no reference.
        with sqlite_driver.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM exchange_credentials WHERE exchange_id = ?", (exchange_id,))
            legacy_deleted = cur.rowcount > 0
            cur.execute("DELETE FROM exchange_credential_refs WHERE exchange_id = ?", (exchange_id,))
            ref_deleted = cur.rowcount > 0
            conn.commit()

        logger.info("[EXCHANGE-CREDENTIALS] Credentials deleted for '%s'.", exchange_id)
        return bool(legacy_deleted or ref_deleted)

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
            logger.warning("[EXCHANGE-TEST] Authentication failed for '%s' (details withheld).", exchange_id)
            return {
                "success": False,
                "error_type": "AUTHENTICATION_ERROR",
                "message": _safe_exchange_error_message("AUTHENTICATION_ERROR"),
            }
        except ccxt.NetworkError as e:
            logger.warning("[EXCHANGE-TEST] Network error reaching '%s' (details withheld).", exchange_id)
            return {
                "success": False,
                "error_type": "NETWORK_ERROR",
                "message": _safe_exchange_error_message("NETWORK_ERROR"),
            }
        except Exception as e:
            logger.error("[EXCHANGE-TEST] Unexpected error testing '%s' (details withheld).", exchange_id)
            return {
                "success": False,
                "error_type": "UNEXPECTED_ERROR",
                "message": _safe_exchange_error_message("UNEXPECTED_ERROR"),
            }


exchange_credentials_manager = ExchangeCredentialsManager()
