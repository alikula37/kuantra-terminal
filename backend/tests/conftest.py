"""
Global Pytest Configuration & Micro-Kernel Plugin Auto-Mount Fixtures.
Ensures seamless test execution across all legacy test suites and dynamic plugins.
"""

import sys
import os
import pytest
from typing import Generator

# Ensure root and backend directories are in sys.path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BACKEND_DIR)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import create_app
from app.services.plugin_manager import plugin_manager

@pytest.fixture(scope="session", autouse=True)
def init_test_environment():
    """Session-wide initialization ensuring all plugins and database tables are available."""
    app = create_app()
    plugin_manager.set_app(app)
    plugin_manager.discover_plugins()
    yield app

@pytest.fixture
def test_app():
    """Provides a fresh FastAPI test application instance."""
    app = create_app()
    plugin_manager.set_app(app)
    return app