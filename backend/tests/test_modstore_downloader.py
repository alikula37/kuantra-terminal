"""
Test Suite for ModStore Remote Downloader & Dynamic .kmod Extraction.
"""

import pytest
import os
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from main import create_app
from app.services.modstore_downloader import ModStoreDownloader, modstore_downloader
from app.services.plugin_manager import plugin_manager

app = create_app()
plugin_manager.set_app(app)
client = TestClient(app)

@pytest.fixture
def temp_plugins_dir(tmp_path):
    target = tmp_path / "plugins"
    target.mkdir()
    return target

@pytest.mark.asyncio
async def test_modstore_downloader_synthetic_lifecycle(temp_plugins_dir):
    downloader = ModStoreDownloader(target_dir=temp_plugins_dir)
    res = await downloader.download_and_install(
        plugin_id="mod_test_analytics",
        download_url=None,
        expected_sha256=None,
        task_id="test_task_1"
    )

    assert res["success"] is True
    assert res["task_id"] == "test_task_1"
    assert "plugin_mod_test_analytics" in res["plugin_id"]

    status = downloader.get_task_status("test_task_1")
    assert status is not None
    assert status["status"] == "completed"
    assert status["progress_percent"] == 100

def test_modstore_catalog_and_download_endpoints():
    # 1. Test catalog retrieval
    cat_res = client.get("/api/v1/plugins/modstore-catalog")
    assert cat_res.status_code == 200
    data = cat_res.json()
    assert "modules" in data
    assert len(data["modules"]) >= 4

    # 2. Test queueing download
    dl_res = client.post(
        "/api/v1/plugins/download",
        json={"plugin_id": "mod_options_greeks"}
    )
    assert dl_res.status_code == 200
    dl_data = dl_res.json()
    assert dl_data["status"] == "QUEUED"
    assert "task_id" in dl_data

    task_id = dl_data["task_id"]
    status_res = client.get(f"/api/v1/plugins/download-status/{task_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert "status" in status_data
    assert "progress_percent" in status_data