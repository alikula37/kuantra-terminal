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


@pytest.fixture
def recorded_trade():
    """Explicit closed-trade evidence fixture, never a production fallback."""
    return {
        "id": "EVIDENCE-TEST", "symbol": "BTCUSDT", "side": "BUY", "status": "CLOSED",
        "entry_price": 100.0, "exit_price": 103.0, "qty": 2.0,
        "stop_loss": 99.0, "take_profit": 105.0, "pnl": 5.5,
        "entry_time": "2026-09-01T10:00:15Z", "exit_time": "2026-09-01T10:02:35Z",
    }


@pytest.fixture
def recorded_candles():
    from datetime import datetime, timezone
    start = int(datetime(2026, 9, 1, 9, 59, tzinfo=timezone.utc).timestamp())
    values = [
        (100, 1000, 1, 100),  # pre-entry context must not influence excursion
        (100, 100.5, 99.2, 99.8),
        (99.8, 104, 99.5, 103.5),
        (103.5, 104, 102, 103),
        (103, 900, 0.1, 104),  # post-exit extremes must not influence excursion
        (104, 800, 0.5, 104),
    ]
    return [
        {"symbol": "BTCUSDT", "timeframe": "1m", "time": start + index * 60,
         "open": o, "high": h, "low": low, "close": c, "volume": 10.0}
        for index, (o, h, low, c) in enumerate(values)
    ]
