from fastapi import FastAPI, APIRouter
from app.core.plugins import BasePlugin, PluginMetadata
from app.services.matching.order_book import global_order_book
from app.services.fix.fix_gateway import fix_session

router = APIRouter()

@router.get("/status")
def get_fix_dma_status():
    return {
        "status": "ONLINE",
        "service": "Institutional FIX 5.0 & Limit Order Book",
        "session_state": fix_session.state.value
    }

class Plugin(BasePlugin):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.router = router

    async def on_startup(self, app: FastAPI):
        pass

    async def on_shutdown(self, app: FastAPI):
        pass