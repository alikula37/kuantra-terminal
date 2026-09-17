"""P1-WP43 independent spot-product consistency check: pure module tests.

The comparator never equates futures/tokens with spot, never turns a single
source into a positive result, and reports its measured overlap and deviation
with the documented tolerance instead of a bare "verified" claim.
"""

from __future__ import annotations

from app.quant.instrument_product import (
    DAY_CLOSE_NOTE, FX_TOLERANCE_PCT, METAL_TOLERANCE_PCT, MIN_OVERLAP_BARS,
    evaluate_product_consistency, independent_candidate, not_run_payload,
    product_definition,
)

DAY = 86_400
BASE_TS = 1_760_000_000 - (1_760_000_000 % DAY)


def bars(closes, *, start=BASE_TS, step=60, timestamp_ms=False):
    rows = []
    for index, close in enumerate(closes):
        timestamp = start + index * step
        rows.append({"timestamp": timestamp * 1000 if timestamp_ms else timestamp, "close": close})
    return rows


def evaluate(declared_bars, independent_bars, *, provider="biquote_public", symbol="XAUUSD"):
    return evaluate_product_consistency(
        declared_provider=provider, declared_symbol=symbol,
        declared_candles=declared_bars, candidate=independent_candidate(provider, symbol),
        independent_candles=independent_bars, checked_at="2026-09-17T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Registry and candidate selection
# ---------------------------------------------------------------------------


def test_registry_classifies_spot_fx_futures_and_unknown():
    gold = product_definition("biquote_public", "XAUUSD")
    assert (gold.key, gold.asset_class, gold.tolerance_pct) == (
        "SPOT_METAL:XAU:USD", "SPOT_METAL", METAL_TOLERANCE_PCT)
    assert product_definition("yahoo_public", "XAUUSD=X").key == gold.key
    assert product_definition("stooq_public", "XAUUSD").key == gold.key  # case-insensitive alias
    silver = product_definition("yahoo_public", "XAGUSD=X")
    assert (silver.key, silver.asset_class) == ("SPOT_METAL:XAG:USD", "SPOT_METAL")
    fx = product_definition("yahoo_public", "EURUSD=X")
    assert (fx.key, fx.asset_class, fx.tolerance_pct) == ("FX:EUR:USD", "FX", FX_TOLERANCE_PCT)
    assert product_definition("stooq_public", "usdjpy").key == "FX:USD:JPY"
    futures = product_definition("yahoo_public", "GC=F")
    assert (futures.key, futures.asset_class, futures.tolerance_pct) == ("FUTURE:GC", "FUTURE", None)
    assert product_definition("biquote_public", "BTCUSDT") is None
    assert product_definition("manual", "XAUUSD") is None


def test_independent_candidate_picks_a_different_same_product_source():
    biquote_declared = independent_candidate("biquote_public", "XAUUSD")
    assert (biquote_declared.provider, biquote_declared.symbol, biquote_declared.interval) == (
        "yahoo_public", "XAUUSD=X", "1m")
    yahoo_declared = independent_candidate("yahoo_public", "XAUUSD=X")
    assert (yahoo_declared.provider, yahoo_declared.symbol, yahoo_declared.interval) == (
        "biquote_public", "XAUUSD", "1m")
    stooq_declared = independent_candidate("stooq_public", "xauusd")
    assert stooq_declared.provider != "stooq_public"
    assert stooq_declared.interval == "1d"  # daily declared -> daily independent fetch
    silver = independent_candidate("yahoo_public", "XAGUSD=X")
    assert (silver.provider, silver.symbol) == ("stooq_public", "xagusd")
    fx = independent_candidate("yahoo_public", "EURUSD=X")
    assert (fx.provider, fx.symbol) == ("stooq_public", "eurusd")
    # Futures and tokens have no independent free same-product source.
    assert independent_candidate("yahoo_public", "GC=F") is None
    assert independent_candidate("biquote_public", "BTCUSDT") is None


# ---------------------------------------------------------------------------
# Comparator outcomes
# ---------------------------------------------------------------------------


def test_spot_consistency_requires_enough_exact_aligned_bars():
    nine = evaluate(bars([4260.0] * 9), bars([4260.0] * 9))
    assert nine["status"] == "UNVERIFIABLE"
    assert nine["reason"] == "INSUFFICIENT_OVERLAP"
    assert nine["overlap_bars"] == 9
    ten = evaluate(bars([4260.0] * MIN_OVERLAP_BARS), bars([4260.0] * MIN_OVERLAP_BARS))
    assert ten["status"] == "CONSISTENT"
    assert ten["alignment"] == "EXACT_BAR"
    assert ten["median_deviation_pct"] == 0.0
    assert ten["overlap_bars"] == MIN_OVERLAP_BARS
    assert ten["note"] == "NOT_BROKER_EXECUTION_EVIDENCE"


def test_spot_divergence_is_measured_and_reported():
    declared = bars([4000.0] * 12)
    independent = bars([4120.0] * 12)  # ~3 % apart, beyond the 0.5 % metal tolerance
    result = evaluate(declared, independent)
    assert result["status"] == "DIVERGENT"
    assert result["median_deviation_pct"] > result["tolerance_pct"]
    assert result["max_deviation_pct"] >= result["median_deviation_pct"]
    assert result["overlap_bars"] == 12


def test_skewed_timestamps_never_align():
    declared = bars([4260.0] * 12)
    independent = bars([4260.0] * 12, start=BASE_TS + 30)
    result = evaluate(declared, independent)
    assert result["status"] == "UNVERIFIABLE"
    assert result["reason"] == "INSUFFICIENT_OVERLAP"
    assert result["overlap_bars"] == 0


def test_millisecond_timestamps_are_normalized_before_alignment():
    declared = bars([4260.0] * 12, timestamp_ms=True)
    independent = bars([4260.0] * 12)
    result = evaluate(declared, independent)
    assert result["status"] == "CONSISTENT"
    assert result["alignment"] == "EXACT_BAR"
    assert result["overlap_bars"] == 12


def test_daily_alignment_uses_utc_day_closes_and_excludes_the_latest_day():
    declared = bars([4300.0 + index for index in range(12)], start=BASE_TS, step=DAY)
    independent = bars([4300.0 + index for index in range(12)], start=BASE_TS, step=DAY)
    result = evaluate_product_consistency(
        declared_provider="stooq_public", declared_symbol="xauusd",
        declared_candles=declared, candidate=independent_candidate("stooq_public", "xauusd"),
        independent_candles=independent, checked_at="2026-09-17T00:00:00Z",
    )
    assert result["status"] == "CONSISTENT"
    assert result["alignment"] == "UTC_DAY"
    assert result["overlap_bars"] == 11  # the latest (possibly partial) day is excluded
    assert result["alignment_note"] == DAY_CLOSE_NOTE


def test_intraday_declared_series_cannot_fake_daily_overlap():
    # Silver has no independent intraday alias: a one-day 1m declared window
    # against the stooq daily candidate finds at most one common UTC day.
    declared = bars([4260.0] * 20, step=60)
    independent = bars([4260.0 + index for index in range(12)], start=BASE_TS, step=DAY)
    result = evaluate_product_consistency(
        declared_provider="yahoo_public", declared_symbol="XAGUSD=X",
        declared_candles=declared, candidate=independent_candidate("yahoo_public", "XAGUSD=X"),
        independent_candles=independent, checked_at="2026-09-17T00:00:00Z",
    )
    assert result["status"] == "UNVERIFIABLE"
    assert result["reason"] == "INSUFFICIENT_OVERLAP"
    assert result["alignment"] == "UTC_DAY"
    assert result["overlap_bars"] == 1


def test_zero_and_invalid_closes_are_dropped_not_compared():
    declared = bars([0.0] * 5 + [4260.0] * 10)
    independent = bars([None, 0.0] + [4260.0] * 13)
    result = evaluate(declared, independent)
    assert result["status"] == "CONSISTENT"  # only the finite, positive closes align
    assert result["overlap_bars"] == 10


# ---------------------------------------------------------------------------
# Honesty rules
# ---------------------------------------------------------------------------


def test_single_source_or_missing_key_never_produces_a_positive_result():
    perfect = bars([4260.0] * 20)
    futures = evaluate_product_consistency(
        declared_provider="yahoo_public", declared_symbol="GC=F",
        declared_candles=[{"timestamp": BASE_TS, "close": 4300.0}],
        candidate=independent_candidate("yahoo_public", "GC=F"),
        independent_candles=perfect, checked_at="2026-09-17T00:00:00Z",
    )
    assert futures["status"] == "UNVERIFIABLE"
    assert futures["reason"] == "NO_INDEPENDENT_SOURCE"
    assert futures["product_key"] == "FUTURE:GC"
    unknown = evaluate_product_consistency(
        declared_provider="biquote_public", declared_symbol="BTCUSDT",
        declared_candles=perfect, candidate=None, independent_candles=perfect,
        checked_at="2026-09-17T00:00:00Z",
    )
    assert unknown["status"] == "UNVERIFIABLE"
    assert unknown["reason"] == "NO_PRODUCT_KEY"
    assert unknown["product_key"] is None


def test_fetch_failure_is_reported_with_the_candidate():
    result = evaluate_product_consistency(
        declared_provider="biquote_public", declared_symbol="XAUUSD",
        declared_candles=bars([4260.0] * 12),
        candidate=independent_candidate("biquote_public", "XAUUSD"),
        failure_reason="PROVIDER_FETCH_FAILED", checked_at="2026-09-17T00:00:00Z",
    )
    assert result["status"] == "UNVERIFIABLE"
    assert result["reason"] == "FETCH_FAILED"
    assert result["reason_detail"] == "PROVIDER_FETCH_FAILED"
    assert result["independent_provider"] == "yahoo_public"


def test_not_run_payload_is_explicit():
    payload = not_run_payload(declared_provider="biquote_public", declared_symbol="XAUUSD")
    assert payload["status"] == "UNVERIFIABLE"
    assert payload["reason"] == "CHECK_NOT_RUN"
    assert payload["product_key"] == "SPOT_METAL:XAU:USD"
    assert payload["overlap_bars"] == 0
    assert payload["median_deviation_pct"] is None
