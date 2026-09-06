"""
MetaTrader 5 (MT5) IPC & Zero-Cost Account Bridge Adapter.
Communicates with local MT5 terminal process for accounts, positions, and quotes.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mt5_adapter")

class MetaTrader5Adapter:
    """IPC bridge to MetaTrader 5 terminal."""

    def __init__(self):
        self.is_initialized: bool = False
        self.account_info: Optional[Dict[str, Any]] = None

    def initialize(self) -> bool:
        """Initializes a real local MT5 IPC session when the native bridge exists.

        This adapter deliberately does not enter a mock-connected state.  A
        future connector may call this method after implementing terminal
        discovery, authentication, and session reconciliation.
        """
        self.is_initialized = False
        self.account_info = None
        logger.warning("[MT5] Native IPC transport is not integrated; adapter remains unavailable.")
        return False

    def get_account_summary(self) -> Dict[str, Any]:
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "capability": "mt5_connector",
            "provenance": "UNVERIFIED_ADAPTER",
            "reason": "REAL_TRANSPORT_NOT_CONFIGURED",
            "broker": None,
            "account": self.account_info,
            "open_positions_count": None,
            "transport_connected": False,
        }

    def get_symbol_quote(self, symbol: str) -> Dict[str, Any]:
        """Returns no quote until a real MT5 transport is connected."""
        sym = symbol.replace("/", "").upper()
        return {
            "symbol": sym,
            "bid": None,
            "ask": None,
            "source": "UNVERIFIED_ADAPTER",
            "status": "EXPERIMENTAL_DISABLED",
            "provenance": "UNVERIFIED_ADAPTER",
            "transport_connected": False,
        }

mt5_adapter = MetaTrader5Adapter()
