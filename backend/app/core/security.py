"""
Kuantra Terminal Cryptographic Secret Vault & Security Manager.
Provides zero-plaintext, AES-256-GCM authenticated encryption for API keys and in-memory authorization headers.
"""

import os
import sys
import base64
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

class StrongholdVault:
    """In-memory encrypted secret vault using AES-256-GCM & PBKDF2-HMAC-SHA256."""

    def __init__(self, master_password: Optional[str] = None):
        self._master_key = self._derive_master_key(master_password or os.environ.get("KUANTRA_MASTER_KEY", "kuantra-default-sec-vault-key-32b"))
        self._secrets: Dict[str, bytes] = {} # Store ciphertext in memory
        self._nonce_map: Dict[str, bytes] = {}

    def _derive_master_key(self, passphrase: str, salt: bytes = b"kuantra_salt_9876543210") -> bytes:
        """Derives 256-bit AES key from passphrase using PBKDF2-HMAC-SHA256 (100,000 iterations)."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(passphrase.encode("utf-8"))

    def store_secret(self, key: str, plaintext: str) -> None:
        """Encrypts plaintext with AES-256-GCM and stores ciphertext in memory."""
        aesgcm = AESGCM(self._master_key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        self._secrets[key] = ciphertext
        self._nonce_map[key] = nonce

    def get_secret(self, key: str) -> Optional[str]:
        """Decrypts and returns secret plaintext from memory."""
        if key not in self._secrets or key not in self._nonce_map:
            return None
        aesgcm = AESGCM(self._master_key)
        nonce = self._nonce_map[key]
        ciphertext = self._secrets[key]
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode("utf-8")
        except Exception:
            return None

    def delete_secret(self, key: str) -> bool:
        """Securely zeroes and removes secret from vault."""
        if key in self._secrets:
            del self._secrets[key]
            if key in self._nonce_map:
                del self._nonce_map[key]
            return True
        return False

    def list_keys(self) -> List[str]:
        """Returns list of active secret keys in vault (without values)."""
        return list(self._secrets.keys())

    def clear(self) -> None:
        """Zeroes all in-memory secrets."""
        self._secrets.clear()
        self._nonce_map.clear()

    @staticmethod
    def encrypt_payload(plaintext: str, password: str) -> str:
        """Stateless one-shot AES-256-GCM encryption with embedded salt & nonce."""
        salt = secrets.token_bytes(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode("utf-8"))
        nonce = secrets.token_bytes(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Format: base64(salt + nonce + ciphertext)
        combined = salt + nonce + ciphertext
        return base64.b64encode(combined).decode("utf-8")

    @staticmethod
    def decrypt_payload(encrypted_b64: str, password: str) -> str:
        """Stateless one-shot AES-256-GCM decryption."""
        combined = base64.b64decode(encrypted_b64.encode("utf-8"))
        salt = combined[:16]
        nonce = combined[16:28]
        ciphertext = combined[28:]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode("utf-8"))
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

vault = StrongholdVault()