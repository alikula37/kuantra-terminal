"""P1-WP14 regression tests for versioned playbooks and risk policies."""

import sqlite3
import uuid

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.playbook.playbook_service import PlaybookService
from app.quant.risk_guard import RiskGuard
from app.services.risk_policy_service import RiskPolicyService


def _safe_compliance(monkeypatch):
    monkeypatch.setattr(
        "app.quant.risk_guard.compliance_engine.evaluate_compliance",
        lambda: {
            "overall_status": "COMPLIANT",
            "daily_loss_pct_of_account": 0.0,
            "daily_loss_limit_pct": 5.0,
        },
    )


def test_playbook_definition_and_audit_are_version_pinned():
    service = PlaybookService()
    playbook = service.create_playbook(
        title=f"WP14-{uuid.uuid4().hex[:8]}",
        description="version one",
        rules=[{"rule_text": "Stop is defined", "is_mandatory": True, "weight": 2.0}],
    )

    version_one = service.get_playbook(playbook["id"], version=1)
    assert version_one["version"] == 1
    version_two = service.create_playbook_version(playbook["id"], description="version two")
    assert version_two["version"] == 2
    assert version_two["snapshot_sha256"] != version_one["snapshot_sha256"]
    assert service.get_playbook(playbook["id"], version=1)["description"] == "version one"

    audit = service.audit_trade_discipline(
        trade_id=f"WP14-TRADE-{uuid.uuid4().hex[:8]}",
        playbook_id=playbook["id"],
        checked_rule_ids=[version_one["rules"][0]["id"]],
        playbook_version=1,
    )
    assert audit["playbook_version"] == 1
    assert audit["playbook_snapshot_sha256"] == version_one["snapshot_sha256"]
    assert audit["audit_event_id"]

    ledger = EvidenceLedgerRepository()
    events = list(ledger.export_events(account_id="local-journal"))
    version_events = [
        event
        for event in events
        if event["event_type"] == "JournalReviewAdded"
        and (
            event["normalized_payload"].get("playbook_id") == playbook["id"]
            or event["normalized_payload"].get("playbook_version", {}).get("playbook_id") == playbook["id"]
        )
    ]
    assert len(version_events) >= 3
    assert ledger.verify_chain(account_id="local-journal")["valid"] is True

    with sqlite3.connect(ledger.db_path) as conn:
        try:
            conn.execute(
                "UPDATE playbook_versions SET title = 'tampered' WHERE playbook_id = ? AND version = 1",
                (playbook["id"],),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("playbook_versions must remain append-only")


def test_risk_policy_versions_emit_immutable_policy_events():
    service = RiskPolicyService()
    policy_id = f"wp14-{uuid.uuid4().hex[:8]}"
    first = service.create_policy(policy_id, 2.0)
    second = service.create_policy(policy_id, 1.5)
    assert first["version"] == 1
    assert second["version"] == 2
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
    assert service.get_version(policy_id, 1)["max_risk_pct_per_trade"] == 2.0

    ledger = EvidenceLedgerRepository()
    events = [
        event
        for event in ledger.export_events(account_id="local-risk")
        if event["normalized_payload"].get("policy_kind") == "RISK_POLICY_VERSION"
        and event["normalized_payload"].get("risk_policy", {}).get("policy_id") == policy_id
    ]
    assert len(events) == 2
    assert ledger.verify_chain(account_id="local-risk")["valid"] is True


def test_risk_guard_returns_policy_identity_and_evidence(monkeypatch):
    _safe_compliance(monkeypatch)
    policy_id = f"wp14-guard-{uuid.uuid4().hex[:8]}"
    guard = RiskGuard(default_max_risk_pct=2.5, policy_id=policy_id)
    approved, reason, metadata = guard.validate_pre_execution_risk(
        {
            "id": f"WP14-ORDER-{uuid.uuid4().hex[:8]}",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 0.1,
            "price": 65000.0,
            "stop_loss": 64000.0,
            "mode": "PAPER",
        },
        account_balance=10000.0,
    )
    assert approved is True
    assert reason == "RISK_VALIDATION_PASSED"
    assert metadata["policy_id"] == policy_id
    assert metadata["policy_version"] == 1
    assert len(metadata["policy_snapshot_sha256"]) == 64
    assert metadata["risk_event_id"]

    event = EvidenceLedgerRepository().get_event(metadata["risk_event_id"])
    assert event["event_type"] == "RiskEvaluated"
    assert event["normalized_payload"]["decision"]["approved"] is True
    assert event["provenance"]["policy_id"] == policy_id
