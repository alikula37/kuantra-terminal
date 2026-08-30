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
    """Returns curated ModStore marketplace catalog of verified institutional modules."""
    catalog = [
        {
            "id": "mod_options_greeks",
            "name": "Options Analytics & Live Black-Scholes Greeks",
            "category": "Derivatives",
            "version": "1.0.4",
            "author": "Kuantra Institutional",
            "description": "Real-time volatility smile, Delta/Gamma/Vega/Theta surface visualizer with CME options DMA.",
            "rating": 4.9,
            "downloads": 12450,
            "verified": True,
            "installed": False
        },
        {
            "id": "mod_macro_nowcasting",
            "name": "Global Macro Nowcasting & Central Bank Sentiment",
            "category": "Macro & NLP",
            "version": "2.1.0",
            "author": "Kuantra Research",
            "description": "Scrapes FOMC, ECB, and BOJ minutes using fine-tuned transformer models for macro bias scoring.",
            "rating": 4.8,
            "downloads": 8920,
            "verified": True,
            "installed": False
        },
        {
            "id": "mod_binance_liquidation_radar",
            "name": "High-Density Liquidation Heatmap & Cascade Hunter",
            "category": "Order Flow",
            "version": "1.3.2",
            "author": "Community Verified",
            "description": "Live visual liquidation levels and high-conviction cascading squeeze entry alerts.",
            "rating": 4.95,
            "downloads": 24100,
            "verified": True,
            "installed": False
        }
    ]
    return {
        "catalog_version": "1.1.0",
        "total_available": len(catalog),
        "modules": catalog
    }