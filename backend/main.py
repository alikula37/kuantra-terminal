import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import router as api_router
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

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)