from fastapi import FastAPI, APIRouter
from app.core.plugins import BasePlugin, PluginMetadata
from app.services.biometrics.hardware_driver import hardware_biometrics_driver
from app.services.biometrics.stress_interceptor import stress_interceptor

router = APIRouter()

@router.get("/status")
def get_biometrics_status():
    return {
        "status": "ONLINE",
        "service": "Hardware Wearables & Stress Interceptor",
        "lockout_state": stress_interceptor.lockout_state
    }

class Plugin(BasePlugin):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.router = router

    async def on_startup(self, app: FastAPI):
        pass

    async def on_shutdown(self, app: FastAPI):
        pass