"""
Dynamic FastAPI Plugin Manager & Runtime Route Mutator for Kuantra Terminal.
Enables runtime hot-mounting/unmounting of routers, lifecycle execution,
lazy dependency management, and persona-driven subsystem activation.
"""

import os
import sys
import json
import asyncio
import logging
import importlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from fastapi import FastAPI, APIRouter
from starlette.routing import BaseRoute

from app.core.plugins import BasePlugin, PluginMetadata
from app.core.lazy_loader import lazy_loader
from app.db.sqlite_driver import sqlite_driver

logger = logging.getLogger("plugin_manager")

PERSONA_PROFILES: Dict[str, List[str]] = {
    "kuantra_lite": [],
    "kuantra_quant": ["plugin_quant_shield", "plugin_orderflow"],
    "kuantra_defai": ["plugin_ai_swarm", "plugin_dex_arbitrage", "plugin_mcp_gateway"],
    "kuantra_institutional": [
        "plugin_quant_shield",
        "plugin_orderflow",
        "plugin_fix_dma",
        "plugin_biometrics",
        "plugin_ai_swarm",
        "plugin_reverse_skill"
    ],
    "full": [
        "plugin_quant_shield",
        "plugin_orderflow",
        "plugin_ai_swarm",
        "plugin_mcp_gateway",
        "plugin_reverse_skill",
        "plugin_dex_arbitrage",
        "plugin_fix_dma",
        "plugin_biometrics"
    ]
}

