"""Bounded account-event normalization and coverage-gated reconciliation.

P1-WP19 keeps account cash events separate from order/fill lifecycle facts.  It
does not infer a complete account statement from an incomplete export, and it
does not add new SQLite event types implicitly.  The current ledger can persist
fee and correction events; funding/transfer and venue-specific liquidation/ADL
observations remain explicit in the normalized report until a separately
approved ledger-schema contract exists.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json
from app.services.broker_import_service import (
    DECIMAL_ENCODING,
    SUPPORTED_SOURCE_EXCHANGES,
    SUPPORTED_SOURCE_EXCHANGE_IDS,
    SUPPORTED_VENUES,
    _decimal_number,
    _decimal_text,
    _first,
    _normalize_fee_currency,
    _normalize_timestamp,
    _required_text,
    _row_hash,
)


ACCOUNT_EVENT_KINDS = (
    "FUNDING",
    "TRADE_FEE",
    "TRANSFER",
    "REBATE",
    "LIQUIDATION",
    "ADL",
    "MANUAL_CORRECTION",
)

_KIND_ALIASES = {
    "FUNDING": "FUNDING",
    "FUNDING_PAYMENT": "FUNDING",
    "FUNDING_FEE": "FUNDING",
    "TRADE_FEE": "TRADE_FEE",
    "FEE": "TRADE_FEE",
    "COMMISSION": "TRADE_FEE",
    "FEE_ADJUSTMENT": "TRADE_FEE",
    "FEE_ADJUSTED": "TRADE_FEE",
    "TRANSFER": "TRANSFER",
    "CASH_TRANSFER": "TRANSFER",
    "DEPOSIT": "TRANSFER",
    "WITHDRAWAL": "TRANSFER",
    "REBATE": "REBATE",
    "MAKER_REBATE": "REBATE",
    "LIQUIDATION": "LIQUIDATION",
    "LIQUIDATED": "LIQUIDATION",
    "ADL": "ADL",
    "AUTO_DELEVERAGING": "ADL",
    "MANUAL_CORRECTION": "MANUAL_CORRECTION",
    "CORRECTION": "MANUAL_CORRECTION",
    "ADJUSTMENT": "MANUAL_CORRECTION",
    "TRADE_CORRECTION": "MANUAL_CORRECTION",
}
_UNSUPPORTED_KINDS = frozenset({"LIQUIDATION", "ADL"})
_PERSISTABLE_LEDGER_EVENT_TYPES = {
    "TRADE_FEE": "FeeAdjusted",
    "REBATE": "FeeAdjusted",
    "MANUAL_CORRECTION": "TradeCorrected",
}
_CASH_MOVEMENT_KINDS = frozenset({"FUNDING", "TRADE_FEE", "TRANSFER", "REBATE"})
_UNKNOWN_CURRENCY = "UNKNOWN_CURRENCY"


class AccountEventValidationError(ValueError):
    """Raised when an account event cannot be represented fail-closed."""


def _normalize_kind(value: Any) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    normalized = _KIND_ALIASES.get(text)
    if normalized is None:
        raise AccountEventValidationError(f"unsupported account event type: {value}")
    return normalized


def _bounded_optional_text(value: Any, field: str, *, max_length: int = 128) -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if len(text) > max_length:
        raise AccountEventValidationError(f"{field} is too long")
    return text


def _validate_source_identity(
    venue: str,
    source_exchange_id: Any,
    market_type: Any,
) -> Tuple[Optional[str], Optional[str]]:
    normalized_venue = str(venue).strip().upper()
    if normalized_venue not in SUPPORTED_VENUES:
        raise AccountEventValidationError(f"unsupported account venue: {normalized_venue}")

    source_id = _bounded_optional_text(source_exchange_id, "source_exchange_id")
    source_id = source_id.lower() if source_id else None
    normalized_market = _bounded_optional_text(market_type, "market_type")
    normalized_market = normalized_market.lower() if normalized_market else None
    if source_id is None:
        return None, normalized_market
    if source_id not in SUPPORTED_SOURCE_EXCHANGE_IDS:
        raise AccountEventValidationError("source_exchange_id is unsupported")
    expected = SUPPORTED_SOURCE_EXCHANGES[source_id]
    if expected["venue"] != normalized_venue:
        raise AccountEventValidationError("source exchange and venue disagree")
    if normalized_market is not None and normalized_market != expected["market_type"]:
        raise AccountEventValidationError("source exchange and market type disagree")
    return source_id, expected["market_type"]


def _normalize_decimal_map(value: Optional[Mapping[str, Any]], field: str) -> Optional[Dict[str, str]]:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise AccountEventValidationError(f"{field} must be an object")
    normalized: Dict[str, str] = {}
    for currency, amount in value.items():
        normalized_currency = _normalize_fee_currency(currency)
        if normalized_currency is None:
            raise AccountEventValidationError(f"{field} currency is required")
        try:
            decimal_amount = _decimal_number(amount, f"{field}.{normalized_currency}", allow_negative=True, required=True)
        except ValueError as exc:
            raise AccountEventValidationError(str(exc)) from exc
        normalized[normalized_currency] = _decimal_text(decimal_amount) or "0"
    return normalized


def _decimal_add(target: Dict[str, Decimal], currency: str, value: Decimal) -> None:
    with localcontext() as context:
        context.prec = 128
        target[currency] = target.get(currency, Decimal("0")) + value


def _decimal_dict(values: Mapping[str, Decimal]) -> Dict[str, str]:
    return {key: _decimal_text(values[key]) or "0" for key in sorted(values)}


@dataclass(frozen=True)
class AccountEventRecord:
    """Immutable, secret-free normalized account observation."""

    event_kind: str
    account_id: str
    venue: str
    external_event_id: str
    amount: Optional[Decimal]
    currency: Optional[str]
    occurred_at: str
    effective_at: Optional[str]
    corrects_event_id: Optional[str]
    source_exchange_id: Optional[str]
    market_type: Optional[str]
    account_event_status: str
    storage_status: str
    source_row_number: int
    source_row_sha256: str

    @property
    def ledger_event_type(self) -> Optional[str]:
        return _PERSISTABLE_LEDGER_EVENT_TYPES.get(self.event_kind)

    @property
    def identity_key(self) -> Tuple[str, str, str, str]:
        return (
            self.account_id,
            self.source_exchange_id or self.venue,
            self.market_type or "UNKNOWN_MARKET",
            self.external_event_id,
        )

    def payload(self) -> Dict[str, Any]:
        return {
            "account_event_kind": self.event_kind,
            "account_event_status": self.account_event_status,
            "storage_status": self.storage_status,
            "account_id": self.account_id,
            "venue": self.venue,
            "source_exchange_id": self.source_exchange_id,
            "market_type": self.market_type,
            "external_event_id": self.external_event_id,
            "amount": _decimal_text(self.amount),
            "currency": self.currency,
            "numeric_encoding": DECIMAL_ENCODING,
            "numeric_units": {
                "amount": f"CURRENCY:{self.currency}" if self.currency else "UNKNOWN_CURRENCY",
            },
            "occurred_at": self.occurred_at,
            "effective_at": self.effective_at,
            "corrects_event_id": self.corrects_event_id,
            "source_row_number": self.source_row_number,
            "source_row_sha256": self.source_row_sha256,
        }


class AccountReconciliationService:
    """Normalize bounded account rows and produce explicit coverage reports."""

    def __init__(self, ledger_repo: Optional[EvidenceLedgerRepository] = None):
        self.ledger_repo = ledger_repo or EvidenceLedgerRepository()

    @classmethod
    def normalize_event(
        cls,
        venue: str,
        row: Mapping[str, Any],
        *,
        account_id: str,
        row_number: int = 1,
        source_exchange_id: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> AccountEventRecord:
        if not isinstance(row, Mapping):
            raise AccountEventValidationError("account event row must be an object")
        normalized_venue = str(venue or "").strip().upper()
        if normalized_venue not in SUPPORTED_VENUES:
            raise AccountEventValidationError(f"unsupported account venue: {normalized_venue}")
        normalized_account = _required_text(account_id, "account_id")
        if len(normalized_account) > 128:
            raise AccountEventValidationError("account_id is too long")
        normalized_source, normalized_market = _validate_source_identity(
            normalized_venue,
            source_exchange_id or _first(dict(row), "source_exchange_id", "exchange_id"),
            market_type or _first(dict(row), "market_type"),
        )
        event_kind = _normalize_kind(_first(dict(row), "event_type", "account_event_type", "kind", "type"))
        external_event_id = _required_text(
            _first(dict(row), "external_event_id", "event_id", "transaction_id", "bill_id", "tranId", "id"),
            "external_event_id",
        )
        amount_value = _first(
            dict(row),
            "amount",
            "amt",
            "delta",
            "change",
            "cash_flow",
            "funding_fee",
            "fee",
            "rebate",
        )
        try:
            amount = _decimal_number(
                amount_value,
                "amount",
                allow_negative=True,
                required=event_kind not in _UNSUPPORTED_KINDS,
            )
        except ValueError as exc:
            raise AccountEventValidationError(str(exc)) from exc
        try:
            occurred_at = _normalize_timestamp(
                _first(dict(row), "occurred_at", "timestamp", "time", "ts", "uTime", "effective_at")
            )
            effective_at = (
                _normalize_timestamp(_first(dict(row), "effective_at", "effective_time"))
                if _first(dict(row), "effective_at", "effective_time") is not None
                else None
            )
            currency = _normalize_fee_currency(_first(dict(row), "currency", "asset", "ccy", "feeCcy"))
        except ValueError as exc:
            raise AccountEventValidationError(str(exc)) from exc

        corrects_event_id = _bounded_optional_text(
            _first(dict(row), "corrects_event_id", "correction_of", "replaces_event_id"),
            "corrects_event_id",
        )
        if event_kind == "MANUAL_CORRECTION":
            if not corrects_event_id:
                raise AccountEventValidationError("corrects_event_id is required for manual correction")
            if effective_at is None:
                raise AccountEventValidationError("effective_at is required for manual correction")

        status = "UNSUPPORTED" if event_kind in _UNSUPPORTED_KINDS else "SUPPORTED"
        storage_status = "UNSUPPORTED" if status == "UNSUPPORTED" else (
            "PERSISTABLE" if event_kind in _PERSISTABLE_LEDGER_EVENT_TYPES else "SCHEMA_EVENT_TYPE_PENDING"
        )
        return AccountEventRecord(
            event_kind=event_kind,
            account_id=normalized_account,
            venue=normalized_venue,
            external_event_id=external_event_id,
            amount=amount,
            currency=currency,
            occurred_at=occurred_at,
            effective_at=effective_at,
            corrects_event_id=corrects_event_id,
            source_exchange_id=normalized_source,
            market_type=normalized_market,
            account_event_status=status,
            storage_status=storage_status,
            source_row_number=row_number,
            source_row_sha256=_row_hash(dict(row)),
        )

    @classmethod
    def normalize_events(
        cls,
        venue: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        account_id: str,
        source_exchange_id: Optional[str] = None,
        market_type: Optional[str] = None,
    ) -> Tuple[List[AccountEventRecord], List[Dict[str, Any]]]:
        records: List[AccountEventRecord] = []
        rejected: List[Dict[str, Any]] = []
        for row_number, row in enumerate(rows, start=1):
            try:
                records.append(
                    cls.normalize_event(
                        venue,
                        row,
                        account_id=account_id,
                        row_number=row_number,
                        source_exchange_id=source_exchange_id,
                        market_type=market_type,
                    )
                )
            except (AccountEventValidationError, TypeError, ValueError) as exc:
                rejected.append({"source_row_number": row_number, "reason": str(exc)})
        return records, rejected

    @classmethod
    def reconcile(
        cls,
        records: Iterable[AccountEventRecord],
        *,
        opening_balance: Optional[Mapping[str, Any]] = None,
        opening_positions: Optional[Sequence[Mapping[str, Any]]] = None,
        coverage: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        records = list(records)
        coverage_input = dict(coverage or {})
        normalized_opening_balance = _normalize_decimal_map(opening_balance, "opening_balance")
        discrepancies: List[Dict[str, Any]] = []
        by_identity: Dict[Tuple[str, str, str, str], List[AccountEventRecord]] = defaultdict(list)
        cash_by_kind: Dict[str, Dict[str, Decimal]] = defaultdict(dict)
        event_counts = Counter(record.event_kind for record in records)

        for record in records:
            by_identity[record.identity_key].append(record)
            if record.account_event_status == "UNSUPPORTED":
                discrepancies.append({
                    "type": "UNSUPPORTED_ACCOUNT_EVENT",
                    "event_kind": record.event_kind,
                    "external_event_id": record.external_event_id,
                })
            elif record.storage_status == "SCHEMA_EVENT_TYPE_PENDING":
                discrepancies.append({
                    "type": "EVENT_STORAGE_SCHEMA_PENDING",
                    "event_kind": record.event_kind,
                    "external_event_id": record.external_event_id,
                })
            if record.event_kind in _CASH_MOVEMENT_KINDS:
                currency = record.currency or _UNKNOWN_CURRENCY
                if record.amount is not None:
                    _decimal_add(cash_by_kind[record.event_kind], currency, record.amount)
                if record.currency is None:
                    discrepancies.append({
                        "type": "ACCOUNT_CURRENCY_UNKNOWN",
                        "event_kind": record.event_kind,
                        "external_event_id": record.external_event_id,
                    })

        for identity, same_identity in by_identity.items():
            if len(same_identity) <= 1:
                continue
            payloads = {canonical_json(record.payload()) for record in same_identity}
            discrepancy_type = "DUPLICATE_ACCOUNT_EVENT" if len(payloads) == 1 else "ACCOUNT_EVENT_ID_COLLISION"
            discrepancies.append({
                "type": discrepancy_type,
                "account_id": identity[0],
                "source_exchange_id": identity[1],
                "market_type": identity[2],
                "external_event_id": identity[3],
                "count": len(same_identity),
            })

        reasons: List[str] = []
        if opening_balance is None:
            reasons.append("OPENING_BALANCE_MISSING")
        if opening_positions is None:
            reasons.append("OPENING_POSITION_MISSING")
        if coverage_input.get("events_complete") is not True:
            reasons.append("EVENT_COVERAGE_UNVERIFIED")
        if coverage_input.get("realized_pnl_complete") is not True:
            reasons.append("REALIZED_PNL_COVERAGE_MISSING")
        if coverage_input.get("unrealized_pnl_complete") is not True:
            reasons.append("UNREALIZED_PNL_COVERAGE_MISSING")
        if any(record.account_event_status == "UNSUPPORTED" for record in records):
            reasons.append("UNSUPPORTED_ACCOUNT_EVENT")
        if any(record.storage_status == "SCHEMA_EVENT_TYPE_PENDING" for record in records):
            reasons.append("EVENT_STORAGE_SCHEMA_PENDING")
        if any(record.currency is None for record in records if record.event_kind in _CASH_MOVEMENT_KINDS):
            reasons.append("ACCOUNT_CURRENCY_UNKNOWN")
        reasons = list(dict.fromkeys(reasons))

        if opening_balance is None and opening_positions is None:
            status = "NOT_AVAILABLE"
        elif reasons:
            status = "PARTIAL"
        elif coverage_input.get("account_coverage_complete") is True:
            status = "COMPLETE"
        else:
            status = "PARTIAL"

        return {
            "status": status,
            "coverage": {
                "status": status,
                "opening_balance_available": opening_balance is not None,
                "opening_position_available": opening_positions is not None,
                "events_complete": coverage_input.get("events_complete") is True,
                "realized_pnl_complete": coverage_input.get("realized_pnl_complete") is True,
                "unrealized_pnl_complete": coverage_input.get("unrealized_pnl_complete") is True,
                "reasons": reasons,
            },
            "opening_balance": normalized_opening_balance,
            "opening_position_count": len(opening_positions) if opening_positions is not None else None,
            "event_count": len(records),
            "event_counts": dict(sorted(event_counts.items())),
            "cash_movement_by_kind": {
                kind: _decimal_dict(cash_by_kind[kind])
                for kind in sorted(cash_by_kind)
            },
            "realized_pnl": None,
            "unrealized_pnl": None,
            "discrepancies": discrepancies,
            "persistable_event_count": sum(1 for record in records if record.storage_status == "PERSISTABLE"),
            "unsupported_event_count": sum(1 for record in records if record.account_event_status == "UNSUPPORTED"),
        }

    def persist_records(
        self,
        records: Sequence[AccountEventRecord],
        *,
        source_bytes: Optional[bytes] = None,
        source_name: str = "account-events",
    ) -> Dict[str, Any]:
        records = list(records)
        source_document = source_bytes if source_bytes is not None else canonical_json(
            [record.payload() for record in records]
        ).encode("utf-8")
        source_file_sha256 = hashlib.sha256(source_document).hexdigest()
        commands: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for record in records:
            if record.storage_status != "PERSISTABLE":
                skipped.append({
                    "event_kind": record.event_kind,
                    "external_event_id": record.external_event_id,
                    "reason": record.storage_status,
                })
                continue
            if record.event_kind == "MANUAL_CORRECTION":
                target = self.ledger_repo.get_event(record.corrects_event_id or "")
                if target is None:
                    raise AccountEventValidationError(
                        f"corrects_event_id target not found: {record.corrects_event_id}"
                    )
                if target["account_id"] != record.account_id or target["venue"] != record.venue:
                    raise AccountEventValidationError("correction target account or venue disagrees")
            payload = {"account_event": record.payload()}
            payload_digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
            identity = (
                f"account:{record.source_exchange_id or record.venue.lower()}:{record.account_id}:"
                f"{source_file_sha256}:{record.event_kind}:{record.external_event_id}:{payload_digest}"
            )
            provenance: Dict[str, Any] = {
                "source": "account_reconciliation",
                "source_file_sha256": source_file_sha256,
                "source_row_number": record.source_row_number,
                "source_row_sha256": record.source_row_sha256,
                "account_event_kind": record.event_kind,
            }
            if record.corrects_event_id:
                provenance["corrects_event_id"] = record.corrects_event_id
            commands.append({
                "event_type": record.ledger_event_type,
                "account_id": record.account_id,
                "venue": record.venue,
                "idempotency_key": identity,
                "normalized_payload": payload,
                "occurred_at": record.occurred_at,
                "schema_version": "1",
                "adapter_version": f"{record.venue.lower()}-account-reconciliation-v1",
                "correlation_id": record.external_event_id,
                "causation_id": record.corrects_event_id,
                "provenance": provenance,
            })

        events = self.ledger_repo.append_events(commands) if commands else []
        return {
            "status": "PARTIAL" if skipped else "PERSISTED",
            "source_name": source_name,
            "source_file_sha256": source_file_sha256,
            "requested_count": len(records),
            "created_count": sum(1 for event in events if event.get("created")),
            "duplicate_count": sum(1 for event in events if not event.get("created")),
            "skipped_count": len(skipped),
            "skipped": skipped,
            "event_ids": [event["event_id"] for event in events],
        }


account_reconciliation_service = AccountReconciliationService()
