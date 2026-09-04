import os
import json
import time
import pytest
from app.core.hardware_detector import hardware_detector, HardwareDetector
from app.core.model_downloader import model_downloader
from app.db.sqlite_driver import sqlite_driver

class TestPhase10OnboardingAndProductionBuild:
    """Test suite for Hardware Detection, GGUF Downloader, Onboarding State, and Production Bundling."""

    def test_hardware_detection_profile_and_quant_selection(self):
        hw = hardware_detector.detect_hardware()
        assert "detected_backend" in hw
        assert hw["detected_backend"] in ["CUDA", "METAL", "DIRECTML", "VULKAN", "CPU"]
        assert "hardware_tier" in hw
        assert "recommended_quant" in hw
        assert hw["recommended_quant"] in ["Q4_K_M", "Q5_K_M", "Q8_0", "Q4_0"]
        assert hw["cpu_cores"] > 0
        assert hw["estimated_tokens_per_sec"] > 0

    def test_model_downloader_lifecycle_and_hash_integrity(self, tmp_path):
        test_model_name = "test_phase10_model.gguf"
        # Initial status
        init_st = model_downloader.get_status(test_model_name)
        assert init_st["status"] in ["IDLE", "COMPLETED", "DOWNLOADING", "PAUSED"]

        # Test authentic checksum verification
        sample_file = tmp_path / "sample_model.bin"
        sample_file.write_bytes(b"AUTHENTIC_GGUF_HEADER_STREAM_DATA")
        import hashlib
        expected_sha = hashlib.sha256(b"AUTHENTIC_GGUF_HEADER_STREAM_DATA").hexdigest()
        
        assert model_downloader.verify_checksum(str(sample_file), expected_sha) is True
        assert model_downloader.verify_checksum(str(sample_file), "0000000000000000000000000000000000000000000000000000000000000000") is False

    def test_model_downloader_pause_resume_cancel(self):
        test_model_name = "test_pause_cancel.gguf"
        # Pause
        pause_st = model_downloader.pause_download(test_model_name)
        assert pause_st["status"] in ["PAUSED", "IDLE", "COMPLETED"]

        # Cancel
        cancel_st = model_downloader.cancel_download(test_model_name)
        assert cancel_st["status"] in ["CANCELED", "IDLE"]


    def test_onboarding_state_persistence_and_settings(self):
        # Initial test
        sqlite_driver.set_setting("first_boot_completed", "false")
        val = sqlite_driver.get_setting("first_boot_completed")
        assert val == "false"

        # Complete onboarding with local_gguf mode
        sqlite_driver.set_setting("first_boot_completed", "true")
        sqlite_driver.set_setting("ai_mode", "local_gguf")

        assert sqlite_driver.get_setting("first_boot_completed") == "true"
        assert sqlite_driver.get_setting("ai_mode") == "local_gguf"

    def test_production_bundle_version_is_single_sourced(self):
        from app.version import __version__
        from app.core.config import settings

        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # backend/app/version.py is the single source of truth for the packaged build.
        assert __version__.count(".") == 2
        assert settings.version == __version__

        front_pkg_path = os.path.join(root_dir, "frontend", "package.json")
        with open(front_pkg_path, "r", encoding="utf-8") as f:
            front_pkg = json.load(f)
        assert front_pkg["version"] == __version__