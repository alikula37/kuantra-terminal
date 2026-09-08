"""Deterministic economic fill deduplication and lifecycle grouping.

Source observations are not trades.  This service groups only bounded,
read-only order/fill observations, keeps every source lineage, and refuses to
invent an economic identity when scope or values conflict.  It intentionally
does not calculate PnL or mutate the canonical evidence ledger; journal and
projection propagation remain a later work package.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.db.repositories.evidence_ledger_repo import canonical_json
from app.services.account_reconciliation import _validate_source_identity
from app.services.broker_import_service import (
    SUPPORTED_VENUES,
    _decimal_number,
    _decimal_text,
    _first,
    _normalize_order_status,
    _normalize_side,
    _normalize_symbol,
    _normalize_timestamp,
    _required_text,
    _row_hash,
)


OBSERVATION_TYPES = ("ORDER", "FILL", "CORRECTION")
SOURCE_KINDS = frozenset({"CSV", "API"})
_HARD_DISCREPANCIES = frozenset({
    "ECONOMIC_QUANTITY_CONFLICT",
    "ECONOMIC_PRICE_CONFLICT",
    "SOURCE_OBSERVATION_CONFLICT",
    "SOURCE_IDENTITY_INCOMPLETE",
    "CORRECTION_TARGET_NOT_FOUND",
    "CORRECTION_VALUES_MISSING",
    "FILLED_ORDER_INCOMPLETE",
    "OVERFILLED_ORDER",
    "POSITION_MODE_UNKNOWN",
    "POSITION_MODE_UNSUPPORTED",
})


class EconomicGroupingValidationError(ValueError):
    """Raised when an observation cannot be normalized safely."""


def _normalize_source_kind(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "CSV": "CSV",
        "EXPORT": "CSV",
        "BROKER_EXPORT": "CSV",
        "JSON_EXPORT": "CSV",
        "API": "API",
        "BROKER_API": "API",
        "READ_ONLY_API": "API",
    }
    normalized = aliases.get(text)
    if normalized is None:
        raise EconomicGroupingValidationError("source_kind must be CSV or API")
    return normalized


def _validate_sha256(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise EconomicGroupingValidationError(f"{field} must be lowercase SHA-256")
    return text


def _bounded_text(value: Any, field: str, *, required: bool = False, max_length: int = 160) -> Optional[str]:
    if value is None or str(value).strip() == "":
        if required:
            raise EconomicGroupingValidationError(f"{field} is required")
        return None
    text = str(value).strip()
    if len(text) > max_length:
        raise EconomicGroupingValidationError(f"{field} is too long")
    return text


def _decimal_optional(value: Any, field: str, *, allow_negative: bool = True) -> Optional[Decimal]:
    try:
        return _decimal_number(value, field, allow_negative=allow_negative)
    except ValueError as exc:
        raise EconomicGroupingValidationError(str(exc)) from exc


def _decimal_required(value: Any, field: str, *, allow_negative: bool = False) -> Decimal:
    try:
        number = _decimal_number(value, field, allow_negative=allow_negative, required=True)
    except ValueError as exc:
        raise EconomicGroupingValidationError(str(exc)) from exc
    assert number is not None
    return number


def _decimal_sum(values: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        return sum(values, Decimal("0"))


def _decimal_add(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        return left + right


def _canonical_optional_decimal(value: Optional[Decimal]) -> Optional[str]:
    return _decimal_text(value) if value is not None else None


def _lineage(record: "EconomicObservation") -> Dict[str, Any]:
    return {
        "observation_id": record.observation_id,
        "source_kind": record.source_kind,
        "source_document_sha256": record.source_document_sha256,
        "source_row_number": record.source_row_number,
        "source_row_sha256": record.source_row_sha256,
        "external_order_id": record.external_order_id,
        "external_fill_id": record.external_fill_id,
        "external_event_id": record.external_event_id,
    }


@dataclass(frozen=True)
class EconomicObservation:
    """Secret-free immutable observation from one source document."""

    observation_type: str
    account_id: str
    venue: str
    source_exchange_id: Optional[str]
    market_type: Optional[str]
    source_kind: str
    source_document_sha256: str
    source_row_number: int
    source_row_sha256: str
    external_order_id: Optional[str]
    external_fill_id: Optional[str]
    external_event_id: str
    symbol: str
    side: str
    status: str
    order_qty: Optional[Decimal]
    filled_qty: Optional[Decimal]
    price: Optional[Decimal]
    occurred_at: str
    effective_at: Optional[str]
    economic_identity: Optional[str]
    corrects_economic_key: Optional[str]

    @property
    def observation_id(self) -> str:
        return (
            f"{self.account_id}:{self.venue}:{self.source_exchange_id or 'UNKNOWN_SOURCE'}:"
            f"{self.market_type or 'UNKNOWN_MARKET'}:{self.source_kind}:{self.source_document_sha256}:"
            f"{self.source_row_number}:{self.source_row_sha256}"
        )

    @property
    def scope_key(self) -> str:
        return "|".join((
            self.account_id,
            self.venue,
            self.source_exchange_id or "UNKNOWN_SOURCE",
            self.market_type or "UNKNOWN_MARKET",
            self.symbol,
        ))

    @property
    def economic_group_key(self) -> Optional[str]:
        if self.observation_type == "FILL":
            identity = self.economic_identity or f"FILL_ID:{self.external_fill_id}"
            return f"{self.scope_key}|{identity}"
        if self.observation_type == "CORRECTION" and self.corrects_economic_key:
            identity = self.corrects_economic_key
            if not identity.startswith("EXPLICIT:") and not identity.startswith("FILL_ID:"):
                identity = f"EXPLICIT:{identity}"
            return f"{self.scope_key}|{identity}"
        return None

    @property
    def order_group_key(self) -> Optional[str]:
        if not self.external_order_id:
            return None
        return f"{self.scope_key}|ORDER:{self.external_order_id}"

    def payload(self) -> Dict[str, Any]:
        return {
            "observation_type": self.observation_type,
            "account_id": self.account_id,
            "venue": self.venue,
            "source_exchange_id": self.source_exchange_id,
            "market_type": self.market_type,
            "source_kind": self.source_kind,
            "source_document_sha256": self.source_document_sha256,
            "source_row_number": self.source_row_number,
            "source_row_sha256": self.source_row_sha256,
            "external_order_id": self.external_order_id,
            "external_fill_id": self.external_fill_id,
            "external_event_id": self.external_event_id,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "order_qty": _canonical_optional_decimal(self.order_qty),
            "filled_qty": _canonical_optional_decimal(self.filled_qty),
            "price": _canonical_optional_decimal(self.price),
            "occurred_at": self.occurred_at,
            "effective_at": self.effective_at,
            "economic_identity": self.economic_identity,
            "corrects_economic_key": self.corrects_economic_key,
        }


class EconomicGroupingService:
    """Normalize observations and group their economic contribution deterministically."""

    @classmethod
    def normalize_observation(
        cls,
        venue: str,
        row: Mapping[str, Any],
        *,
        account_id: str,
        source_kind: str,
        source_document_sha256: str,
        source_exchange_id: Optional[str] = None,
        market_type: Optional[str] = None,
        row_number: int = 1,
    ) -> EconomicObservation:
        if not isinstance(row, Mapping):
            raise EconomicGroupingValidationError("observation row must be an object")
        row_dict = dict(row)
        normalized_venue = str(venue or "").strip().upper()
        if normalized_venue not in SUPPORTED_VENUES:
            raise EconomicGroupingValidationError(f"unsupported venue: {normalized_venue}")
        normalized_account = _bounded_text(account_id, "account_id", required=True, max_length=128)
        assert normalized_account is not None
        normalized_source_kind = _normalize_source_kind(source_kind)
        normalized_source_sha = _validate_sha256(source_document_sha256, "source_document_sha256")
        try:
            normalized_source_id, normalized_market = _validate_source_identity(
                normalized_venue,
                source_exchange_id or _first(row_dict, "source_exchange_id", "exchange_id"),
                market_type or _first(row_dict, "market_type"),
            )
        except ValueError as exc:
            raise EconomicGroupingValidationError(str(exc)) from exc

        raw_type = _first(row_dict, "observation_type", "record_type", "kind")
        if raw_type is None:
            raw_type = "FILL" if _first(row_dict, "fill_id", "trade_id", "fillId") is not None else "ORDER"
        observation_type = str(raw_type).strip().upper().replace("-", "_").replace(" ", "_")
        if observation_type not in OBSERVATION_TYPES:
            raise EconomicGroupingValidationError(f"unsupported observation type: {raw_type}")

        symbol = _normalize_symbol(_first(row_dict, "symbol", "instId"))
        try:
            side = _normalize_side(_first(row_dict, "side", "direction"))
            occurred_at = _normalize_timestamp(
                _first(row_dict, "occurred_at", "timestamp", "time", "ts", "uTime")
            )
            effective_at = (
                _normalize_timestamp(_first(row_dict, "effective_at", "effective_time"))
                if _first(row_dict, "effective_at", "effective_time") is not None
                else None
            )
        except ValueError as exc:
            raise EconomicGroupingValidationError(str(exc)) from exc

        external_order_id = _bounded_text(
            _first(row_dict, "external_order_id", "order_id", "orderId", "ordId"),
            "external_order_id",
        )
        external_fill_id = _bounded_text(
            _first(row_dict, "external_fill_id", "fill_id", "fillId", "tradeId"),
            "external_fill_id",
        )
        external_event_id = _bounded_text(
            _first(row_dict, "external_event_id", "event_id", "id"),
            "external_event_id",
            required=True,
        )
        assert external_event_id is not None
        order_qty = _decimal_optional(_first(row_dict, "order_qty", "origQty", "quantity", "sz"), "order_qty", allow_negative=False)
        filled_qty = _decimal_optional(
            _first(row_dict, "filled_qty", "executedQty", "accFillSz", "filled_size"),
            "filled_qty",
            allow_negative=False,
        )
        price = _decimal_optional(_first(row_dict, "price", "fill_price", "fillPx", "avgPrice", "avgPx"), "price", allow_negative=False)

        if observation_type == "FILL":
            if not external_order_id:
                raise EconomicGroupingValidationError("external_order_id is required for fill")
            if not external_fill_id:
                external_fill_id = external_event_id
            filled_qty = _decimal_required(
                _first(row_dict, "qty", "fill_qty", "quantity", "size", "sz", "filled_qty"),
                "filled_qty",
                allow_negative=False,
            )
            if filled_qty <= 0:
                raise EconomicGroupingValidationError("filled_qty must be greater than zero")
            price = _decimal_required(
                _first(row_dict, "price", "fill_price", "fillPx", "px"),
                "price",
                allow_negative=False,
            )
            if price <= 0:
                raise EconomicGroupingValidationError("price must be greater than zero")
            status = "FILLED"
        elif observation_type == "ORDER":
            if not external_order_id:
                external_order_id = external_event_id
            if order_qty is None:
                raise EconomicGroupingValidationError("order_qty is required for order")
            if order_qty <= 0:
                raise EconomicGroupingValidationError("order_qty must be greater than zero")
            try:
                status = _normalize_order_status(_first(row_dict, "status", "state"))
            except ValueError as exc:
                raise EconomicGroupingValidationError(str(exc)) from exc
        else:
            if not external_order_id:
                external_order_id = None
            status = "CORRECTION"

        explicit_key = _bounded_text(
            _first(row_dict, "economic_key", "economic_identity", "economic_fill_id"),
            "economic_key",
        )
        economic_identity: Optional[str] = None
        if observation_type == "FILL":
            economic_identity = f"EXPLICIT:{explicit_key}" if explicit_key else f"FILL_ID:{external_fill_id}"
        corrects_key = _bounded_text(
            _first(row_dict, "corrects_economic_key", "correction_of", "replaces_economic_key"),
            "corrects_economic_key",
        )
        if observation_type == "CORRECTION":
            if not corrects_key:
                raise EconomicGroupingValidationError("corrects_economic_key is required for correction")
            if effective_at is None:
                raise EconomicGroupingValidationError("effective_at is required for correction")
            if _first(row_dict, "qty", "replacement_qty", "filled_qty") is not None:
                filled_qty = _decimal_required(
                    _first(row_dict, "qty", "replacement_qty", "filled_qty"),
                    "filled_qty",
                    allow_negative=False,
                )
                if filled_qty <= 0:
                    raise EconomicGroupingValidationError("correction filled_qty must be greater than zero")
            if _first(row_dict, "price", "replacement_price") is not None:
                price = _decimal_required(
                    _first(row_dict, "price", "replacement_price"),
                    "price",
                    allow_negative=False,
                )
                if price <= 0:
                    raise EconomicGroupingValidationError("correction price must be greater than zero")

        return EconomicObservation(
            observation_type=observation_type,
            account_id=normalized_account,
            venue=normalized_venue,
            source_exchange_id=normalized_source_id,
            market_type=normalized_market,
            source_kind=normalized_source_kind,
            source_document_sha256=normalized_source_sha,
            source_row_number=row_number,
            source_row_sha256=_row_hash(row_dict),
            external_order_id=external_order_id,
            external_fill_id=external_fill_id,
            external_event_id=external_event_id,
            symbol=symbol,
            side=side,
            status=status,
            order_qty=order_qty,
            filled_qty=filled_qty,
            price=price,
            occurred_at=occurred_at,
            effective_at=effective_at,
            economic_identity=economic_identity,
            corrects_economic_key=corrects_key,
        )

    @classmethod
    def normalize_observations(
        cls,
        venue: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        account_id: str,
        source_kind: str,
        source_document_sha256: str,
        source_exchange_id: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> Tuple[List[EconomicObservation], List[Dict[str, Any]]]:
        records: List[EconomicObservation] = []
        rejected: List[Dict[str, Any]] = []
        for row_number, row in enumerate(rows, start=1):
            try:
                records.append(
                    cls.normalize_observation(
                        venue,
                        row,
                        account_id=account_id,
                        source_kind=source_kind,
                        source_document_sha256=source_document_sha256,
                        source_exchange_id=source_exchange_id,
                        market_type=market_type,
                        row_number=row_number,
                    )
                )
            except (EconomicGroupingValidationError, TypeError, ValueError) as exc:
                rejected.append({"source_row_number": row_number, "reason": str(exc)})
        return records, rejected

    @staticmethod
    def _sort_observation(record: EconomicObservation) -> Tuple[str, str, str]:
        return (record.observation_id, record.observation_type, canonical_json(record.payload()))

    @staticmethod
    def _group_id(group_key: str) -> str:
        return f"economic:{hashlib.sha256(group_key.encode('utf-8')).hexdigest()[:24]}"

    @classmethod
    def _deduplicate_source_observations(
        cls,
        records: Iterable[EconomicObservation],
        discrepancies: List[Dict[str, Any]],
    ) -> Tuple[List[EconomicObservation], int]:
        selected: Dict[str, EconomicObservation] = {}
        source_rows: Dict[Tuple[str, ...], EconomicObservation] = {}
        duplicate_count = 0
        for record in sorted(records, key=cls._sort_observation):
            existing = selected.get(record.observation_id)
            if existing is not None:
                if existing.payload() == record.payload():
                    duplicate_count += 1
                else:
                    discrepancies.append({
                        "type": "SOURCE_OBSERVATION_CONFLICT",
                        "observation_id": record.observation_id,
                    })
                continue
            row_key = (
                record.account_id,
                record.venue,
                record.source_exchange_id or "UNKNOWN_SOURCE",
                record.market_type or "UNKNOWN_MARKET",
                record.source_kind,
                record.source_document_sha256,
                record.source_row_number,
            )
            existing_row = source_rows.get(row_key)
            if existing_row is not None and existing_row.source_row_sha256 != record.source_row_sha256:
                discrepancies.append({
                    "type": "SOURCE_OBSERVATION_CONFLICT",
                    "source_kind": record.source_kind,
                    "source_document_sha256": record.source_document_sha256,
                    "source_row_number": record.source_row_number,
                })
                continue
            selected[record.observation_id] = record
            source_rows[row_key] = record
        return list(selected.values()), duplicate_count

    @classmethod
    def group(
        cls,
        observations: Iterable[EconomicObservation],
        *,
        position_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        discrepancies: List[Dict[str, Any]] = []
        records, duplicate_source_observation_count = cls._deduplicate_source_observations(
            observations,
            discrepancies,
        )
        records.sort(key=lambda record: (record.occurred_at, record.observation_id))
        for record in records:
            if record.source_exchange_id is None or record.market_type is None:
                discrepancies.append({
                    "type": "SOURCE_IDENTITY_INCOMPLETE",
                    "observation_id": record.observation_id,
                })

        fills_by_group: Dict[str, List[EconomicObservation]] = defaultdict(list)
        orders_by_group: Dict[str, List[EconomicObservation]] = defaultdict(list)
        corrections: List[EconomicObservation] = []
        for record in records:
            if record.observation_type == "FILL" and record.economic_group_key:
                fills_by_group[record.economic_group_key].append(record)
            elif record.observation_type == "ORDER" and record.order_group_key:
                orders_by_group[record.order_group_key].append(record)
            elif record.observation_type == "CORRECTION":
                corrections.append(record)

        groups: Dict[str, Dict[str, Any]] = {}
        group_to_records: Dict[str, List[EconomicObservation]] = {}
        for group_key in sorted(fills_by_group):
            group_records = sorted(fills_by_group[group_key], key=cls._sort_observation)
            group_to_records[group_key] = group_records
            group_discrepancies: List[Dict[str, Any]] = []
            quantities = {record.filled_qty for record in group_records}
            prices = {record.price for record in group_records}
            if len(quantities) > 1:
                group_discrepancies.append({"type": "ECONOMIC_QUANTITY_CONFLICT", "group_key": group_key})
                discrepancies.append(group_discrepancies[-1])
            if len(prices) > 1:
                group_discrepancies.append({"type": "ECONOMIC_PRICE_CONFLICT", "group_key": group_key})
                discrepancies.append(group_discrepancies[-1])
            first = group_records[0]
            group_id = cls._group_id(group_key)
            groups[group_key] = {
                "economic_group_id": group_id,
                "economic_group_key": group_key,
                "account_id": first.account_id,
                "venue": first.venue,
                "source_exchange_id": first.source_exchange_id,
                "market_type": first.market_type,
                "symbol": first.symbol,
                "side": first.side,
                "quantity": _canonical_optional_decimal(first.filled_qty) if len(quantities) == 1 else None,
                "price": _canonical_optional_decimal(first.price) if len(prices) == 1 else None,
                "original_quantity": _canonical_optional_decimal(first.filled_qty) if len(quantities) == 1 else None,
                "original_price": _canonical_optional_decimal(first.price) if len(prices) == 1 else None,
                "occurred_at": min(record.occurred_at for record in group_records),
                "status": "UNRESOLVED" if group_discrepancies else "CONFIRMED",
                "source_observation_count": len(group_records),
                "source_lineage": sorted((_lineage(record) for record in group_records), key=lambda item: item["observation_id"]),
                "external_order_ids": sorted({record.external_order_id for record in group_records if record.external_order_id}),
                "external_fill_ids": sorted({record.external_fill_id for record in group_records if record.external_fill_id}),
                "correction_count": 0,
                "correction_lineage": [],
                "discrepancies": group_discrepancies,
            }

        for correction in sorted(
            corrections,
            key=lambda record: (record.effective_at or record.occurred_at, record.observation_id),
        ):
            target_key = correction.economic_group_key
            target = groups.get(target_key or "")
            if target is None:
                discrepancy = {
                    "type": "CORRECTION_TARGET_NOT_FOUND",
                    "external_event_id": correction.external_event_id,
                    "corrects_economic_key": correction.corrects_economic_key,
                }
                discrepancies.append(discrepancy)
                continue
            if correction.filled_qty is None and correction.price is None:
                discrepancy = {
                    "type": "CORRECTION_VALUES_MISSING",
                    "external_event_id": correction.external_event_id,
                    "group_key": target_key,
                }
                discrepancies.append(discrepancy)
                target["status"] = "UNRESOLVED"
                target["discrepancies"].append(discrepancy)
                continue
            if target["correction_count"] == 0:
                target["original_quantity"] = target["quantity"]
                target["original_price"] = target["price"]
            if correction.filled_qty is not None:
                target["quantity"] = _decimal_text(correction.filled_qty)
            if correction.price is not None:
                target["price"] = _decimal_text(correction.price)
            target["correction_count"] += 1
            target["correction_lineage"].append(_lineage(correction))
            target["correction_lineage"][-1]["effective_at"] = correction.effective_at
            discrepancies.append({
                "type": "LATE_CORRECTION_APPLIED",
                "external_event_id": correction.external_event_id,
                "group_key": target_key,
            })

        order_lifecycle: List[Dict[str, Any]] = []
        group_order_keys: Dict[str, set[str]] = defaultdict(set)
        for group_key, group_records in group_to_records.items():
            for record in group_records:
                if record.order_group_key:
                    group_order_keys[record.order_group_key].add(group_key)
        all_order_keys = sorted(set(orders_by_group) | set(group_order_keys))
        for order_key in all_order_keys:
            order_records = sorted(
                orders_by_group.get(order_key, []),
                key=lambda record: (record.occurred_at, record.observation_id),
            )
            linked_group_keys = sorted(group_order_keys.get(order_key, set()))
            linked_groups = [groups[key] for key in linked_group_keys if key in groups]
            latest = order_records[-1] if order_records else None
            observed_quantities = [
                Decimal(group["quantity"])
                for group in linked_groups
                if group["quantity"] is not None and group["status"] == "CONFIRMED"
            ]
            observed_qty = _decimal_sum(observed_quantities) if observed_quantities else None
            expected_qty = latest.filled_qty if latest and latest.filled_qty is not None else None
            state = "ORPHAN_FILL" if latest is None else "NO_FILL"
            order_discrepancies: List[Dict[str, Any]] = []
            if latest is not None:
                if observed_qty is None or observed_qty == Decimal("0"):
                    if latest.status == "FILLED" and expected_qty and expected_qty > 0:
                        state = "FILLED_ORDER_WITHOUT_FILL"
                        order_discrepancies.append({"type": "MISSING_FILL_FOR_FILLED_ORDER", "order_id": latest.external_order_id})
                    elif latest.status in {"CANCELED", "EXPIRED", "REJECTED"}:
                        state = latest.status
                elif latest.status == "REJECTED":
                    state = "REJECTED_WITH_FILL"
                elif latest.status == "CANCELED":
                    state = "CANCELED_WITH_FILL"
                elif expected_qty is None:
                    state = "PARTIAL_UNKNOWN"
                    order_discrepancies.append({"type": "ORDER_FILLED_QTY_UNKNOWN", "order_id": latest.external_order_id})
                elif observed_qty == expected_qty:
                    state = "FILLED"
                elif observed_qty < expected_qty:
                    state = "FILLED_ORDER_INCOMPLETE" if latest.status == "FILLED" else "PARTIALLY_FILLED"
                    if state == "FILLED_ORDER_INCOMPLETE":
                        order_discrepancies.append({"type": "FILLED_ORDER_INCOMPLETE", "order_id": latest.external_order_id})
                else:
                    state = "OVERFILLED"
                    order_discrepancies.append({"type": "OVERFILLED_ORDER", "order_id": latest.external_order_id})
            for discrepancy in order_discrepancies:
                discrepancies.append(discrepancy)
            order_lifecycle.append({
                "order_group_key": order_key,
                "order_id": latest.external_order_id if latest else order_key.rsplit("|ORDER:", 1)[-1],
                "scope_key": order_key.split("|ORDER:", 1)[0],
                "state": state,
                "order_qty": _canonical_optional_decimal(latest.order_qty) if latest else None,
                "expected_filled_qty": _canonical_optional_decimal(expected_qty),
                "observed_filled_qty": _canonical_optional_decimal(observed_qty),
                "fill_group_ids": [groups[key]["economic_group_id"] for key in linked_group_keys],
                "source_observation_count": len(order_records),
                "discrepancies": order_discrepancies,
            })
            if latest is None:
                for group_key in linked_group_keys:
                    discrepancies.append({
                        "type": "ORPHAN_FILL",
                        "order_id": order_key.rsplit("|ORDER:", 1)[-1],
                        "group_id": groups[group_key]["economic_group_id"],
                    })

        position_lifecycle: List[Dict[str, Any]] = []
        confirmed_groups = [group for group in groups.values() if group["status"] == "CONFIRMED" and group["quantity"] is not None]
        if confirmed_groups and position_mode is None:
            discrepancies.append({"type": "POSITION_MODE_UNKNOWN"})
        elif confirmed_groups and str(position_mode).upper() != "ONE_WAY":
            discrepancies.append({"type": "POSITION_MODE_UNSUPPORTED", "position_mode": position_mode})
        elif confirmed_groups:
            positions: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
            for group in sorted(confirmed_groups, key=lambda item: (item["occurred_at"], item["economic_group_id"])):
                quantity = Decimal(group["quantity"])
                signed = quantity if group["side"] == "BUY" else -quantity
                scope = "|".join((
                    group["account_id"],
                    group["venue"],
                    group["source_exchange_id"] or "UNKNOWN_SOURCE",
                    group["market_type"] or "UNKNOWN_MARKET",
                    group["symbol"],
                ))
                before = positions[scope]
                after = _decimal_add(before, signed)
                if before == 0:
                    effect = "OPEN"
                elif (before > 0 and signed > 0) or (before < 0 and signed < 0):
                    effect = "SCALE_IN" if abs(after) > abs(before) else "SCALE_OUT"
                elif after == 0:
                    effect = "CLOSE"
                elif (before > 0 > after) or (before < 0 < after):
                    effect = "FLIP"
                else:
                    effect = "SCALE_OUT"
                positions[scope] = after
                group["position_effect"] = effect
                position_lifecycle.append({
                    "economic_group_id": group["economic_group_id"],
                    "symbol": group["symbol"],
                    "side": group["side"],
                    "quantity": group["quantity"],
                    "position_before": _decimal_text(before),
                    "position_after": _decimal_text(after),
                    "position_effect": effect,
                })

        hard = any(item.get("type") in _HARD_DISCREPANCIES for item in discrepancies)
        status = "UNRESOLVED" if hard else ("PARTIAL" if discrepancies else "RECONCILED")
        return {
            "status": status,
            "source_observation_count": len(records),
            "duplicate_source_observation_count": duplicate_source_observation_count,
            "economic_group_count": len(groups),
            "economic_contribution_count": sum(
                1 for group in groups.values() if group["status"] == "CONFIRMED" and group["quantity"] is not None
            ),
            "groups": [groups[key] for key in sorted(groups)],
            "order_lifecycle": order_lifecycle,
            "position_lifecycle": position_lifecycle,
            "discrepancies": discrepancies,
        }


economic_grouping_service = EconomicGroupingService()
