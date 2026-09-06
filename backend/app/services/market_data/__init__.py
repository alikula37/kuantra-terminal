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
from .market_event_envelope import (
    GENESIS_HASH,
    MARKET_EVENT_SCHEMA_VERSION,
    MarketEventChain,
    MarketEventEnvelope,
    MarketEventEnvelopeError,
    MarketEventIdentityConflict,
    envelope_from_dict,
    validate_market_event_envelope,
)
from .market_event_segment import (
    MarketEventSegmentRecoveryError,
    MarketEventSegmentWriter,
)
from .market_event_segments import (
    MANIFEST_SCHEMA_VERSION,
    MarketEventSegmentSet,
    MarketEventSegmentSetRecoveryError,
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
    "GENESIS_HASH",
    "MARKET_EVENT_SCHEMA_VERSION",
    "MarketEventChain",
    "MarketEventEnvelope",
    "MarketEventEnvelopeError",
    "MarketEventIdentityConflict",
    "envelope_from_dict",
    "validate_market_event_envelope",
    "MarketEventSegmentRecoveryError",
    "MarketEventSegmentWriter",
    "MANIFEST_SCHEMA_VERSION",
    "MarketEventSegmentSet",
    "MarketEventSegmentSetRecoveryError",
]
