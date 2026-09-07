import os
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import diagnose_webview2  # noqa: E402


def test_webview2_version_comparison_is_fail_closed():
    assert diagnose_webview2._version_at_least("152.0.4191.66", "86.0.622.0")
    assert not diagnose_webview2._version_at_least("85.0.564.0", "86.0.622.0")
    assert not diagnose_webview2._version_at_least("unknown", "86.0.622.0")


def test_safe_environment_contains_only_diagnostic_keys(monkeypatch):
    monkeypatch.setenv("PYWEBVIEW_GUI", "edgechromium")
    monkeypatch.setenv("SECRET_SHOULD_NOT_APPEAR", "redacted")
    result = diagnose_webview2._safe_environment()
    assert result == {"PYWEBVIEW_GUI": "edgechromium"}
    assert "SECRET_SHOULD_NOT_APPEAR" not in result


def test_base_report_is_bounded_and_non_authoritative(tmp_path):
    report = diagnose_webview2._base_report(tmp_path / "webview2")
    assert report["renderer_expected"] == "edgechromium"
    assert report["renderer_controller_ready"] is False
    assert report["ok"] is False
    assert report["user_data_dir"] == str(tmp_path / "webview2")
