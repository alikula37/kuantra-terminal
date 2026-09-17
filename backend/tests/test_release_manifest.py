import json
import os
import subprocess
import sys

import pytest

from app.version import __version__
from scripts import generate_release_manifest
from scripts.release_truth import canonical_matrix_digest, load_matrix


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

        assert "Kuantra Terminal v1.1.5 — Trusted macOS Pilot" in content
        assert "Kuantra-Terminal-1.1.5-arm64.dmg" in content
        assert "Kuantra-Terminal-1.1.5-x86_64.dmg" in content
        assert "CURRENT_RELEASE_NOTES:START" in content
        assert "CURRENT_RELEASE_NOTES:END" in content
        assert "Historical release archive (non-current)" in content
        assert "docs/release/truth-matrix.v1.1.5.json" in content
        # Historical notes remain auditable in the repository, but they are not the current
        # release body. The renderer/checker enforce that boundary before publishing.
        assert "v1.2.0-modular" in content

    def test_manifest_generator_execution(self, root_dir, tmp_path):
        script_path = os.path.join(root_dir, "scripts", "generate_release_manifest.py")
        assert os.path.exists(script_path), "generate_release_manifest.py script must exist"

        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / f"Kuantra-Terminal-{__version__}-arm64.dmg").write_bytes(b"A" * 4096)
        (dist_dir / f"Kuantra-Terminal-{__version__}-x86_64.dmg").write_bytes(b"X" * 4096)
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
        assert manifest["truth_matrix"]["document_id"] == "KTR-001"
        assert manifest["truth_matrix"]["version"] == "1.1.5"
        assert manifest["truth_matrix"]["sha256"] == canonical_matrix_digest(load_matrix())
        assert manifest["total_artifacts"] == 2
        assert len(manifest["artifacts"]) == 2
        assert all(a["filename"].startswith("Kuantra-Terminal-") for a in manifest["artifacts"])

        platforms = {a["platform"] for a in manifest["artifacts"]}
        assert platforms == {"macOS"}
        assert {a["arch"] for a in manifest["artifacts"]} == {"arm64", "x86_64"}

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

    def test_manifest_binds_each_n05_report_to_the_exact_architecture_artifact(
        self, tmp_path, monkeypatch
    ):
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        arm64 = dist_dir / f"Kuantra-Terminal-{__version__}-arm64.dmg"
        x86_64 = dist_dir / f"Kuantra-Terminal-{__version__}-x86_64.dmg"
        arm64.write_bytes(b"arm64 artifact")
        x86_64.write_bytes(b"x86_64 artifact")

        reports = []
        for artifact in (arm64, x86_64):
            report = tmp_path / f"{artifact.stem}-n05.json"
            report.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "source": {"commit_sha": "a" * 40},
                        "artifacts": {
                            "dmg_sha256": generate_release_manifest.compute_sha256(str(artifact)),
                        },
                    }
                ),
                encoding="utf-8",
            )
            reports.append(str(report))

        # The N05 contract is covered by its own suite; this test isolates the
        # manifest's exact artifact/report binding and multi-architecture shape.
        monkeypatch.setattr(generate_release_manifest, "validate_n05_report", lambda *args, **kwargs: None)
        manifest = generate_release_manifest.generate_manifest(
            dist_dir=str(dist_dir),
            tag=f"v{__version__}",
            macos_distribution_reports=reports,
        )

        assert set(manifest["distribution_attestations"]) == {"macOS-arm64", "macOS-x86_64"}
        assert manifest["distribution_attestations"]["macOS-arm64"]["artifact_filename"] == arm64.name
        assert manifest["distribution_attestations"]["macOS-x86_64"]["artifact_filename"] == x86_64.name
        assert manifest["distribution_attestations"]["macOS-arm64"]["architecture"] == "arm64"
        assert manifest["distribution_attestations"]["macOS-x86_64"]["architecture"] == "x86_64"

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
