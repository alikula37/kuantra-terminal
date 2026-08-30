from fastapi import FastAPI, APIRouter
from app.core.plugins import BasePlugin, PluginMetadata
from app.services.dex.rpc_gateway import rpc_gateway
from app.services.dex.arbitrage_engine import arbitrage_engine

router = APIRouter()

@router.get("/status")
def get_dex_arbitrage_status():
    return {
        "status": "ONLINE",
        "service": "Cross-DEX Flash Loan Arbitrage Engine",
        "supported_protocols": ["BALANCER_VAULT", "MORPHO_BLUE", "AAVE_V3"]
    }

class Plugin(BasePlugin):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.router = router

    async def on_startup(self, app: FastAPI):
        pass

    async def on_shutdown(self, app: FastAPI):
        pass