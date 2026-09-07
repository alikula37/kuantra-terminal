import logging

import pytest

import desktop_main


def test_qt_preflight_is_noop_for_non_qt_renderer(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_frozen", lambda: False)
    desktop_main._preflight_renderer("edgechromium", logging.getLogger("test"))


def test_qt_preflight_is_noop_for_development_runs(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_frozen", lambda: False)
    desktop_main._preflight_renderer("qt", logging.getLogger("test"))


def test_windows_default_renderer_is_webview2(monkeypatch):
    monkeypatch.setattr(desktop_main.sys, "platform", "win32")
    monkeypatch.delenv("PYWEBVIEW_GUI", raising=False)
    assert desktop_main._default_gui() == "edgechromium"


def test_webview2_version_comparison_is_fail_closed():
    assert desktop_main._version_at_least("120.0.2210.61", "86.0.622.0")
    assert not desktop_main._version_at_least("85.0.564.0", "86.0.622.0")
    assert not desktop_main._version_at_least("unknown", "86.0.622.0")


def test_frozen_webview2_preflight_rejects_missing_runtime(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_frozen", lambda: True)
    monkeypatch.setattr(desktop_main, "_webview2_runtime_available", lambda: False)
    with pytest.raises(RuntimeError, match="runtime is not installed"):
        desktop_main._preflight_renderer("edgechromium", logging.getLogger("test"))


def test_frozen_windows_rejects_explicit_mshtml_fallback(monkeypatch):
    monkeypatch.setattr(desktop_main, "is_frozen", lambda: True)
    with pytest.raises(RuntimeError, match="require the edgechromium renderer"):
        desktop_main._preflight_renderer("mshtml", logging.getLogger("test"))


def test_windows_smoke_uses_visible_webview2_host():
    assert desktop_main._window_hidden_for_smoke(True, "edgechromium") is False
    assert desktop_main._window_hidden_for_smoke(True, "qt") is True
    assert desktop_main._window_hidden_for_smoke(False, "edgechromium") is False
