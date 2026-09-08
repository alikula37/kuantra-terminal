"""
Filesystem locations.

Dev (running from a checkout): data lives in backend/data as before.
Frozen (PyInstaller desktop app): data lives in the per-user application data directory,
because the install location is read-only / replaced on update. KUANTRA_DATA_DIR overrides both.
"""
from pathlib import Path
import os
import stat
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


class DataDirectoryError(RuntimeError):
    """Raised when the local data boundary cannot be made private and writable."""


PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def ensure_private_directory(path: Path) -> Path:
    """Create/tighten a data directory without weakening a read-only boundary."""

    directory = Path(path).expanduser()
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
        if os.name != "nt":
            current_mode = stat.S_IMODE(directory.stat().st_mode)
            if current_mode & 0o077:
                directory.chmod(current_mode & 0o700)
            current_mode = stat.S_IMODE(directory.stat().st_mode)
            if (current_mode & 0o700) != PRIVATE_DIRECTORY_MODE:
                raise DataDirectoryError(
                    f"data directory is not owner-writable/private: {directory}"
                )
        elif not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
            raise DataDirectoryError(f"data directory is not accessible: {directory}")
    except DataDirectoryError:
        raise
    except OSError as exc:
        raise DataDirectoryError(f"unable to prepare private data directory: {directory}") from exc
    return directory


def ensure_private_file(path: Path) -> Path:
    """Create/tighten a generated local file to owner-only access."""

    file_path = Path(path).expanduser()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True, mode=PRIVATE_DIRECTORY_MODE)
        file_path.touch(exist_ok=True)
        if os.name != "nt":
            current_mode = stat.S_IMODE(file_path.stat().st_mode)
            if current_mode & 0o077:
                file_path.chmod(current_mode & 0o600)
            current_mode = stat.S_IMODE(file_path.stat().st_mode)
            if (current_mode & 0o600) != PRIVATE_FILE_MODE:
                raise DataDirectoryError(
                    f"generated file is not owner-writable/private: {file_path}"
                )
        elif not os.access(file_path, os.R_OK | os.W_OK):
            raise DataDirectoryError(f"generated file is not accessible: {file_path}")
    except DataDirectoryError:
        raise
    except OSError as exc:
        raise DataDirectoryError(f"unable to prepare private generated file: {file_path}") from exc
    return file_path


# Tighten the resolved application boundary before any database, log or queue
# module derives files beneath it.  This is intentionally fail-closed for a
# read-only or unexpectedly shared directory.
DATA_DIR = ensure_private_directory(DATA_DIR)


def get_sqlite_path() -> str:
    return str(SQLITE_DB_PATH)


def get_duckdb_path() -> str:
    return str(DUCKDB_PATH)
