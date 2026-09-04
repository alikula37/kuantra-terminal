"""
ModStore & Dynamic Plugin Management REST API Endpoints for Kuantra Terminal.
Provides endpoints for inspecting installed plugins, runtime hot-toggling,
persona batch switching, and ModStore marketplace discovery.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.plugin_manager import plugin_manager, PERSONA_PROFILES

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply persona: {str(e)}")

@router.get("/personas")
def list_available_personas():
    """Returns all supported persona profiles and their corresponding plugin IDs."""
    return {
        "current_persona": plugin_manager._active_persona,
        "personas": PERSONA_PROFILES
    }

@router.get("/modstore-catalog")
def get_modstore_catalog():
    """Returns curated ModStore marketplace catalog of verified institutional modules and remote extensions."""
    catalog = [
        {
            "id": "mod_options_greeks",
            "name": "Options Analytics & Live Black-Scholes Greeks",
            "category": "Derivatives",
            "version": "1.0.0",
            "author": "Kuantra Institutional",
            "description": "Volatility smile, Delta/Gamma/Vega/Theta surface visualizer with options calculation models.",
            "status": "Available on-demand / Remote Registry",
            "verified": True,
            "installed": False
        },
        {
            "id": "mod_macro_nowcasting",
            "name": "Global Macro Nowcasting & Central Bank Sentiment",
            "category": "Macro & NLP",
            "version": "1.0.0",
            "author": "Kuantra Research",
            "description": "Automated central bank speech parser and economic indicator nowcasting engine.",
            "status": "Available on-demand / Remote Registry",
            "verified": True,
            "installed": False
        },
        {
            "id": "mod_binance_liquidation_radar",
            "name": "High-Density Liquidation Heatmap & Cascade Hunter",
            "category": "Order Flow",
            "version": "1.0.0",
            "author": "Community Verified",
            "description": "Liquidation volume cluster detector and cascading squeeze event monitor.",
            "status": "Available on-demand / Remote Registry",
            "verified": True,
            "installed": False
        },
        {
            "id": "mod_hft_tick_compressor",
            "name": "ZSTD High-Frequency Tick Database Compressor",
            "category": "Storage",
            "version": "1.0.0",
            "author": "Kuantra Infrastructure",
            "description": "Lossless column-oriented tick archival achieving high-density storage compression.",
            "status": "Available on-demand / Remote Registry",
            "verified": True,
            "installed": False
        }
    ]
    return {
        "catalog_version": "1.4.0",
        "total_available": len(catalog),
        "modules": catalog
    }

class DownloadPluginRequest(BaseModel):
    plugin_id: str
    download_url: Optional[str] = None
    expected_sha256: Optional[str] = None

@router.post("/download")
async def download_plugin_endpoint(req: DownloadPluginRequest):
    """Initiates an asynchronous download and dynamic mounting task for a remote .kmod plugin."""
    from app.services.modstore_downloader import modstore_downloader
    from app.core.background import fire_and_forget
    import uuid
    task_id = str(uuid.uuid4())[:8]
    fire_and_forget(
        modstore_downloader.download_and_install,
        plugin_id=req.plugin_id,
        download_url=req.download_url,
        expected_sha256=req.expected_sha256,
        task_id=task_id
    )
    return {
        "status": "QUEUED",
        "task_id": task_id,
        "plugin_id": req.plugin_id,
        "message": f"Plugin download task '{task_id}' queued successfully."
    }

@router.get("/download-status/{task_id}")
def get_download_status_endpoint(task_id: str):
    """Fetches real-time progress and completion status for a plugin download task."""
    from app.services.modstore_downloader import modstore_downloader
    status_data = modstore_downloader.get_task_status(task_id)
    if not status_data:
        raise HTTPException(status_code=404, detail=f"Download task '{task_id}' not found.")
    return status_data