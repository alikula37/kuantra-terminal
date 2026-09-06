from fastapi import FastAPI, APIRouter
from app.core.plugins import BasePlugin, PluginMetadata

router = APIRouter()

@router.get("/status")
def get_orderflow_status():
    return {
        "status": "NO_DATA",
        "provenance": "RUNTIME_INGEST_ONLY",
        "caveat": "No recorded trade-tick or order-book feed is connected; the plugin will only expose explicitly ingested in-memory observations.",
        "service": "Order Flow Footprint & CVD Engine",
        "imbalance_ratio_threshold": 3.0
    }

class Plugin(BasePlugin):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.router = router

    async def on_startup(self, app: FastAPI):
        pass

    async def on_shutdown(self, app: FastAPI):
        pass
