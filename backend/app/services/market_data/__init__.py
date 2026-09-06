"""
Public Unauthenticated Market Data Fetcher Module for Kuantra Terminal.
Provides zero-auth crypto and macro/forex market data retrieval.
"""

from .public_fetcher import PublicMarketDataFetcher, public_market_fetcher
from .binance_depth_sequence import (
    BinanceDepthSequenceValidator,
    DepthSequenceDecision,
    DepthSequenceResult,
    DepthSequenceState,
)
from .binance_depth_recovery import (
    BinanceDepthRecoveryCoordinator,
    DepthRecoveryDecision,
    DepthRecoveryResult,
    DepthRecoveryState,
)
from .binance_depth_payload import (
    BinanceDepthBook,
    DepthBookDecision,
    DepthBookResult,
    DepthLevel,
    DepthPayloadError,
    NormalizedDepthSnapshot,
    NormalizedDepthUpdate,
    normalize_snapshot,
    normalize_update,
)

__all__ = [
    "PublicMarketDataFetcher",
    "public_market_fetcher",
    "BinanceDepthSequenceValidator",
    "DepthSequenceDecision",
    "DepthSequenceResult",
    "DepthSequenceState",
    "BinanceDepthRecoveryCoordinator",
    "DepthRecoveryDecision",
    "DepthRecoveryResult",
    "DepthRecoveryState",
    "BinanceDepthBook",
    "DepthBookDecision",
    "DepthBookResult",
    "DepthLevel",
    "DepthPayloadError",
    "NormalizedDepthSnapshot",
    "NormalizedDepthUpdate",
    "normalize_snapshot",
    "normalize_update",
]
