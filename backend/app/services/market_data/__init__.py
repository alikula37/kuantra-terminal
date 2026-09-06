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
from .market_event_batch import (
    BATCH_SCHEMA_VERSION,
    MarketEventBatch,
    MarketEventBatchError,
    MarketEventBatchProjector,
)
from .binance_depth_ingestor import (
    BinanceDepthIngestor,
    DepthIngestDecision,
    DepthIngestResult,
    DepthIngestorState,
)
from .binance_depth_transport import (
    BinanceDepthTransport,
    BinanceDepthTransportConfig,
    DepthTransportDecision,
    DepthTransportResult,
)
from .binance_depth_network import (
    BinanceDepthEnvironment,
    BinanceDepthNetworkAdapter,
    BinanceDepthNetworkConfig,
    BinanceDepthNetworkError,
)
from .binance_depth_session import (
    BinanceDepthReconnectPolicy,
    BinanceDepthSession,
    DepthSessionDecision,
    DepthSessionResult,
)
from .binance_depth_soak import (
    BinanceDepthFixtureRunner,
    BinanceDepthSoakHarness,
    DepthFixtureCycle,
    DepthSoakReport,
)
from .binance_depth_report import (
    REPORT_SCHEMA_VERSION,
    DepthSoakReportVerification,
    DepthSoakReportVerdict,
    verify_depth_soak_report,
)
from .binance_depth_report_archive import (
    ARCHIVE_SCHEMA_VERSION,
    BinanceDepthReportArchive,
    DepthSoakArchiveError,
    DepthSoakArchiveRecord,
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
    "BATCH_SCHEMA_VERSION",
    "MarketEventBatch",
    "MarketEventBatchError",
    "MarketEventBatchProjector",
    "BinanceDepthIngestor",
    "DepthIngestDecision",
    "DepthIngestResult",
    "DepthIngestorState",
    "BinanceDepthTransport",
    "BinanceDepthTransportConfig",
    "DepthTransportDecision",
    "DepthTransportResult",
    "BinanceDepthEnvironment",
    "BinanceDepthNetworkAdapter",
    "BinanceDepthNetworkConfig",
    "BinanceDepthNetworkError",
    "BinanceDepthReconnectPolicy",
    "BinanceDepthSession",
    "DepthSessionDecision",
    "DepthSessionResult",
    "BinanceDepthFixtureRunner",
    "BinanceDepthSoakHarness",
    "DepthFixtureCycle",
    "DepthSoakReport",
    "REPORT_SCHEMA_VERSION",
    "DepthSoakReportVerification",
    "DepthSoakReportVerdict",
    "verify_depth_soak_report",
    "ARCHIVE_SCHEMA_VERSION",
    "BinanceDepthReportArchive",
    "DepthSoakArchiveError",
    "DepthSoakArchiveRecord",
]
