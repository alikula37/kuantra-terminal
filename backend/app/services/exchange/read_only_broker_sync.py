"""Read-only Binance/OKX lifecycle snapshots through an explicit CCXT boundary.

The adapter in this module is deliberately narrower than the execution engine:
it can call only ``fetch_orders`` and ``fetch_my_trades`` and it accepts only
credentials marked ``READ_ONLY``.  It maps CCXT's normalized response into the
P1-WP11 broker lifecycle contract, records pagination/retry evidence in a
stable snapshot manifest, and never stores the raw CCXT response or secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
import random
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import ccxt

from app.db.repositories.evidence_ledger_repo import canonical_json
from app.services.broker_import_service import BrokerImportService, broker_import_service
from app.services.exchange.credentials_manager import (
    ExchangeCredentialsManager,
    exchange_credentials_manager,
)


READ_ONLY_SCOPE = "READ_ONLY"
SUPPORTED_API_EXCHANGES = {
    "binance_spot": {"venue": "BINANCE", "ccxt_id": "binance"},
    "binance_futures": {"venue": "BINANCE", "ccxt_id": "binanceusdm"},
    "okx": {"venue": "OKX", "ccxt_id": "okx"},
}


class ReadOnlyBrokerSyncError(ValueError):
    """Base error for validation, credential-scope, or transport failures."""


class ReadOnlyCredentialScopeError(ReadOnlyBrokerSyncError):
    """Raised when a credential is absent, inactive, or not read-only."""


class ReadOnlyBrokerTransportError(ReadOnlyBrokerSyncError):
    """Raised when a bounded upstream request cannot be completed safely."""


class SnapshotManifestValidationError(ReadOnlyBrokerSyncError):
    """Raised when a snapshot manifest is malformed or tampered with."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None and str(row[key]).strip() != "":
            return row[key]
    return None


