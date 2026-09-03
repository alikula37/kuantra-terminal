"""
In-App Remote Plugin Downloader & .kmod Package Extractor for Kuantra Terminal.
Handles cryptographic SHA-256 verification, zip/kmod extraction, dynamic activation by file
location, and live async progress streaming.
"""

import os
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
        self.target_dir = target_dir or plugin_manager.user_plugins_dir
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

    async def download_and_install(
        self,
        plugin_id: str,
        download_url: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Asynchronously downloads, verifies, extracts, and mounts a remote plugin from a verified registry.
        """
        tid = task_id or str(uuid.uuid4())[:8]
        self._tasks[tid] = {
            "task_id": tid,
            "plugin_id": plugin_id,
            "status": "downloading",
            "progress_percent": 5,
            "bytes_downloaded": 0,
            "total_bytes": 1024 * 1024 * 18,
            "error": None
        }

        try:
            plugin_folder_name = plugin_id if plugin_id.startswith("plugin_") else f"plugin_{plugin_id}"
            plugin_dest = self.target_dir / plugin_folder_name
            temp_bundle = self.target_dir / f"{plugin_folder_name}_temp.kmod"

            # 1. Download archive from registry if remote URL is configured
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
                self._tasks[tid]["status"] = "offline_registry"
                self._tasks[tid]["progress_percent"] = 0
                self._tasks[tid]["error"] = "Plugin registry URL not configured."
                return {
                    "success": False,
                    "task_id": tid,
                    "plugin_id": plugin_id,
                    "status": "REGISTRY_OFFLINE",
                    "message": f"Plugin registry endpoint not configured for '{plugin_id}'. Module is cataloged as remote on-demand."
                }

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

            # 4. Discover & Dynamically Activate
            # (No sys.path juggling: activation loads plugin.py by file location, and the user
            # plugin directory now lives outside the package tree entirely.)
            self._tasks[tid]["status"] = "activating"
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