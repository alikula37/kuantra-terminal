import base64
import json
import time
import pytest
from desktop.runtime import BackendRuntime
from desktop.push import PushChannel
from desktop.bridge import DesktopBridge


class FakeDialogWindow:
    def __init__(self, path):
        self._path = path
        self.created = []

    def create_file_dialog(self, kind, save_filename="", **kw):
        return self._path


@pytest.fixture(scope="module")
def runtime():
    rt = BackendRuntime()
    rt.start(timeout=60)
    yield rt
    rt.stop()


@pytest.fixture
def bridge(runtime, tmp_path):
    push = PushChannel()
    dialog = FakeDialogWindow(str(tmp_path / "out.csv"))
    b = DesktopBridge(runtime, push, gateway=None, index_url="file:///tmp/index.html",
                      dialog_window_getter=lambda: dialog)
    yield b
    b._close()


def test_request_json(bridge):
    r = bridge.request({"method": "GET", "path": "/health", "query": "", "headers": {}, "body": None, "files": [], "fields": []})
    assert r["status"] == 200
    assert json.loads(r["body"])["status"] == "online"
    assert r["body_b64"] is None
    assert "content-type" in r["headers"]


def test_request_strips_framing_headers(bridge):
    r = bridge.request({"method": "GET", "path": "/health", "query": "", "headers": {}, "body": None, "files": [], "fields": []})
    lowered = {k.lower() for k in r["headers"]}
    assert "content-length" not in lowered
    assert not lowered & {"content-encoding", "transfer-encoding", "connection", "keep-alive", "upgrade"}
    assert "content-type" in lowered  # the useful headers still come through


def test_request_multipart(bridge):
    csv = base64.b64encode(b"symbol,side,qty,price\nBTCUSDT,BUY,1,100\n").decode()
    r = bridge.request({"method": "POST", "path": "/api/v1/journal/preview-csv", "query": "", "headers": {},
                        "body": None, "files": [{"field": "file", "filename": "t.csv", "content_type": "text/csv", "data_b64": csv}], "fields": []})
    assert r["status"] in (200, 400, 422)


def test_request_binary_body_is_base64(bridge, tmp_path):
    r = bridge.request({"method": "GET", "path": "/api/v1/telemetry/export-logs", "query": "", "headers": {}, "body": None, "files": [], "fields": []})
    assert r["status"] in (200, 404, 500)
    if r["status"] == 200:
        assert r["body"] is None and r["body_b64"]


def test_evidence_pack_job_is_async_and_completes(bridge):
    started_at = time.perf_counter()
    started = bridge.start_evidence_pack({"trade_id": "MISSING"})
    elapsed = time.perf_counter() - started_at

    assert started["status"] == "PENDING"
    assert len(started["job_id"]) == 32
    assert elapsed < 0.5

    deadline = time.monotonic() + 5
    result = None
    while time.monotonic() < deadline:
        result = bridge.get_evidence_pack_job({"job_id": started["job_id"]})
        if result["status"] != "PENDING":
            break
        time.sleep(0.01)
    assert result is not None and result["status"] == "COMPLETED"
    assert result["response"]["status"] == 404


def test_evidence_pack_job_rejects_invalid_or_unknown_requests(bridge):
    rejected = bridge.start_evidence_pack({"trade_id": "../outside"})
    assert rejected["status"] == "REJECTED"
    assert rejected["response"]["status"] == 400

    missing = bridge.get_evidence_pack_job({"job_id": "not-a-job"})
    assert missing["status"] == "FAILED"
    assert missing["response"]["status"] == 400

    unknown = bridge.get_evidence_pack_job({"job_id": "0" * 32})
    assert unknown["status"] == "FAILED"
    assert unknown["response"]["status"] == 404


def test_stream_open_returns_snapshot_and_attaches(bridge, runtime):
    snap = bridge.stream_open()
    assert snap["type"] == "SNAPSHOT" and "last_price" in snap
    from app.websocket.connection_manager import ws_manager
    assert bridge._push in ws_manager.active_connections
    bridge.stream_open()  # idempotent
    assert list(ws_manager.active_connections).count(bridge._push) == 1


def test_save_file_text_and_base64(bridge, tmp_path):
    r = bridge.save_file({"filename": "a.csv", "content": "x,y\n1,2\n", "encoding": "text"})
    assert r["saved"] is True and open(r["path"]).read() == "x,y\n1,2\n"
    r = bridge.save_file({"filename": "b.bin", "content": base64.b64encode(b"\x00\x01").decode(), "encoding": "base64"})
    assert open(r["path"], "rb").read() == b"\x00\x01"


def test_download_uses_backend_and_dialog(bridge):
    r = bridge.download({"path": "/api/v1/journal/template-csv", "filename": "template.csv"})
    assert r["saved"] is True
    assert open(r["path"], "rb").read().strip() != b""


def test_open_external_rejects_non_http(bridge, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert bridge.open_external("file:///etc/passwd") == {"ok": False}
    assert bridge.open_external("https://example.com") == {"ok": True}
    assert opened == ["https://example.com"]


def test_only_intended_methods_are_exposed_to_js(bridge):
    """pywebview publishes every public attribute of js_api, recursing into non-callable objects.

    A public `self.runtime`/`self.push`/`self.gateway` would therefore hand the UI (and anything
    running in it) the backend loop and the uvicorn server themselves, `stop()` included.
    """
    public = {n for n in dir(bridge) if not n.startswith("_")}
    assert {n for n in public if callable(getattr(bridge, n))} == {
        "request", "stream_open", "open_popout", "save_file", "download",
        "copy_text", "open_external", "get_app_info", "start_evidence_pack",
        "get_evidence_pack_job",
    }
    for name in public:
        value = getattr(bridge, name)
        if not callable(value):
            assert not hasattr(value, "stop"), f"public attribute {name!r} exposes a stoppable object to JS"


def test_get_app_info(bridge):
    info = bridge.get_app_info()
    from app.version import __version__
    assert info["version"] == __version__ and info["gateway_url"] is None and "data_dir" in info
