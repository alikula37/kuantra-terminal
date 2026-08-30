import os
import json
import subprocess
import pytest

class TestReleaseManifestAndPackaging:
    """Test suite for Official v1.2.0-modular Release Verification & Version Synchronization."""

    @pytest.fixture
    def root_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_release_notes_integrity(self, root_dir):
        notes_path = os.path.join(root_dir, "RELEASE_NOTES.md")
        assert os.path.exists(notes_path), "RELEASE_NOTES.md must exist at root"

        with open(notes_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "v1.2.0-modular" in content, "Release tag v1.2.0-modular must be present"
        assert "23-Phase Architectural Completion Matrix" in content
        assert "Micro-Kernel Base & Lazy Dependency Loader" in content
        assert "Five Architectural Persona Presets" in content
        assert "In-App ModStore Marketplace Studio" in content

        # Verify all 23 phases are listed
        for phase_num in range(1, 24):
            phase_tag = f"Phase {phase_num:02d}"
            assert phase_tag in content, f"Milestone '{phase_tag}' must be in RELEASE_NOTES.md"

    def test_manifest_generator_execution(self, root_dir):
        script_path = os.path.join(root_dir, "scripts", "generate_release_manifest.py")
        assert os.path.exists(script_path), "generate_release_manifest.py script must exist"

        # Execute manifest generator in dry-run mode
        result = subprocess.run(
            [os.sys.executable, script_path, "--dry-run"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Manifest generator failed: {result.stderr or result.stdout}"

        # Verify generated MANIFEST.json
        manifest_file = os.path.join(root_dir, "dist-binaries", "MANIFEST.json")
        assert os.path.exists(manifest_file), "MANIFEST.json must be generated in dist-binaries/"

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["release_tag"] == "v1.2.0-modular"
        assert manifest["version"] == "1.2.0"
        assert manifest["total_artifacts"] >= 4
        assert len(manifest["artifacts"]) >= 4

        for art in manifest["artifacts"]:
            assert "filename" in art
            assert "platform" in art
            assert "arch" in art
            assert "sha256" in art
            assert len(art["sha256"]) == 64  # Valid SHA-256 hex length
            assert art["size_bytes"] > 0

    def test_version_sync_across_manifests(self, root_dir):
        target_version = "1.2.0"

        # 1. Root package.json
        root_pkg_path = os.path.join(root_dir, "package.json")
        with open(root_pkg_path, "r", encoding="utf-8") as f:
            root_pkg = json.load(f)
        assert root_pkg["version"] == target_version, f"Root package.json version mismatch: {root_pkg['version']}"

        # 2. Frontend package.json
        front_pkg_path = os.path.join(root_dir, "frontend", "package.json")
        with open(front_pkg_path, "r", encoding="utf-8") as f:
            front_pkg = json.load(f)
        assert front_pkg["version"] == target_version, f"Frontend package.json version mismatch: {front_pkg['version']}"

        # 3. Tauri tauri.conf.json
        tauri_conf_path = os.path.join(root_dir, "src-tauri", "tauri.conf.json")
        with open(tauri_conf_path, "r", encoding="utf-8") as f:
            tauri_conf = json.load(f)
        assert tauri_conf["version"] == target_version, f"tauri.conf.json version mismatch: {tauri_conf['version']}"

        # 4. Backend app/__init__.py
        init_py_path = os.path.join(root_dir, "backend", "app", "__init__.py")
        with open(init_py_path, "r", encoding="utf-8") as f:
            init_content = f.read()
        assert f'__version__ = "{target_version}"' in init_content, "backend/app/__init__.py version mismatch"