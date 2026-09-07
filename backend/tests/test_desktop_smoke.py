from types import SimpleNamespace

from desktop.smoke import run_smoke


class _NeverReady:
    def wait(self, timeout):
        return False


def test_smoke_fails_fast_when_renderer_controller_never_becomes_ready():
    window = SimpleNamespace(events=SimpleNamespace(_pywebviewready=_NeverReady()))
    result = run_smoke(window, ctx=object(), timeout=0.01)
    assert result == {
        "ok": False,
        "reason": "renderer controller did not become ready",
        "checks": {
            "react_mounted": False,
            "bridge_roundtrip": False,
            "health": False,
            "push_sink": False,
            "plugin_boundary": False,
        },
    }
