import os
import sys
import io
import pytest
from build_sidecar import (
    get_target_triple,
    get_binary_name,
    build_nuitka_command,
    run_build,
)
from main import find_available_port, report_port_handshake
from app.core.parent_watcher import (
    is_process_alive,
    ParentProcessWatcher,
    start_parent_watcher,
)

class TestSidecarPipelineAndLifecycle:
    """Test suite for Nuitka C++ compilation pipeline, dynamic port allocation, and parent process watcher."""

    def test_target_triple_detection(self):
        triple = get_target_triple()
        assert triple is not None
        assert len(triple) > 0
        assert any(os_tag in triple for os_tag in ["windows", "linux", "darwin"])

    def test_binary_name_convention(self):
        triple = "x86_64-pc-windows-msvc"
        name = get_binary_name(triple)
        assert name == "kuantra-backend-x86_64-pc-windows-msvc.exe"

        triple_linux = "x86_64-unknown-linux-gnu"
        name_linux = get_binary_name(triple_linux)
        assert name_linux == "kuantra-backend-x86_64-unknown-linux-gnu"

    def test_nuitka_command_generation(self):
        cmd = build_nuitka_command(output_dir="test_binaries", target_triple="x86_64-pc-windows-msvc")
        cmd_str = " ".join(cmd)
        
        assert "nuitka" in cmd_str
        assert "--standalone" in cmd
        assert "--onefile" in cmd
        assert "--plugin-enable=pydantic" in cmd
        assert "--include-package=app" in cmd
        assert "--include-package=duckdb" in cmd
        assert "--include-package=sqlite3" in cmd
        assert "kuantra-backend-x86_64-pc-windows-msvc.exe" in cmd_str

    def test_build_dry_run_execution(self):
        ret = run_build(output_dir="src-tauri/binaries", dry_run=True)
        assert ret == 0

    def test_find_available_port_dynamic_allocation(self):
        port1 = find_available_port()
        port2 = find_available_port()
        assert port1 > 1024
        assert port2 > 1024
        assert port1 < 65536
        assert port2 < 65536

    def test_stdout_handshake_formatting(self, capsys):
        report_port_handshake(9876)
        captured = capsys.readouterr()
        assert "KUANTRA_BACKEND_PORT:9876" in captured.out

    def test_parent_process_watcher_active_check(self):
        current_pid = os.getpid()
        assert is_process_alive(current_pid) is True
        assert is_process_alive(0) is False
        assert is_process_alive(-1) is False
        assert is_process_alive(99999999) is False

    def test_parent_watcher_lifecycle(self):
        current_pid = os.getpid()
        watcher = start_parent_watcher(parent_pid=current_pid, poll_interval=0.2)
        assert watcher is not None
        assert watcher._thread is not None
        assert watcher._thread.is_alive() is True
        watcher.stop()