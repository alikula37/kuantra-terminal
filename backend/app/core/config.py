from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from app.version import __version__

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class AppSettings(BaseModel):
    app_name: str = "Kuantra Terminal Backend"
    version: str = __version__
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    # Integrations gateway: the only socket the desktop app opens (Chrome extension + TV webhooks).
    gateway_enabled: bool = Field(default_factory=lambda: _env_bool("KUANTRA_GATEWAY_ENABLED", True))
    gateway_host: str = Field(default_factory=lambda: os.getenv("KUANTRA_GATEWAY_HOST", "127.0.0.1"))
    gateway_port: int = Field(default_factory=lambda: int(os.getenv("KUANTRA_GATEWAY_PORT", "8765")))
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    default_symbol: str = "BTCUSDT"
    ws_broadcast_interval_ms: int = 50
    sqlite_db_url: str = Field(default_factory=lambda: os.getenv("SQLITE_DB_URL", ""))
    duckdb_url: str = Field(default_factory=lambda: os.getenv("DUCKDB_URL", ""))

    def gateway_url(self) -> str:
        return f"http://{self.gateway_host}:{self.gateway_port}"


settings = AppSettings()
