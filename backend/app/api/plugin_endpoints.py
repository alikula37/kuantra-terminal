"""
ModStore & Dynamic Plugin Management REST API Endpoints for Kuantra Terminal.
Provides endpoints for inspecting installed plugins, runtime hot-toggling,
persona batch switching, and ModStore marketplace discovery.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.availability import experimental_disabled_exception
from app.services.plugin_manager import (
    plugin_manager,
    PERSONA_PROFILES,
    ExperimentalPersonaDisabledError,
    ExperimentalPluginDisabledError,
)

router = APIRouter(prefix="/plugins", tags=["Plugins & ModStore"])

class PluginTogglePayload(BaseModel):
    plugin_id: str
    enable: bool

class PersonaApplyPayload(BaseModel):
    persona: str

@router.get("/installed")
def get_installed_plugins():
    """Returns a list of all installed local plugins, active statuses, and memory footprints."""
    return {
        "total_plugins": len(plugin_manager.list_installed_plugins()),
        "active_persona": plugin_manager._active_persona,
        "plugins": plugin_manager.list_installed_plugins()
    }

@router.post("/toggle")
async def toggle_plugin_endpoint(payload: PluginTogglePayload):
    """Dynamically activates or deactivates a plugin at runtime."""
    try:
        res = await plugin_manager.toggle_plugin(payload.plugin_id, payload.enable)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ExperimentalPluginDisabledError as e:
        raise experimental_disabled_exception(
            "plugin_runtime",
            reason="UNSIGNED_PLUGIN_REGISTRY_NOT_AVAILABLE",
            message=str(e),
            provenance="UNVERIFIED_PLUGIN",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle plugin: {str(e)}")

@router.post("/apply-persona")
async def apply_persona_endpoint(payload: PersonaApplyPayload):
    """Batch-activates/deactivates plugins based on architectural persona preset."""
    try:
        res = await plugin_manager.apply_persona(payload.persona)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ExperimentalPersonaDisabledError as e:
        raise experimental_disabled_exception(
            "experimental_persona",
            reason="EXPERIMENTAL_PERSONA_DISABLED",
            message=str(e),
            provenance="UNVERIFIED_PLUGIN",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply persona: {str(e)}")

@router.get("/personas")
def list_available_personas():
    """Returns production-safe persona profiles only."""
    return {
        "current_persona": plugin_manager._active_persona,
        "personas": PERSONA_PROFILES
    }

@router.get("/modstore-catalog")
def get_modstore_catalog():
    """Returns an explicit empty catalog until signed registry support exists."""
    return {
        "catalog_version": "DISABLED",
        "status": "EXPERIMENTAL_DISABLED",
        "capability": "plugin_marketplace",
        "provenance": "UNVERIFIED_PLUGIN",
        "reason": "SIGNED_REGISTRY_NOT_AVAILABLE",
        "execution_authority": False,
        "total_available": 0,
        "modules": []
    }

class DownloadPluginRequest(BaseModel):
    plugin_id: str
    download_url: Optional[str] = None
    expected_sha256: Optional[str] = None

@router.post("/download")
async def download_plugin_endpoint(req: DownloadPluginRequest):
    """Remote plugin download is closed until a signed sandbox registry exists."""
    raise experimental_disabled_exception(
        "plugin_marketplace_download",
        reason="SIGNED_REGISTRY_NOT_AVAILABLE",
        message="Remote plugin download and in-process activation are disabled in this release.",
        provenance="UNVERIFIED_PLUGIN",
    )

@router.get("/download-status/{task_id}")
def get_download_status_endpoint(task_id: str):
    """Fetches real-time progress and completion status for a plugin download task."""
    from app.services.modstore_downloader import modstore_downloader
    status_data = modstore_downloader.get_task_status(task_id)
    if not status_data:
        raise HTTPException(status_code=404, detail=f"Download task '{task_id}' not found.")
    return status_data
