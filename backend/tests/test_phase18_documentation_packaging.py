import os
import sys
import subprocess
import pytest

class TestPhase18DocumentationAndPackaging:
    """Test suite for Enterprise Documentation, Architecture Blueprints, and Packaging Verification."""

    @pytest.fixture
    def root_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def test_readme_and_governance_files_exist(self, root_dir):
        governance_files = ["README.md", "CONTRIBUTING.md", "SECURITY.md", "ARCHITECTURE.md"]
        for f_name in governance_files:
            f_path = os.path.join(root_dir, f_name)
            assert os.path.exists(f_path), f"Missing governance document: {f_name}"
            assert os.path.getsize(f_path) > 100, f"Document is empty or too short: {f_name}"

    def test_ascii_architecture_integrity(self, root_dir):
        readme_path = os.path.join(root_dir, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for Shields badges
        assert "img.shields.io" in content
        assert "KUANTRA TERMINAL" in content.upper()

        # Check for ASCII architecture diagrams
        assert "KUANTRA INSTITUTIONAL DESKTOP" in content
        assert "FASTAPI" in content.upper()
        assert "SQLITE" in content.upper()
        assert "DUCKDB" in content.upper()

        # Check for ModStore & Subsystems
        assert "MODSTORE" in content.upper()
        assert "REVERSE-SKILL" in content.upper() or "REVERSE_SKILL" in content.upper()

    def test_build_runbooks_structure(self, root_dir):
        runbooks = ["BUILD_WINDOWS.md", "BUILD_MACOS.md", "BUILD_LINUX.md"]
        for rb in runbooks:
            rb_path = os.path.join(root_dir, "docs", rb)
            assert os.path.exists(rb_path), f"Missing build runbook: {rb}"
            with open(rb_path, "r", encoding="utf-8") as f:
                rb_content = f.read()
            assert "Nuitka" in rb_content
            assert "Tauri" in rb_content

    def test_packaging_verification_script(self, root_dir):
        script_path = os.path.join(root_dir, "scripts", "verify_packaging.py")
        assert os.path.exists(script_path), "Missing verify_packaging.py script"

        # Execute verify script via python subprocess
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"verify_packaging.py failed: {result.stderr or result.stdout}"
        assert "[SUCCESS] ALL PACKAGING PRE-FLIGHT CHECKS PASSED" in result.stdout