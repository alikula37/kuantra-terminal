"""P2-WP09 injected depth ingestion boundary contracts."""

from app.services.market_data.binance_depth_ingestor import (
    BinanceDepthIngestor,
    DepthIngestDecision,
    DepthIngestorState,
)
from app.services.market_data.market_event_segments import MarketEventSegmentSet


def _snapshot(last_id: int = 101):
    return {
        "lastUpdateId": last_id,
        "bids": [["65000", "2"]],
        "asks": [["65010", "3"]],
    }


def _event(first: int = 101, final: int = 102, *, bid_qty: str = "1.5"):
    return {
        "e": "depthUpdate",
        "s": "BTCUSDT",
        "U": first,
        "u": final,
        "b": [["65000", bid_qty]],
        "a": [],
    }


def test_buffer_snapshot_replay_book_chain_and_segment_boundary(tmp_path):
    sink = MarketEventSegmentSet(tmp_path / "events", max_events_per_segment=10)
    ingestor = BinanceDepthIngestor("BTCUSDT", event_sink=sink)

    buffered = ingestor.ingest_event(_event())
    applied = ingestor.ingest_snapshot(_snapshot())

    assert buffered.decision is DepthIngestDecision.BUFFERED
    assert applied.decision is DepthIngestDecision.SNAPSHOT_APPLIED
    assert applied.applied_updates == 1
    assert applied.envelopes_processed == 2
    assert ingestor.state is DepthIngestorState.LIVE
    assert ingestor.book.as_dict()["bids"] == [["65000", "1.5"]]
    assert len(sink.events) == 2
    assert sink.recovery_report()["valid"] is True


def test_live_gap_never_reaches_book_or_sink():
    # Keep this test independent from the repository: the injected sink is a
    # local fake with the same append/events surface.
    class Sink:
        def __init__(self):
            self.events = []

        def append(self, envelope):
            self.events.append(envelope)

    sink = Sink()
    ingestor = BinanceDepthIngestor("BTCUSDT", event_sink=sink)
    ingestor.ingest_snapshot(_snapshot(100))
    ingestor.ingest_event(_event(101, 102))
    before = ingestor.book.as_dict()
    gap = ingestor.ingest_event(_event(105, 106, bid_qty="9"))

    assert gap.decision is DepthIngestDecision.GAP_DETECTED
    assert ingestor.state is DepthIngestorState.RECOVERY_REQUIRED
    assert ingestor.book.as_dict() == before
    assert len(sink.events) == 2


def test_malformed_payload_fails_closed_before_book_mutation():
    ingestor = BinanceDepthIngestor("BTCUSDT")

    rejected = ingestor.ingest_event({"s": "BTCUSDT", "U": 101, "u": 102, "b": [["NaN", "1"]], "a": []})

    assert rejected.decision is DepthIngestDecision.REJECTED
    assert ingestor.state is DepthIngestorState.RECOVERY_REQUIRED
    assert ingestor.book.as_dict()["status"] == "NO_DATA"


def test_segment_restart_rehydrates_chain_and_accepts_next_snapshot_cycle(tmp_path):
    root = tmp_path / "events"
    sink = MarketEventSegmentSet(root, max_events_per_segment=10)
    first = BinanceDepthIngestor("BTCUSDT", event_sink=sink)
    first.ingest_snapshot(_snapshot(100))
    first.ingest_event(_event(101, 102))

    reopened_sink = MarketEventSegmentSet(root, max_events_per_segment=10)
    second = BinanceDepthIngestor("BTCUSDT", event_sink=reopened_sink)
    restored = second.ingest_snapshot(_snapshot(102))
    next_event = second.ingest_event(_event(103, 104, bid_qty="1"))

    assert restored.decision is DepthIngestDecision.SNAPSHOT_APPLIED
    assert next_event.decision is DepthIngestDecision.LIVE_APPLIED
    assert [event.chain_sequence for event in reopened_sink.events] == [1, 2, 3, 4]
    assert reopened_sink.recovery_report()["valid"] is True


def test_sink_failure_blocks_continuation_without_claiming_persistence():
    class FailingSink:
        events = ()

        def append(self, envelope):
            raise OSError("disk full")

    ingestor = BinanceDepthIngestor("BTCUSDT", event_sink=FailingSink())

    failed = ingestor.ingest_snapshot(_snapshot(100))
    blocked = ingestor.ingest_event(_event(101, 102))

    assert failed.decision is DepthIngestDecision.PERSISTENCE_FAILED
    assert failed.state is DepthIngestorState.PERSISTENCE_ERROR
    assert blocked.decision is DepthIngestDecision.PERSISTENCE_FAILED
    assert blocked.reason_code == "PERSISTENCE_ERROR_BLOCKS_INGEST"
