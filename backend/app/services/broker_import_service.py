"""Read-only broker order/fill import and deterministic reconciliation.

This module intentionally accepts already-decoded export rows.  It does not
open exchange connections, hold credentials, submit orders, or mutate the
legacy ``trades`` table.  Normalized lifecycle observations are appended to the
canonical evidence ledger and can be reconciled against one another without
pretending that an imported observation was a local trading intent.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json


SUPPORTED_VENUES = {"BINANCE", "OKX"}
SUPPORTED_SOURCE_EXCHANGES = {
    "binance_spot": {"venue": "BINANCE", "market_type": "spot"},
    "binance_futures": {"venue": "BINANCE", "market_type": "swap"},
    "okx": {"venue": "OKX", "market_type": "swap"},
}
SUPPORTED_SOURCE_EXCHANGE_IDS = set(SUPPORTED_SOURCE_EXCHANGES)
SUPPORTED_MARKET_TYPES = {metadata["market_type"] for metadata in SUPPORTED_SOURCE_EXCHANGES.values()}
DECIMAL_ENCODING = "DECIMAL_STRING_V1"
_DECIMAL_ZERO = Decimal("0")
_DECIMAL_MAX_DIGITS = 64
_DECIMAL_MAX_EXPONENT = 64
ORDER_EVENT_STATUSES = {
    "NEW",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED",
}

_MISSING = object()


class BrokerImportValidationError(ValueError):
    """Raised when a broker export row cannot be normalized safely."""


def _first(row: Dict[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key in row and row[key] is not None and str(row[key]).strip() != "":
            return row[key]
    if default is not _MISSING:
        return default
    return None


def _required_text(value: Any, field: str) -> str:
    if value is None or not str(value).strip():
        raise BrokerImportValidationError(f"{field} is required")
    return str(value).strip()


def _decimal_number(
    value: Any,
    field: str,
    *,
    required: bool = False,
    allow_negative: bool = False,
) -> Optional[Decimal]:
    if value is None or str(value).strip() == "":
        if required:
            raise BrokerImportValidationError(f"{field} is required")
        return None
    if isinstance(value, bool):
        raise BrokerImportValidationError(f"{field} must be a finite number")
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerImportValidationError(f"{field} must be a finite number") from exc
    if not number.is_finite():
        raise BrokerImportValidationError(f"{field} must be a finite number")
    decimal_tuple = number.as_tuple()
    if len(decimal_tuple.digits) > _DECIMAL_MAX_DIGITS or (
        isinstance(decimal_tuple.exponent, int)
        and abs(decimal_tuple.exponent) > _DECIMAL_MAX_EXPONENT
    ):
        raise BrokerImportValidationError(f"{field} exceeds the supported decimal precision")
    if not allow_negative and number < 0:
        raise BrokerImportValidationError(f"{field} cannot be negative")
    return number


def _decimal_text(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _normalize_fee_currency(value: Any) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().upper()
    if len(text) > 32 or not all(character.isalnum() or character in "._:-" for character in text):
        raise BrokerImportValidationError("fee_currency must be a bounded currency identifier")
    return text


def _decimal_sum(values: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        return sum(values, _DECIMAL_ZERO)


def _decimal_product(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        return left * right


def _decimal_divide(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 128
        return left / right


def _normalize_timestamp(value: Any) -> str:
    if value is None or not str(value).strip():
        raise BrokerImportValidationError("occurred_at is required")
    text = str(value).strip().replace("Z", "+00:00")
    try:
        if text.replace(".", "", 1).isdigit():
            epoch = float(text)
            if not math.isfinite(epoch) or epoch < 0:
                raise ValueError()
            if epoch > 1e11:
                epoch /= 1000.0
            parsed = datetime.fromtimestamp(epoch, timezone.utc)
        else:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise BrokerImportValidationError("occurred_at must be an ISO-8601 or epoch timestamp") from exc
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"BUY", "LONG"}:
        return "BUY"
    if text in {"SELL", "SHORT"}:
        return "SELL"
    raise BrokerImportValidationError("side must be BUY or SELL")


def _normalize_symbol(value: Any) -> str:
    text = _required_text(value, "symbol").upper().replace("/", "")
    if len(text) > 80:
        raise BrokerImportValidationError("symbol is too long")
    return text


def _normalize_order_status(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "OPEN": "NEW",
        "LIVE": "NEW",
        "PARTIALLYFILLED": "PARTIALLY_FILLED",
        "CANCELLED": "CANCELED",
        "MMP_CANCELED": "CANCELED",
        "ORDER_FAILED": "REJECTED",
        "EXPIRED_IN_MATCH": "EXPIRED",
    }
    normalized = aliases.get(text, text)
    if normalized not in ORDER_EVENT_STATUSES:
        raise BrokerImportValidationError(f"unsupported order status: {value}")
    return normalized


def _row_hash(row: Dict[str, Any]) -> str:
    try:
        canonical = canonical_json(row).encode("utf-8")
    except Exception as exc:
        raise BrokerImportValidationError("source row is not canonical JSON") from exc
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class BrokerLifecycleRecord:
    """Normalized immutable observation from a broker export."""

    venue: str
    record_type: str
    external_order_id: str
    external_fill_id: Optional[str]
    symbol: str
    side: str
    status: str
    order_qty: Optional[Decimal]
    filled_qty: Optional[Decimal]
    price: Optional[Decimal]
    avg_price: Optional[Decimal]
    fee: Optional[Decimal]
    fee_currency: Optional[str]
    occurred_at: str
    source_row_number: int
    source_row_sha256: str

    @property
    def external_identity(self) -> str:
        return self.external_fill_id or self.external_order_id

    def payload(self) -> Dict[str, Any]:
        return {
            "numeric_encoding": DECIMAL_ENCODING,
            "numeric_units": {
                "order_qty": "VENUE_NATIVE_QUANTITY",
                "filled_qty": "VENUE_NATIVE_QUANTITY",
                "price": "VENUE_NATIVE_PRICE",
                "avg_price": "VENUE_NATIVE_PRICE",
                "fee": f"CURRENCY:{self.fee_currency}" if self.fee_currency else "UNKNOWN_CURRENCY",
            },
            "record_type": self.record_type,
            "venue": self.venue,
            "external_order_id": self.external_order_id,
            "external_fill_id": self.external_fill_id,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "order_qty": _decimal_text(self.order_qty),
            "filled_qty": _decimal_text(self.filled_qty),
            "price": _decimal_text(self.price),
            "avg_price": _decimal_text(self.avg_price),
            "fee": _decimal_text(self.fee),
            "fee_currency": self.fee_currency,
            "occurred_at": self.occurred_at,
            "source_row_number": self.source_row_number,
            "source_row_sha256": self.source_row_sha256,
        }


class BrokerImportService:
    """Normalize fixture/export rows, append lifecycle evidence, and reconcile."""

    def __init__(self, ledger_repo: Optional[EvidenceLedgerRepository] = None):
        self.ledger_repo = ledger_repo or EvidenceLedgerRepository()

    @staticmethod
    def _coverage_summary(
        report: Dict[str, Any],
        *,
        normalized_record_count: int,
        rejected_row_count: int,
    ) -> Dict[str, str]:
        """Describe what the order/fill export proves, without widening scope."""

        if report.get("status") == "RECONCILED" and normalized_record_count and not rejected_row_count:
            lifecycle = "COMPLETE"
        elif normalized_record_count:
            lifecycle = "PARTIAL"
        else:
            lifecycle = "UNKNOWN"
        return {
            # A broker lifecycle snapshot never proves account balance, funding,
            # transfer history, or market context.  Overall coverage therefore
            # remains PARTIAL even when order/fill arithmetic reconciles.
            "status": "PARTIAL" if normalized_record_count else "UNKNOWN",
            "lifecycle": lifecycle,
            "fees": str(report.get("fee_reconciliation_status") or "UNKNOWN"),
            "account_events": "NOT_AVAILABLE",
            "funding_transfer": "NOT_AVAILABLE",
            "market_context": "NOT_AVAILABLE",
        }

    @classmethod
    def _review_summary(
        cls,
        report: Dict[str, Any],
        *,
        coverage: Dict[str, str],
        normalized_record_count: int,
        rejected_row_count: int,
    ) -> Dict[str, Any]:
        discrepancy_types = sorted({
            str(item.get("type"))
            for item in report.get("discrepancies", [])
            if isinstance(item, dict) and item.get("type")
        })
        ready = (
            report.get("status") == "RECONCILED"
            and normalized_record_count > 0
            and rejected_row_count == 0
        )
        return {
            "status": "READY_FOR_USER_REVIEW" if ready else "REVIEW_REQUIRED",
            "source_type": "BROKER_ORDER_FILL_EXPORT",
            "next_action": "USER_DECISION_REQUIRED_TO_CREATE_TRADE_SNAPSHOT",
            "reconciliation_status": report.get("status"),
            "coverage": coverage,
            "discrepancy_count": len(report.get("discrepancies", [])),
            "discrepancy_types": discrepancy_types,
        }

    @staticmethod
    def _validate_venue(venue: str) -> str:
        normalized = _required_text(venue, "venue").upper()
        if normalized not in SUPPORTED_VENUES:
            raise BrokerImportValidationError(
                f"unsupported broker venue: {normalized}; supported={sorted(SUPPORTED_VENUES)}"
            )
        return normalized

    @classmethod
    def normalize_order(cls, venue: str, row: Dict[str, Any], row_number: int) -> BrokerLifecycleRecord:
        venue = cls._validate_venue(venue)
        order_id = _required_text(_first(row, "orderId", "order_id", "ordId", "id"), "external_order_id")
        status = _normalize_order_status(_first(row, "status", "state"))
        order_qty = _decimal_number(
            _first(row, "origQty", "order_qty", "quantity", "qty", "sz"),
            "order_qty",
            required=True,
        )
        filled_qty = _decimal_number(
            _first(row, "executedQty", "filled_qty", "filledQty", "accFillSz", "filled_size"),
            "filled_qty",
        )
        avg_price = _decimal_number(_first(row, "avgPrice", "avg_price", "avgPx"), "avg_price")
        price = _decimal_number(_first(row, "price", "px", "order_price"), "price")
        fee = _decimal_number(_first(row, "fee", "commission", "fee_cost"), "fee", allow_negative=True)
        fee_currency = _normalize_fee_currency(_first(row, "fee_currency", "commissionAsset", "feeCcy"))
        return BrokerLifecycleRecord(
            venue=venue,
            record_type="order",
            external_order_id=order_id,
            external_fill_id=None,
            symbol=_normalize_symbol(_first(row, "symbol", "instId")),
            side=_normalize_side(_first(row, "side", "direction")),
            status=status,
            order_qty=order_qty,
            filled_qty=filled_qty,
            price=price,
            avg_price=avg_price,
            fee=fee,
            fee_currency=fee_currency,
            occurred_at=_normalize_timestamp(_first(row, "updateTime", "uTime", "time", "cTime", "timestamp")),
            source_row_number=row_number,
            source_row_sha256=_row_hash(row),
        )

    @classmethod
    def normalize_fill(cls, venue: str, row: Dict[str, Any], row_number: int) -> BrokerLifecycleRecord:
        venue = cls._validate_venue(venue)
        order_id = _required_text(_first(row, "orderId", "order_id", "ordId"), "external_order_id")
        fill_id = _required_text(_first(row, "id", "tradeId", "fillId", "fill_id"), "external_fill_id")
        quantity = _decimal_number(
            _first(row, "qty", "quantity", "size", "fill_qty", "sz"),
            "filled_qty",
            required=True,
        )
        if quantity <= 0:
            raise BrokerImportValidationError("filled_qty must be greater than zero")
        price = _decimal_number(_first(row, "price", "fill_price", "fillPx"), "price", required=True)
        if price <= 0:
            raise BrokerImportValidationError("price must be greater than zero")
        fee = _decimal_number(_first(row, "fee", "commission", "fee_cost"), "fee", allow_negative=True)
        fee_currency = _normalize_fee_currency(_first(row, "fee_currency", "commissionAsset", "feeCcy"))
        return BrokerLifecycleRecord(
            venue=venue,
            record_type="fill",
            external_order_id=order_id,
            external_fill_id=fill_id,
            symbol=_normalize_symbol(_first(row, "symbol", "instId")),
            side=_normalize_side(_first(row, "side", "direction")),
            status="FILLED",
            order_qty=None,
            filled_qty=quantity,
            price=price,
            avg_price=price,
            fee=fee,
            fee_currency=fee_currency,
            occurred_at=_normalize_timestamp(_first(row, "time", "fillTime", "ts", "uTime", "timestamp")),
            source_row_number=row_number,
            source_row_sha256=_row_hash(row),
        )

    @classmethod
    def normalize_records(
        cls,
        venue: str,
        *,
        orders: Sequence[Dict[str, Any]] = (),
        fills: Sequence[Dict[str, Any]] = (),
    ) -> Tuple[List[BrokerLifecycleRecord], List[Dict[str, Any]]]:
        """Normalize rows and return ``(records, rejected_rows)``.

        Rejected rows are reported with row/type/reason only; raw row content is
        never returned to the UI or written to the evidence ledger.
        """
        records: List[BrokerLifecycleRecord] = []
        rejected: List[Dict[str, Any]] = []
        row_number = 1
        for record_type, rows, normalizer in (
            ("order", orders, cls.normalize_order),
            ("fill", fills, cls.normalize_fill),
        ):
            for row in rows:
                try:
                    records.append(normalizer(venue, dict(row), row_number))
                except (TypeError, BrokerImportValidationError, ValueError) as exc:
                    rejected.append({"record_type": record_type, "source_row_number": row_number, "reason": str(exc)})
                row_number += 1
        return records, rejected

    @staticmethod
    def _tolerance(_expected: Decimal) -> Decimal:
        """Return no implicit numeric tolerance before a unit contract exists."""

        return _DECIMAL_ZERO

    @classmethod
    def _reconcile_fees(
        cls,
        order: BrokerLifecycleRecord,
        fills: Sequence[BrokerLifecycleRecord],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Reconcile fees without treating missing amounts as zero."""

        fee_records = [order, *fills]
        fee_amounts = [record.fee for record in fee_records if record.fee is not None]
        fee_currency_only = any(record.fee is None and record.fee_currency is not None for record in fee_records)
        if not fee_amounts:
            if fee_currency_only:
                return "UNKNOWN", [{
                    "type": "FEE_AMOUNT_UNKNOWN",
                    "external_order_id": order.external_order_id,
                }]
            return "NOT_PROVIDED", []

        discrepancies: List[Dict[str, Any]] = []
        if order.fee is None or any(fill.fee is None for fill in fills):
            discrepancies.append({
                "type": "FEE_DATA_INCOMPLETE",
                "external_order_id": order.external_order_id,
            })

        fee_records_with_amount = [record for record in fee_records if record.fee is not None]
        if any(record.fee_currency is None for record in fee_records_with_amount):
            discrepancies.append({
                "type": "FEE_CURRENCY_UNKNOWN",
                "external_order_id": order.external_order_id,
            })
        currencies = {record.fee_currency for record in fee_records_with_amount if record.fee_currency is not None}
        if len(currencies) > 1:
            discrepancies.append({
                "type": "MULTI_CURRENCY_FEES",
                "external_order_id": order.external_order_id,
                "currencies": sorted(currencies),
            })

        if fills and order.fee_currency is not None and all(fill.fee_currency is not None for fill in fills):
            fill_currencies = {fill.fee_currency for fill in fills}
            if fill_currencies != {order.fee_currency}:
                discrepancies.append({
                    "type": "FEE_CURRENCY_MISMATCH",
                    "external_order_id": order.external_order_id,
                })

        if not discrepancies:
            fill_fee = _decimal_sum(fill.fee for fill in fills if fill.fee is not None)
            if fill_fee != order.fee:
                discrepancies.append({
                    "type": "FEE_MISMATCH",
                    "external_order_id": order.external_order_id,
                    "order_fee": _decimal_text(order.fee),
                    "fill_fee": _decimal_text(fill_fee),
                    "fee_currency": order.fee_currency,
                })
        if discrepancies:
            has_hard_conflict = any(
                item["type"] in {
                    "FEE_CURRENCY_UNKNOWN",
                    "MULTI_CURRENCY_FEES",
                    "FEE_CURRENCY_MISMATCH",
                    "FEE_MISMATCH",
                }
                for item in discrepancies
            )
            return "UNRECONCILED" if has_hard_conflict else "UNKNOWN", discrepancies
        return "RECONCILED", []

    @classmethod
    def reconcile(cls, records: Iterable[BrokerLifecycleRecord]) -> Dict[str, Any]:
        orders: Dict[str, BrokerLifecycleRecord] = {}
        fills_by_order: Dict[str, List[BrokerLifecycleRecord]] = defaultdict(list)
        discrepancies: List[Dict[str, Any]] = []
        duplicate_orders = 0
        duplicate_fills = 0
        fee_statuses: List[str] = []

        for record in records:
            if record.record_type == "order":
                if record.external_order_id in orders:
                    duplicate_orders += 1
                    discrepancies.append({
                        "type": "DUPLICATE_ORDER_ID",
                        "external_order_id": record.external_order_id,
                    })
                else:
                    orders[record.external_order_id] = record
            else:
                existing = fills_by_order[record.external_order_id]
                if any(fill.external_fill_id == record.external_fill_id for fill in existing):
                    duplicate_fills += 1
                    discrepancies.append({
                        "type": "DUPLICATE_FILL_ID",
                        "external_order_id": record.external_order_id,
                        "external_fill_id": record.external_fill_id,
                    })
                fills_by_order[record.external_order_id].append(record)

        reconciled_orders = 0
        for order_id, order in orders.items():
            fills = fills_by_order.get(order_id, [])
            total_filled = _decimal_sum(fill.filled_qty for fill in fills if fill.filled_qty is not None)
            if order.filled_qty is None:
                discrepancies.append({"type": "MISSING_ORDER_FILLED_QTY", "external_order_id": order_id})
            elif abs(total_filled - order.filled_qty) > cls._tolerance(order.filled_qty):
                discrepancies.append({
                    "type": "QUANTITY_MISMATCH",
                    "external_order_id": order_id,
                    "order_filled_qty": _decimal_text(order.filled_qty),
                    "fill_qty": _decimal_text(total_filled),
                })

            if order.status == "FILLED" and total_filled <= _DECIMAL_ZERO:
                discrepancies.append({"type": "FILLED_ORDER_WITHOUT_FILL", "external_order_id": order_id})
            if order.filled_qty is not None and order.filled_qty > _DECIMAL_ZERO and not fills:
                discrepancies.append({"type": "MISSING_FILL_ROWS", "external_order_id": order_id})

            expected_price = order.avg_price if order.avg_price is not None else order.price
            if expected_price is not None and total_filled > _DECIMAL_ZERO:
                weighted_numerator = _decimal_sum(
                    _decimal_product(fill.filled_qty, fill.price)
                    for fill in fills
                    if fill.filled_qty is not None and fill.price is not None
                )
                if weighted_numerator != _decimal_product(expected_price, total_filled):
                    discrepancies.append({
                        "type": "AVERAGE_PRICE_MISMATCH",
                        "external_order_id": order_id,
                        "order_avg_price": _decimal_text(expected_price),
                        "fill_weighted_price": _decimal_text(_decimal_divide(weighted_numerator, total_filled)),
                    })

            _fee_status, fee_discrepancies = cls._reconcile_fees(order, fills)
            fee_statuses.append(_fee_status)
            discrepancies.extend(fee_discrepancies)

            if not any(item.get("external_order_id") == order_id for item in discrepancies):
                reconciled_orders += 1

        orphan_fill_orders = sorted(set(fills_by_order) - set(orders))
        for order_id in orphan_fill_orders:
            discrepancies.append({"type": "ORPHAN_FILL", "external_order_id": order_id})

        if any(status == "UNRECONCILED" for status in fee_statuses):
            fee_reconciliation_status = "UNRECONCILED"
        elif any(status == "UNKNOWN" for status in fee_statuses):
            fee_reconciliation_status = "UNKNOWN"
        elif any(status == "RECONCILED" for status in fee_statuses):
            fee_reconciliation_status = "RECONCILED"
        else:
            fee_reconciliation_status = "NOT_PROVIDED"

        return {
            "status": "RECONCILED" if not discrepancies else "UNRECONCILED",
            "order_count": len(orders),
            "fill_count": sum(len(fills) for fills in fills_by_order.values()),
            "reconciled_order_count": reconciled_orders,
            "unreconciled_order_count": len(orders) - reconciled_orders,
            "orphan_fill_order_count": len(orphan_fill_orders),
            "duplicate_order_count": duplicate_orders,
            "duplicate_fill_count": duplicate_fills,
            "fee_reconciliation_status": fee_reconciliation_status,
            "discrepancies": discrepancies,
        }

    @staticmethod
    def _event_type(record: BrokerLifecycleRecord) -> str:
        if record.record_type == "fill":
            return "FillRecorded"
        return "VenueReject" if record.status == "REJECTED" else "VenueAck"

    @staticmethod
    def _snapshot_provenance(snapshot_manifest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Reduce a validated API manifest to safe, bounded ledger provenance.

        The full manifest is returned to the caller, but only immutable summary
        fields enter the evidence event.  This prevents page data or accidental
        credential material from becoming part of the ledger payload.
        """

        if snapshot_manifest is None:
            return None
        if not isinstance(snapshot_manifest, dict):
            raise BrokerImportValidationError("snapshot_manifest must be an object")
        scope = str(snapshot_manifest.get("permission_scope") or "").strip().upper()
        if scope != "READ_ONLY":
            raise BrokerImportValidationError("snapshot_manifest permission_scope must be READ_ONLY")
        digest = str(snapshot_manifest.get("snapshot_sha256") or "").strip()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise BrokerImportValidationError("snapshot_manifest snapshot_sha256 must be lowercase SHA-256")
        version = str(snapshot_manifest.get("manifest_version") or "").strip()
        if version not in {"1", "2"}:
            raise BrokerImportValidationError("unsupported snapshot_manifest version")
        complete = snapshot_manifest.get("complete")
        if not isinstance(complete, bool):
            raise BrokerImportValidationError("snapshot_manifest complete must be boolean")
        summary: Dict[str, Any] = {
            "source": "broker_api_snapshot",
            "snapshot_manifest_version": version,
            "snapshot_manifest_sha256": digest,
            "snapshot_permission_scope": scope,
            "snapshot_complete": complete,
        }
        if version == "2":
            source_exchange_id = str(snapshot_manifest.get("source_exchange_id") or "").strip().lower()
            market_type = str(snapshot_manifest.get("market_type") or "").strip().lower()
            if source_exchange_id not in SUPPORTED_SOURCE_EXCHANGE_IDS:
                raise BrokerImportValidationError("snapshot_manifest source_exchange_id is unsupported")
            if market_type not in SUPPORTED_MARKET_TYPES:
                raise BrokerImportValidationError("snapshot_manifest market_type is unsupported")
            expected_market_type = SUPPORTED_SOURCE_EXCHANGES[source_exchange_id]["market_type"]
            if market_type != expected_market_type:
                raise BrokerImportValidationError("snapshot_manifest source exchange and market type disagree")
            summary["source_exchange_id"] = source_exchange_id
            summary["market_type"] = market_type
        for key in (
            "orders_page_count",
            "fills_page_count",
            "order_count",
            "fill_count",
            "request_count",
        ):
            value = snapshot_manifest.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise BrokerImportValidationError(f"snapshot_manifest {key} must be non-negative integer")
            summary[f"snapshot_{key}"] = value
        warnings = snapshot_manifest.get("warnings", [])
        if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
            raise BrokerImportValidationError("snapshot_manifest warnings must be a string array")
        # Warnings are bounded codes, not upstream exception text.
        summary["snapshot_warning_count"] = len(warnings)
        return summary

    def import_records(
        self,
        venue: str,
        *,
        orders: Sequence[Dict[str, Any]] = (),
        fills: Sequence[Dict[str, Any]] = (),
        account_id: str = "local-broker-import",
        source_name: str = "broker-export",
        source_bytes: Optional[bytes] = None,
        snapshot_manifest: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        venue = self._validate_venue(venue)
        records, rejected = self.normalize_records(venue, orders=orders, fills=fills)
        source_document = source_bytes if source_bytes is not None else canonical_json({"orders": orders, "fills": fills}).encode("utf-8")
        source_file_sha256 = hashlib.sha256(source_document).hexdigest()
        snapshot_provenance = self._snapshot_provenance(snapshot_manifest)
        if snapshot_provenance:
            source_exchange_id = snapshot_provenance.get("source_exchange_id")
            if source_exchange_id:
                expected_venue = SUPPORTED_SOURCE_EXCHANGES[source_exchange_id]["venue"]
                if venue != expected_venue:
                    raise BrokerImportValidationError("snapshot_manifest source exchange and venue disagree")
        report = self.reconcile(records)
        if rejected:
            report["status"] = "UNRECONCILED"
            report["discrepancies"].append({
                "type": "REJECTED_ROWS",
                "count": len(rejected),
            })
        if snapshot_provenance and not snapshot_provenance["snapshot_complete"]:
            report["status"] = "UNRECONCILED"
            report["discrepancies"].append({
                "type": "SNAPSHOT_INCOMPLETE",
                "warning_count": snapshot_provenance["snapshot_warning_count"],
            })
        coverage = self._coverage_summary(
            report,
            normalized_record_count=len(records),
            rejected_row_count=len(rejected),
        )
        review = self._review_summary(
            report,
            coverage=coverage,
            normalized_record_count=len(records),
            rejected_row_count=len(rejected),
        )

        commands: List[Dict[str, Any]] = []
        for record in records:
            payload = record.payload()
            record_hash = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            # The source manifest is part of the observation identity.  A
            # later export may contain the same external ID with a corrected
            # state; it must become a new immutable observation rather than a
            # ledger conflict.  Re-importing the same bytes remains idempotent.
            source_identity = snapshot_provenance.get("source_exchange_id", venue) if snapshot_provenance else venue
            identity = f"broker:{source_identity}:{account_id}:{source_file_sha256}:{record.record_type}:{record.external_identity}:{record_hash}"
            commands.append({
                "event_type": self._event_type(record),
                "account_id": account_id,
                "venue": venue,
                "idempotency_key": identity,
                "normalized_payload": {"broker_lifecycle": payload},
                "occurred_at": record.occurred_at,
                "schema_version": "1",
                "adapter_version": (
                    f"{venue.lower()}-read-only-api-v2"
                    if snapshot_provenance
                    else f"{venue.lower()}-export-v2"
                ),
                "correlation_id": record.external_order_id,
                "provenance": {
                    "source": "broker_export",
                    "source_file_sha256": source_file_sha256,
                    "source_row_number": record.source_row_number,
                    "source_row_sha256": record.source_row_sha256,
                    "record_type": record.record_type,
                    "reconciliation_review": review,
                },
            })
            if snapshot_provenance:
                commands[-1]["provenance"].update(snapshot_provenance)
        events = self.ledger_repo.append_events(commands) if commands else []
        report.update({
            "venue": venue,
            "account_id": account_id,
            "source_name": source_name,
            "source_file_sha256": source_file_sha256,
            "normalized_record_count": len(records),
            "rejected_row_count": len(rejected),
            "rejected_rows": rejected,
            "ledger_event_count": len(events),
            "ledger_created_count": sum(1 for event in events if event.get("created")),
            "ledger_duplicate_count": sum(1 for event in events if not event.get("created")),
            "event_ids": [event["event_id"] for event in events],
            "coverage": coverage,
            "review": review,
        })
        if snapshot_provenance:
            report.update({
                "snapshot_manifest_sha256": snapshot_provenance["snapshot_manifest_sha256"],
                "snapshot_complete": snapshot_provenance["snapshot_complete"],
                "snapshot_request_count": snapshot_provenance["snapshot_request_count"],
                "snapshot_source_exchange_id": snapshot_provenance.get("source_exchange_id"),
                "snapshot_market_type": snapshot_provenance.get("market_type"),
            })
        return report

    def import_json_document(
        self,
        venue: str,
        source_bytes: bytes,
        *,
        account_id: str = "local-broker-import",
        source_name: str = "broker-export.json",
    ) -> Dict[str, Any]:
        """Import the bounded fixture/export envelope without opening a connector.

        The first integration contract deliberately accepts an explicit
        ``{"orders": [...], "fills": [...]}`` document.  Venue-specific API
        pagination and credential handling remain outside this package.
        """
        try:
            document = json.loads(source_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BrokerImportValidationError("broker export must be UTF-8 JSON") from exc
        if not isinstance(document, dict):
            raise BrokerImportValidationError("broker export root must be an object")
        orders = document.get("orders", [])
        fills = document.get("fills", [])
        if not isinstance(orders, list) or not isinstance(fills, list):
            raise BrokerImportValidationError("broker export orders/fills must be arrays")
        return self.import_records(
            venue,
            orders=orders,
            fills=fills,
            account_id=account_id,
            source_name=source_name,
            source_bytes=source_bytes,
        )


broker_import_service = BrokerImportService()
