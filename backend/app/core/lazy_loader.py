"""
Lazy Dependency Loader & Runtime Memory Reclaim Engine for Kuantra Terminal.
Prevents heavy binary C-extensions from loading at boot and enforces sys.modules cleanup.
"""

import sys
import gc
import importlib
import logging
import psutil
import os
from typing import Dict, Any, List, Set, Optional

logger = logging.getLogger("lazy_loader")

class LazyDependencyLoader:
    """Manages on-demand module importation, dependency tracking, and aggressive garbage collection."""

    def __init__(self):
        self._loaded_modules: Dict[str, Set[str]] = {} # plugin_id -> set of module names

    def load(self, module_name: str, plugin_id: Optional[str] = None) -> Any:
        """
        Dynamically imports a module on demand and associates it with a plugin_id.
        """
        try:
            mod = importlib.import_module(module_name)
            if plugin_id:
                if plugin_id not in self._loaded_modules:
                    self._loaded_modules[plugin_id] = set()
                self._loaded_modules[plugin_id].add(module_name)
            logger.info(f"[LAZY-LOADER] Successfully lazy-loaded module '{module_name}' for plugin '{plugin_id or 'core'}'")
            return mod
        except ImportError as e:
            logger.error(f"[LAZY-LOADER] Failed to lazy-load module '{module_name}': {e}")
            raise

    def unload(self, module_name: str):
        """
        Unloads a plugin module and invokes gc.collect() to release memory.
        Safely clears references without corrupting Python 3.11 C extension threadstate.
        """
        if module_name.startswith("app.plugins"):
            to_delete = [m for m in list(sys.modules.keys()) if m == module_name or m.startswith(f"{module_name}.")]
            for m in to_delete:
                try:
                    del sys.modules[m]
                except KeyError:
                    pass
        gc.collect()
        logger.info(f"[LAZY-LOADER] Cleaned up module references for '{module_name}' and ran gc.collect()")

    def unload_plugin_dependencies(self, plugin_id: str, heavy_deps: Optional[List[str]] = None):
        """Unloads all tracked and declared heavy dependencies for a given plugin."""
        deps_to_unload = set(heavy_deps or [])
        if plugin_id in self._loaded_modules:
            deps_to_unload.update(self._loaded_modules.pop(plugin_id))

        for dep in deps_to_unload:
            self.unload(dep)

    @staticmethod
    def get_process_memory_mb() -> float:
        """Returns the current Resident Set Size (RSS) in MB for the backend sidecar."""
        process = psutil.Process(os.getpid())
        return round(process.memory_info().rss / (1024 * 1024), 2)

lazy_loader = LazyDependencyLoader()