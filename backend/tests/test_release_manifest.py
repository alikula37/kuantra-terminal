import json
import os
import subprocess
import sys

import pytest

from app.version import __version__


class TestReleaseManifestAndPackaging:
    """Release verification and version synchronization for the pywebview desktop shell."""

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

    def test_manifest_generator_execution(self, root_dir, tmp_path):
        script_path = os.path.join(root_dir, "scripts", "generate_release_manifest.py")
        assert os.path.exists(script_path), "generate_release_manifest.py script must exist"

        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / f"Kuantra-Terminal-{__version__}-Setup.exe").write_bytes(b"MZ" + b"W" * 2048)
        (dist_dir / f"Kuantra-Terminal-{__version__}-aarch64.dmg").write_bytes(b"D" * 4096)
        (dist_dir / f"Kuantra-Terminal-{__version__}-x86_64.AppImage").write_bytes(b"A" * 1024)
        # Files that do not match the artifact prefix must be ignored.
        (dist_dir / "smoke.json").write_text("{}", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, script_path, "--dist", str(dist_dir), "--tag", f"v{__version__}"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Manifest generator failed: {result.stderr or result.stdout}"

        manifest_file = dist_dir / "MANIFEST.json"
        assert manifest_file.exists(), "MANIFEST.json must be generated in the dist directory"

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["release_tag"] == f"v{__version__}"
        assert manifest["version"] == __version__
        assert manifest["product_name"] == "Kuantra Terminal"
        assert manifest["total_artifacts"] == 3
        assert len(manifest["artifacts"]) == 3
        assert all(a["filename"].startswith("Kuantra-Terminal-") for a in manifest["artifacts"])

        platforms = {a["platform"] for a in manifest["artifacts"]}
        assert platforms == {"Windows", "macOS", "Linux"}

        for art in manifest["artifacts"]:
            assert "filename" in art
            assert "platform" in art
            assert "arch" in art
            assert "sha256" in art
            assert len(art["sha256"]) == 64  # Valid SHA-256 hex length
            assert art["size_bytes"] > 0

    def test_manifest_generator_dry_run_fabricates_nothing(self, root_dir, tmp_path):
        script_path = os.path.join(root_dir, "scripts", "generate_release_manifest.py")
        dist_dir = tmp_path / "empty-dist"

        result = subprocess.run(
            [sys.executable, script_path, "--dist", str(dist_dir), "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Dry run failed: {result.stderr or result.stdout}"

        with open(dist_dir / "MANIFEST.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["version"] == __version__
        assert manifest["release_tag"] == f"v{__version__}"
        assert manifest["total_artifacts"] == 0
        assert manifest["artifacts"] == []
        # No synthetic binaries may be written to disk.
        assert sorted(p.name for p in dist_dir.iterdir()) == ["MANIFEST.json"]

    def test_version_sync_across_manifests(self, root_dir):
        target_version = __version__

        # 1. Root package.json
        root_pkg_path = os.path.join(root_dir, "package.json")
        with open(root_pkg_path, "r", encoding="utf-8") as f:
            root_pkg = json.load(f)
        assert root_pkg["version"] == target_version, \
            f"Root package.json version mismatch: {root_pkg['version']}"

        # 2. Frontend package.json
        front_pkg_path = os.path.join(root_dir, "frontend", "package.json")
        with open(front_pkg_path, "r", encoding="utf-8") as f:
            front_pkg = json.load(f)
        assert front_pkg["version"] == target_version, \
            f"Frontend package.json version mismatch: {front_pkg['version']}"

        # 3. Backend app/version.py is the single source of truth; app/__init__.py re-exports it.
        version_py_path = os.path.join(root_dir, "backend", "app", "version.py")
        with open(version_py_path, "r", encoding="utf-8") as f:
            version_content = f.read()
        assert f'__version__ = "{target_version}"' in version_content, \
            "backend/app/version.py version mismatch"

        init_py_path = os.path.join(root_dir, "backend", "app", "__init__.py")
        with open(init_py_path, "r", encoding="utf-8") as f:
            init_content = f.read()
        assert "from app.version import __version__" in init_content, \
            "backend/app/__init__.py must re-export the single-source version"
