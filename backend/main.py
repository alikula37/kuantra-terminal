import sys
import os
import argparse
import socket
import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import router as api_router
from app.websocket.binance_client import binance_client
from app.websocket.tv_sync import tv_sync_manager

def find_available_port(host: str = "127.0.0.1") -> int:
    """Binds to ephemeral port 0 and returns allocated dynamic port number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def report_port_handshake(port: int):
    """Outputs standard Tauri sidecar IPC handshake string to stdout."""
    handshake_msg = f"KUANTRA_BACKEND_PORT:{port}\n"
    sys.stdout.write(handshake_msg)
    sys.stdout.flush()
    print(f"[+] Kuantra Terminal Backend bound to http://127.0.0.1:{port}", flush=True)

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
        description="High-frequency Quant Analytics & Real-time Trading Terminal Backend",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health")
    async def health_check():
        return {
            "status": "online",
            "service": settings.app_name,
            "version": settings.version,
            "ws_active": binance_client.is_running,
            "last_price": binance_client.last_price
        }

    @app.websocket("/ws/tv-sync")
    async def websocket_tv_sync_endpoint(websocket: WebSocket):
        await tv_sync_manager.connect_extension(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                await tv_sync_manager.handle_extension_message(data)
        except WebSocketDisconnect:
            tv_sync_manager.disconnect_extension(websocket)
        except Exception:
            tv_sync_manager.disconnect_extension(websocket)

    return app

app = create_app()

def main():
    parser = argparse.ArgumentParser(description="Kuantra Terminal Backend Server")
    parser.add_argument("--host", default=settings.host, help="Bind host address")
    parser.add_argument("--port", type=int, default=settings.port, help="Port to bind (0 for ephemeral dynamic port)")
    parser.add_argument("--parent-pid", type=int, default=None, help="Parent Tauri process PID to watch")
    parser.add_argument("--reload", action="store_true", help="Enable reload mode")
    args = parser.parse_args()

    actual_port = args.port
    if actual_port == 0:
        actual_port = find_available_port(args.host)

    # Report port to parent process (Tauri sidecar IPC handshake)
    report_port_handshake(actual_port)

    # Start Parent Process Watcher if PID provided
    if args.parent_pid:
        try:
            from app.core.parent_watcher import start_parent_watcher
            start_parent_watcher(args.parent_pid)
        except Exception as e:
            print(f"[!] Warning: Unable to start parent watcher: {e}", flush=True)

    uvicorn.run(app, host=args.host, port=actual_port, log_level="info")

if __name__ == "__main__":
    main()