"""
Micro-Kernel Core Base Plugin Interfaces & Metadata Specifications.
Defines abstract lifecycle contracts and metadata structures for dynamic plugins.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, APIRouter

@dataclass
class PluginMetadata:
    """Standardized metadata model for Kuantra Terminal modular plugins."""
    plugin_id: str
    name: str
    version: str
    category: str
    description: str = ""
    author: str = "Kuantra Core Team"
    heavy_dependencies: List[str] = field(default_factory=list)
    router_prefix: Optional[str] = None
    is_active: bool = False
    ram_footprint_mb: float = 0.0
    persona_tags: List[str] = field(default_factory=list)
    manifest_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "heavy_dependencies": self.heavy_dependencies,
            "router_prefix": self.router_prefix,
            "is_active": self.is_active,
            "ram_footprint_mb": self.ram_footprint_mb,
            "persona_tags": self.persona_tags
        }

class BasePlugin(ABC):
    """Abstract Base Class for all Kuantra Terminal modular plugin subsystems."""

    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self.router: Optional[APIRouter] = None

    @abstractmethod
    async def on_startup(self, app: FastAPI):
        """Lifecycle hook executed when the plugin is activated and mounted."""
        pass

    @abstractmethod
    async def on_shutdown(self, app: FastAPI):
        """Lifecycle hook executed when the plugin is deactivated and unmounted."""
        pass

    def get_router(self) -> Optional[APIRouter]:
        """Returns the FastAPI APIRouter associated with this plugin, if any."""
        return self.router