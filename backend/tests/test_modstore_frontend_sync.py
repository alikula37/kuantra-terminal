import pytest
import asyncio
from fastapi.testclient import TestClient
from main import create_app
from app.services.plugin_manager import plugin_manager, PERSONA_PROFILES

class TestModStoreFrontendSync:
    """Validates Frontend-Backend synchronization for ModStore, Slot mappings, and Personas."""

    @pytest.fixture
    def client_and_manager(self):
        app = create_app()
        plugin_manager.set_app(app)
        client = TestClient(app)
        return client, plugin_manager, app

    def test_persona_preset_payload_and_slot_mappings(self, client_and_manager):
        client, manager, app = client_and_manager

        # 1. Fetch available personas endpoint
        res = client.get("/api/v1/plugins/personas")
        assert res.status_code == 200
        data = res.json()
        assert "personas" in data
        personas = data["personas"]

        # 2. Only production-safe personas are exposed.
        assert "kuantra_lite" in personas
        assert "kuantra_quant" in personas
        assert set(personas) == {"kuantra_lite", "lite", "kuantra_quant", "quant"}

        # 3. Assert plugin mapping integrity
        assert len(personas["kuantra_lite"]) == 0
        assert personas["kuantra_quant"] == []

    def test_plugin_hot_toggle_and_manifest_integrity(self, client_and_manager):
        client, manager, app = client_and_manager

        # 1. Verify all 8 plugin manifests have complete schemas
        plugins = manager.list_installed_plugins()
        assert len(plugins) >= 8

        for p in plugins:
            assert "plugin_id" in p
            assert "name" in p
            assert "version" in p
            assert "category" in p
            assert "ram_footprint_mb" in p
            assert "persona_tags" in p
            assert isinstance(p["heavy_dependencies"], list)
            assert p["ram_footprint_mb"] > 0

        # 2. Runtime mounting remains unavailable until signed sandbox support.
        res_enable = client.post("/api/v1/plugins/toggle", json={
            "plugin_id": "plugin_ai_swarm",
            "enable": True
        })
        assert res_enable.status_code == 503
        assert res_enable.json()["detail"]["status"] == "EXPERIMENTAL_DISABLED"

        # Verify all installed experimental components are inactive.
        installed = client.get("/api/v1/plugins/installed").json()["plugins"]
        ai_plugin = next((p for p in installed if p["plugin_id"] == "plugin_ai_swarm"), None)
        assert ai_plugin is not None
        assert ai_plugin["is_active"] is False

    def test_modstore_catalog_endpoint_integrity(self, client_and_manager):
        client, manager, app = client_and_manager

        res = client.get("/api/v1/plugins/modstore-catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["catalog_version"] == "DISABLED"
        assert data["status"] == "EXPERIMENTAL_DISABLED"
        assert data["modules"] == []
