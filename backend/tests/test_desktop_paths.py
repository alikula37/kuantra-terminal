import importlib
import os
import sys
from pathlib import Path


_ORIGINAL_TEST_DATA_DIR = os.environ.get("KUANTRA_DATA_DIR")


def _reload_paths(monkeypatch, **env):
    for k in ("KUANTRA_DATA_DIR",):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app.core.paths as paths
    return importlib.reload(paths)


def test_env_override_wins(monkeypatch, tmp_path):
    paths = _reload_paths(monkeypatch, KUANTRA_DATA_DIR=str(tmp_path / "custom"))
    assert paths.DATA_DIR == tmp_path / "custom"
    assert paths.DATA_DIR.is_dir()


def test_dev_mode_uses_backend_data(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    paths = _reload_paths(monkeypatch)
    assert paths.DATA_DIR == paths.BACKEND_ROOT / "data"


def test_frozen_mode_uses_user_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / ".local" / "share"))
    paths = _reload_paths(monkeypatch)
    assert str(paths.DATA_DIR).startswith(str(tmp_path))
    assert paths.DATA_DIR.name in ("Kuantra Terminal", "kuantra-terminal")
    assert paths.USER_PLUGINS_DIR == paths.DATA_DIR / "plugins"


def test_frozen_macos_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    paths = _reload_paths(monkeypatch)
    assert paths.DATA_DIR == tmp_path / "Library" / "Application Support" / "Kuantra Terminal"


def test_version_single_source():
    from app.version import __version__
    from app.core.config import settings
    import app
    assert settings.version == __version__ == app.__version__
    assert settings.gateway_port == 8765
    assert settings.gateway_host == "127.0.0.1"
    assert settings.gateway_enabled is True


def teardown_module(module):
    # restore module state for the rest of the suite
    if _ORIGINAL_TEST_DATA_DIR is None:
        os.environ.pop("KUANTRA_DATA_DIR", None)
    else:
        os.environ["KUANTRA_DATA_DIR"] = _ORIGINAL_TEST_DATA_DIR
    import app.core.paths as paths
    importlib.reload(paths)
