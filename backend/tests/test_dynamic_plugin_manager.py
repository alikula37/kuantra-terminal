import pytest
import asyncio
from fastapi.testclient import TestClient
from main import create_app
from app.core.plugins import PluginMetadata, BasePlugin
from app.core.lazy_loader import lazy_loader
from app.services.plugin_manager import plugin_manager, DynamicPluginManager, PERSONA_PROFILES

class TestDynamicPluginManagerAndMicroKernel:
    """Test suite for Micro-Kernel Core, Dynamic Route Mutation, Lazy Loader, and ModStore."""

    @pytest.fixture
    def client_and_manager(self):
        app = create_app()
        plugin_manager.set_app(app)
        client = TestClient(app)
        return client, plugin_manager, app

    def test_plugin_dynamic_mount_and_unmount(self, client_and_manager):
        client, manager, app = client_and_manager

        # Verify initial state of plugin_quant_shield
        initial_routes_count = len(app.router.routes)
        
        # 1. Activate plugin
        act_res = asyncio.run(manager.activate_plugin("plugin_quant_shield"))
        assert act_res["status"] in ("ACTIVATED", "ALREADY_ACTIVE")
        assert len(app.router.routes) > initial_routes_count

        # 2. Test mounted endpoint
        res = client.get("/api/v1/plugins/quant-shield/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ONLINE"
        assert data["shield_active"] is True

        # 3. Deactivate plugin
        deact_res = asyncio.run(manager.deactivate_plugin("plugin_quant_shield"))
        assert deact_res["status"] == "DEACTIVATED"

        # 4. Verify route is removed (returns 404)
        res_after = client.get("/api/v1/plugins/quant-shield/status")
        assert res_after.status_code == 404

    def test_lazy_dependency_loading_and_cleanup(self):
        # 1. Lazy load a plugin module
        plug_mod = lazy_loader.load("app.plugins.plugin_orderflow.plugin", plugin_id="test_plugin")
        assert plug_mod is not None
        assert "app.plugins.plugin_orderflow.plugin" in lazy_loader._loaded_modules.get("test_plugin", set())

        # 2. Memory usage query
        mem_mb = lazy_loader.get_process_memory_mb()
        assert mem_mb > 0.0

        # 3. Unload tracking
        lazy_loader.unload_plugin_dependencies("test_plugin")
        assert "test_plugin" not in lazy_loader._loaded_modules

    def test_persona_switching_and_persistence(self, client_and_manager):
        client, manager, app = client_and_manager

        # 1. Apply kuantra_lite (zero plugins)
        res_lite = asyncio.run(manager.apply_persona("kuantra_lite"))
        assert res_lite["status"] == "PERSONA_APPLIED"
        assert res_lite["persona"] == "kuantra_lite"
        assert len(res_lite["active_plugins"]) == 0

        # 2. Apply kuantra_defai
        res_defai = asyncio.run(manager.apply_persona("kuantra_defai"))
        assert res_defai["status"] == "PERSONA_APPLIED"
        assert "plugin_ai_swarm" in res_defai["active_plugins"]
        assert "plugin_dex_arbitrage" in res_defai["active_plugins"]

        # 3. Apply full persona
        res_full = asyncio.run(manager.apply_persona("full"))
        assert res_full["status"] == "PERSONA_APPLIED"
        assert len(res_full["active_plugins"]) >= 6

    def test_modstore_and_plugin_api_endpoints(self, client_and_manager):
        client, manager, app = client_and_manager

        # 1. GET /api/v1/plugins/installed
        res_inst = client.get("/api/v1/plugins/installed")
        assert res_inst.status_code == 200
        inst_data = res_inst.json()
        assert inst_data["total_plugins"] >= 8
        assert "plugins" in inst_data

        # 2. POST /api/v1/plugins/toggle
        res_tog = client.post("/api/v1/plugins/toggle", json={
            "plugin_id": "plugin_orderflow",
            "enable": True
        })
        assert res_tog.status_code == 200

        # 3. POST /api/v1/plugins/apply-persona
        res_pers = client.post("/api/v1/plugins/apply-persona", json={
            "persona": "kuantra_institutional"
        })
        assert res_pers.status_code == 200
        pers_data = res_pers.json()
        assert pers_data["persona"] == "kuantra_institutional"

        # 4. GET /api/v1/plugins/modstore-catalog
        res_cat = client.get("/api/v1/plugins/modstore-catalog")
        assert res_cat.status_code == 200
        cat_data = res_cat.json()
        assert cat_data["total_available"] >= 3
        assert len(cat_data["modules"]) >= 3