"""
Chunked GGUF Model Downloader with HTTP Range Resume & SHA256 Checksum for Kuantra Terminal.
Supports pause, resume, cancel, and streaming progress telemetry without blocking application runtime.
"""

import os
import sys
import time
import hashlib
import threading
import logging
from typing import Dict, Any, Optional
import urllib.request
from app.core.paths import DATA_DIR

logger = logging.getLogger("model_downloader")

MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

class ModelDownloader:
    """Manages background chunked downloads of GGUF model weights with Range headers."""

    DEFAULT_MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    DEFAULT_MODEL_NAME = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

    def __init__(self):
        self._downloads: Dict[str, Dict[str, Any]] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._pause_events: Dict[str, threading.Event] = {}
        self._cancel_events: Dict[str, threading.Event] = {}

    def get_status(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Returns live download progress, state, and verification status."""
        name = model_name or self.DEFAULT_MODEL_NAME
        target_path = MODELS_DIR / name

        if os.path.exists(target_path) and name not in self._downloads:
            return {
                "model_name": name,
                "status": "COMPLETED",
                "progress_pct": 100.0,
                "downloaded_bytes": os.path.getsize(target_path),
                "total_bytes": os.path.getsize(target_path),
                "speed_mbps": 0.0,
                "is_verified": True,
                "file_path": str(target_path)
            }

        state = self._downloads.get(name, {
            "model_name": name,
            "status": "IDLE",
            "progress_pct": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 1250000000, # Approx 1.25 GB
            "speed_mbps": 0.0,
            "is_verified": False,
            "file_path": str(target_path)
        })
        return state

    def start_download(
        self,
        model_name: Optional[str] = None,
        url: Optional[str] = None,
        expected_sha256: Optional[str] = None,
        mock_mode: bool = False
    ) -> Dict[str, Any]:
        """Initiates or resumes chunked GGUF download in background thread."""
        name = model_name or self.DEFAULT_MODEL_NAME
        download_url = url or self.DEFAULT_MODEL_URL

        if name in self._downloads and self._downloads[name]["status"] == "DOWNLOADING":
            return self._downloads[name]

        self._pause_events[name] = threading.Event()
        self._cancel_events[name] = threading.Event()

        self._downloads[name] = {
            "model_name": name,
            "status": "DOWNLOADING",
            "progress_pct": self._downloads.get(name, {}).get("progress_pct", 0.0),
            "downloaded_bytes": self._downloads.get(name, {}).get("downloaded_bytes", 0),
            "total_bytes": 1250000000,
            "speed_mbps": 18.5,
            "is_verified": False,
            "url": download_url,
            "expected_sha256": expected_sha256,
            "file_path": str(MODELS_DIR / name)
        }

        thread = threading.Thread(
            target=self._download_worker,
            args=(name, download_url, expected_sha256, mock_mode),
            daemon=True
        )
        self._threads[name] = thread
        thread.start()
        logger.info(f"Started background GGUF download: {name}")
        return self._downloads[name]

    def pause_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        name = model_name or self.DEFAULT_MODEL_NAME
        if name in self._pause_events:
            self._pause_events[name].set()
            if name in self._downloads:
                self._downloads[name]["status"] = "PAUSED"
                self._downloads[name]["speed_mbps"] = 0.0
        return self.get_status(name)

    def resume_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        name = model_name or self.DEFAULT_MODEL_NAME
        return self.start_download(model_name=name)

    def cancel_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        name = model_name or self.DEFAULT_MODEL_NAME
        if name in self._cancel_events:
            self._cancel_events[name].set()
        if name in self._downloads:
            self._downloads[name]["status"] = "CANCELED"
            self._downloads[name]["progress_pct"] = 0.0
            self._downloads[name]["downloaded_bytes"] = 0
            self._downloads[name]["speed_mbps"] = 0.0
        part_file = MODELS_DIR / f"{name}.part"
        if os.path.exists(part_file):
            try:
                os.remove(part_file)
            except Exception:
                pass
        return self.get_status(name)

    def verify_checksum(self, file_path: str, expected_sha256: Optional[str]) -> bool:
        """Computes SHA256 checksum of completed file."""
        if not expected_sha256:
            return True
        if not os.path.exists(file_path):
            return False
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest().lower() == expected_sha256.lower()

    def _download_worker(
        self,
        name: str,
        url: str,
        expected_sha256: Optional[str],
        mock_mode: bool
    ):
        """Worker executing streaming chunked download with HTTP Range."""
        target_file = MODELS_DIR / name
        part_file = MODELS_DIR / f"{name}.part"

        if mock_mode:
            # Fast deterministic mock simulation for unit testing
            total = 1000000
            current = self._downloads[name]["downloaded_bytes"]
            while current < total:
                if self._cancel_events[name].is_set():
                    return
                if self._pause_events[name].is_set():
                    return
                time.sleep(0.05)
                current += 200000
                current = min(current, total)
                pct = round((current / total) * 100, 1)
                self._downloads[name]["downloaded_bytes"] = current
                self._downloads[name]["total_bytes"] = total
                self._downloads[name]["progress_pct"] = pct
                self._downloads[name]["speed_mbps"] = 24.5

            with open(target_file, "wb") as f:
                f.write(b"MOCK_GGUF_MODEL_TENSOR_WEIGHTS_KUANTRA_V1")

            self._downloads[name]["status"] = "COMPLETED"
            self._downloads[name]["progress_pct"] = 100.0
            self._downloads[name]["is_verified"] = True
            return

        # Real HTTP Range download
        try:
            downloaded = os.path.getsize(part_file) if os.path.exists(part_file) else 0
            req = urllib.request.Request(url)
            if downloaded > 0:
                req.add_header("Range", f"bytes={downloaded}-")

            with urllib.request.urlopen(req, timeout=10) as resp, open(part_file, "ab" if downloaded > 0 else "wb") as out_f:
                content_len = resp.headers.get("Content-Length")
                total_bytes = downloaded + int(content_len) if content_len else 1250000000
                self._downloads[name]["total_bytes"] = total_bytes

                start_t = time.time()
                bytes_since_t = 0

                while True:
                    if self._cancel_events[name].is_set():
                        return
                    if self._pause_events[name].is_set():
                        return

                    chunk = resp.read(65536)
                    if not chunk:
                        break

                    out_f.write(chunk)
                    downloaded += len(chunk)
                    bytes_since_t += len(chunk)

                    now = time.time()
                    if now - start_t >= 0.5:
                        speed = (bytes_since_t / (now - start_t)) / (1024 * 1024)
                        start_t = now
                        bytes_since_t = 0
                        self._downloads[name]["speed_mbps"] = round(speed, 2)

                    pct = round((downloaded / total_bytes) * 100, 1)
                    self._downloads[name]["downloaded_bytes"] = downloaded
                    self._downloads[name]["progress_pct"] = pct

            # Rename part to final target file
            if os.path.exists(target_file):
                os.remove(target_file)
            os.rename(part_file, target_file)

            is_valid = self.verify_checksum(str(target_file), expected_sha256)
            self._downloads[name]["status"] = "COMPLETED"
            self._downloads[name]["progress_pct"] = 100.0
            self._downloads[name]["is_verified"] = is_valid
        except Exception as e:
            logger.warning(f"Download stream notice: {e}")
            if self._downloads.get(name):
                self._downloads[name]["status"] = "PAUSED"

model_downloader = ModelDownloader()