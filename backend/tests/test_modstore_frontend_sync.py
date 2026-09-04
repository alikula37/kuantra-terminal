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

        # 2. Verify all 5 personas match frontend specifications
        assert "kuantra_lite" in personas
        assert "kuantra_quant" in personas
        assert "kuantra_defai" in personas
        assert "kuantra_institutional" in personas
        assert "full" in personas

        # 3. Assert plugin mapping integrity
        assert len(personas["kuantra_lite"]) == 0
        assert "plugin_quant_shield" in personas["kuantra_quant"]
        assert "plugin_ai_swarm" in personas["kuantra_defai"]
        assert "plugin_fix_dma" in personas["kuantra_institutional"]
        assert len(personas["full"]) >= 8

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

        # 2. Test hot toggle via REST endpoint
        # Mount plugin_ai_swarm
        res_enable = client.post("/api/v1/plugins/toggle", json={
            "plugin_id": "plugin_ai_swarm",
            "enable": True
        })
        assert res_enable.status_code == 200
        assert res_enable.json()["status"] in ("ACTIVATED", "ALREADY_ACTIVE")

        # Query mounted status endpoint
        res_status = client.get("/api/v1/plugins/ai-swarm/status")
        assert res_status.status_code == 200
        assert res_status.json()["status"] == "ONLINE"

        # Unmount plugin_ai_swarm
        res_disable = client.post("/api/v1/plugins/toggle", json={
            "plugin_id": "plugin_ai_swarm",
            "enable": False
        })
        assert res_disable.status_code == 200
        assert res_disable.json()["status"] in ("DEACTIVATED", "NOT_ACTIVE")

        # Verify plugin is marked inactive in installed catalog
        installed = client.get("/api/v1/plugins/installed").json()["plugins"]
        ai_plugin = next((p for p in installed if p["plugin_id"] == "plugin_ai_swarm"), None)
        assert ai_plugin is not None
        assert ai_plugin["is_active"] is False

    def test_modstore_catalog_endpoint_integrity(self, client_and_manager):
        client, manager, app = client_and_manager

        res = client.get("/api/v1/plugins/modstore-catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["catalog_version"] in ("1.1.0", "1.2.0", "1.3.0", "1.4.0")
        assert len(data["modules"]) >= 3

        module_ids = [m["id"] for m in data["modules"]]
        assert "mod_options_greeks" in module_ids
        assert "mod_macro_nowcasting" in module_ids
        assert "mod_binance_liquidation_radar" in module_ids