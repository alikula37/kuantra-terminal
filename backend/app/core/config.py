from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

class AppSettings(BaseModel):
    app_name: str = "Kuantra Terminal Backend"
    version: str = "0.1.0"
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    default_symbol: str = "BTCUSDT"
    ws_broadcast_interval_ms: int = 50
    sqlite_db_url: str = Field(default_factory=lambda: os.getenv("SQLITE_DB_URL", ""))
    duckdb_url: str = Field(default_factory=lambda: os.getenv("DUCKDB_URL", ""))

settings = AppSettings()