def _timestamp_ms(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            number = float(value)
        else:
            text = str(value).strip()
            if text.replace(".", "", 1).isdigit():
                number = float(text)
            else:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                number = parsed.timestamp() * 1000.0
        if not math.isfinite(number):
            return None
        if abs(number) < 1e11:
            number *= 1000.0
        return int(number)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _fee_fields(row: Mapping[str, Any]) -> Tuple[Any, Any]:
    fee = row.get("fee")
    if isinstance(fee, Mapping):
        return fee.get("cost", fee.get("amount")), fee.get("currency")
    return fee, _first(row, "fee_currency", "commissionAsset", "feeCcy")


def _ccxt_order_status(row: Mapping[str, Any]) -> Any:
    """Resolve CCXT's ``closed`` state without inventing a full fill."""

    status = _first(row, "status", "state")
    if str(status or "").strip().lower() != "closed":
        return status
    amount = _first(row, "amount", "origQty", "order_qty", "quantity", "qty", "sz")
    filled = _first(row, "filled", "executedQty", "filled_qty", "filledQty", "accFillSz")
    try:
        if amount is not None and filled is not None and float(filled) + 1e-12 < float(amount):
            return "PARTIALLY_FILLED"
    except (TypeError, ValueError, OverflowError):
        # The canonical importer will reject malformed quantities; status must
        # not turn an invalid row into a fabricated fill.
        pass
    return "FILLED"


def _map_order(row: Any) -> Dict[str, Any]:
    """Map only non-sensitive CCXT normalized fields into the import contract."""

    if not isinstance(row, Mapping):
        return {}
    fee, fee_currency = _fee_fields(row)
    return {
        "orderId": _first(row, "id", "orderId", "order_id"),
        "symbol": _first(row, "symbol", "instId"),
        "side": _first(row, "side", "direction"),
        "status": _ccxt_order_status(row),
        "origQty": _first(row, "amount", "origQty", "order_qty", "quantity", "qty", "sz"),
        "executedQty": _first(row, "filled", "executedQty", "filled_qty", "filledQty", "accFillSz"),
        "avgPrice": _first(row, "average", "avgPrice", "avg_price", "avgPx"),
        "price": _first(row, "price", "px", "order_price"),
        "fee": fee,
        "fee_currency": fee_currency,
        "updateTime": _first(row, "timestamp", "lastTradeTimestamp", "updateTime", "uTime", "cTime"),
    }


def _map_fill(row: Any) -> Dict[str, Any]:
    """Map only non-sensitive CCXT normalized trade fields into the import contract."""

    if not isinstance(row, Mapping):
        return {}
    fee, fee_currency = _fee_fields(row)
    return {
        "id": _first(row, "id", "tradeId", "fillId", "fill_id"),
        "orderId": _first(row, "order", "orderId", "order_id", "ordId"),
        "symbol": _first(row, "symbol", "instId"),
        "side": _first(row, "side", "direction"),
        "qty": _first(row, "amount", "qty", "quantity", "size", "fill_qty", "sz"),
        "price": _first(row, "price", "fill_price", "fillPx"),
        "fee": fee,
        "fee_currency": fee_currency,
        "time": _first(row, "timestamp", "datetime", "time", "fillTime", "ts", "uTime"),
    }


def _page_hash(kind: str, page_index: int, rows: Sequence[Dict[str, Any]]) -> str:
    payload = {"kind": kind, "page_index": page_index, "rows": list(rows)}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReadOnlySnapshotManifest:
    """Stable, secret-free description of one broker API snapshot."""

    manifest_version: str
    exchange_id: str
    account_id: str
    permission_scope: str
    requested_since_ms: Optional[int]
    requested_until_ms: Optional[int]
    orders_page_count: int
    fills_page_count: int
    order_count: int
    fill_count: int
    request_count: int
    page_hashes: Tuple[str, ...]
    complete: bool
    warnings: Tuple[str, ...]
    captured_at_utc: str
    snapshot_sha256: str

    def stable_payload(self) -> Dict[str, Any]:
        """Return fields that identify source content, excluding run metadata."""

        return {
            "manifest_version": self.manifest_version,
            "exchange_id": self.exchange_id,
            "account_id": self.account_id,
            "permission_scope": self.permission_scope,
            "requested_since_ms": self.requested_since_ms,
            "requested_until_ms": self.requested_until_ms,
            "orders_page_count": self.orders_page_count,
            "fills_page_count": self.fills_page_count,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "page_hashes": list(self.page_hashes),
            "complete": self.complete,
        }

    def validate(self) -> None:
        if self.manifest_version != "1":
            raise SnapshotManifestValidationError("unsupported snapshot manifest version")
        if self.exchange_id not in {"BINANCE", "OKX"}:
            raise SnapshotManifestValidationError("snapshot manifest has an unsupported venue")
        if self.permission_scope != READ_ONLY_SCOPE:
            raise SnapshotManifestValidationError("snapshot manifest is not READ_ONLY")
        if not self.account_id or len(self.account_id) > 128:
            raise SnapshotManifestValidationError("snapshot account_id is invalid")
        if self.requested_since_ms is not None and self.requested_since_ms < 0:
            raise SnapshotManifestValidationError("requested_since_ms cannot be negative")
        if self.requested_until_ms is not None and self.requested_until_ms < 0:
            raise SnapshotManifestValidationError("requested_until_ms cannot be negative")
        if (
            self.requested_since_ms is not None
            and self.requested_until_ms is not None
            and self.requested_until_ms < self.requested_since_ms
        ):
            raise SnapshotManifestValidationError("requested_until_ms precedes requested_since_ms")
        for field_name in (
            "orders_page_count",
            "fills_page_count",
            "order_count",
            "fill_count",
            "request_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise SnapshotManifestValidationError(f"{field_name} must be a non-negative integer")
        if len(self.page_hashes) != self.orders_page_count + self.fills_page_count:
            raise SnapshotManifestValidationError("page hash count does not match page counts")
        for digest in self.page_hashes:
            if not isinstance(digest, str) or len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise SnapshotManifestValidationError("page hashes must be lowercase SHA-256 digests")
        try:
            captured = datetime.fromisoformat(self.captured_at_utc.replace("Z", "+00:00"))
            if captured.tzinfo is None:
                raise ValueError()
        except (TypeError, ValueError) as exc:
            raise SnapshotManifestValidationError("captured_at_utc must be timezone-aware ISO-8601") from exc
        expected = hashlib.sha256(canonical_json(self.stable_payload()).encode("utf-8")).hexdigest()
        if self.snapshot_sha256 != expected:
            raise SnapshotManifestValidationError("snapshot_sha256 does not match manifest content")

    @classmethod
    def build(
        cls,
        *,
        exchange_id: str,
        account_id: str,
        requested_since_ms: Optional[int],
        requested_until_ms: Optional[int],
        orders_page_count: int,
        fills_page_count: int,
        order_count: int,
        fill_count: int,
        request_count: int,
        page_hashes: Sequence[str],
        complete: bool,
        warnings: Sequence[str] = (),
    ) -> "ReadOnlySnapshotManifest":
        draft = cls(
            manifest_version="1",
            exchange_id=exchange_id,
            account_id=account_id,
            permission_scope=READ_ONLY_SCOPE,
            requested_since_ms=requested_since_ms,
            requested_until_ms=requested_until_ms,
            orders_page_count=orders_page_count,
            fills_page_count=fills_page_count,
            order_count=order_count,
            fill_count=fill_count,
            request_count=request_count,
            page_hashes=tuple(page_hashes),
            complete=bool(complete),
            warnings=tuple(str(warning) for warning in warnings),
            captured_at_utc=_utc_now(),
            snapshot_sha256="0" * 64,
        )
        digest = hashlib.sha256(canonical_json(draft.stable_payload()).encode("utf-8")).hexdigest()
        manifest = cls(**{**draft.__dict__, "snapshot_sha256": digest})
        manifest.validate()
        return manifest

    def as_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "exchange_id": self.exchange_id,
            "account_id": self.account_id,
            "permission_scope": self.permission_scope,
            "requested_since_ms": self.requested_since_ms,
            "requested_until_ms": self.requested_until_ms,
            "orders_page_count": self.orders_page_count,
            "fills_page_count": self.fills_page_count,
            "order_count": self.order_count,
            "fill_count": self.fill_count,
            "request_count": self.request_count,
            "page_hashes": list(self.page_hashes),
            "complete": self.complete,
            "warnings": list(self.warnings),
            "captured_at_utc": self.captured_at_utc,
            "snapshot_sha256": self.snapshot_sha256,
        }


class ReadOnlyExchangeClient:
    """Proxy that prevents accidental order-write calls on a CCXT client."""

    _WRITE_METHODS = {
        "create_order",
        "create_orders",
        "cancel_order",
        "cancel_all_orders",
        "cancel_orders",
        "edit_order",
        "create_stop_order",
        "create_trigger_order",
        "set_leverage",
        "set_margin_mode",
        "set_position_mode",
        "add_margin",
        "reduce_margin",
        "transfer",
        "withdraw",
        "close_position",
    }
    _WRITE_PREFIXES = ("create_", "cancel_", "edit_", "withdraw", "transfer", "set_")

    def __init__(self, client: Any):
        object.__setattr__(self, "_client", client)

    def __getattr__(self, name: str) -> Any:
        if name in self._WRITE_METHODS or name.startswith(self._WRITE_PREFIXES):
            raise ReadOnlyCredentialScopeError(f"CCXT write method '{name}' is blocked in READ_ONLY scope")
        return getattr(self._client, name)


@dataclass
class _PageCollection:
    rows: List[Dict[str, Any]]
    page_hashes: List[str]
    page_count: int
    request_count: int
    complete: bool
    warnings: List[str]


class ReadOnlyBrokerSyncService:
    """Fetches and imports bounded, authenticated broker lifecycle snapshots."""

    def __init__(
        self,
        credentials_manager: Optional[ExchangeCredentialsManager] = None,
        import_service: Optional[BrokerImportService] = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        jitter_fn: Callable[[], float] = random.random,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.25,
        max_backoff_seconds: float = 5.0,
    ):
        self.credentials_manager = credentials_manager or exchange_credentials_manager
        self.import_service = import_service or broker_import_service
        self.sleeper = sleeper
        self.jitter_fn = jitter_fn
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_base_seconds = max(0.0, float(backoff_base_seconds))
        self.max_backoff_seconds = max(0.0, float(max_backoff_seconds))
        retry_classes = []
        for name in (
            "NetworkError",
            "RequestTimeout",
            "DDoSProtection",
            "RateLimitExceeded",
            "ExchangeNotAvailable",
        ):
            candidate = getattr(ccxt, name, None)
            if isinstance(candidate, type) and candidate not in retry_classes:
                retry_classes.append(candidate)
        self._retryable_errors = tuple(retry_classes)

    @staticmethod
    def _validate_exchange(exchange_id: str) -> str:
        normalized = str(exchange_id or "").strip().lower()
        if normalized not in SUPPORTED_API_EXCHANGES:
            raise ReadOnlyBrokerSyncError(
                f"unsupported read-only API exchange '{exchange_id}'; "
                f"supported={sorted(SUPPORTED_API_EXCHANGES)}"
            )
        return normalized

    @staticmethod
    def _validate_account_id(account_id: str) -> str:
        normalized = str(account_id or "").strip()
        if not normalized or len(normalized) > 128:
            raise ReadOnlyBrokerSyncError("account_id must be 1-128 characters")
        return normalized

    @staticmethod
    def _validate_bounds(since_ms: Optional[int], until_ms: Optional[int]) -> None:
        for field_name, value in (("since_ms", since_ms), ("until_ms", until_ms)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ReadOnlyBrokerSyncError(f"{field_name} must be a non-negative integer")
        if since_ms is not None and until_ms is not None and until_ms < since_ms:
            raise ReadOnlyBrokerSyncError("until_ms must be greater than or equal to since_ms")

    def _build_client(self, exchange_id: str) -> ReadOnlyExchangeClient:
        credentials = self.credentials_manager.get_decrypted_credentials(exchange_id)
        if not credentials:
            raise ReadOnlyCredentialScopeError(f"no keychain credentials configured for '{exchange_id}'")
        if not credentials.get("is_active", True):
            raise ReadOnlyCredentialScopeError(f"credentials for '{exchange_id}' are inactive")
        scope = str(credentials.get("permission_scope") or READ_ONLY_SCOPE).strip().upper()
        if scope != READ_ONLY_SCOPE:
            raise ReadOnlyCredentialScopeError(
                f"credentials for '{exchange_id}' have scope '{scope}', READ_ONLY is required"
            )
        metadata = SUPPORTED_API_EXCHANGES[exchange_id]
        exchange_class = getattr(ccxt, metadata["ccxt_id"], None)
        if not exchange_class:
            raise ReadOnlyBrokerSyncError(f"CCXT driver '{metadata['ccxt_id']}' is unavailable")
        config: Dict[str, Any] = {
            "apiKey": str(credentials.get("api_key") or "").strip(),
            "secret": str(credentials.get("api_secret") or "").strip(),
            "enableRateLimit": True,
            "timeout": 15000,
        }
        if not config["apiKey"] or not config["secret"]:
            raise ReadOnlyCredentialScopeError(f"keychain credentials for '{exchange_id}' are incomplete")
        if credentials.get("passphrase"):
            config["password"] = str(credentials["passphrase"]).strip()
        try:
            client = exchange_class(config)
            if credentials.get("is_testnet"):
                client.set_sandbox_mode(True)
        except Exception as exc:  # noqa: BLE001
            raise ReadOnlyBrokerTransportError("read-only CCXT client could not be initialized") from exc
        return ReadOnlyExchangeClient(client)

    def _call_with_retry(self, call: Callable[[], Any], operation: str) -> Tuple[Any, int]:
        attempts = 0
        last_error: Optional[BaseException] = None
        while attempts < self.max_attempts:
            attempts += 1
            try:
                return call(), attempts
            except (ccxt.AuthenticationError, getattr(ccxt, "PermissionDenied", ccxt.AuthenticationError)) as exc:
                raise ReadOnlyCredentialScopeError(f"broker rejected read-only authentication for {operation}") from exc
            except self._retryable_errors as exc:
                last_error = exc
                if attempts >= self.max_attempts:
                    break
                delay = min(
                    self.max_backoff_seconds,
                    self.backoff_base_seconds * (2 ** (attempts - 1)),
                )
                # Jitter is deliberately bounded and can be injected as zero in
                # tests; the manifest records attempts, not secret-bearing errors.
                if delay > 0:
                    delay += min(delay * 0.1, max(0.0, float(self.jitter_fn())) * delay * 0.1)
                self.sleeper(delay)
            except Exception as exc:  # noqa: BLE001
                raise ReadOnlyBrokerTransportError(f"broker {operation} failed") from exc
        raise ReadOnlyBrokerTransportError(
            f"broker {operation} failed after {attempts} attempts ({type(last_error).__name__})"
        ) from last_error

    @staticmethod
    def _row_identity(kind: str, row: Mapping[str, Any]) -> str:
        identifier = row.get("orderId") if kind == "orders" else row.get("id")
        if identifier is not None and str(identifier).strip():
            return f"{kind}:{str(identifier).strip()}"
        return f"{kind}:row:{hashlib.sha256(canonical_json(dict(row)).encode('utf-8')).hexdigest()}"

    def _paginate(
        self,
        client: ReadOnlyExchangeClient,
        *,
        kind: str,
        method_name: str,
        mapper: Callable[[Any], Dict[str, Any]],
        symbol: Optional[str],
        since_ms: Optional[int],
        until_ms: Optional[int],
        max_pages: int,
        page_limit: int,
        params: Optional[Mapping[str, Any]],
    ) -> _PageCollection:
        method = getattr(client, method_name, None)
        if not callable(method):
            raise ReadOnlyBrokerSyncError(f"CCXT client does not support {method_name}")

        cursor = since_ms
        rows_by_identity: Dict[str, Dict[str, Any]] = {}
        page_hashes: List[str] = []
        warnings: List[str] = []
        request_count = 0
        complete = False
        previous_page_max_timestamp: Optional[int] = None
        seen_page_fingerprints: set[str] = set()

        for page_index in range(max_pages):
            request_params = dict(params or {})
            raw_page, attempts = self._call_with_retry(
                lambda: method(
                    symbol=symbol,
                    since=cursor,
                    limit=page_limit,
                    params=request_params,
                ),
                f"{method_name}[page={page_index}]",
            )
            request_count += attempts
            if not isinstance(raw_page, list):
                raise ReadOnlyBrokerTransportError(f"broker {method_name} returned a non-list page")

            mapped_page: List[Dict[str, Any]] = []
            timestamps: List[int] = []
            for raw_row in raw_page:
                mapped = mapper(raw_row)
                timestamp_value = _first(mapped, "updateTime", "time")
                row_timestamp = _timestamp_ms(timestamp_value)
                if row_timestamp is not None:
                    timestamps.append(row_timestamp)
                if until_ms is not None and row_timestamp is not None and row_timestamp > until_ms:
                    continue
                mapped_page.append(mapped)
                rows_by_identity[self._row_identity(kind, mapped)] = mapped

            page_hashes.append(_page_hash(kind, page_index, mapped_page))

            # ``since`` is an inclusive timestamp boundary in the normalized
            # CCXT contract.  A content fingerprint is kept separately from
            # the manifest page hash (which includes page_index) so an
            # exchange that ignores the cursor cannot silently spin forever.
            page_fingerprint = hashlib.sha256(
                canonical_json({"kind": kind, "rows": mapped_page}).encode("utf-8")
            ).hexdigest()
            repeated_page = page_fingerprint in seen_page_fingerprints
            seen_page_fingerprints.add(page_fingerprint)
            if repeated_page:
                warnings.append(f"{kind.upper()}_REPEATED_PAGE")

            missing_timestamp = len(timestamps) != len(raw_page)
            if missing_timestamp:
                warnings.append(f"{kind.upper()}_MISSING_TIMESTAMP_CURSOR")

            unsorted_page = bool(timestamps) and timestamps != sorted(timestamps)
            if unsorted_page:
                warnings.append(f"{kind.upper()}_UNSORTED_PAGE")

            non_monotonic_page = (
                previous_page_max_timestamp is not None
                and bool(timestamps)
                and min(timestamps) < previous_page_max_timestamp
            )
            if non_monotonic_page:
                warnings.append(f"{kind.upper()}_NON_MONOTONIC_PAGE")

            if repeated_page or missing_timestamp or unsorted_page or non_monotonic_page:
                break

            if not raw_page:
                complete = True
                break
            max_timestamp = max(timestamps) if timestamps else None
            if len(raw_page) < page_limit:
                complete = True
                break
            if max_timestamp is None:
                warnings.append(f"{kind.upper()}_MISSING_TIMESTAMP_CURSOR")
                break
            if until_ms is not None and max_timestamp >= until_ms:
                # A full page ending at the requested boundary may contain
                # more records with that same timestamp.  A short page or an
                # empty page is the only bounded end-of-history signal this
                # adapter currently accepts.
                warnings.append(f"{kind.upper()}_UNTIL_BOUNDARY_UNCERTAIN")
                break
            if cursor is not None and max_timestamp < cursor:
                warnings.append(f"{kind.upper()}_NON_ADVANCING_TIMESTAMP_CURSOR")
                break
            previous_page_max_timestamp = max_timestamp
            # Keep the boundary inclusive.  The overlap is deduplicated by
            # broker identity and is required to retrieve same-millisecond
            # records that straddle two pages.
            cursor = max_timestamp
        else:
            warnings.append(f"{kind.upper()}_MAX_PAGES_REACHED")

        if not complete and not warnings:
            warnings.append(f"{kind.upper()}_SNAPSHOT_INCOMPLETE")
        return _PageCollection(
            rows=list(rows_by_identity.values()),
            page_hashes=page_hashes,
            page_count=len(page_hashes),
            request_count=request_count,
            complete=complete,
            warnings=warnings,
        )

    def sync(
        self,
        *,
        exchange_id: str,
        account_id: str = "local-broker-api",
        symbol: Optional[str] = None,
        since_ms: Optional[int] = None,
        until_ms: Optional[int] = None,
        max_pages: int = 100,
        page_limit: int = 100,
        params: Optional[Mapping[str, Any]] = None,
        client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        normalized_exchange = self._validate_exchange(exchange_id)
        normalized_account = self._validate_account_id(account_id)
        self._validate_bounds(since_ms, until_ms)
        if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 1000:
            raise ReadOnlyBrokerSyncError("max_pages must be between 1 and 1000")
        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or not 1 <= page_limit <= 1000:
            raise ReadOnlyBrokerSyncError("page_limit must be between 1 and 1000")
        normalized_symbol = str(symbol).strip() if symbol is not None else None
        if normalized_symbol == "":
            normalized_symbol = None
        if normalized_symbol and len(normalized_symbol) > 80:
            raise ReadOnlyBrokerSyncError("symbol is too long")

        transport = self._build_client(normalized_exchange) if client is None else ReadOnlyExchangeClient(client)
        metadata = SUPPORTED_API_EXCHANGES[normalized_exchange]
        orders = self._paginate(
            transport,
            kind="orders",
            method_name="fetch_orders",
            mapper=_map_order,
            symbol=normalized_symbol,
            since_ms=since_ms,
            until_ms=until_ms,
            max_pages=max_pages,
            page_limit=page_limit,
            params=params,
        )
        fills = self._paginate(
            transport,
            kind="fills",
            method_name="fetch_my_trades",
            mapper=_map_fill,
            symbol=normalized_symbol,
            since_ms=since_ms,
            until_ms=until_ms,
            max_pages=max_pages,
            page_limit=page_limit,
            params=params,
        )
        complete = orders.complete and fills.complete
        warnings = tuple(orders.warnings + fills.warnings)
        manifest = ReadOnlySnapshotManifest.build(
            exchange_id=metadata["venue"],
            account_id=normalized_account,
            requested_since_ms=since_ms,
            requested_until_ms=until_ms,
            orders_page_count=orders.page_count,
            fills_page_count=fills.page_count,
            order_count=len(orders.rows),
            fill_count=len(fills.rows),
            request_count=orders.request_count + fills.request_count,
            page_hashes=orders.page_hashes + fills.page_hashes,
            complete=complete,
            warnings=warnings,
        )
        manifest.validate()

        report = self.import_service.import_records(
            metadata["venue"],
            orders=orders.rows,
            fills=fills.rows,
            account_id=normalized_account,
            source_name=f"{normalized_exchange}-read-only-api-snapshot",
            snapshot_manifest=manifest.as_dict(),
        )
        report["snapshot_manifest"] = manifest.as_dict()
        report["read_only_scope"] = READ_ONLY_SCOPE
        report["transport"] = {
            "adapter": "ccxt-read-only-v1",
            "exchange_id": normalized_exchange,
            "methods": ["fetch_orders", "fetch_my_trades"],
            "request_count": manifest.request_count,
        }
        return report


read_only_broker_sync_service = ReadOnlyBrokerSyncService()
