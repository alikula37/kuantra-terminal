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
            "evidence_worker": False,
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


def test_smoke_export_failure_is_not_success(monkeypatch):
    import desktop.smoke as smoke
    window = SimpleNamespace(evaluate_js=lambda script, **_kw: "synthetic" if "innerText" in script else 1)
    runtime = _Runtime([_Call(200, b'{"status":"online"}')])
    monkeypatch.setattr(smoke, "_eval", lambda *_a: {"version": "synthetic"})
    monkeypatch.setattr(smoke, "_check_plugin_boundary", lambda _ctx: True)
    monkeypatch.setattr(smoke, "_check_journal_export", lambda _ctx: False)
    monkeypatch.setattr(smoke, "_check_evidence_worker", lambda _ctx: True)
    monkeypatch.delenv("KUANTRA_SMOKE_LOCAL_TRACKING", raising=False)
    result = run_smoke(window, SimpleNamespace(runtime=runtime), timeout=1)
    assert result["checks"]["journal_export"] is False
    assert result["ok"] is False


def test_worker_failure_cannot_pass_packaged_smoke(monkeypatch):
    import desktop.smoke as smoke
    window = SimpleNamespace(evaluate_js=lambda script, **_kw: "synthetic" if "innerText" in script else 1)
    runtime = _Runtime([_Call(200, b'{"status":"online"}')])
    monkeypatch.setattr(smoke, "_eval", lambda *_a: {"version": "synthetic"})
    monkeypatch.setattr(smoke, "_check_plugin_boundary", lambda _ctx: True)
    monkeypatch.setattr(smoke, "_check_journal_export", lambda _ctx: True)
    monkeypatch.setattr(smoke, "_check_evidence_worker", lambda _ctx: False)
    monkeypatch.delenv("KUANTRA_SMOKE_LOCAL_TRACKING", raising=False)
    assert run_smoke(window, SimpleNamespace(runtime=runtime), timeout=1)["ok"] is False
