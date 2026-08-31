import os
import yaml
import pytest
from build_sidecar import get_target_triple, get_binary_name, build_nuitka_command

class TestCICDWorkflowsAndPackaging:
    """Test suite for GitHub Actions CI/CD workflows, YAML integrity, and sidecar matrix mappings."""

    @pytest.fixture
    def root_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_ci_workflow_yaml_syntax(self, root_dir):
        ci_path = os.path.join(root_dir, ".github", "workflows", "ci.yml")
        assert os.path.exists(ci_path), ".github/workflows/ci.yml must exist"

        with open(ci_path, "r", encoding="utf-8") as f:
            ci_data = yaml.safe_load(f)

        assert "name" in ci_data
        # Triggers
        triggers = ci_data.get("on", {}) or ci_data.get(True, {})
        assert "push" in triggers or True in triggers
        assert "pull_request" in triggers or True in triggers

        # Jobs
        assert "jobs" in ci_data
        assert "test-and-lint" in ci_data["jobs"]

        job = ci_data["jobs"]["test-and-lint"]
        assert "strategy" in job
        matrix = job["strategy"]["matrix"]
        assert "os" in matrix
        assert "windows-latest" in matrix["os"]
        assert "macos-latest" in matrix["os"]
        assert "ubuntu-latest" in matrix["os"]

        # Steps
        steps = job["steps"]
        step_names = [s.get("name", "") for s in steps]
        step_uses = [s.get("uses", "") for s in steps]

        assert any("checkout" in u.lower() for u in step_uses)
        assert any("setup-python" in u.lower() for u in step_uses)
        assert any("setup-node" in u.lower() for u in step_uses)
        assert any("rust-toolchain" in u.lower() for u in step_uses)
        assert any("pytest" in n.lower() or "test" in n.lower() for n in step_names)
        assert any("frontend" in n.lower() or "build" in n.lower() for n in step_names)

    def test_release_workflow_yaml_syntax(self, root_dir):
        rel_path = os.path.join(root_dir, ".github", "workflows", "release.yml")
        assert os.path.exists(rel_path), ".github/workflows/release.yml must exist"

        with open(rel_path, "r", encoding="utf-8") as f:
            rel_data = yaml.safe_load(f)

        assert "name" in rel_data
        assert "permissions" in rel_data
        assert rel_data["permissions"].get("contents") == "write"

        # Jobs
        assert "jobs" in rel_data
        assert "build-and-package" in rel_data["jobs"]
        assert "publish-release" in rel_data["jobs"]

        bp_job = rel_data["jobs"]["build-and-package"]
        matrix_includes = bp_job["strategy"]["matrix"]["include"]
        targets = [m["target"] for m in matrix_includes]

        assert "x86_64-pc-windows-msvc" in targets
        assert "aarch64-apple-darwin" in targets
        assert "x86_64-unknown-linux-gnu" in targets

        # Check steps in build-and-package
        bp_steps = bp_job["steps"]
        bp_uses = [s.get("uses", "") for s in bp_steps]
        bp_names = [s.get("name", "") for s in bp_steps]

        assert any("checkout" in u.lower() for u in bp_uses)
        assert any("upload-artifact" in u.lower() for u in bp_uses)
        # Staging step renames bundles to clean asset names (no individual .sha256 files)
        assert any("rename" in n.lower() or "clean" in n.lower() or "bundle" in n.lower() for n in bp_names)

        # Check publish-release job
        pub_job = rel_data["jobs"]["publish-release"]
        assert pub_job.get("needs") == "build-and-package"
        pub_steps = pub_job["steps"]
        pub_uses = [s.get("uses", "") for s in pub_steps]
        pub_names = [s.get("name", "") for s in pub_steps]
        assert any("download-artifact" in u.lower() for u in pub_uses)
        assert any("action-gh-release" in u.lower() for u in pub_uses)
        # Consolidated checksums are in MANIFEST.json generated in publish-release
        assert any("manifest" in n.lower() or "checksum" in n.lower() or "sha-256" in n.lower() for n in pub_names)

    def test_sidecar_target_triple_mappings(self):
        # 1. Windows x64
        win_bin = get_binary_name("x86_64-pc-windows-msvc")
        assert win_bin == "kuantra-backend-x86_64-pc-windows-msvc.exe"

        # 2. macOS Apple Silicon (ARM64)
        mac_arm = get_binary_name("aarch64-apple-darwin")
        assert mac_arm == "kuantra-backend-aarch64-apple-darwin"

        # 3. macOS Intel (x64)
        mac_intel = get_binary_name("x86_64-apple-darwin")
        assert mac_intel == "kuantra-backend-x86_64-apple-darwin"

        # 4. Linux x64
        linux_bin = get_binary_name("x86_64-unknown-linux-gnu")
        assert linux_bin == "kuantra-backend-x86_64-unknown-linux-gnu"

        # 5. Nuitka Command Generation
        cmd = build_nuitka_command(
            output_dir="../src-tauri/binaries",
            entry_point="main.py",
            target_triple="x86_64-pc-windows-msvc"
        )
        assert "--onefile" in cmd
        assert "--standalone" in cmd
        assert "--output-filename=kuantra-backend-x86_64-pc-windows-msvc.exe" in cmd