class DynamicPluginManager:
    """Micro-Kernel Core Dynamic Plugin & Route Mutation Controller."""

    def __init__(self, app: Optional[FastAPI] = None, plugins_dir: Optional[str] = None):
        self.app = app
        if plugins_dir:
            self.plugins_dir = Path(plugins_dir)
        else:
            backend_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.plugins_dir = backend_dir / "plugins"

        self.plugins_dir.mkdir(parents=True, exist_ok=True)

        self._plugins_metadata: Dict[str, PluginMetadata] = {}
        self._active_plugins: Dict[str, BasePlugin] = {}
        self._mounted_routes: Dict[str, List[BaseRoute]] = {}
        self._lock = asyncio.Lock()
        self._active_persona: str = "full"

        self._init_sqlite_table()
        self.discover_plugins()

    def set_app(self, app: FastAPI):
        """Attaches the FastAPI application instance to the manager."""
        self.app = app

    def _init_sqlite_table(self):
        """Initializes the installed_plugins table in SQLite."""
        try:
            with sqlite_driver.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS installed_plugins (
                        plugin_id TEXT PRIMARY KEY,
                        is_active INTEGER DEFAULT 0,
                        install_path TEXT,
                        enabled_at TEXT
                    );
                """)
        except Exception as e:
            logger.warning(f"[PLUGIN-MANAGER] Failed to init installed_plugins table: {e}")

    def discover_plugins(self) -> Dict[str, PluginMetadata]:
        """Scans the plugins directory and reads all manifest.json descriptors."""
        self._plugins_metadata.clear()
        if not self.plugins_dir.exists():
            return self._plugins_metadata

        for sub_dir in self.plugins_dir.iterdir():
            if sub_dir.is_dir() and sub_dir.name.startswith("plugin_"):
                manifest_file = sub_dir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        meta = PluginMetadata(
                            plugin_id=data.get("plugin_id", sub_dir.name),
                            name=data.get("name", sub_dir.name),
                            version=data.get("version", "1.0.0"),
                            category=data.get("category", "General"),
                            description=data.get("description", ""),
                            author=data.get("author", "Kuantra Core Team"),
                            heavy_dependencies=data.get("heavy_dependencies", []),
                            router_prefix=data.get("router_prefix"),
                            is_active=False,
                            ram_footprint_mb=data.get("ram_footprint_mb", 5.0),
                            persona_tags=data.get("persona_tags", []),
                            manifest_path=str(manifest_file)
                        )
                        self._plugins_metadata[meta.plugin_id] = meta
                    except Exception as e:
                        logger.error(f"[PLUGIN-MANAGER] Failed to parse manifest in {sub_dir.name}: {e}")

        logger.info(f"[PLUGIN-MANAGER] Discovered {len(self._plugins_metadata)} plugins.")
        return self._plugins_metadata

    async def activate_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """
        Dynamically activates a plugin, executes on_startup, attaches routes to Starlette routing table,
        and invalidates OpenAPI cache.
        """
        if plugin_id in self._active_plugins:
            return {"status": "ALREADY_ACTIVE", "plugin_id": plugin_id}

        if plugin_id not in self._plugins_metadata:
            self.discover_plugins()
            if plugin_id not in self._plugins_metadata:
                raise ValueError(f"Plugin '{plugin_id}' not found in registry.")

        meta = self._plugins_metadata[plugin_id]

        try:
            # 1. Dynamically import plugin module
            module_path = f"app.plugins.{plugin_id}.plugin"
            plugin_mod = importlib.import_module(module_path)
            plugin_class = getattr(plugin_mod, "Plugin")
            plugin_instance: BasePlugin = plugin_class(metadata=meta)

            # 2. Execute on_startup hook
            if self.app:
                await plugin_instance.on_startup(self.app)

            # 3. Mount APIRouter dynamically onto Starlette router
            router = plugin_instance.get_router()
            if router and self.app:
                # Capture route references
                initial_routes_count = len(self.app.router.routes)
                self.app.include_router(router, prefix=meta.router_prefix or "")
                new_routes = self.app.router.routes[initial_routes_count:]
                self._mounted_routes[plugin_id] = new_routes
                # Invalidate cached OpenAPI schema to reflect new endpoints
                self.app.openapi_schema = None

            meta.is_active = True
            self._active_plugins[plugin_id] = plugin_instance

            # 4. Update SQLite state
            self._persist_plugin_state(plugin_id, is_active=True)

            logger.info(f"[PLUGIN-MANAGER] Successfully activated plugin '{plugin_id}' ({len(self._mounted_routes.get(plugin_id, []))} routes mounted)")
            return {
                "status": "ACTIVATED",
                "plugin_id": plugin_id,
                "routes_mounted": len(self._mounted_routes.get(plugin_id, [])),
                "ram_footprint_mb": meta.ram_footprint_mb
            }
        except Exception as e:
            logger.error(f"[PLUGIN-MANAGER] Error activating plugin '{plugin_id}': {e}")
            raise

    async def deactivate_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """
        Dynamically deactivates a plugin, executes on_shutdown, strips routes from Starlette routing table,
        unloads heavy C-extensions, and runs garbage collection.
        """
        if plugin_id not in self._active_plugins:
            return {"status": "NOT_ACTIVE", "plugin_id": plugin_id}

        plugin_instance = self._active_plugins[plugin_id]
        meta = self._plugins_metadata.get(plugin_id, plugin_instance.metadata)

        try:
            # 1. Execute on_shutdown hook
            if self.app:
                await plugin_instance.on_shutdown(self.app)

            # 2. Remove routes from Starlette app router
            if self.app and plugin_id in self._mounted_routes:
                routes_to_remove = self._mounted_routes.pop(plugin_id)
                self.app.router.routes = [r for r in self.app.router.routes if r not in routes_to_remove]
                self.app.openapi_schema = None

            # 3. Unload heavy dependencies & clean sys.modules
            lazy_loader.unload_plugin_dependencies(plugin_id, meta.heavy_dependencies)

            meta.is_active = False
            del self._active_plugins[plugin_id]

            # 4. Update SQLite state
            self._persist_plugin_state(plugin_id, is_active=False)

            logger.info(f"[PLUGIN-MANAGER] Successfully deactivated plugin '{plugin_id}'")
            return {
                "status": "DEACTIVATED",
                "plugin_id": plugin_id
            }
        except Exception as e:
            logger.error(f"[PLUGIN-MANAGER] Error deactivating plugin '{plugin_id}': {e}")
            raise

    async def toggle_plugin(self, plugin_id: str, enable: bool) -> Dict[str, Any]:
        """Toggles a plugin between active and inactive state."""
        if enable:
            return await self.activate_plugin(plugin_id)
        else:
            return await self.deactivate_plugin(plugin_id)

    async def apply_persona(self, persona_name: str) -> Dict[str, Any]:
        """
        Batch-configures active plugins based on an architectural persona profile:
        - kuantra_lite: Base core.
        - kuantra_quant: Quantitative trading and orderflow.
        - kuantra_defai: Autonomous AI Swarm & DEX flash loan arbitrage.
        - kuantra_institutional: High-frequency FIX DMA, DOM Ladder, and Hardware Biometrics.
        - full: All plugins active.
        """
        target_persona = persona_name.lower().strip()
        if target_persona not in PERSONA_PROFILES:
            raise ValueError(f"Unknown persona '{persona_name}'. Available: {list(PERSONA_PROFILES.keys())}")

        target_plugins = set(PERSONA_PROFILES[target_persona])
        activated = []
        deactivated = []

        for p_id in list(self._plugins_metadata.keys()):
            if p_id in target_plugins:
                if p_id not in self._active_plugins:
                    await self.activate_plugin(p_id)
                    activated.append(p_id)
            else:
                if p_id in self._active_plugins:
                    await self.deactivate_plugin(p_id)
                    deactivated.append(p_id)

        self._active_persona = target_persona
        logger.info(f"[PLUGIN-MANAGER] Applied persona '{target_persona}': Activated={activated}, Deactivated={deactivated}")
        return {
            "status": "PERSONA_APPLIED",
            "persona": target_persona,
            "activated": activated,
            "deactivated": deactivated,
            "active_plugins": list(self._active_plugins.keys())
        }

    def list_installed_plugins(self) -> List[Dict[str, Any]]:
        """Returns details of all installed plugins."""
        self.discover_plugins()
        results = []
        for p_id, meta in self._plugins_metadata.items():
            info = meta.to_dict()
            info["is_active"] = p_id in self._active_plugins
            results.append(info)
        return results

    def _persist_plugin_state(self, plugin_id: str, is_active: bool):
        """Updates SQLite database with plugin active status."""
        try:
            with sqlite_driver.get_connection() as conn:
                conn.execute("""
                    INSERT INTO installed_plugins (plugin_id, is_active, install_path, enabled_at)
                    VALUES (?, ?, ?, datetime('now'))
                    ON CONFLICT(plugin_id) DO UPDATE SET is_active=excluded.is_active, enabled_at=datetime('now');
                """, (plugin_id, 1 if is_active else 0, str(self.plugins_dir / plugin_id)))
        except Exception as e:
            logger.warning(f"[PLUGIN-MANAGER] SQLite persistence error: {e}")

plugin_manager = DynamicPluginManager()