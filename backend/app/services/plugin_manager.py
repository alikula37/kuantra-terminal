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
from app.core.availability import is_explicit_experimental_mode

logger = logging.getLogger("plugin_manager")

"""Production-safe personas.  Prototype profiles stay documented separately
so an explicit local research session can still inspect legacy code without
making those capabilities part of the normal API/UI contract.
"""
PERSONA_PROFILES: Dict[str, List[str]] = {
    "kuantra_lite": [],
    "lite": [],
    # Quant analytics are core endpoints in this release; no plugin is needed
    # to claim the journal/research workflow.
    "kuantra_quant": [],
    "quant": [],
}

EXPERIMENTAL_PERSONA_PROFILES: Dict[str, List[str]] = {
    "kuantra_defai": ["plugin_ai_swarm", "plugin_dex_arbitrage", "plugin_mcp_gateway"],
    "defai": ["plugin_ai_swarm", "plugin_dex_arbitrage", "plugin_mcp_gateway"],
    "kuantra_institutional": [
        "plugin_quant_shield",
        "plugin_orderflow",
        "plugin_fix_dma",
        "plugin_biometrics",
        "plugin_ai_swarm",
        "plugin_reverse_skill"
    ],
    "institutional": [
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
    ],
    "kuantra_full": [
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

EXPERIMENTAL_PLUGIN_IDS = frozenset(
    plugin_id for profile in EXPERIMENTAL_PERSONA_PROFILES.values() for plugin_id in profile
)
# No dynamic plugin is part of the verified v1.4.0 core.  Keeping this allowlist
# explicit prevents an arbitrary directory dropped into the user plugin path
# from becoming executable merely because it has a manifest.
PRODUCTION_PLUGIN_IDS = frozenset()


class ExperimentalPluginDisabledError(RuntimeError):
    """Raised when an unsigned/prototype plugin is requested in production."""


class ExperimentalPersonaDisabledError(RuntimeError):
    """Raised when a prototype persona is requested in production."""

class DynamicPluginManager:
    """Micro-Kernel Core Dynamic Plugin & Route Mutation Controller."""

    def __init__(self, app: Optional[FastAPI] = None, plugins_dir: Optional[str] = None):
        self.app = app
        from app.core.paths import USER_PLUGINS_DIR, is_frozen
        if plugins_dir:
            self.plugins_dir = Path(plugins_dir)
        else:
            backend_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.plugins_dir = backend_dir / "plugins"
        # Downloaded .kmod plugins must never be written into the install directory.
        self.user_plugins_dir = Path(plugins_dir) if plugins_dir else USER_PLUGINS_DIR
        if not is_frozen():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.user_plugins_dir.mkdir(parents=True, exist_ok=True)

        self._plugins_metadata: Dict[str, PluginMetadata] = {}
        self._active_plugins: Dict[str, BasePlugin] = {}
        self._mounted_routes: Dict[str, List[BaseRoute]] = {}
        self._lock = asyncio.Lock()
        self._active_persona: str = "kuantra_lite"

        self._init_sqlite_table()
        self.discover_plugins()

    def set_app(self, app: FastAPI):
        """Attaches the FastAPI application instance to the manager and syncs mounted routers."""
        self.app = app
        self._mounted_routes.clear()
        for p_id, plugin_instance in list(self._active_plugins.items()):
            router = plugin_instance.get_router()
            meta = self._plugins_metadata.get(p_id, plugin_instance.metadata)
            if router and self.app:
                initial_routes_count = len(self.app.router.routes)
                self.app.include_router(router, prefix=meta.router_prefix or "")
                self._mounted_routes[p_id] = self.app.router.routes[initial_routes_count:]
                self.app.openapi_schema = None

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
        """Scans the bundled and user plugin directories and reads all manifest.json descriptors."""
        self._plugins_metadata.clear()

        scanned_roots: List[Path] = []
        for root in (self.plugins_dir, getattr(self, "user_plugins_dir", None)):
            if root is None or not root.exists():
                continue
            if any(root.resolve() == seen.resolve() for seen in scanned_roots):
                continue
            scanned_roots.append(root)

        for root in scanned_roots:
            for sub_dir in root.iterdir():
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
                                is_active=sub_dir.name in self._active_plugins,
                                ram_footprint_mb=data.get("ram_footprint_mb", 5.0),
                                persona_tags=data.get("persona_tags", []),
                                manifest_path=str(manifest_file)
                            )
                            # Bundled plugins are scanned first and win on duplicate ids.
                            if meta.plugin_id not in self._plugins_metadata:
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
        if plugin_id not in PRODUCTION_PLUGIN_IDS and not is_explicit_experimental_mode():
            raise ExperimentalPluginDisabledError(
                f"Plugin '{plugin_id}' is not in the verified production allowlist; signed sandbox support is required."
            )

        if plugin_id in self._active_plugins and plugin_id in self._mounted_routes:
            return {"status": "ALREADY_ACTIVE", "plugin_id": plugin_id}

        if plugin_id not in self._plugins_metadata:
            self.discover_plugins()
            if plugin_id not in self._plugins_metadata:
                raise ValueError(f"Plugin '{plugin_id}' not found in registry.")

        meta = self._plugins_metadata[plugin_id]

        try:
            # 1. Dynamically import plugin module
            plugin_py_path = Path(meta.manifest_path).parent / "plugin.py" if meta.manifest_path else None
            if plugin_py_path and plugin_py_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", str(plugin_py_path))
                if spec and spec.loader:
                    plugin_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_mod)
                else:
                    module_path = f"app.plugins.{plugin_id}.plugin"
                    plugin_mod = importlib.import_module(module_path)
            else:
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
                # Invalidate cached OpenAPI schema and rebuild ASGI middleware stack
                self.app.openapi_schema = None
                self.app.middleware_stack = self.app.build_middleware_stack()

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

            # 2. Remove routes from Starlette app router and rebuild middleware stack
            if self.app and plugin_id in self._mounted_routes:
                routes_to_remove = self._mounted_routes.pop(plugin_id)
                self.app.router.routes = [r for r in self.app.router.routes if r not in routes_to_remove]
                self.app.openapi_schema = None
                self.app.middleware_stack = self.app.build_middleware_stack()

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
        allowed_profiles = {
            **PERSONA_PROFILES,
            **(EXPERIMENTAL_PERSONA_PROFILES if is_explicit_experimental_mode() else {}),
        }
        if target_persona in EXPERIMENTAL_PERSONA_PROFILES and not is_explicit_experimental_mode():
            raise ExperimentalPersonaDisabledError(
                f"Persona '{target_persona}' is experimental and disabled until its integrations are verified."
            )
        if target_persona not in allowed_profiles:
            raise ValueError(f"Unknown persona '{persona_name}'. Available: {list(PERSONA_PROFILES.keys())}")

        target_plugins = set(allowed_profiles[target_persona])
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
            info["is_active"] = p_id in self._active_plugins and (
                p_id not in EXPERIMENTAL_PLUGIN_IDS or is_explicit_experimental_mode()
            )
            info["lifecycle"] = "CORE" if p_id in PRODUCTION_PLUGIN_IDS else "EXPERIMENTAL_DISABLED"
            info["execution_authority"] = False
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
