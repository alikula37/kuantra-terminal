from fastapi import FastAPI, APIRouter
from app.core.plugins import BasePlugin, PluginMetadata
from app.services.mcp.client_gateway import mcp_gateway

router = APIRouter()

@router.get("/status")
def get_mcp_status():
    return {
        "status": "ONLINE",
        "service": "Financial Model Context Protocol Gateway",
        "connected_servers": ["sec-edgar", "cryptopanic", "macro-treasury"]
    }

class Plugin(BasePlugin):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.router = router

    async def on_startup(self, app: FastAPI):
        pass

    async def on_shutdown(self, app: FastAPI):
        pass