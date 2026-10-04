from desktop.bridge import DesktopBridge
from desktop.push import PushChannel
from app.services import local_backup


class Dialog:
    def __init__(self, selected):
        self.selected = selected
        self.calls = []

    def create_file_dialog(self, kind, **kwargs):
        self.calls.append((kind, kwargs))
        return self.selected


def make_bridge(dialog):
    return DesktopBridge(None, PushChannel(), dialog_window_getter=lambda: dialog)


def test_dialog_cancellation_never_calls_service(monkeypatch):
    monkeypatch.setattr(local_backup, 'create_local_backup', lambda *a, **k: (_ for _ in ()).throw(AssertionError('write')))
    dialog = Dialog(None); bridge = make_bridge(dialog)
    assert bridge.create_local_backup({})['status'] == 'CANCELLED'
    assert bridge.preview_local_backup({})['status'] == 'CANCELLED'
    assert len(dialog.calls) == 2


def test_renderer_cannot_supply_paths_or_force(monkeypatch):
    dialog = Dialog(None); bridge = make_bridge(dialog)
    for spec in [{'path': '/etc/passwd'}, {'force': True}, {'source': '/tmp'}, [], None]:
        assert bridge.create_local_backup(spec)['status'] == 'REJECTED'
        assert bridge.preview_local_backup(spec)['status'] == 'REJECTED'
    assert not dialog.calls


def test_selected_paths_are_used_once_and_source_is_native(monkeypatch, tmp_path):
    selected = tmp_path / 'selected.zip'; dialog = Dialog([str(selected)])
    import desktop.bridge as module
    monkeypatch.setattr(module, 'DATA_DIR', tmp_path / 'native-data')
    calls = []
    def create(source, target, **kwargs):
        calls.append((source, target)); return {'status': 'SAVED', 'sha256': 'a' * 64}
    monkeypatch.setattr(local_backup, 'create_local_backup', create)
    monkeypatch.setattr(local_backup, 'preview_local_backup', lambda path: {'status': 'INVALID', 'name': 'selected.zip'})
    bridge = make_bridge(dialog)
    assert bridge.create_local_backup({})['status'] == 'SAVED'
    assert calls == [(tmp_path / 'native-data', str(selected))]
    assert bridge.preview_local_backup({})['status'] == 'INVALID'


def test_busy_closed_and_errors_do_not_report_success(monkeypatch, tmp_path):
    bridge = make_bridge(Dialog(str(tmp_path / 'target.zip')))
    bridge._local_backup_lock.acquire()
    try:
        assert bridge.create_local_backup({})['status'] == 'BUSY'
    finally:
        bridge._local_backup_lock.release()
    def fail(*args, **kw):
        raise OSError('sensitive local path')
    monkeypatch.setattr(local_backup, 'create_local_backup', fail)
    assert bridge.create_local_backup({}) == {'status': 'FAILED'}
    bridge._close()
    assert bridge.create_local_backup({})['status'] == 'UNAVAILABLE'
