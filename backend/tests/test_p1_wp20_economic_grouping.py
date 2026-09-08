"""P1-WP20 economic fill deduplication and lifecycle contracts."""

from decimal import Decimal

from app.services.economic_trade_grouping import EconomicGroupingService


SOURCE_SHA = {
    "csv": "a" * 64,
    "api": "b" * 64,
}


def _row(
    observation_type: str,
    external_id: str,
    *,
    order_id: str = "ORDER-1",
    qty: str = "0.5",
    price: str = "100",
    status: str = "FILLED",
    economic_key: str | None = None,
    **extra,
):
    row = {
        "observation_type": observation_type,
        "id": external_id,
        "order_id": order_id,
        "qty": qty,
        "price": price,
        "status": status,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "occurred_at": "2026-09-08T10:00:00Z",
    }
    if observation_type == "ORDER":
        row.update({"order_qty": qty, "filled_qty": qty})
    if economic_key is not None:
        row["economic_key"] = economic_key
    row.update(extra)
    return row


def _normalize(service, rows, *, account_id="acct-1", source_kind="CSV", source_sha=None):
    return service.normalize_observations(
        "BINANCE",
        rows,
        account_id=account_id,
        source_exchange_id="binance_futures",
        market_type="swap",
        source_kind=source_kind,
        source_document_sha256=source_sha or SOURCE_SHA[source_kind.lower()],
    )


def test_overlapping_csv_and_api_fill_is_one_contribution_with_both_lineages():
    service = EconomicGroupingService()
    csv_records, csv_rejected = _normalize(
        service,
        [_row("FILL", "CSV-FILL-1", economic_key="ECO-FILL-1")],
        source_kind="CSV",
    )
    api_records, api_rejected = _normalize(
        service,
        [_row("FILL", "API-FILL-1", economic_key="ECO-FILL-1")],
        source_kind="API",
    )

    report = service.group([*csv_records, *api_records], position_mode="ONE_WAY")

    assert csv_rejected == []
    assert api_rejected == []
    assert report["economic_group_count"] == 1
    assert report["economic_contribution_count"] == 1
    group = report["groups"][0]
    assert group["quantity"] == "0.5"
    assert group["source_observation_count"] == 2
    assert {lineage["source_kind"] for lineage in group["source_lineage"]} == {"CSV", "API"}


def test_scope_separates_accounts_and_rejects_same_scope_economic_conflict():
    service = EconomicGroupingService()
    first, _ = _normalize(service, [_row("FILL", "FILL-1", qty="0.5")], account_id="acct-a")
    second, _ = _normalize(service, [_row("FILL", "FILL-1", qty="0.5")], account_id="acct-b")
    conflicting, _ = _normalize(
        service,
        [_row("FILL", "FILL-1", qty="0.7")],
        account_id="acct-a",
        source_kind="API",
    )

    separate = service.group([*first, *second], position_mode="ONE_WAY")
    conflict = service.group([*first, *conflicting], position_mode="ONE_WAY")

    assert separate["economic_group_count"] == 2
    assert not any(item["type"] == "ECONOMIC_QUANTITY_CONFLICT" for item in separate["discrepancies"])
    assert conflict["status"] == "UNRESOLVED"
    assert any(item["type"] == "ECONOMIC_QUANTITY_CONFLICT" for item in conflict["discrepancies"])


def test_partial_cancelled_and_orphan_lifecycle_states_are_explicit():
    service = EconomicGroupingService()
    records, rejected = _normalize(
        service,
        [
            _row("ORDER", "ORDER-PARTIAL", order_id="ORDER-PARTIAL", qty="1", status="PARTIALLY_FILLED"),
            _row("FILL", "FILL-PARTIAL", order_id="ORDER-PARTIAL", qty="0.4"),
            _row("ORDER", "ORDER-CANCEL", order_id="ORDER-CANCEL", qty="1", status="CANCELED"),
            _row("FILL", "FILL-CANCEL", order_id="ORDER-CANCEL", qty="0.2"),
            _row("FILL", "FILL-ORPHAN", order_id="ORDER-MISSING", qty="0.1"),
        ],
    )

    report = service.group(records, position_mode="ONE_WAY")
    lifecycle = {item["order_id"]: item["state"] for item in report["order_lifecycle"]}

    assert rejected == []
    assert lifecycle["ORDER-PARTIAL"] == "PARTIALLY_FILLED"
    assert lifecycle["ORDER-CANCEL"] == "CANCELED_WITH_FILL"
    assert any(item["type"] == "ORPHAN_FILL" for item in report["discrepancies"])


