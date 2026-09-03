import os

import pytest
import yaml


class TestCICDWorkflowsAndPackaging:
    """Test suite for the pywebview/PyInstaller GitHub Actions CI and release pipelines."""

    @pytest.fixture
    def root_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_ci_workflow_yaml_syntax(self, root_dir):
        ci_path = os.path.join(root_dir, ".github", "workflows", "ci.yml")
        assert os.path.exists(ci_path), ".github/workflows/ci.yml must exist"

        with open(ci_path, "r", encoding="utf-8") as f:
            ci_raw = f.read()
        ci_data = yaml.safe_load(ci_raw)

        assert "name" in ci_data
        # Triggers (PyYAML parses the bare `on:` key as the boolean True)
        triggers = ci_data.get("on", ci_data.get(True, {}))
        assert "push" in triggers
        assert "pull_request" in triggers

        # Jobs
        assert "jobs" in ci_data
        assert "test-and-build" in ci_data["jobs"]

        job = ci_data["jobs"]["test-and-build"]
        assert "strategy" in job
        matrix = job["strategy"]["matrix"]
        assert "os" in matrix
        assert matrix["os"] == ["windows-latest", "macos-latest", "ubuntu-22.04"]

        # Steps
        steps = job["steps"]
        step_names = [s.get("name", "") for s in steps]
        step_uses = [s.get("uses", "") for s in steps]

        assert any("checkout" in u.lower() for u in step_uses)
        assert any("setup-python" in u.lower() for u in step_uses)
        assert any("setup-node" in u.lower() for u in step_uses)
        assert any("upload-artifact" in u.lower() for u in step_uses)

        for required_step in (
            "Run backend tests",
            "Frontend tests and build",
            "Build desktop app",
            "Smoke test desktop app",
        ):
            assert required_step in step_names, f"ci.yml must have a '{required_step}' step"

        # The Rust toolchain is gone with the Tauri shell.
        assert "rust-toolchain" not in ci_raw
        assert not any("rust-toolchain" in u.lower() for u in step_uses)

    def test_release_workflow_yaml_syntax(self, root_dir):
        rel_path = os.path.join(root_dir, ".github", "workflows", "release.yml")
        assert os.path.exists(rel_path), ".github/workflows/release.yml must exist"

        with open(rel_path, "r", encoding="utf-8") as f:
            rel_raw = f.read()
        rel_data = yaml.safe_load(rel_raw)

        assert "name" in rel_data
        assert "permissions" in rel_data
        assert rel_data["permissions"].get("contents") == "write"

        # Triggers: tag pushes only
        triggers = rel_data.get("on", rel_data.get(True, {}))
        assert "push" in triggers
        assert triggers["push"]["tags"] == ["v*"]

        # Jobs
        assert "jobs" in rel_data
        assert "build-and-package" in rel_data["jobs"]
        assert "publish-release" in rel_data["jobs"]

        bp_job = rel_data["jobs"]["build-and-package"]
        matrix_includes = bp_job["strategy"]["matrix"]["include"]
        oses = [m["os"] for m in matrix_includes]
        packages = [m["package"] for m in matrix_includes]

        assert "windows-latest" in oses
        assert "macos-latest" in oses
        assert "ubuntu-22.04" in oses

        for script in (
            "scripts/package_windows.sh",
            "scripts/package_macos.sh",
            "scripts/package_linux.sh",
        ):
            assert any(script in p for p in packages), f"release.yml must run {script}"

        # Check steps in build-and-package
        bp_steps = bp_job["steps"]
        bp_uses = [s.get("uses", "") for s in bp_steps]
        bp_names = [s.get("name", "") for s in bp_steps]

        assert any("checkout" in u.lower() for u in bp_uses)
        assert any("upload-artifact" in u.lower() for u in bp_uses)
        assert "Build desktop app" in bp_names
        assert "Smoke test desktop app" in bp_names
        assert "Package" in bp_names

        # Check publish-release job
        pub_job = rel_data["jobs"]["publish-release"]
        assert pub_job.get("needs") == "build-and-package"
        pub_steps = pub_job["steps"]
        pub_uses = [s.get("uses", "") for s in pub_steps]
        pub_names = [s.get("name", "") for s in pub_steps]
        assert any("download-artifact" in u.lower() for u in pub_uses)
        assert any("softprops/action-gh-release" in u.lower() for u in pub_uses)
        # Consolidated checksums live in MANIFEST.json, generated in publish-release
        assert any("manifest" in n.lower() for n in pub_names)
        assert "scripts/generate_release_manifest.py" in rel_raw

        # No Rust / Tauri leftovers in the release pipeline.
        assert "rust-toolchain" not in rel_raw
        assert "tauri" not in rel_raw.lower()

    def test_legacy_tauri_and_nuitka_artifacts_removed(self, root_dir):
        for legacy in (
            os.path.join("backend", "build_sidecar.py"),
            os.path.join("backend", "kuantra-backend-x86_64-pc-windows-msvc.spec"),
            os.path.join("backend", "kuantra-backend-aarch64-apple-darwin.spec"),
            os.path.join("backend", "kuantra-backend.spec"),
            os.path.join(".github", "workflows", "cleanup-release-assets.yml"),
        ):
            assert not os.path.exists(os.path.join(root_dir, legacy)), \
                f"Legacy Tauri/Nuitka artifact must be deleted: {legacy}"
