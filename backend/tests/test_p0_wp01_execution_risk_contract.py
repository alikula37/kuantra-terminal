"""Regression coverage for the P0-WP01 paper-execution and compliance contract."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import create_app
from app.quant.risk_guard import RiskGuard
from app.services.compliance_engine import ComplianceEngine
from app.services.execution.risk_interceptor import RiskGuardrailInterceptor
from app.services.p2p.copy_engine import ZeroKnowledgeCopyEngine


@pytest.fixture
def api_client():
    return TestClient(create_app())


def paper_order_payload(**overrides):
    payload = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "qty": 0.05,
        "price": 64000.0,
        "stop_loss": 63000.0,
    }
    payload.update(overrides)
    return payload


class TestPaperExecutionRoute:
    def test_order_route_is_registered_once(self, api_client):
        matching_routes = [
            route
            for route in api_client.app.routes
            if route.path == "/api/v1/execution/order" and "POST" in route.methods
        ]

        assert len(matching_routes) == 1

    def test_live_execution_is_rejected_before_any_execution_engine_or_router_call(self, api_client, monkeypatch):
        engine_create_order = MagicMock()
        router_order = MagicMock()
        monkeypatch.setattr("app.api.endpoints.ccxt_execution_engine.create_order", engine_create_order)
        monkeypatch.setattr("app.services.execution.order_router.order_router.route_order", router_order)

        response = api_client.post("/api/v1/execution/order", json=paper_order_payload(mode="live"))

        assert response.status_code == 403
        assert response.json()["detail"] == {
            "code": "LIVE_EXECUTION_DISABLED",
            "reason": "Live execution is disabled until the Phase 4 execution safety gates are complete.",
        }
        engine_create_order.assert_not_called()
        router_order.assert_not_called()

    def test_unknown_execution_mode_is_rejected_before_engine_call(self, api_client, monkeypatch):
        engine_create_order = MagicMock()
        monkeypatch.setattr("app.api.endpoints.ccxt_execution_engine.create_order", engine_create_order)

        response = api_client.post("/api/v1/execution/order", json=paper_order_payload(mode="shadow"))

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "UNSUPPORTED_EXECUTION_MODE"
        assert response.json()["detail"]["reason"] == "Only PAPER execution mode is supported."
        engine_create_order.assert_not_called()

    def test_case_insensitive_paper_mode_preserves_dispatch_schema_behavior(self, api_client, monkeypatch):
        engine_create_order = MagicMock(return_value={"success": True, "mode": "PAPER", "status": "FILLED"})
        monkeypatch.setattr("app.api.endpoints.ccxt_execution_engine.create_order", engine_create_order)

        response = api_client.post("/api/v1/execution/order", json=paper_order_payload(mode="paper"))

        assert response.status_code == 200
        assert response.json()["mode"] == "PAPER"
        assert engine_create_order.call_args.kwargs["mode"] == "PAPER"


class TestComplianceRiskContract:
    def test_risk_guard_rejects_canonical_compliance_breach(self, monkeypatch):
        monkeypatch.setattr(
            "app.quant.risk_guard.compliance_engine.evaluate_compliance",
            lambda: {"overall_status": "BREACHED"},
        )

        approved, reason, metadata = RiskGuard().validate_pre_execution_risk(
            paper_order_payload(), account_balance=10000.0
        )

        assert approved is False
        assert "ORDER_REJECTED_PROP_FIRM_BREACH" in reason
        assert metadata["stage"] == "PROP_FIRM_BREACH"

    def test_risk_guard_rejects_within_half_percentage_point_of_daily_limit(self, monkeypatch):
        monkeypatch.setattr(
            "app.quant.risk_guard.compliance_engine.evaluate_compliance",
            lambda: {
                "overall_status": "CRITICAL",
                "daily_loss_pct_of_account": 4.5,
                "daily_loss_limit_pct": 5.0,
            },
        )

        approved, reason, metadata = RiskGuard().validate_pre_execution_risk(
            paper_order_payload(), account_balance=10000.0
        )

        assert approved is False
        assert "ORDER_REJECTED_NEAR_DRAWDOWN_LIMIT" in reason
        assert metadata["daily_loss_pct"] == 4.5
        assert metadata["daily_loss_limit"] == 5.0

    def test_risk_guard_fails_closed_when_daily_loss_fields_are_missing(self, monkeypatch):
        monkeypatch.setattr(
            "app.quant.risk_guard.compliance_engine.evaluate_compliance",
            lambda: {"overall_status": "COMPLIANT"},
        )

        approved, reason, metadata = RiskGuard().validate_pre_execution_risk(
            paper_order_payload(), account_balance=10000.0
        )

        assert approved is False
        assert "ORDER_REJECTED_COMPLIANCE_DATA_UNAVAILABLE" in reason
        assert metadata["stage"] == "COMPLIANCE_DATA_UNAVAILABLE"

    def test_risk_interceptor_rejects_canonical_compliance_breach_after_prior_gates_pass(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.panic_kill_switch.is_locked_down", False
        )
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.biometric_watch_bridge.get_biometric_state",
            lambda: {"is_stress_critical": False, "biometric_tilt_score": 0.0},
        )
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.swarm_consensus_engine.conduct_debate",
            lambda order: {"is_approved": True, "consensus_status": "APPROVED", "reason": "ok"},
        )
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.psychology_engine.calculate_session_tilt_score",
            lambda: {"tilt_score": 0.0},
        )
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.compliance_engine.evaluate_compliance",
            lambda: {"overall_status": "BREACHED"},
        )

        approved, reason, metadata = RiskGuardrailInterceptor().evaluate_order(paper_order_payload())

        assert approved is False
        assert "ORDER_BLOCKED_PROP_FIRM_BREACH" in reason
        assert metadata["stage"] == "PROP_FIRM_GUARD"


@pytest.mark.parametrize(
    ("setting_value", "expected_account_size"),
    [("25000.0", 25000.0), (None, 100000.0), ("invalid", 100000.0), ("0", 100000.0)],
)
def test_compliance_account_size_uses_valid_setting_or_explicit_default(monkeypatch, setting_value, expected_account_size):
    mock_get_setting = MagicMock(return_value=setting_value)
    monkeypatch.setattr("app.services.compliance_engine.sqlite_driver.get_setting", mock_get_setting)

    engine = ComplianceEngine()

    assert engine.config.account_size == expected_account_size
    mock_get_setting.assert_called_once_with("user_initial_balance")


def test_copy_engine_reads_initial_balance_without_unsupported_default_argument(monkeypatch):
    mock_get_setting = MagicMock(return_value="25000.0")
    monkeypatch.setattr("app.services.p2p.copy_engine.sqlite_driver.get_setting", mock_get_setting)

    copy_engine = ZeroKnowledgeCopyEngine()

    assert copy_engine.follower_settings["follower_equity"] == 25000.0
    mock_get_setting.assert_called_once_with("user_initial_balance")
