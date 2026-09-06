"""P2-WP01 sequence continuity and market-context truth contracts."""

from app.quant.candle_evidence import load_candle_evidence


def _provenance_rows(recorded_candles, sequences):
    rows = []
    for candle, sequence in zip(recorded_candles, sequences):
        rows.append(
            {
                **candle,
                "venue": "BINANCE",
                "feed": "BINANCE_WS_KLINE",
                "source_event_id": f"BTCUSDT:1m:{candle['time']}",
                "source_sequence": sequence,
                "ingested_at": "2026-09-01T10:05:00Z",
                "source_verified": True,
            }
        )
    return rows


def test_sequence_gap_is_explicit_and_never_promoted_to_verified(recorded_trade, recorded_candles):
    evidence = load_candle_evidence(
        recorded_trade,
        _provenance_rows(recorded_candles[1:4], [100, 102, 103]),
    )

    context = evidence.market_context
    assert context["sequence_coverage"] == "GAPPED"
    assert context["sequence_contiguous"] is False
    assert context["sequence_gap_count"] == 1
    assert context["sequence_gaps"] == [{"from": 100, "to": 102, "missing": 1}]
    assert context["source_verified"] is False


def test_partial_sequence_coverage_is_distinct_from_a_clean_sequence(recorded_trade, recorded_candles):
    evidence = load_candle_evidence(
        recorded_trade,
        _provenance_rows(recorded_candles[1:4], [100, None, 102]),
    )

    context = evidence.market_context
    assert context["sequence_coverage"] == "PARTIAL"
    assert context["sequence_contiguous"] is False
    assert context["sequence_gap_count"] == 1
    assert context["source_verified"] is False


def test_clean_sequence_can_be_verified_when_all_other_provenance_is_complete(recorded_trade, recorded_candles):
    evidence = load_candle_evidence(
        recorded_trade,
        _provenance_rows(recorded_candles[1:4], [100, 101, 102]),
    )

    context = evidence.market_context
    assert context["sequence_coverage"] == "COMPLETE"
    assert context["sequence_contiguous"] is True
    assert context["sequence_gap_count"] == 0
    assert context["source_verified"] is True
