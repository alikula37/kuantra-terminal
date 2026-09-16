from types import SimpleNamespace

from desktop.smoke import _check_journal_export, run_smoke


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
            "journal_export": False,
        },
    }


class _Call:
    def __init__(self, status, content):
        self.status = status
        self.content = content


class _Runtime:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def call(self, method, path, query=""):
        self.requests.append((method, path, query))
        return self.responses[len(self.requests) - 1]


def test_journal_export_smoke_check_accepts_frozen_artifacts():
    runtime = _Runtime([
        _Call(200, b"%PDF-1.4 fake"),
        _Call(200, b"\xef\xbb\xbfkayit_no"),
        _Call(200, b"{}"),
    ])
    assert _check_journal_export(SimpleNamespace(runtime=runtime)) is True
    assert runtime.requests[0][2] == "format=pdf&scope=all&lang=tr"


def test_journal_export_smoke_check_rejects_missing_fonts_or_failures():
    bad_pdf = _Runtime([_Call(200, b"not a pdf"), _Call(200, b"\xef\xbb\xbf"), _Call(200, b"{}")])
    assert _check_journal_export(SimpleNamespace(runtime=bad_pdf)) is False
    bad_csv = _Runtime([_Call(200, b"%PDF"), _Call(200, b"kayit_no"), _Call(200, b"{}")])
    assert _check_journal_export(SimpleNamespace(runtime=bad_csv)) is False
    bad_preview = _Runtime([_Call(200, b"%PDF"), _Call(200, b"\xef\xbb\xbf"), _Call(500, b"{}")])
    assert _check_journal_export(SimpleNamespace(runtime=bad_preview)) is False
