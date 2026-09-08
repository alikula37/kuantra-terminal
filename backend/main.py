import argparse
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import router as api_router
from app.api.tv_sync_ws import tv_sync_websocket
from app.websocket.binance_client import binance_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start Binance Stream Client Background Task
    await binance_client.start()
    yield
    # Shutdown: Stop Binance Client
    await binance_client.stop()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Local-first Trade Forensics & Execution Intelligence Backend (live execution experimental/disabled)",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    
    from app.services.plugin_manager import plugin_manager
    plugin_manager.set_app(app)

    @app.get("/health")
    async def health_check():
        return {
            "status": "online",
            "service": settings.app_name,
            "version": settings.version,
            "ws_active": binance_client.is_running,
            "last_price": binance_client.last_price,
            "market_data_enabled": binance_client.market_data_enabled,
            "market_data_status": binance_client.market_data_status,
            "market_data": {
                "enabled": binance_client.market_data_enabled,
                "status": binance_client.market_data_status,
                "stream_active": binance_client.is_running,
            },
        }

    app.add_api_websocket_route("/ws/tv-sync", tv_sync_websocket)

    return app

def main():
    """Development HTTP server. The desktop app does not use this; see desktop_main.py."""
    parser = argparse.ArgumentParser(description="Kuantra Terminal Backend (dev server)")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    args = parser.parse_args()
    # Built here rather than at module level: the desktop shell imports create_app() and builds
    # its own instance, and an import-time app would construct a second one (re-running plugin
    # discovery and rebinding the manager) for nothing.
    app = create_app()
    print(f"[+] Kuantra dev backend on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
