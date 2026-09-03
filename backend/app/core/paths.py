"""
Filesystem locations.

Dev (running from a checkout): data lives in backend/data as before.
Frozen (PyInstaller desktop app): data lives in the per-user application data directory,
because the install location is read-only / replaced on update. KUANTRA_DATA_DIR overrides both.
"""
from pathlib import Path
import os
import sys

APP_NAME = "Kuantra Terminal"
APP_SLUG = "kuantra-terminal"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Directory holding bundled read-only resources (frontend, alembic) when frozen."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return BACKEND_ROOT


def default_user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_SLUG


def resolve_data_dir() -> Path:
    env = os.environ.get("KUANTRA_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if is_frozen():
        return default_user_data_dir()
    return BACKEND_ROOT / "data"


DATA_DIR = resolve_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_PLUGINS_DIR = DATA_DIR / "plugins"

SQLITE_DB_PATH = DATA_DIR / "kuantra_oltp.sqlite3"
DUCKDB_PATH = DATA_DIR / "kuantra_olap.duckdb"


def get_sqlite_path() -> str:
    return str(SQLITE_DB_PATH)


def get_duckdb_path() -> str:
    return str(DUCKDB_PATH)
