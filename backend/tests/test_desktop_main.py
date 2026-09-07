import json
import subprocess
import sys
from pathlib import Path
import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_resolve_frontend_index_dev(tmp_path):
    import desktop_main
    (tmp_path / "index.html").write_text("<html></html>")
    assert desktop_main.resolve_frontend_index(str(tmp_path)) == tmp_path / "index.html"
    with pytest.raises(FileNotFoundError):
        desktop_main.resolve_frontend_index(str(tmp_path / "nope"))


def test_cli_parser_defaults():
    import desktop_main
    args = desktop_main.parse_args([])
    assert args.smoke is False and args.dev_url is None and args.gui is None
    args = desktop_main.parse_args(["--smoke", "--smoke-report", "r.json", "--smoke-timeout", "5"])
    assert args.smoke and args.smoke_report == "r.json" and args.smoke_timeout == 5.0


def test_macos_uses_native_cocoa_renderer(monkeypatch):
    import desktop_main

    monkeypatch.setattr(desktop_main.sys, "platform", "darwin")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    assert desktop_main._default_gui() is None
    monkeypatch.setenv("PYWEBVIEW_GUI", "cocoa")
    assert desktop_main._default_gui() == "cocoa"


def test_main_py_has_no_sidecar_handshake():
    src = (BACKEND / "main.py").read_text()
    assert "KUANTRA_BACKEND_PORT" not in src and "parent-pid" not in src
    assert not (BACKEND / "app" / "core" / "parent_watcher.py").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="GUI smoke runs on the macOS dev box; CI covers the others")
def test_smoke_mode_end_to_end(tmp_path):
    dist = BACKEND.parent / "frontend" / "dist" / "index.html"
    if not dist.exists():
        pytest.skip("frontend not built")
    report = tmp_path / "smoke.json"
    proc = subprocess.run([sys.executable, str(BACKEND / "desktop_main.py"), "--smoke", "--smoke-report", str(report), "--smoke-timeout", "60"],
                          cwd=str(BACKEND), capture_output=True, text=True, timeout=180,
                          env={**__import__("os").environ, "KUANTRA_DATA_DIR": str(tmp_path / "data"), "KUANTRA_GATEWAY_ENABLED": "0"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(report.read_text())
    assert data["ok"] is True and data["checks"]["react_mounted"] and data["checks"]["bridge_roundtrip"]
