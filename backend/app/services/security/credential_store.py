"""Credential storage boundary for secrets that must outlive a process.

Production credentials are written to the operating system credential manager through
``keyring``.  SQLite stores only non-secret metadata and stable keychain account names.
The in-memory provider exists solely for isolated tests and requires an explicit test
environment flag; there is no plaintext-file or deterministic-machine-key fallback.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


SERVICE_NAME = "com.kuantra.terminal"


class CredentialStoreError(RuntimeError):
    """Base error for credential storage failures."""


class CredentialStoreUnavailable(CredentialStoreError):
    """Raised when no persistent OS credential backend is available."""


@dataclass(frozen=True)
class CredentialStoreStatus:
    backend: str
    available: bool
    persistent: bool
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "backend": self.backend,
            "available": self.available,
            "persistent": self.persistent,
            "reason": self.reason,
        }


class _CredentialStore:
    """Small common interface implemented by OS and test providers."""

    status: CredentialStoreStatus

    def set_secret(self, account: str, value: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get_secret(self, account: str) -> Optional[str]:  # pragma: no cover - interface
        raise NotImplementedError

    def delete_secret(self, account: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class _UnavailableCredentialStore(_CredentialStore):
    def __init__(self, reason: str):
        self.status = CredentialStoreStatus(
            backend="unavailable",
            available=False,
            persistent=False,
            reason=reason,
        )

    def _raise(self) -> None:
        raise CredentialStoreUnavailable(self.status.reason or "OS credential store unavailable")

    def set_secret(self, account: str, value: str) -> None:
        self._raise()

    def get_secret(self, account: str) -> Optional[str]:
        self._raise()

    def delete_secret(self, account: str) -> None:
        self._raise()


class _MemoryCredentialStore(_CredentialStore):
    """Ephemeral test provider; never selected for a normal application process."""

    def __init__(self):
        self.status = CredentialStoreStatus(
            backend="memory-test",
            available=True,
            persistent=False,
            reason="Ephemeral provider enabled explicitly for tests.",
        )
        self._values: Dict[str, str] = {}

    def set_secret(self, account: str, value: str) -> None:
        self._values[account] = value

    def get_secret(self, account: str) -> Optional[str]:
        return self._values.get(account)

    def delete_secret(self, account: str) -> None:
        self._values.pop(account, None)


class _OSKeychainStore(_CredentialStore):
    def __init__(self):
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - depends on installed runtime
            raise CredentialStoreUnavailable(
                "The keyring package is not installed; persistent credentials are disabled."
            ) from exc

        try:
            backend = keyring.get_keyring()
            priority = getattr(backend, "priority", 0)
            module_name = backend.__class__.__module__
            if priority is None or priority <= 0 or module_name.startswith("keyring.backends.fail"):
                raise CredentialStoreUnavailable(
                    "No OS credential manager is available (Windows Credential Manager, macOS Keychain "
                    "or a Linux Secret Service backend is required)."
                )
            # Keep the module rather than a second global import so tests can inject a backend.
            self._keyring = keyring
            self._backend_name = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
        except CredentialStoreUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreUnavailable(f"OS credential manager initialization failed: {exc}") from exc

        self.status = CredentialStoreStatus(
            backend="os-keychain",
            available=True,
            persistent=True,
            reason=self._backend_name,
        )

    def set_secret(self, account: str, value: str) -> None:
        try:
            self._keyring.set_password(SERVICE_NAME, account, value)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreUnavailable(f"OS credential manager rejected a write: {exc}") from exc

    def get_secret(self, account: str) -> Optional[str]:
        try:
            return self._keyring.get_password(SERVICE_NAME, account)
        except Exception as exc:  # noqa: BLE001
            raise CredentialStoreUnavailable(f"OS credential manager rejected a read: {exc}") from exc

    def delete_secret(self, account: str) -> None:
        try:
            self._keyring.delete_password(SERVICE_NAME, account)
        except Exception as exc:  # noqa: BLE001
            # Deleting an absent item is idempotent; other failures remain fail-closed.
            message = str(exc).lower()
            if "not found" not in message and "no password" not in message and "does not exist" not in message:
                raise CredentialStoreUnavailable(f"OS credential manager rejected a delete: {exc}") from exc


def _build_store() -> _CredentialStore:
    requested = os.environ.get("KUANTRA_CREDENTIAL_STORE", "os").strip().lower()
    if requested == "memory":
        if os.environ.get("KUANTRA_TEST_MODE") == "1":
            return _MemoryCredentialStore()
        return _UnavailableCredentialStore(
            "The memory credential provider is test-only; configure an OS keychain for application use."
        )
    if requested not in {"os", "keyring", "auto"}:
        return _UnavailableCredentialStore(f"Unsupported credential store '{requested}'.")
    try:
        return _OSKeychainStore()
    except CredentialStoreUnavailable as exc:
        return _UnavailableCredentialStore(str(exc))


credential_store = _build_store()


def credential_store_status() -> Dict[str, object]:
    """Return non-secret backend status for the settings UI and diagnostics."""

    return credential_store.status.as_dict()
