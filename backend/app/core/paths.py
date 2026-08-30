from pathlib import Path
import os

# Base paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SQLITE_DB_PATH = DATA_DIR / "kuantra_oltp.sqlite3"
DUCKDB_PATH = DATA_DIR / "kuantra_olap.duckdb"

def get_sqlite_path() -> str:
    return str(SQLITE_DB_PATH)

def get_duckdb_path() -> str:
    return str(DUCKDB_PATH)
