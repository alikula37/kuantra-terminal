"""Versioned, append-only risk policy snapshots and decision evidence.

The risk guard is intentionally the authority for a pre-trade decision.  This
service only gives that decision a durable policy identity and an immutable
ledger record.  It never places or modifies an order.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.db.sqlite_driver import sqlite_driver
from app.services.settings_service import settings_service


class RiskPolicyError(RuntimeError):
    """Raised when a policy cannot be safely loaded or persisted."""


_POLICY_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
_SECRET_KEYS = {
    "apikey",
    "apisecret",
    "secret",
    "password",
    "passphrase",
    "privatekey",
    "authorization",
    "accesstoken",
    "refreshtoken",
    "clientsecret",
    "credential",
    "credentials",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _safe_value(value: Any) -> Any:
    """Keep decision metadata JSON-safe and remove credential-shaped keys."""

    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in _SECRET_KEYS:
                continue
            result[str(key)] = _safe_value(child)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    return str(value)


class RiskPolicyService:
    """Stores immutable policy snapshots and risk-evaluation evidence."""

    DEFAULT_POLICY_ID = "default-risk-policy"
    DEFAULT_DAILY_LOSS_GUARD_BAND_PCT = 0.5

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = str(db_path or sqlite_driver.db_path)
        self._init_db()
        self._ledger = EvidenceLedgerRepository(self.db_path)

    def _init_db(self) -> None:
        with sqlite_driver.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS risk_policy_versions (
                    policy_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version > 0),
                    max_risk_pct_per_trade REAL NOT NULL,
                    daily_loss_guard_band_pct REAL NOT NULL DEFAULT 0.5,
                    policy_json TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(policy_id, version),
                    UNIQUE(policy_id, snapshot_sha256)
                );

                CREATE INDEX IF NOT EXISTS idx_risk_policy_versions_latest
                    ON risk_policy_versions(policy_id, version DESC);

                CREATE TRIGGER IF NOT EXISTS risk_policy_versions_no_update
                BEFORE UPDATE ON risk_policy_versions
                BEGIN
                    SELECT RAISE(ABORT, 'risk_policy_versions is append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS risk_policy_versions_no_delete
                BEFORE DELETE ON risk_policy_versions
                BEGIN
                    SELECT RAISE(ABORT, 'risk_policy_versions is append-only');
                END;
                """
            )
            conn.commit()

    @staticmethod
    def _validate_policy_id(policy_id: str) -> str:
        value = str(policy_id or "").strip()
        if not _POLICY_ID_RE.fullmatch(value):
            raise RiskPolicyError("policy_id must contain only letters, numbers, '.', '_' ':' or '-'.")
        return value

    @staticmethod
    def _validate_percent(value: Any, field_name: str, *, allow_zero: bool = False) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise RiskPolicyError(f"{field_name} must be numeric") from exc
        if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero) or number > 100:
            raise RiskPolicyError(f"{field_name} must be within {0 if allow_zero else '>0'} and 100")
        return number

    @classmethod
    def _policy_payload(
        cls,
        *,
        policy_id: str,
        version: int,
        max_risk_pct_per_trade: float,
        daily_loss_guard_band_pct: float,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "policy_id": policy_id,
            "version": int(version),
            "max_risk_pct_per_trade": float(max_risk_pct_per_trade),
            "daily_loss_guard_band_pct": float(daily_loss_guard_band_pct),
            "description": str(description or ""),
            "metadata": _safe_value(metadata or {}),
        }

    def _append_version_in_transaction(
        self,
        conn,
        *,
        policy_id: str,
        max_risk_pct_per_trade: float,
        daily_loss_guard_band_pct: float,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        previous = conn.execute(
            "SELECT version FROM risk_policy_versions WHERE policy_id = ? ORDER BY version DESC LIMIT 1",
            (policy_id,),
        ).fetchone()
        version = int(previous["version"]) + 1 if previous else 1
        payload = self._policy_payload(
            policy_id=policy_id,
            version=version,
            max_risk_pct_per_trade=max_risk_pct_per_trade,
            daily_loss_guard_band_pct=daily_loss_guard_band_pct,
            description=description,
            metadata=metadata,
        )
        digest = _sha256(payload)
        created_at = _utc_now()
        conn.execute(
            """
            INSERT INTO risk_policy_versions (
                policy_id, version, max_risk_pct_per_trade,
                daily_loss_guard_band_pct, policy_json, snapshot_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy_id,
                version,
                max_risk_pct_per_trade,
                daily_loss_guard_band_pct,
                canonical_json(payload),
                digest,
                created_at,
            ),
        )
        event = self._ledger.append_event_in_transaction(
            conn,
            event_type="RiskEvaluated",
            account_id="local-risk",
            venue="local-risk-policy",
            idempotency_key=f"risk-policy:{policy_id}:version:{version}",
            normalized_payload={"policy_kind": "RISK_POLICY_VERSION", "risk_policy": payload},
            raw_payload={"risk_policy": payload},
            occurred_at=created_at,
            schema_version="1",
            adapter_version="risk-policy-v1",
            correlation_id=policy_id,
            provenance={
                "source": "risk_policy_version",
                "policy_id": policy_id,
                "version": version,
                "snapshot_sha256": digest,
            },
        )
        return {
            **payload,
            "snapshot_sha256": digest,
            "created_at": created_at,
            "event_id": event["event_id"],
            "event_created": event["created"],
        }

    def create_policy(
        self,
        policy_id: str,
        max_risk_pct_per_trade: float,
        *,
        daily_loss_guard_band_pct: float = DEFAULT_DAILY_LOSS_GUARD_BAND_PCT,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append a policy version; identical snapshots are idempotent."""

        policy_id = self._validate_policy_id(policy_id)
        max_risk = self._validate_percent(max_risk_pct_per_trade, "max_risk_pct_per_trade")
        band = self._validate_percent(
            daily_loss_guard_band_pct,
            "daily_loss_guard_band_pct",
            allow_zero=True,
        )
        # Calculate the candidate digest before taking a write lock so a retry
        # can resolve an existing immutable snapshot without a new version.
        latest = self.get_active_policy(policy_id, create_default=False)
        next_version = int(latest["version"]) + 1 if latest else 1
        candidate = self._policy_payload(
            policy_id=policy_id,
            version=next_version,
            max_risk_pct_per_trade=max_risk,
            daily_loss_guard_band_pct=band,
            description=description,
            metadata=metadata,
        )
        candidate_digest = _sha256(candidate)
        if latest and (
            float(latest.get("max_risk_pct_per_trade")) == max_risk
            and float(latest.get("daily_loss_guard_band_pct")) == band
            and str(latest.get("description") or "") == str(description or "")
            and _safe_value(latest.get("metadata") or {}) == _safe_value(metadata or {})
        ):
            return latest

        conn = sqlite_driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            # Re-check under the lock to avoid two callers allocating the same
            # version concurrently.
            locked_latest = conn.execute(
                "SELECT * FROM risk_policy_versions WHERE policy_id = ? ORDER BY version DESC LIMIT 1",
                (policy_id,),
            ).fetchone()
            if locked_latest:
                locked_policy = self._row_to_policy(locked_latest)
                if (
                    float(locked_policy.get("max_risk_pct_per_trade")) == max_risk
                    and float(locked_policy.get("daily_loss_guard_band_pct")) == band
                    and str(locked_policy.get("description") or "") == str(description or "")
                    and _safe_value(locked_policy.get("metadata") or {}) == _safe_value(metadata or {})
                ):
                    conn.commit()
                    return locked_policy
            existing = conn.execute(
                "SELECT * FROM risk_policy_versions WHERE policy_id = ? AND snapshot_sha256 = ?",
                (policy_id, candidate_digest),
            ).fetchone()
            if existing:
                conn.commit()
                return self._row_to_policy(existing)
            result = self._append_version_in_transaction(
                conn,
                policy_id=policy_id,
                max_risk_pct_per_trade=max_risk,
                daily_loss_guard_band_pct=band,
                description=description,
                metadata=metadata,
            )
            conn.commit()
            return result
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_default_policy(self, default_max_risk_pct: Optional[float] = None) -> Dict[str, Any]:
        """Create the default snapshot once, using the persisted setting if present."""

        existing = self.get_active_policy(self.DEFAULT_POLICY_ID, create_default=False)
        if existing:
            return existing
        configured = default_max_risk_pct
        if configured is None:
            configured = settings_service.get_setting("max_risk_pct_per_trade", None)
        if configured is None:
            configured = 5.0
        try:
            configured = float(configured)
            self._validate_percent(configured, "max_risk_pct_per_trade")
        except RiskPolicyError:
            configured = 5.0
        return self.create_policy(
            self.DEFAULT_POLICY_ID,
            configured,
            daily_loss_guard_band_pct=self.DEFAULT_DAILY_LOSS_GUARD_BAND_PCT,
            description="Default deterministic pre-trade risk policy",
        )

    def ensure_policy(
        self,
        policy_id: str,
        max_risk_pct_per_trade: float,
        *,
        daily_loss_guard_band_pct: float = DEFAULT_DAILY_LOSS_GUARD_BAND_PCT,
    ) -> Dict[str, Any]:
        existing = self.get_active_policy(policy_id, create_default=False)
        if existing:
            return existing
        return self.create_policy(
            policy_id,
            max_risk_pct_per_trade,
            daily_loss_guard_band_pct=daily_loss_guard_band_pct,
            description="RiskGuard instance policy",
        )

    @staticmethod
    def _row_to_policy(row: Any) -> Dict[str, Any]:
        result = dict(row)
        try:
            payload = json.loads(result.pop("policy_json"))
            result.update(payload)
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RiskPolicyError("Stored risk policy JSON is invalid") from exc
        return result

    def get_active_policy(
        self,
        policy_id: str = DEFAULT_POLICY_ID,
        *,
        create_default: bool = True,
    ) -> Optional[Dict[str, Any]]:
        policy_id = self._validate_policy_id(policy_id)
        with sqlite_driver.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM risk_policy_versions WHERE policy_id = ? ORDER BY version DESC LIMIT 1",
                (policy_id,),
            ).fetchone()
        if row:
            return self._row_to_policy(row)
        if create_default and policy_id == self.DEFAULT_POLICY_ID:
            return self.ensure_default_policy()
        return None

    def get_version(self, policy_id: str, version: int) -> Optional[Dict[str, Any]]:
        policy_id = self._validate_policy_id(policy_id)
        with sqlite_driver.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM risk_policy_versions WHERE policy_id = ? AND version = ?",
                (policy_id, int(version)),
            ).fetchone()
        return self._row_to_policy(row) if row else None

    def list_versions(self, policy_id: str = DEFAULT_POLICY_ID) -> List[Dict[str, Any]]:
        policy_id = self._validate_policy_id(policy_id)
        with sqlite_driver.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM risk_policy_versions WHERE policy_id = ? ORDER BY version ASC",
                (policy_id,),
            ).fetchall()
        return [self._row_to_policy(row) for row in rows]

    def record_evaluation(
        self,
        policy: Dict[str, Any],
        order: Dict[str, Any],
        *,
        approved: bool,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append an idempotent RiskEvaluated event for one guard decision."""

        policy_id = self._validate_policy_id(policy.get("policy_id"))
        version = int(policy.get("version"))
        decision = {
            "policy_id": policy_id,
            "policy_version": version,
            "policy_snapshot_sha256": str(policy.get("snapshot_sha256")),
            "approved": bool(approved),
            "reason": str(reason)[:1000],
            "order": _safe_value(
                {
                    key: order.get(key)
                    for key in (
                        "id", "order_id", "symbol", "side", "qty", "price",
                        "stop_loss", "take_profit", "mode", "exchange",
                    )
                    if order.get(key) is not None
                }
            ),
            "metadata": _safe_value(metadata or {}),
        }
        digest = _sha256(decision)
        occurred_at = order.get("occurred_at") or order.get("entry_time") or _utc_now()
        account_id = str(order.get("account_id") or "local-risk")
        venue = str(order.get("exchange") or "local-risk")
        ledger = EvidenceLedgerRepository(self.db_path)
        return ledger.append_event(
            event_type="RiskEvaluated",
            account_id=account_id,
            venue=venue,
            idempotency_key=f"risk-evaluation:{policy_id}:v{version}:{digest}",
            normalized_payload={"decision_kind": "PRE_EXECUTION_RISK", "decision": decision},
            raw_payload={"decision": decision},
            occurred_at=occurred_at,
            schema_version="1",
            adapter_version="risk-evaluation-v1",
            correlation_id=str(order.get("id") or order.get("order_id") or digest),
            provenance={
                "source": "risk_evaluation",
                "policy_id": policy_id,
                "version": version,
                "snapshot_sha256": policy.get("snapshot_sha256"),
            },
        )


risk_policy_service = RiskPolicyService()
