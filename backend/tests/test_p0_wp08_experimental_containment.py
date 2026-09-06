"""P0-WP08 truth gates for prototype capability surfaces."""

from fastapi.testclient import TestClient

from main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _assert_disabled(response, capability: str) -> None:
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "EXPERIMENTAL_DISABLED"
    assert detail["capability"] == capability
    assert detail["execution_authority"] is False
    assert detail["data_connected"] is False
    assert detail["transport_connected"] is False


def test_plugin_download_and_toggle_are_closed_by_default():
    client = _client()
    _assert_disabled(
        client.post("/api/v1/plugins/download", json={"plugin_id": "plugin_unknown"}),
        "plugin_marketplace_download",
    )
    _assert_disabled(
        client.post(
            "/api/v1/plugins/toggle",
            json={"plugin_id": "plugin_ai_swarm", "enable": True},
        ),
        "plugin_runtime",
    )
    _assert_disabled(
        client.post(
            "/api/v1/plugins/apply-persona",
            json={"persona": "full"},
        ),
        "experimental_persona",
    )


def test_fake_ai_defai_and_biometric_surfaces_are_unavailable():
    client = _client()
    _assert_disabled(client.get("/api/v1/hardware/gpu-status"), "local_llm_hardware")
    _assert_disabled(client.post("/api/v1/swarm/fast-eval", json={}), "local_llm_swarm")
    _assert_disabled(client.post("/api/v1/ai/swarm/debate", json={}), "ai_swarm_debate")
    _assert_disabled(client.get("/api/v1/dex/chains"), "dex_rpc")
    _assert_disabled(client.post("/api/v1/dex/scan-opportunities", json={}), "dex_opportunity_scan")
    _assert_disabled(client.get("/api/v1/biometrics/devices"), "biometric_hardware")
    _assert_disabled(client.get("/api/v1/biometrics/live-telemetry"), "biometric_telemetry")
    _assert_disabled(client.get("/api/v1/security/passkey/challenge"), "webauthn_passkey")


def test_source_and_adapter_surfaces_do_not_claim_live_data():
    client = _client()
    _assert_disabled(client.get("/api/v1/mcp/sources"), "mcp_external_sources")
    _assert_disabled(client.post("/api/v1/mcp/query", json={"source": "sec"}), "mcp_external_sources")
    _assert_disabled(
        client.post(
            "/api/v1/reverse-skill/deploy-agent",
            json={"agent_name": "demo", "strategy_config": {}},
        ),
        "reverse_skill_deploy",
    )
    _assert_disabled(
        client.post(
            "/api/v1/adapters/subscribe",
            json={"adapter": "polygon", "symbols": ["AAPL"]},
        ),
        "polygon_connector",
    )

    statuses = client.get("/api/v1/adapters/status")
    assert statuses.status_code == 200
    body = statuses.json()
    assert body["polygon"]["status"] == "EXPERIMENTAL_DISABLED"
    assert body["twelvedata"]["transport_connected"] is False
    assert body["mt5"]["status"] == "EXPERIMENTAL_DISABLED"


def test_production_personas_are_core_only():
    client = _client()
    response = client.get("/api/v1/plugins/personas")
    assert response.status_code == 200
    personas = response.json()["personas"]
    assert set(personas) == {"kuantra_lite", "lite", "kuantra_quant", "quant"}
    assert all(not plugins for plugins in personas.values())

    installed = client.get("/api/v1/plugins/installed")
    assert installed.status_code == 200
    assert all(plugin["is_active"] is False for plugin in installed.json()["plugins"])
    assert all(
        plugin["lifecycle"] == "EXPERIMENTAL_DISABLED"
        for plugin in installed.json()["plugins"]
    )
