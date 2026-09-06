"""Versioned strategy playbooks and discipline evidence.

The compatibility ``playbooks`` tables remain the fast current projection.
Every definition and audit is also captured as an immutable snapshot in the
canonical evidence ledger so a later review cannot silently change history.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.db.sqlite_driver import sqlite_driver
from app.quant.quant_engine import quant_engine


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class PlaybookService:
    """Manages strategy playbooks, immutable versions, and execution audits."""

    def __init__(self):
        self._init_db()
        self._ledger = EvidenceLedgerRepository(sqlite_driver.db_path)
        self._backfill_legacy_versions()
        self._seed_default_playbooks()

    def _init_db(self):
        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS playbooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    win_rate_target REAL DEFAULT 65.0,
                    rr_target REAL DEFAULT 2.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS playbook_rules (
                    id TEXT PRIMARY KEY,
                    playbook_id TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    is_mandatory INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS trade_rule_checks (
                    trade_id TEXT NOT NULL,
                    playbook_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    is_checked INTEGER NOT NULL,
                    PRIMARY KEY (trade_id, rule_id)
                );

                CREATE TABLE IF NOT EXISTS playbook_versions (
                    playbook_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK(version > 0),
                    title TEXT NOT NULL,
                    description TEXT,
                    win_rate_target REAL,
                    rr_target REAL,
                    rules_json TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(playbook_id, version),
                    UNIQUE(playbook_id, snapshot_sha256),
                    FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_playbook_versions_latest
                    ON playbook_versions(playbook_id, version DESC);

                CREATE TRIGGER IF NOT EXISTS playbook_versions_no_update
                BEFORE UPDATE ON playbook_versions
                BEGIN
                    SELECT RAISE(ABORT, 'playbook_versions is append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS playbook_versions_no_delete
                BEFORE DELETE ON playbook_versions
                BEGIN
                    SELECT RAISE(ABORT, 'playbook_versions is append-only');
                END;
                """
            )

            # Additive metadata migration for existing installations. The
            # current table remains a projection; history lives in versions and
            # the ledger, so updating these columns cannot rewrite evidence.
            check_columns = {
                row["name"] for row in cursor.execute("PRAGMA table_info(trade_rule_checks)").fetchall()
            }
            if "playbook_version" not in check_columns:
                cursor.execute(
                    "ALTER TABLE trade_rule_checks ADD COLUMN playbook_version INTEGER NOT NULL DEFAULT 1"
                )
            if "snapshot_sha256" not in check_columns:
                cursor.execute("ALTER TABLE trade_rule_checks ADD COLUMN snapshot_sha256 TEXT")
            if "audited_at" not in check_columns:
                cursor.execute("ALTER TABLE trade_rule_checks ADD COLUMN audited_at TEXT")
            conn.commit()

    def _backfill_legacy_versions(self) -> None:
        """Pin pre-WP14 playbooks without rewriting their compatibility rows."""
        conn = sqlite_driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            legacy_rows = conn.execute(
                """
                SELECT p.* FROM playbooks p
                WHERE NOT EXISTS (
                    SELECT 1 FROM playbook_versions v WHERE v.playbook_id = p.id
                )
                ORDER BY p.created_at ASC, p.id ASC
                """
            ).fetchall()
            for row in legacy_rows:
                rule_rows = conn.execute(
                    "SELECT * FROM playbook_rules WHERE playbook_id = ? ORDER BY rowid ASC",
                    (row["id"],),
                ).fetchall()
                rules = self._normalise_rules([dict(rule) for rule in rule_rows], playbook_id=row["id"])
                self._append_version_in_transaction(
                    conn,
                    playbook_id=row["id"],
                    title=row["title"],
                    description=row["description"] or "",
                    win_rate_target=float(row["win_rate_target"] or 65.0),
                    rr_target=float(row["rr_target"] or 2.5),
                    rules=rules,
                )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def _seed_default_playbooks(self):
        """Seed standard institutional playbooks only on an empty database."""
        with sqlite_driver.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM playbooks").fetchone()["count"]
        if count == 0:
            self.create_playbook(
                title="Liquidity Sweep & Order Block Reversal",
                description="Institutional smart money setup catching stops above/below key swing levels with MSS confirmation.",
                win_rate_target=68.0,
                rr_target=2.75,
                rules=[
                    {"rule_text": "Higher timeframe (4h/1D) key level swept and rejected", "is_mandatory": True, "weight": 2.0},
                    {"rule_text": "Market structure shift (MSS) confirmed on 5m execution timeframe", "is_mandatory": True, "weight": 2.0},
                    {"rule_text": "Fair Value Gap (FVG) or optimal trade entry (OTE) tap on entry", "is_mandatory": False, "weight": 1.5},
                    {"rule_text": "Relative Volume (RVOL) > 1.5x on reversal displacement", "is_mandatory": False, "weight": 1.0},
                    {"rule_text": "Stop loss placed strictly beyond swing invalidation point", "is_mandatory": True, "weight": 2.5},
                ],
            )
            self.create_playbook(
                title="High-Momentum Breakout & Retest",
                description="Trend continuation strategy capturing clean compression breaks above major volume nodes.",
                win_rate_target=62.0,
                rr_target=2.5,
                rules=[
                    {"rule_text": "Consolidation base duration >= 2 hours with volatility compression", "is_mandatory": True, "weight": 1.5},
                    {"rule_text": "Breakout bar closes clearly beyond resistance with volume surge", "is_mandatory": True, "weight": 2.0},
                    {"rule_text": "First retest of broken level holds with lower timeframe wick rejection", "is_mandatory": False, "weight": 1.5},
                    {"rule_text": "Pre-defined Take Profit at least 2.5x initial stop risk", "is_mandatory": True, "weight": 2.0},
                ],
            )

    @staticmethod
    def _normalise_rules(rules: Optional[List[Dict[str, Any]]], *, playbook_id: str) -> List[Dict[str, Any]]:
        normalised: List[Dict[str, Any]] = []
        for raw in rules or []:
            text = str(raw.get("rule_text") or "").strip()
            if not text:
                raise ValueError("Playbook rule text cannot be empty")
            try:
                weight = float(raw.get("weight", 1.0))
            except (TypeError, ValueError) as exc:
                raise ValueError("Playbook rule weight must be numeric") from exc
            if not math.isfinite(weight) or weight < 0:
                raise ValueError("Playbook rule weight must be finite and non-negative")
            normalised.append(
                {
                    "id": str(raw.get("id") or f"RUL-{uuid.uuid4().hex[:6].upper()}"),
                    "playbook_id": playbook_id,
                    "rule_text": text,
                    "is_mandatory": bool(raw.get("is_mandatory")),
                    "weight": weight,
                }
            )
        return normalised

    @staticmethod
    def _snapshot_payload(
        *,
        playbook_id: str,
        version: int,
        title: str,
        description: str,
        win_rate_target: float,
        rr_target: float,
        rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "playbook_id": playbook_id,
            "version": int(version),
            "title": str(title),
            "description": str(description or ""),
            "win_rate_target": float(win_rate_target),
            "rr_target": float(rr_target),
            "rules": [
                {
                    "id": str(rule["id"]),
                    "playbook_id": playbook_id,
                    "rule_text": str(rule["rule_text"]),
                    "is_mandatory": bool(rule.get("is_mandatory")),
                    "weight": float(rule.get("weight", 1.0)),
                }
                for rule in rules
            ],
        }

    def _append_version_in_transaction(
        self,
        conn,
        *,
        playbook_id: str,
        title: str,
        description: str,
        win_rate_target: float,
        rr_target: float,
        rules: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        previous = conn.execute(
            "SELECT version FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1",
            (playbook_id,),
        ).fetchone()
        version = int(previous["version"]) + 1 if previous else 1
        payload = self._snapshot_payload(
            playbook_id=playbook_id,
            version=version,
            title=title,
            description=description,
            win_rate_target=win_rate_target,
            rr_target=rr_target,
            rules=rules,
        )
        digest = _sha256(payload)
        created_at = _utc_now()
        conn.execute(
            """
            INSERT INTO playbook_versions (
                playbook_id, version, title, description, win_rate_target,
                rr_target, rules_json, snapshot_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                playbook_id,
                version,
                title,
                description,
                win_rate_target,
                rr_target,
                canonical_json(payload["rules"]),
                digest,
                created_at,
            ),
        )
        snapshot = {**payload, "snapshot_sha256": digest, "created_at": created_at}
        event = self._ledger.append_event_in_transaction(
            conn,
            event_type="JournalReviewAdded",
            account_id="local-journal",
            venue="local-playbook",
            idempotency_key=f"playbook:{playbook_id}:version:{version}",
            normalized_payload={"policy_kind": "PLAYBOOK", "playbook_version": snapshot},
            raw_payload={"playbook_version": snapshot},
            occurred_at=created_at,
            schema_version="1",
            adapter_version="playbook-version-v1",
            correlation_id=playbook_id,
            provenance={
                "source": "playbook_version",
                "playbook_id": playbook_id,
                "version": version,
                "snapshot_sha256": digest,
            },
        )
        return {**snapshot, "event_id": event["event_id"], "event_created": event["created"]}

    def create_playbook(
        self,
        title: str,
        description: str,
        win_rate_target: float = 65.0,
        rr_target: float = 2.5,
        rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        now = _utc_now()
        playbook_id = f"PB-{uuid.uuid4().hex[:6].upper()}"
        title = str(title or "").strip()
        if not title:
            raise ValueError("Playbook title cannot be empty")
        normalised_rules = self._normalise_rules(rules, playbook_id=playbook_id)
        conn = sqlite_driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO playbooks (id, title, description, win_rate_target, rr_target, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (playbook_id, title, description, float(win_rate_target), float(rr_target), now, now),
            )
            for rule in normalised_rules:
                conn.execute(
                    """
                    INSERT INTO playbook_rules (id, playbook_id, rule_text, is_mandatory, weight)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (rule["id"], playbook_id, rule["rule_text"], int(rule["is_mandatory"]), rule["weight"]),
                )
            self._append_version_in_transaction(
                conn,
                playbook_id=playbook_id,
                title=title,
                description=description,
                win_rate_target=float(win_rate_target),
                rr_target=float(rr_target),
                rules=normalised_rules,
            )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_playbook(playbook_id)  # type: ignore[return-value]

    def create_playbook_version(
        self,
        playbook_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        win_rate_target: Optional[float] = None,
        rr_target: Optional[float] = None,
        rules: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Append a new immutable version and advance the compatibility view."""
        current = self.get_playbook(playbook_id)
        if not current:
            raise ValueError(f"Playbook {playbook_id} not found")
        resolved_title = str(title if title is not None else current["title"]).strip()
        if not resolved_title:
            raise ValueError("Playbook title cannot be empty")
        resolved_description = str(description if description is not None else current.get("description") or "")
        resolved_win = float(win_rate_target if win_rate_target is not None else current.get("win_rate_target", 65.0))
        resolved_rr = float(rr_target if rr_target is not None else current.get("rr_target", 2.5))
        resolved_rules = self._normalise_rules(
            rules if rules is not None else current.get("rules", []),
            playbook_id=playbook_id,
        )

        conn = sqlite_driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            now = _utc_now()
            conn.execute(
                """
                UPDATE playbooks SET title = ?, description = ?, win_rate_target = ?, rr_target = ?, updated_at = ?
                WHERE id = ?
                """,
                (resolved_title, resolved_description, resolved_win, resolved_rr, now, playbook_id),
            )
            conn.execute("DELETE FROM playbook_rules WHERE playbook_id = ?", (playbook_id,))
            for rule in resolved_rules:
                conn.execute(
                    "INSERT INTO playbook_rules (id, playbook_id, rule_text, is_mandatory, weight) VALUES (?, ?, ?, ?, ?)",
                    (rule["id"], playbook_id, rule["rule_text"], int(rule["is_mandatory"]), rule["weight"]),
                )
            self._append_version_in_transaction(
                conn,
                playbook_id=playbook_id,
                title=resolved_title,
                description=resolved_description,
                win_rate_target=resolved_win,
                rr_target=resolved_rr,
                rules=resolved_rules,
            )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_playbook(playbook_id)  # type: ignore[return-value]

    @staticmethod
    def _version_row_to_snapshot(row: Any) -> Dict[str, Any]:
        result = dict(row)
        try:
            result["rules"] = json.loads(result.pop("rules_json"))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Stored playbook version JSON is invalid") from exc
        return result

    def list_playbook_versions(self, playbook_id: str) -> List[Dict[str, Any]]:
        with sqlite_driver.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM playbook_versions WHERE playbook_id = ? ORDER BY version ASC",
                (playbook_id,),
            ).fetchall()
        return [self._version_row_to_snapshot(row) for row in rows]

    def get_playbook(self, playbook_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with sqlite_driver.get_connection() as conn:
            pb_row = conn.execute("SELECT * FROM playbooks WHERE id = ?", (playbook_id,)).fetchone()
            if not pb_row:
                return None
            if version is None:
                version_row = conn.execute(
                    "SELECT * FROM playbook_versions WHERE playbook_id = ? ORDER BY version DESC LIMIT 1",
                    (playbook_id,),
                ).fetchone()
            else:
                version_row = conn.execute(
                    "SELECT * FROM playbook_versions WHERE playbook_id = ? AND version = ?",
                    (playbook_id, int(version)),
                ).fetchone()
                if version_row is None:
                    return None

            if version_row:
                snapshot = self._version_row_to_snapshot(version_row)
                title = snapshot["title"]
                rules = snapshot["rules"]
                identity = {
                    "version": int(snapshot["version"]),
                    "snapshot_sha256": snapshot["snapshot_sha256"],
                }
                base = dict(pb_row)
                base.update({
                    "title": title,
                    "description": snapshot.get("description"),
                    "win_rate_target": snapshot.get("win_rate_target"),
                    "rr_target": snapshot.get("rr_target"),
                })
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM playbook_rules WHERE playbook_id = ?", (playbook_id,))
                rules = [dict(r) for r in cursor.fetchall()]
                identity = {"version": None, "snapshot_sha256": None}
                base = dict(pb_row)
                title = base["title"]

            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM trades WHERE notes LIKE ? OR notes LIKE ?",
                (f"%{playbook_id}%", f"%{title}%"),
            )
            trades = [dict(t) for t in cursor.fetchall()]
            pnls = [float(t["pnl"]) for t in trades if t.get("pnl") is not None]
            r_mults = [float(t["r_multiple"]) for t in trades if t.get("r_multiple") is not None]
            scorecard = quant_engine.calculate_full_performance_suite(
                pnls,
                r_multiples=r_mults if len(r_mults) == len(pnls) else None,
            )
            return {
                **base,
                **identity,
                "rules": rules,
                "trades_count": len(trades),
                "performance": scorecard,
            }

    def list_playbooks(self) -> List[Dict[str, Any]]:
        with sqlite_driver.get_connection() as conn:
            rows = conn.execute("SELECT id FROM playbooks ORDER BY created_at ASC").fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            playbook = self.get_playbook(row["id"])
            if playbook:
                result.append(playbook)
        return result

    @staticmethod
    def calculate_discipline_score(
        rules: List[Dict[str, Any]],
        checked_rule_ids: List[str],
    ) -> Dict[str, Any]:
        """Discipline Score = checked weights / total weights * 100."""
        if not rules:
            return {"score": 100.0, "mandatory_violation": False, "passed_rules": 0, "total_rules": 0}
        total_weight = sum(float(r.get("weight", 1.0)) for r in rules)
        checked_set = set(checked_rule_ids)
        checked_weight = sum(float(r.get("weight", 1.0)) for r in rules if r["id"] in checked_set)
        mandatory_violation = any(bool(r.get("is_mandatory")) and r["id"] not in checked_set for r in rules)
        score = (checked_weight / total_weight) * 100.0 if total_weight > 0 else 0.0
        return {
            "score": round(score, 2),
            "mandatory_violation": mandatory_violation,
            "checked_weight": round(checked_weight, 2),
            "total_weight": round(total_weight, 2),
            "passed_rules": len(checked_set),
            "total_rules": len(rules),
        }

    def audit_trade_discipline(
        self,
        trade_id: str,
        playbook_id: str,
        checked_rule_ids: List[str],
        playbook_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Record a version-pinned checklist and append a journal review event."""
        pb = self.get_playbook(playbook_id, version=playbook_version)
        if not pb:
            raise ValueError(f"Playbook {playbook_id} not found")
        rules = pb["rules"]
        checked = sorted(set(str(rule_id) for rule_id in checked_rule_ids))
        audit_result = self.calculate_discipline_score(rules, checked)
        version = int(pb["version"] or 1)
        snapshot_hash = pb.get("snapshot_sha256")
        audited_at = _utc_now()
        payload = {
            "review_kind": "PLAYBOOK_AUDIT",
            "trade_id": str(trade_id),
            "playbook_id": playbook_id,
            "playbook_version": version,
            "playbook_snapshot_sha256": snapshot_hash,
            "checked_rule_ids": checked,
            "discipline": audit_result,
        }
        audit_digest = _sha256(payload)
        conn = sqlite_driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM trade_rule_checks WHERE trade_id = ?", (trade_id,))
            for rule in rules:
                conn.execute(
                    """
                    INSERT INTO trade_rule_checks (
                        trade_id, playbook_id, rule_id, is_checked,
                        playbook_version, snapshot_sha256, audited_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade_id,
                        playbook_id,
                        rule["id"],
                        1 if rule["id"] in checked else 0,
                        version,
                        snapshot_hash,
                        audited_at,
                    ),
                )
            event = self._ledger.append_event_in_transaction(
                conn,
                event_type="JournalReviewAdded",
                account_id="local-journal",
                venue="local-playbook",
                idempotency_key=f"playbook-audit:{trade_id}:{playbook_id}:v{version}:{audit_digest}",
                normalized_payload=payload,
                raw_payload={"audit": payload},
                occurred_at=audited_at,
                schema_version="1",
                adapter_version="playbook-audit-v1",
                correlation_id=str(trade_id),
                provenance={
                    "source": "playbook_audit",
                    "playbook_id": playbook_id,
                    "version": version,
                    "snapshot_sha256": snapshot_hash,
                },
            )
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

        return {
            "trade_id": trade_id,
            "playbook_id": playbook_id,
            "playbook_title": pb["title"],
            "playbook_version": version,
            "playbook_snapshot_sha256": snapshot_hash,
            "discipline_score": audit_result["score"],
            "mandatory_violation": audit_result["mandatory_violation"],
            "details": audit_result,
            "audit_event_id": event["event_id"],
            "audit_event_created": event["created"],
        }


playbook_service = PlaybookService()