def test_repeated_source_observation_and_permutation_are_deterministic():
    service = EconomicGroupingService()
    records, _ = _normalize(
        service,
        [
            _row("ORDER", "ORDER-1", qty="0.5"),
            _row("FILL", "FILL-1", qty="0.5", economic_key="ECO-1"),
        ],
    )
    repeated = service.group([records[1], records[0], records[1]], position_mode="ONE_WAY")
    normal = service.group(records, position_mode="ONE_WAY")

    assert repeated["duplicate_source_observation_count"] == 1
    assert repeated["groups"] == normal["groups"]
    assert repeated["order_lifecycle"] == normal["order_lifecycle"]


def test_late_correction_changes_effective_contribution_without_erasing_original():
    service = EconomicGroupingService()
    records, rejected = _normalize(
        service,
        [
            _row("FILL", "FILL-1", qty="0.5", economic_key="ECO-1"),
            _row(
                "CORRECTION",
                "CORR-1",
                qty="0.7",
                economic_key="ECO-1",
                corrects_economic_key="ECO-1",
                effective_at="2026-09-08T12:00:00Z",
            ),
        ],
    )

    report = service.group(records, position_mode="ONE_WAY")
    group = report["groups"][0]

    assert rejected == []
    assert group["original_quantity"] == "0.5"
    assert group["quantity"] == "0.7"
    assert group["correction_count"] == 1
    assert group["correction_lineage"][0]["external_event_id"] == "CORR-1"
    assert any(item["type"] == "LATE_CORRECTION_APPLIED" for item in report["discrepancies"])


def test_one_way_lifecycle_classifies_scale_in_out_and_flip():
    service = EconomicGroupingService()
    rows = [
        _row("FILL", "FILL-1", order_id="O1", qty="1", economic_key="ECO-1"),
        _row("FILL", "FILL-2", order_id="O2", qty="0.5", economic_key="ECO-2", occurred_at="2026-09-08T10:01:00Z"),
        _row("FILL", "FILL-3", order_id="O3", qty="0.75", economic_key="ECO-3", occurred_at="2026-09-08T10:02:00Z", side="SELL"),
        _row("FILL", "FILL-4", order_id="O4", qty="2", economic_key="ECO-4", occurred_at="2026-09-08T10:03:00Z", side="SELL"),
    ]
    records, rejected = _normalize(service, rows)

    report = service.group(records, position_mode="ONE_WAY")

    assert rejected == []
    assert [item["position_effect"] for item in report["position_lifecycle"]] == [
        "OPEN",
        "SCALE_IN",
        "SCALE_OUT",
        "FLIP",
    ]


def test_missing_position_mode_does_not_claim_flip_or_scale_semantics():
    service = EconomicGroupingService()
    records, _ = _normalize(service, [_row("FILL", "FILL-1", qty="1", economic_key="ECO-1")])

    report = service.group(records)

    assert report["status"] == "UNRESOLVED"
    assert report["position_lifecycle"] == []
    assert any(item["type"] == "POSITION_MODE_UNKNOWN" for item in report["discrepancies"])


def test_invalid_decimal_and_source_identity_are_rejected():
    service = EconomicGroupingService()
    records, rejected = _normalize(
        service,
        [_row("FILL", "BAD-1", qty="NaN")],
    )
    assert records == []
    assert "finite number" in rejected[0]["reason"]

    records, rejected = service.normalize_observations(
        "BINANCE",
        [_row("FILL", "BAD-MARKET")],
        account_id="acct-1",
        source_exchange_id="binance_futures",
        market_type="spot",
        source_kind="API",
        source_document_sha256=SOURCE_SHA["api"],
    )
    assert records == []
    assert "market type" in rejected[0]["reason"]
