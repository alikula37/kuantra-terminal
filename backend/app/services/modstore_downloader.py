"""
In-App Remote Plugin Downloader & .kmod Package Extractor for Kuantra Terminal.
Handles cryptographic SHA-256 verification, zip/kmod extraction, sys.path dynamic resolution,
and live async progress streaming.
"""

import os
import sys
import uuid
import json
import zipfile
import hashlib
import asyncio
import logging
import urllib.request
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from app.core.paths import BACKEND_ROOT
from app.services.plugin_manager import plugin_manager

logger = logging.getLogger("modstore_downloader")

class ModStoreDownloader:
    """Manages downloading, extracting, verifying, and dynamically mounting .kmod plugins."""

    def __init__(self, target_dir: Optional[Path] = None):
        self.target_dir = target_dir or plugin_manager.plugins_dir
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Returns the real-time status of an ongoing or completed download task."""
        return self._tasks.get(task_id)

    def _verify_sha256(self, file_path: Path, expected_hash: str) -> bool:
        """Computes SHA-256 hash of a file and compares against expected digest."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        calculated = h.hexdigest().lower()
        return calculated == expected_hash.lower()

    def _create_synthetic_bundle(self, plugin_id: str, bundle_path: Path):
        """Creates a valid .kmod synthetic plugin zip bundle for testing or offline installations."""
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            manifest_data = {
                "plugin_id": plugin_id,
                "name": f"Module {plugin_id.replace('plugin_', '').replace('mod_', '').title()}",
                "version": "1.2.0",
                "category": "ModStore Extension",
                "description": f"Dynamically downloaded institutional add-on for {plugin_id}.",
                "author": "Kuantra Community Verified",
                "heavy_dependencies": [],
                "router_prefix": f"/api/v1/plugins/{plugin_id.replace('plugin_', '').replace('mod_', '')}",
                "ram_footprint_mb": 12.0,
                "persona_tags": ["full", "quant", "institutional"]
            }
            zf.writestr("manifest.json", json.dumps(manifest_data, indent=2))
            plugin_py = f"""
import logging
from fastapi import APIRouter
from app.services.plugin_manager import BasePlugin

logger = logging.getLogger("{plugin_id}")

class Plugin(BasePlugin):
    async def on_startup(self, app):
        logger.info("[{plugin_id}] Dynamic plugin on_startup hook initialized successfully.")

    async def on_shutdown(self, app):
        logger.info("[{plugin_id}] Dynamic plugin on_shutdown hook cleanly stopped.")

    def get_router(self):
        router = APIRouter(prefix="{manifest_data['router_prefix']}", tags=["{plugin_id}"])
        @router.get("/status")
        async def get_status():
            return {{"status": "ONLINE", "plugin_id": "{plugin_id}", "dynamic_loaded": True}}
        return router
"""
            zf.writestr("plugin.py", plugin_py)
            zf.writestr("__init__.py", "")

    async def download_and_install(
        self,
        plugin_id: str,
        download_url: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously downloads, verifies, extracts, and mounts a remote plugin.
        """
        tid = task_id or str(uuid.uuid4())[:8]
        self._tasks[tid] = {
            "task_id": tid,
            "plugin_id": plugin_id,
            "status": "downloading",
            "progress_percent": 5,
            "bytes_downloaded": 0,
            "total_bytes": 1024 * 1024 * 18, # 18 MB estimated baseline
            "error": None
        }

        try:
            plugin_folder_name = plugin_id if plugin_id.startswith("plugin_") else f"plugin_{plugin_id}"
            plugin_dest = self.target_dir / plugin_folder_name
            temp_bundle = self.target_dir / f"{plugin_folder_name}_temp.kmod"

            # 1. Download or synthesize archive
            if download_url and download_url.startswith(("http://", "https://")):
                logger.info(f"[MODSTORE-DOWNLOADER] Downloading {plugin_id} from {download_url}...")
                
                def _download_worker():
                    req = urllib.request.Request(download_url, headers={"User-Agent": "Kuantra-ModStore-Downloader"})
                    with urllib.request.urlopen(req) as resp, open(temp_bundle, "wb") as out_f:
                        total_len = int(resp.headers.get("content-length", 1024 * 1024 * 15))
                        self._tasks[tid]["total_bytes"] = total_len
                        downloaded = 0
                        while chunk := resp.read(65536):
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            pct = min(90, int((downloaded / total_len) * 90))
                            self._tasks[tid]["bytes_downloaded"] = downloaded
                            self._tasks[tid]["progress_percent"] = pct

                await asyncio.to_thread(_download_worker)
            else:
                # Local synthetic simulation for offline/testing/mock
                for step in range(1, 10):
                    await asyncio.sleep(0.04)
                    self._tasks[tid]["progress_percent"] = step * 10
                    self._tasks[tid]["bytes_downloaded"] = step * 1024 * 1024 * 2
                self._create_synthetic_bundle(plugin_folder_name, temp_bundle)

            # 2. Checksum Verification
            self._tasks[tid]["status"] = "verifying"
            self._tasks[tid]["progress_percent"] = 92

            if expected_sha256:
                if not self._verify_sha256(temp_bundle, expected_sha256):
                    raise ValueError(f"SHA-256 integrity mismatch for plugin bundle {plugin_id}")

            # 3. Extract Archive
            self._tasks[tid]["status"] = "extracting"
            self._tasks[tid]["progress_percent"] = 96
            plugin_dest.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(temp_bundle, "r") as zf:
                zf.extractall(plugin_dest)

            # Cleanup temp bundle
            if temp_bundle.exists():
                temp_bundle.unlink()

            # 4. Ensure directory is discoverable in sys.path
            parent_str = str(self.target_dir.parent.parent)
            if parent_str not in sys.path:
                sys.path.insert(0, parent_str)

            # 5. Discover & Dynamically Activate
            self._tasks[tid]["status"] = "activating"
            plugin_manager.plugins_dir = self.target_dir
            plugin_manager.discover_plugins()
            await plugin_manager.activate_plugin(plugin_folder_name)

            self._tasks[tid]["status"] = "completed"
            self._tasks[tid]["progress_percent"] = 100
            logger.info(f"[MODSTORE-DOWNLOADER] Plugin {plugin_id} successfully installed and activated.")
            return {
                "success": True,
                "task_id": tid,
                "plugin_id": plugin_folder_name,
                "installed_path": str(plugin_dest)
            }

        except Exception as e:
            logger.error(f"[MODSTORE-DOWNLOADER] Failed to download/install plugin {plugin_id}: {e}", exc_info=True)
            self._tasks[tid]["status"] = "failed"
            self._tasks[tid]["error"] = str(e)
            return {
                "success": False,
                "task_id": tid,
                "plugin_id": plugin_id,
                "error": str(e)
            }

modstore_downloader = ModStoreDownloader()