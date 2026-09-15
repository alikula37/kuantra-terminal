from app.api.webhook_tv import webhook_router
from app.core.position_type import normalize_position_type
from app.core.position_math import instrument_unit_basis, position_summary
from app.core.trade_rules import TradeRuleError, normalize_leverage
from app.core.trade_time import (
    TradeTimeError,
    parse_user_time,
    to_utc_iso,
    validate_not_future,
)
from app.api.plugin_endpoints import router as plugin_router
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Response
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import json
import time
from datetime import datetime, timezone
from app.db.sqlite_driver import SQLiteRevisionConflict, sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.db.sync_pipeline import sync_pipeline
from app.db.repositories.candles_repo import candles_repo
from app.services.trade_edit import TradeEditError, trade_edit_service
from app.services.quote_refresh import quote_refresh_service
from app.services.market_data.public_fetcher import (
    FREE_QUOTE_SOURCES,
    public_market_fetcher,
)
from app.services.portfolio_service import portfolio_service
from app.services.trade_read_adapter import trade_read_adapter
from app.services.evidence_pack_export import (
    EvidencePackExportError,
    EvidencePackNotFoundError,
    evidence_pack_export_service,
)
from app.services.csv_importer import csv_trade_importer
from app.services.broker_import_service import broker_import_service, BrokerImportValidationError
from app.services.reconciliation_inbox import (
    ReconciliationDecisionConflict,
    ReconciliationInboxError,
    ReconciliationReviewNotFound,
    reconciliation_inbox_service,
)
from app.services.weekly_review import WeeklyReviewError, weekly_review_service
from app.services.exchange.read_only_broker_sync import (
    ReadOnlyBrokerSyncError,
    read_only_broker_sync_service,
)
from app.services.exchange.credentials_manager import exchange_credentials_manager
from app.services.security.credential_store import CredentialStoreUnavailable, credential_store_status
from app.core.availability import experimental_disabled_exception, experimental_disabled_response as build_experimental_disabled_response
from app.core.input_limits import MAX_BROKER_JSON_BYTES, MAX_CSV_BYTES
from app.services.execution.ccxt_engine import ccxt_execution_engine
from app.websocket.connection_manager import ws_manager
from app.websocket.binance_client import binance_client
from app.quant.quant_engine import quant_engine

router = APIRouter(prefix="/api/v1")
router.include_router(webhook_router)
router.include_router(plugin_router)


async def _read_bounded_upload(file: UploadFile, limit: int) -> bytes:
    """Read an upload once with an explicit byte ceiling before parsing it."""

    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the safety size limit of {limit} bytes.",
        )
    return content


def experimental_disabled_response(payload: Dict[str, Any]) -> JSONResponse:
    """Expose disabled execution surfaces as a structured, non-success HTTP response."""
    return JSONResponse(status_code=503, content=payload)

class TrackingTargetSchema(BaseModel):
    price: float = Field(gt=0, le=10**15, allow_inf_nan=False)
    percent: float = Field(gt=0, le=100, allow_inf_nan=False)


class TrackingPlanSchema(BaseModel):
    enabled: bool = True
    source_id: Optional[str] = Field(default=None, max_length=40)
    source_symbol: Optional[str] = Field(default=None, max_length=128)
    stop_loss: Optional[float] = Field(default=None, gt=0, le=10**15, allow_inf_nan=False)
    targets: List[TrackingTargetSchema] = Field(default_factory=list, max_length=3)


class TrackingEditSchema(TrackingPlanSchema):
    expected_revision: int = Field(ge=0)


class TrackingCloseSchema(BaseModel):
    expected_revision: int = Field(ge=1)
    price: float = Field(gt=0, le=10**15, allow_inf_nan=False)


def tracking_service():
    from app.services.local_tracking import LocalTrackingService
    return LocalTrackingService(sqlite_driver)


def tracking_call(fn):
    from app.services.local_tracking import TrackingConflict
    try:
        return fn()
    except TrackingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/local-tracking")
def list_local_tracking():
    from app.services.local_tracking_monitor import tracking_monitor
    return tracking_call(lambda: [tracking_monitor.view(s) for s in tracking_service().list()])


@router.get("/trades/{trade_id}/tracking")
def get_local_tracking(trade_id: str):
    return tracking_call(lambda: {"plan": tracking_service().get(trade_id),
                                  "history": tracking_service().history(trade_id)})


@router.put("/trades/{trade_id}/tracking")
def edit_local_tracking(trade_id: str, payload: TrackingEditSchema):
    return tracking_call(lambda: tracking_service().edit(
        trade_id, payload.model_dump(exclude={"expected_revision"}), expected_revision=payload.expected_revision))


@router.post("/trades/{trade_id}/tracking/close")
def close_local_tracking(trade_id: str, payload: TrackingCloseSchema):
    return tracking_call(lambda: tracking_service().observe(
        trade_id, {"price": payload.price, "basis": "MANUAL_LOCAL"},
        manual=True, expected_revision=payload.expected_revision))


class TradeCreateSchema(BaseModel):
    local_tracking: Optional[TrackingPlanSchema] = None
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    position_type: Literal["SPOT", "LONG", "SHORT", "UNKNOWN"] = "UNKNOWN"
    entry_price: float = Field(..., gt=0, le=10**15)
    qty: Optional[float] = Field(default=None, gt=0, le=10**12)
    size_input_mode: Literal["QTY", "NOTIONAL"] = "QTY"
    notional_size: Optional[float] = Field(default=None, gt=0, le=10**18)
    leverage: Optional[float] = Field(default=None, gt=0, le=1000)
    stop_loss: Optional[float] = Field(default=None, gt=0, le=10**15)
    take_profit: Optional[float] = Field(default=None, gt=0, le=10**15)
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    exit_price: Optional[float] = Field(default=None, gt=0, le=10**15)
    exit_time: Optional[str] = Field(default=None, min_length=1, max_length=64)
    entry_time: Optional[str] = Field(default=None, min_length=1, max_length=64)
    notes: Optional[str] = Field(default="", max_length=2000)
    qty_unit: Literal["BASE", "UNKNOWN"] = "UNKNOWN"
    record_mode: Literal["EXTERNAL", "SIMULATION"] = "EXTERNAL"
    execution_venue: Optional[str] = Field(default=None, max_length=120)
    price_source: Literal[
        "manual", "binance_public", "bybit_public", "yahoo_public",
        "stooq_public", "biquote_public", "tradingview_alert", "broker_import", "unknown",
    ] = "manual"
    price_source_symbol: Optional[str] = Field(default=None, max_length=128)
    price_status: Literal["LIVE", "DELAYED", "EOD", "UNAVAILABLE"] = "UNAVAILABLE"
    price_observed_at: Optional[str] = Field(default=None, max_length=64)
    price_origin: Literal[
        "MANUAL", "PUBLIC_QUOTE", "TRADINGVIEW_ALERT", "BROKER_IMPORT", "UNKNOWN",
    ] = "MANUAL"

    @field_validator("execution_venue", "price_source_symbol", "entry_time", "exit_time", "price_observed_at")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if any(ord(character) < 32 for character in value):
            raise ValueError("text fields cannot contain control characters")
        cleaned = value.strip()
        return cleaned or None

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and any(ord(character) < 32 for character in value):
            raise ValueError("notes cannot contain control characters")
        return value

    @model_validator(mode="after")
    def _validate_price_provenance(self):
        """Reject provenance combinations that would overstate quote evidence."""
        normalize_position_type(self.position_type, self.side)
        if self.size_input_mode == "NOTIONAL":
            if self.qty is not None:
                raise ValueError("Provide either quantity or position size, not both")
            if self.notional_size is None:
                raise ValueError("Position size is required in notional mode")
        else:
            if self.qty is None:
                raise ValueError("Quantity is required")
            if self.notional_size is not None:
                raise ValueError("Provide either quantity or position size, not both")
        normalize_leverage(self.leverage, self.position_type.upper())
        if self.status == "CLOSED":
            if self.exit_price is None or self.exit_time is None:
                raise ValueError("A closed trade requires exit price and exit time")
            if self.local_tracking is not None:
                raise ValueError("A historical closed trade cannot enable live tracking")
        elif self.exit_price is not None or self.exit_time is not None:
            raise ValueError("An open trade cannot carry exit price or exit time")
        if self.price_origin == "PUBLIC_QUOTE":
            if self.price_source not in FREE_QUOTE_SOURCES:
                raise ValueError("PUBLIC_QUOTE requires an approved free quote source")
            if not self.price_source_symbol or not self.price_observed_at:
                raise ValueError("PUBLIC_QUOTE requires source symbol and observation time")
            if self.price_status == "UNAVAILABLE":
                raise ValueError("PUBLIC_QUOTE cannot have UNAVAILABLE status")
        elif self.price_origin == "MANUAL":
            if self.price_status != "UNAVAILABLE":
                raise ValueError("MANUAL price origin must remain UNAVAILABLE")
            if self.price_source not in {"manual", "tradingview_alert", "broker_import", "unknown"}:
                raise ValueError("MANUAL price origin cannot claim a public quote source")
        elif self.price_origin == "BROKER_IMPORT":
            if self.price_source != "broker_import":
                raise ValueError("BROKER_IMPORT requires broker_import source")
        elif self.price_origin == "TRADINGVIEW_ALERT":
            if self.price_source != "tradingview_alert":
                raise ValueError("TRADINGVIEW_ALERT requires tradingview_alert source")
        elif self.price_origin == "UNKNOWN":
            if self.price_source != "unknown" or self.price_status != "UNAVAILABLE":
                raise ValueError("UNKNOWN provenance must remain unavailable")
        return self

class TradeCloseSchema(BaseModel):
    exit_price: float
    exit_time: Optional[str] = None
    commission: Optional[float] = 0.0


class TradeEditSchema(BaseModel):
    """A bounded journal correction.  Omitted fields stay untouched.

    An explicit ``null`` clears an optional value (for example a take profit or
    a declared leverage); the endpoint distinguishes omitted vs null through
    ``model_dump(exclude_unset=True)``.  Identity fields (symbol, side, position
    type) and realized close data are deliberately not editable here.
    """

    expected_revision: int = Field(ge=1)
    entry_price: Optional[float] = Field(default=None, gt=0, le=10**15)
    entry_time: Optional[str] = Field(default=None, min_length=1, max_length=64)
    qty: Optional[float] = Field(default=None, gt=0, le=10**12)
    leverage: Optional[float] = Field(default=None, gt=0, le=1000)
    stop_loss: Optional[float] = Field(default=None, gt=0, le=10**15)
    take_profit: Optional[float] = Field(default=None, gt=0, le=10**15)
    notes: Optional[str] = Field(default=None, max_length=2000)
    qty_unit: Optional[Literal["BASE", "UNKNOWN"]] = None
    status: Optional[Literal["OPEN", "CLOSED", "CANCELED"]] = None
    exit_price: Optional[float] = Field(default=None, gt=0, le=10**15)
    exit_time: Optional[str] = Field(default=None, min_length=1, max_length=64)
    local_tracking: Optional[TrackingEditSchema] = None

    @field_validator("entry_time", "exit_time")
    @classmethod
    def _validate_entry_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if any(ord(character) < 32 for character in value):
            raise ValueError("time fields cannot contain control characters")
        cleaned = value.strip()
        return cleaned or None

    @field_validator("notes")
    @classmethod
    def _validate_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and any(ord(character) < 32 for character in value):
            raise ValueError("notes cannot contain control characters")
        return value


class QuoteRefreshSchema(BaseModel):
    trade_ids: Optional[List[str]] = Field(default=None, max_length=200)


class ReconciliationDecisionSchema(BaseModel):
    decision: str = Field(..., min_length=1, max_length=32)
    note: Optional[str] = Field(default=None, max_length=500)
    correction: Optional[Dict[str, Any]] = None


class WeeklyReviewDecisionSchema(BaseModel):
    period_start: str = Field(..., min_length=10, max_length=10)
    period_end: str = Field(..., min_length=10, max_length=10)
    timezone: str = Field(..., min_length=1, max_length=80)
    as_of_utc: str = Field(..., min_length=1, max_length=64)
    decision: str = Field(..., min_length=1, max_length=32)
    note: Optional[str] = Field(default=None, max_length=500)

@router.get("/trades")
def list_trades(
    limit: int = 100,
    offset: int = 0,
    symbol: Optional[str] = None,
    status: Optional[str] = None
):
    trades = trade_read_adapter.list_trades(limit=limit, offset=offset, symbol=symbol, status=status)
    return [attach_position_summary(trade) for trade in trades]

@router.get("/trades/open")
def get_open_trades():
    return [attach_position_summary(trade) for trade in trade_read_adapter.get_open_trades()]

@router.get("/trades/{trade_id}/evidence")
def get_trade_evidence(trade_id: str):
    evidence_pack = trade_read_adapter.get_evidence_pack(trade_id)
    if evidence_pack["trade"] is None and evidence_pack["event_count"] == 0:
        raise HTTPException(status_code=404, detail="Trade evidence not found")
    return evidence_pack


@router.get("/trades/{trade_id}/evidence/export")
def export_trade_evidence(
    trade_id: str,
    format: str = Query("json", min_length=1, max_length=8),
):
    """Download a deterministic JSON, CSV, or static HTML Evidence Pack artifact."""
    try:
        artifact = evidence_pack_export_service.export(trade_id, format)
    except EvidencePackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EvidencePackExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Evidence Pack export failed safely.") from exc
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Kuantra-Evidence-Payload-SHA256": artifact.payload_sha256,
            "X-Kuantra-Evidence-Artifact-SHA256": artifact.artifact_sha256,
            "X-Kuantra-Evidence-Artifact-Version": artifact.artifact_version,
        },
    )

@router.get("/trades/{trade_id}/market-context")
def get_trade_market_context(
    trade_id: str,
    lookback_bars: int = Query(30, ge=0, le=300),
    lookforward_bars: int = Query(20, ge=0, le=300),
):
    return trade_read_adapter.get_market_context(
        trade_id,
        lookback_bars=lookback_bars,
        lookforward_bars=lookforward_bars,
    )

@router.get("/trades/{trade_id}")
def get_trade(trade_id: str):
    trade = trade_read_adapter.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return attach_position_summary(trade)


def attach_position_summary(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the labeled sizing/return view without mutating stored data."""

    enriched = dict(trade)
    enriched["sizing"] = position_summary(
        symbol=trade.get("symbol"),
        position_type=trade.get("position_type") or "UNKNOWN",
        side=trade.get("side") or "BUY",
        entry_price=trade.get("entry_price"),
        qty=trade.get("qty"),
        leverage=trade.get("leverage"),
        exit_price=trade.get("exit_price"),
        commission=trade.get("commission"),
        qty_unit=trade.get("qty_unit"),
    )
    return enriched

@router.post("/trades")
def create_trade(trade: TradeCreateSchema):
    reference = datetime.now(timezone.utc)
    try:
        entry_at = (
            parse_user_time(trade.entry_time, field="entry_time", now=reference)
            if trade.entry_time
            else reference
        )
        validate_not_future(entry_at, field="entry_time", now=reference)
        exit_at = None
        if trade.exit_time:
            exit_at = parse_user_time(trade.exit_time, field="exit_time", now=reference)
            validate_not_future(exit_at, field="exit_time", now=reference)
            if exit_at < entry_at:
                raise TradeTimeError(
                    "EXIT_BEFORE_ENTRY",
                    "The exit time cannot be earlier than the entry time.",
                    field="exit_time",
                )
    except TradeTimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc

    price_source = trade.price_source.lower()
    if price_source not in FREE_QUOTE_SOURCES and price_source not in {
        "manual", "tradingview_alert", "broker_import", "unknown",
    }:
        raise HTTPException(status_code=422, detail="Unsupported price source")
    try:
        leverage = normalize_leverage(trade.leverage, trade.position_type)
    except TradeRuleError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc

    if trade.size_input_mode == "NOTIONAL":
        qty = float(trade.notional_size) / float(trade.entry_price)
    else:
        qty = float(trade.qty)
    if not qty or qty <= 0 or qty != qty or qty in (float("inf"), float("-inf")):
        raise HTTPException(
            status_code=422,
            detail={
                "reason": "QTY_INVALID",
                "message": "The computed position quantity must be a positive finite number.",
                "field": "qty",
            },
        )

    side = trade.side.upper()
    long = side in ("BUY", "LONG")
    direction = 1.0 if long else -1.0
    unit_basis = instrument_unit_basis(trade.symbol, qty_unit=trade.qty_unit)
    monetary_ready = unit_basis["contract_size"] == "BASE_UNIT"
    exit_price = float(trade.exit_price) if trade.status == "CLOSED" else None
    pnl: Optional[float] = 0.0
    r_multiple = None
    if exit_price is not None and monetary_ready:
        pnl = direction * (exit_price - float(trade.entry_price)) * qty
        if trade.stop_loss:
            risk_unit = (
                (float(trade.entry_price) - float(trade.stop_loss)) if long and float(trade.entry_price) > float(trade.stop_loss)
                else (float(trade.stop_loss) - float(trade.entry_price)) if not long and float(trade.stop_loss) > float(trade.entry_price)
                else None
            )
            if risk_unit and qty > 0:
                r_multiple = round(pnl / (risk_unit * qty), 2)
    elif exit_price is not None:
        # The contract/lot size is unknown, so no realized money figure is
        # produced; the close evidence itself is still recorded.
        pnl = None

    tracking_plan = (
        trade.local_tracking.model_dump()
        if trade.local_tracking is not None and trade.status == "OPEN"
        else None
    )
    # The local plan is the authority for the effective stop/targets; mirror the
    # plan's first values into the compatibility columns so journal analytics,
    # R-multiple and the tracking engine never disagree.
    effective_stop = trade.stop_loss
    effective_target = trade.take_profit
    if tracking_plan is not None:
        plan_targets = tracking_plan.get("targets") or []
        if effective_stop is None and tracking_plan.get("stop_loss") is not None:
            effective_stop = float(tracking_plan["stop_loss"])
        if effective_target is None and plan_targets:
            effective_target = float(plan_targets[0]["price"])
    tracking_started_at = (
        to_utc_iso(reference)
        if tracking_plan is not None and tracking_plan.get("enabled")
        else None
    )
    trade_data = {
        "symbol": trade.symbol.upper(),
        "side": side,
        "position_type": trade.position_type,
        "entry_price": trade.entry_price,
        "qty": qty,
        "stop_loss": effective_stop,
        "take_profit": effective_target,
        "entry_time": to_utc_iso(entry_at),
        "status": trade.status,
        "exit_price": exit_price,
        "exit_time": to_utc_iso(exit_at) if exit_at is not None else None,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "r_multiple": r_multiple,
        "commission": 0.0,
        "notes": trade.notes,
        "record_mode": trade.record_mode,
        "execution_venue": trade.execution_venue,
        "price_source": price_source,
        "price_source_symbol": trade.price_source_symbol,
        "price_status": trade.price_status,
        "price_observed_at": trade.price_observed_at,
        "price_origin": trade.price_origin,
        "leverage": leverage,
        "revision": 1,
        "entry_time_source": "USER" if trade.entry_time else "SERVER",
        "close_source": "USER_REPORTED" if trade.status == "CLOSED" else None,
        "tracking_started_at": tracking_started_at,
        "qty_unit": trade.qty_unit,
    }
    saved = tracking_call(lambda: sync_pipeline.record_and_sync_trade(
        trade_data,
        local_tracking_plan=tracking_plan,
        source="journal_simulation" if trade.record_mode == "SIMULATION" else "journal_external",
        source_ref=trade.execution_venue or "manual",
        provenance_extra={
            "record_mode": trade.record_mode,
            "execution_venue": trade.execution_venue,
            "price_source": price_source,
            "price_source_symbol": trade.price_source_symbol,
            "price_status": trade.price_status,
            "price_observed_at": trade.price_observed_at,
            "price_origin": trade.price_origin,
            "entry_time_source": trade_data["entry_time_source"],
            "size_input_mode": trade.size_input_mode,
            "close_source": trade_data["close_source"],
            "qty_unit": trade.qty_unit,
        },
    ))
    return attach_position_summary(saved)


@router.patch("/trades/{trade_id}")
def edit_trade(trade_id: str, payload: TradeEditSchema):
    changes = payload.model_dump(exclude_unset=True)
    expected_revision = changes.pop("expected_revision")
    tracking_plan = changes.pop("local_tracking", None)
    try:
        return trade_edit_service.edit(
            trade_id,
            changes,
            expected_revision=expected_revision,
            tracking_plan=tracking_plan,
        )
    except TradeEditError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc
    except TradeRuleError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc
    except TradeTimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc


@router.get("/trades/{trade_id}/revisions")
def get_trade_revisions(trade_id: str):
    existing = trade_read_adapter.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {
        "trade_id": trade_id,
        "current_revision": int(existing.get("revision") or 1),
        "revisions": trade_edit_service.revision_history(trade_id),
    }

@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: str, close_data: TradeCloseSchema):
    existing = sqlite_driver.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    if str(existing.get("status")) != "OPEN":
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "TRADE_NOT_OPEN",
                "message": "Only an open trade can be closed; the recorded status is preserved.",
            },
        )

    reference = datetime.now(timezone.utc)
    try:
        exit_at = (
            parse_user_time(close_data.exit_time, field="exit_time", now=reference)
            if close_data.exit_time
            else reference
        )
        validate_not_future(exit_at, field="exit_time", now=reference)
        entry_at = parse_user_time(str(existing["entry_time"]), field="entry_time", now=reference)
        if exit_at < entry_at:
            raise TradeTimeError(
                "EXIT_BEFORE_ENTRY",
                "The exit time cannot be earlier than the entry time.",
                field="exit_time",
            )
    except TradeTimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": str(exc), "field": exc.field},
        ) from exc

    entry_price = float(existing["entry_price"])
    qty = float(existing["qty"])
    side = existing["side"].upper()
    exit_price = close_data.exit_price
    sl = float(existing["stop_loss"]) if existing.get("stop_loss") else None
    monetary_ready = instrument_unit_basis(
        existing.get("symbol"),
        qty_unit=existing.get("qty_unit"),
    )["contract_size"] == "BASE_UNIT"

    if not monetary_ready:
        # User-reported close evidence is stored; no realized money figure is
        # produced because the quantity unit/contract multiplier is unknown.
        pnl = None
        r_multiple = None
    elif side in ("BUY", "LONG"):
        pnl = (exit_price - entry_price) * qty - (close_data.commission or 0.0)
        r_unit = (entry_price - sl) if sl and (entry_price > sl) else None
        r_multiple = (pnl / (r_unit * qty)) if (r_unit and qty > 0) else None
    else:
        pnl = (entry_price - exit_price) * qty - (close_data.commission or 0.0)
        r_unit = (sl - entry_price) if sl and (sl > entry_price) else None
        r_multiple = (pnl / (r_unit * qty)) if (r_unit and qty > 0) else None

    update_payload = {
        "status": "CLOSED",
        "exit_price": exit_price,
        "exit_time": to_utc_iso(exit_at),
        "pnl": round(pnl, 2) if pnl is not None else None,
        "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,
        "commission": close_data.commission or 0.0,
        "close_source": "USER_REPORTED",
        "revision": int(existing.get("revision") or 1) + 1,
    }

    try:
        updated = sync_pipeline.record_and_sync_trade(
            {"id": trade_id, **update_payload},
            expected_revision=int(existing.get("revision") or 1),
        )
    except SQLiteRevisionConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason": "REVISION_CONFLICT", "message": str(exc)},
        ) from exc
    return attach_position_summary(updated)

@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: str):
    existing = sqlite_driver.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    if str(existing.get("status")) == "CANCELED":
        raise HTTPException(
            status_code=409,
            detail={"reason": "TRADE_ALREADY_CANCELED", "message": "The trade is already canceled."},
        )
    canceled = sync_pipeline.record_and_sync_trade(
        {
            "id": trade_id,
            "status": "CANCELED",
            "revision": int(existing.get("revision") or 1) + 1,
        },
        source="journal_delete",
        source_ref="api",
        expected_revision=int(existing.get("revision") or 1),
    )
    return {"status": "canceled", "id": trade_id, "trade": canceled}

@router.post("/trades/quotes/refresh")
async def refresh_trade_quotes(payload: QuoteRefreshSchema):
    """Refresh open-trade quotes for the exact confirmed provider identity."""

    if payload.trade_ids:
        selected = []
        for trade_id in payload.trade_ids[:200]:
            trade = trade_read_adapter.get_trade(trade_id)
            if trade:
                selected.append(trade)
    else:
        selected = trade_read_adapter.get_open_trades()[:200]
    return await quote_refresh_service.refresh(selected)

@router.post("/journal/import-csv")
async def import_csv_trades(file: UploadFile = File(...)):
    """Imports multi-format trade history from Binance, Bybit, MetaTrader, or Generic CSV."""
    if not file.filename or not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a .csv or .txt file.")
    content = await _read_bounded_upload(file, MAX_CSV_BYTES)
    try:
        res = csv_trade_importer.parse_and_import_csv(content, file.filename)
        summary = portfolio_service.get_portfolio_summary()
        res["portfolio_summary"] = summary
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV file: {str(e)}")

@router.post("/journal/preview-csv")
async def preview_csv_trades(file: UploadFile = File(...)):
    """Parses and previews CSV rows without committing to the database."""
    if not file.filename or not file.filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a .csv or .txt file.")
    content = await _read_bounded_upload(file, MAX_CSV_BYTES)
    try:
        return csv_trade_importer.parse_and_preview_csv(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse CSV preview: {str(e)}")

@router.get("/journal/template-csv")
def get_template_csv():
    """Returns downloadable generic Kuantra CSV template."""
    csv_data = csv_trade_importer.generate_generic_template_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kuantra_trade_template.csv"}
    )


@router.post("/broker/import-json")
async def import_broker_json(
    venue: str = Query(..., min_length=1, max_length=32),
    file: UploadFile = File(...),
):
    """Import a bounded local broker export; no connector or order write occurs."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Broker import accepts a UTF-8 .json export only.")
    content = await _read_bounded_upload(file, MAX_BROKER_JSON_BYTES)
    try:
        return broker_import_service.import_json_document(
            venue,
            content,
            source_name=file.filename,
        )
    except BrokerImportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Broker export could not be imported safely.") from exc


@router.get("/reconciliation/inbox")
def list_reconciliation_inbox(
    status: Optional[str] = Query(None, min_length=1, max_length=32),
    limit: int = Query(100, ge=1, le=1000),
):
    """List source-linked discrepancy reviews without claiming accounting success."""
    try:
        items = reconciliation_inbox_service.list_items(status=status, limit=limit)
    except ReconciliationInboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": str(status or "ALL").upper(),
        "count": len(items),
        "items": items,
        "scope": "LOCAL_EVIDENCE_ONLY",
    }


@router.post("/reconciliation/inbox/{review_id}/decision")
def decide_reconciliation_review(review_id: str, payload: ReconciliationDecisionSchema):
    """Record an explicit acknowledgement, rejection, or bounded correction."""
    try:
        return reconciliation_inbox_service.record_decision(
            review_id,
            payload.decision,
            note=payload.note,
            correction=payload.correction,
        )
    except ReconciliationReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ReconciliationDecisionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ReconciliationInboxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reviews/weekly")
def get_weekly_review(
    period_start: str = Query(..., min_length=10, max_length=10),
    period_end: str = Query(..., min_length=10, max_length=10),
    timezone_name: str = Query(..., alias="timezone", min_length=1, max_length=80),
    as_of_utc: str = Query(..., min_length=1, max_length=64),
):
    """Build an explicit period/as-of review over immutable local evidence."""
    try:
        return weekly_review_service.build_review(
            period_start=period_start,
            period_end=period_end,
            timezone_name=timezone_name,
            as_of_utc=as_of_utc,
        )
    except WeeklyReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews/weekly/decision")
def decide_weekly_review(payload: WeeklyReviewDecisionSchema):
    """Record a bounded review action through the existing journal event type."""
    try:
        review = weekly_review_service.build_review(
            period_start=payload.period_start,
            period_end=payload.period_end,
            timezone_name=payload.timezone,
            as_of_utc=payload.as_of_utc,
        )
        decision = weekly_review_service.record_decision(
            review,
            decision=payload.decision,
            note=payload.note,
        )
        return {"review": review, "decision": decision}
    except WeeklyReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/broker/sync-read-only")
def sync_broker_read_only(
    exchange_id: str = Query(..., min_length=1, max_length=32),
    account_id: str = Query("local-broker-api", min_length=1, max_length=128),
    symbol: Optional[str] = Query(None, min_length=1, max_length=80),
    since_ms: Optional[int] = Query(None, ge=0),
    until_ms: Optional[int] = Query(None, ge=0),
    max_pages: int = Query(100, ge=1, le=1000),
    page_limit: int = Query(100, ge=1, le=1000),
):
    """Fetches authenticated broker observations through a read-only CCXT scope.

    This endpoint never calls an order-write method.  It stores only normalized
    order/fill observations plus a validated snapshot manifest in the ledger.
    """
    try:
        return read_only_broker_sync_service.sync(
            exchange_id=exchange_id,
            account_id=account_id,
            symbol=symbol,
            since_ms=since_ms,
            until_ms=until_ms,
            max_pages=max_pages,
            page_limit=page_limit,
        )
    except ReadOnlyBrokerSyncError as exc:
        raise HTTPException(status_code=400, detail={"code": "READ_ONLY_SYNC_REJECTED", "message": str(exc)}) from exc
    except BrokerImportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Broker read-only snapshot could not be fetched safely.") from exc

# --- EXCHANGE API CREDENTIALS & EXECUTION ROUTES ---

class ExchangeCredentialsSaveSchema(BaseModel):
    exchange_id: str
    name: Optional[str] = None
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None
    is_testnet: Optional[bool] = False
    is_active: Optional[bool] = True

class ExchangeConnectionTestSchema(BaseModel):
    exchange_id: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    passphrase: Optional[str] = None
    is_testnet: Optional[bool] = False

class OrderDispatchSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    order_type: str = "LIMIT"
    qty: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exchange: Optional[str] = "binance_futures"
    mode: Optional[str] = "PAPER"
    notes: Optional[str] = ""

@router.get("/exchange/credentials")
def list_exchange_credentials():
    """Lists configured exchange API accounts with masked secrets."""
    return exchange_credentials_manager.list_configured_exchanges()

@router.get("/exchange/credentials/status")
def get_exchange_credential_store_status():
    """Reports keychain availability without exposing any credential material."""

    return credential_store_status()

@router.post("/exchange/credentials")
def save_exchange_credentials(payload: ExchangeCredentialsSaveSchema):
    """Stores exchange API credentials in the operating system keychain."""
    try:
        return exchange_credentials_manager.save_credentials(
            exchange_id=payload.exchange_id,
            name=payload.name,
            api_key=payload.api_key,
            api_secret=payload.api_secret,
            passphrase=payload.passphrase,
            is_testnet=bool(payload.is_testnet),
            is_active=bool(payload.is_active)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CredentialStoreUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CREDENTIAL_STORE_UNAVAILABLE",
                "message": str(e),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store credentials: {str(e)}")

@router.delete("/exchange/credentials/{exchange_id}")
def delete_exchange_credentials(exchange_id: str):
    """Purges exchange credentials from vault and database."""
    try:
        deleted = exchange_credentials_manager.delete_credentials(exchange_id)
    except CredentialStoreUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "CREDENTIAL_STORE_UNAVAILABLE", "message": str(e)},
        )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No credentials found for '{exchange_id}'")
    return {"status": "deleted", "exchange_id": exchange_id}

@router.post("/exchange/test-connection")
def test_exchange_connection(payload: ExchangeConnectionTestSchema):
    """Genuinely verifies exchange API connectivity via CCXT."""
    res = exchange_credentials_manager.test_connection(
        exchange_id=payload.exchange_id,
        api_key=payload.api_key,
        api_secret=payload.api_secret,
        passphrase=payload.passphrase,
        is_testnet=payload.is_testnet
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res)
    return res

@router.get("/exchange/balances")
def get_exchange_balances(exchange_id: str = "binance_futures"):
    """Fetches real-time equity & margin from connected exchange."""
    res = ccxt_execution_engine.sync_exchange_balances(exchange_id=exchange_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to sync balances"))
    return res

@router.post("/execution/order")
def dispatch_order(order: OrderDispatchSchema):
    """Dispatches a paper order through the pre-execution risk gatekeeper."""
    mode = str(order.mode or "PAPER").strip().upper()
    if mode == "LIVE":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "LIVE_EXECUTION_DISABLED",
                "reason": "Live execution is disabled until the Phase 4 execution safety gates are complete.",
            },
        )
    if mode != "PAPER":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "UNSUPPORTED_EXECUTION_MODE",
                "reason": "Only PAPER execution mode is supported.",
            },
        )

    res = ccxt_execution_engine.create_order(
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        qty=order.qty,
        price=order.price,
        stop_loss=order.stop_loss,
        take_profit=order.take_profit,
        exchange_id=order.exchange or "binance_futures",
        mode=mode,
        notes=order.notes
    )
    if not res.get("success"):
        if res.get("status") == "REJECTED":
            raise HTTPException(status_code=422, detail=res)
        raise HTTPException(status_code=400, detail=res)
    return res

@router.get("/execution/orders/open")
def get_open_orders(exchange_id: str = "binance_futures", symbol: Optional[str] = None, mode: str = "PAPER"):
    """Lists active open orders from exchange or paper log."""
    return ccxt_execution_engine.fetch_open_orders(exchange_id=exchange_id, symbol=symbol, mode=mode)

@router.delete("/execution/orders/{order_id}")
def cancel_execution_order(order_id: str, symbol: Optional[str] = None, exchange_id: str = "binance_futures", mode: str = "PAPER"):
    """Cancels active order."""
    res = ccxt_execution_engine.cancel_order(order_id=order_id, symbol=symbol, exchange_id=exchange_id, mode=mode)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res)
    return res

@router.get("/analytics/overview")
def get_analytics_overview():
    return duckdb_driver.get_aggregated_stats()

from app.services.compliance_engine import compliance_engine

from app.replay.replay_service import replay_service

class ReplayStepSchema(BaseModel):
    direction: int = 1

class ReplaySeekSchema(BaseModel):
    target_index: int

class ReplaySpeedSchema(BaseModel):
    speed: float = Field(allow_inf_nan=False)

@router.get("/replay/session/{trade_id}")
def get_replay_session_for_trade(trade_id: str):
    return replay_service.create_session_for_trade(trade_id=trade_id)

@router.post("/replay/{session_id}/step")
def step_replay_frame(session_id: str, payload: ReplayStepSchema):
    try:
        return replay_service.step(session_id, direction=payload.direction)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/replay/{session_id}/seek")
def seek_replay_frame(session_id: str, payload: ReplaySeekSchema):
    try:
        return replay_service.seek(session_id, target_index=payload.target_index)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/replay/{session_id}/speed")
def set_replay_speed(session_id: str, payload: ReplaySpeedSchema):
    try:
        return replay_service.set_speed(session_id, speed=payload.speed)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.websocket("/ws/replay")
async def websocket_replay_stream(websocket: WebSocket):
    await websocket.accept()
    session_id = None
    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                data = json.loads(raw_msg)
                if not isinstance(data, dict):
                    raise ValueError("Invalid replay request")
                action = data.get("action")
                if action == "INIT":
                    # Clear prior state before a new trade, including failed INIT.
                    session_id = None
                    trade_id = data.get("trade_id")
                    if not isinstance(trade_id, str) or not trade_id.strip():
                        raise ValueError("A recorded trade ID is required")
                    res = replay_service.create_session_for_trade(trade_id)
                    session_id = res["session_id"]
                elif not session_id:
                    raise ValueError("No active replay session")
                elif action == "STEP":
                    payload = ReplayStepSchema.model_validate(data)
                    res = replay_service.step(session_id, direction=payload.direction)
                elif action == "SEEK":
                    payload = ReplaySeekSchema.model_validate({"target_index": data.get("index", 0)})
                    res = replay_service.seek(session_id, target_index=payload.target_index)
                elif action == "SPEED":
                    payload = ReplaySpeedSchema.model_validate({"speed": data.get("speed", 1.0)})
                    res = replay_service.set_speed(session_id, speed=payload.speed)
                else:
                    raise ValueError("Unsupported replay action")
                await websocket.send_json({"type": "REPLAY_STATE", "data": res})
            except (ValueError, TypeError):
                await websocket.send_json({"type": "REPLAY_ERROR", "reason": "INVALID_REPLAY_REQUEST", "message": "Invalid request or no active recorded replay session."})
    except WebSocketDisconnect:
        pass

from app.playbook.playbook_service import playbook_service

class PlaybookCreateSchema(BaseModel):
    title: str
    description: str = ""
    win_rate_target: float = 65.0
    rr_target: float = 2.5
    rules: Optional[List[Dict[str, Any]]] = None

class PlaybookAuditSchema(BaseModel):
    trade_id: str
    playbook_id: str
    checked_rule_ids: List[str]
    playbook_version: Optional[int] = Field(default=None, ge=1)


class PlaybookVersionCreateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    win_rate_target: Optional[float] = None
    rr_target: Optional[float] = None
    rules: Optional[List[Dict[str, Any]]] = None

@router.get("/playbooks")
def list_playbooks():
    return playbook_service.list_playbooks()

@router.post("/playbooks")
def create_playbook(payload: PlaybookCreateSchema):
    return playbook_service.create_playbook(
        title=payload.title,
        description=payload.description,
        win_rate_target=payload.win_rate_target,
        rr_target=payload.rr_target,
        rules=payload.rules
    )

@router.post("/playbooks/{playbook_id}/versions")
def create_playbook_version(playbook_id: str, payload: PlaybookVersionCreateSchema):
    try:
        return playbook_service.create_playbook_version(
            playbook_id=playbook_id,
            title=payload.title,
            description=payload.description,
            win_rate_target=payload.win_rate_target,
            rr_target=payload.rr_target,
            rules=payload.rules,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/playbooks/{playbook_id}/versions")
def list_playbook_versions(playbook_id: str):
    if not playbook_service.get_playbook(playbook_id):
        raise HTTPException(status_code=404, detail="Playbook not found")
    return playbook_service.list_playbook_versions(playbook_id)

@router.get("/playbooks/{playbook_id}")
def get_playbook_by_id(playbook_id: str):
    pb = playbook_service.get_playbook(playbook_id)
    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return pb

@router.post("/playbooks/audit")
def audit_trade_playbook(payload: PlaybookAuditSchema):
    try:
        return playbook_service.audit_trade_discipline(
            trade_id=payload.trade_id,
            playbook_id=payload.playbook_id,
            checked_rule_ids=payload.checked_rule_ids,
            playbook_version=payload.playbook_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/compliance/status")
def get_compliance_status():
    open_positions = binance_client._recalculate_open_positions(binance_client.last_price)
    return compliance_engine.evaluate_compliance(open_positions)

@router.post("/compliance/config")
def update_compliance_config(config_data: Dict[str, Any]):
    updated = compliance_engine.update_config(config_data)
    return {"status": "updated", "config": updated.model_dump()}

from app.quant.pivot_engine import pivot_engine

class PivotRequestSchema(BaseModel):
    group_by: Optional[List[str]] = Field(default_factory=lambda: ["symbol"])
    symbol: Optional[str] = None
    side: Optional[str] = None

@router.post("/analytics/pivot")
def compute_pivot_analytics(req: PivotRequestSchema):
    return pivot_engine.compute_pivot_grid(
        group_by=req.group_by,
        symbol_filter=req.symbol,
        side_filter=req.side
    )

from app.quant.execution_drift import execution_drift_analyzer

@router.get("/analytics/execution-drift")
def get_execution_drift_analytics(symbol: Optional[str] = None):
    return execution_drift_analyzer.get_drift_analytics(symbol=symbol)

from app.psychology.psychology_engine import psychology_engine

@router.get("/psychology/tilt-status")
def get_session_tilt_status():
    compliance_status = compliance_engine.evaluate_compliance([])
    daily_loss_util = 0.0
    daily_rule = next((r for r in compliance_status["rules"] if r["rule"] == "Daily Max Loss"), None)
    if daily_rule:
        daily_loss_util = float(daily_rule.get("utilization_pct") or 0.0)

    return psychology_engine.calculate_session_tilt_score(daily_loss_utilization_pct=daily_loss_util)

@router.get("/psychology/anomalies")
def get_psychology_anomalies():
    return psychology_engine.get_all_anomalies()

@router.get("/psychology/fatigue-matrix")
def get_mental_fatigue_matrix():
    return psychology_engine.compute_mental_fatigue_matrix()

from app.ai.vision_service import vision_chart_parser
from app.ai.ai_auditor import ai_auditor
from app.ai.ai_query_engine import ai_query_engine

class ChartParseSchema(BaseModel):
    image_data: Optional[str] = None
    hint_text: Optional[str] = None

class AiQuerySchema(BaseModel):
    prompt: str

@router.post("/ai/parse-chart")
def parse_chart_image(payload: ChartParseSchema):
    return vision_chart_parser.parse_chart_screenshot(
        image_data=payload.image_data,
        hint_text=payload.hint_text
    )

@router.get("/ai/audit-report")
def get_ai_trade_audit_report():
    return ai_auditor.generate_audit_report()

@router.post("/ai/query")
def execute_ai_natural_query(payload: AiQuerySchema):
    return ai_query_engine.execute_natural_query(query_text=payload.prompt)


class WorkspaceLayoutSchema(BaseModel):
    preset_name: str = "default"
    layout_data: Dict[str, Any]

@router.get("/workspace/layout/{preset_name}")
def get_workspace_layout(preset_name: str):
    key = f"layout_{preset_name}"
    val = sqlite_driver.get_setting(key)
    if val:
        try:
            return {"preset_name": preset_name, "layout_data": json.loads(val)}
        except Exception:
            return {"preset_name": preset_name, "layout_data": val}
    return {"preset_name": preset_name, "layout_data": None}

@router.post("/workspace/layout")
def save_workspace_layout(payload: WorkspaceLayoutSchema):
    key = f"layout_{payload.preset_name}"
    sqlite_driver.set_setting(key, payload.layout_data)
    return {"status": "SAVED", "preset_name": payload.preset_name}

@router.get("/workspace/presets")
def list_workspace_presets():
    settings_dict = sqlite_driver.get_all_settings()
    presets = []
    for k in settings_dict.keys():
        if k.startswith("layout_"):
            presets.append(k.replace("layout_", ""))
    if "default" not in presets:
        presets.insert(0, "default")
    if "Day Trader" not in presets:
        presets.append("Day Trader")
    if "AI Auditor Focus" not in presets:
        presets.append("AI Auditor Focus")
    if "Multi-Chart Grid" not in presets:
        presets.append("Multi-Chart Grid")
    return {"presets": presets}

from app.core.telemetry import telemetry_manager
from app.core.logging_config import export_logs_zip
from fastapi.responses import FileResponse

class TelemetryConsentSchema(BaseModel):
    opt_in: bool

class SpoolCrashSchema(BaseModel):
    error_type: str
    message: str
    stack_trace: str

@router.get("/telemetry/status")
def get_telemetry_status():
    return {
        "opt_in": telemetry_manager.is_opted_in(),
        "queued_crashes": telemetry_manager.get_queued_crashes_count(),
        "delivery_status": telemetry_manager.delivery_status(),
    }

@router.post("/telemetry/consent")
def set_telemetry_consent(payload: TelemetryConsentSchema):
    telemetry_manager.set_opt_in(payload.opt_in)
    if payload.opt_in:
        telemetry_manager.flush_queue()
    return {"status": "UPDATED", "opt_in": payload.opt_in}

@router.post("/telemetry/spool-crash")
def spool_client_crash(payload: SpoolCrashSchema):
    telemetry_manager.spool_crash(payload.error_type, payload.message, payload.stack_trace)
    return {"status": "SPOOLED"}

@router.get("/telemetry/export-logs")
def export_redacted_system_logs():
    zip_path = export_logs_zip()
    return FileResponse(zip_path, media_type="application/zip", filename="kuantra_diagnostics_redacted.zip")

from app.core.hardware_detector import hardware_detector

@router.get("/system/hardware")
def get_system_hardware_profile():
    return hardware_detector.detect_hardware()

from app.core.model_downloader import model_downloader

class ModelDownloadSchema(BaseModel):
    model_name: Optional[str] = None
    url: Optional[str] = None
    mock_mode: bool = False

@router.get("/system/model/status")
def get_model_download_status(model_name: Optional[str] = None):
    return model_downloader.get_status(model_name)

@router.post("/system/model/download")
def start_model_download(payload: ModelDownloadSchema):
    return model_downloader.start_download(
        model_name=payload.model_name,
        url=payload.url,
        mock_mode=payload.mock_mode
    )

@router.post("/system/model/pause")
def pause_model_download(payload: ModelDownloadSchema):
    return model_downloader.pause_download(model_name=payload.model_name)

@router.post("/system/model/resume")
def resume_model_download(payload: ModelDownloadSchema):
    return model_downloader.resume_download(model_name=payload.model_name)

@router.post("/system/model/cancel")
def cancel_model_download(payload: ModelDownloadSchema):
    return model_downloader.cancel_download(model_name=payload.model_name)


from app.services.settings_service import settings_service

class VaultStoreSchema(BaseModel):
    key: Optional[str] = None
    exchange: Optional[str] = None
    value: Optional[str] = None
    secret: Optional[str] = None

class SettingsUpdateSchema(BaseModel):
    active_theme: Optional[str] = None
    active_locale: Optional[str] = None
    trading_mode: Optional[str] = None
    paper_balance: Optional[float] = None
    first_boot_completed: Optional[bool] = None
    ai_mode: Optional[str] = None

class OnboardingCompleteSchema(BaseModel):
    ai_mode: Optional[str] = "disabled"
    api_key: Optional[str] = None
    provider: Optional[str] = "openai"
    trading_mode: Optional[str] = "paper"
    paper_balance: Optional[float] = None
    active_theme: Optional[str] = "dark"
    active_locale: Optional[str] = "en"
    api_keys: Optional[Dict[str, str]] = None

@router.get("/settings")
def get_runtime_settings():
    return settings_service.get_settings()

@router.put("/settings")
def update_runtime_settings(payload: SettingsUpdateSchema):
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    return settings_service.update_settings(updates)

@router.post("/vault/store")
def store_vault_credential(payload: VaultStoreSchema):
    key = payload.key or (f"{payload.exchange.upper()}_API_KEY" if payload.exchange else None)
    val = payload.value or payload.secret
    if not key or not val:
        raise HTTPException(status_code=400, detail="Both 'key' (or 'exchange') and 'value' are required.")
    try:
        settings_service.store_vault_secret(key, val)
    except CredentialStoreUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "CREDENTIAL_STORE_UNAVAILABLE", "message": str(e)},
        )
    return {"status": "STORED", "key": key.upper()}

@router.get("/onboarding/status")
def get_onboarding_status():
    cfg = settings_service.get_settings()
    hw = hardware_detector.detect_hardware()
    return {
        "first_boot_completed": cfg["first_boot_completed"],
        "config": cfg,
        "ai_mode": cfg.get("ai_mode", "disabled"),
        "hardware": hw
    }

@router.post("/onboarding/complete")
def complete_onboarding(payload: OnboardingCompleteSchema):
    if payload.api_key or payload.api_keys:
        store_status = credential_store_status()
        if not store_status.get("available"):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "CREDENTIAL_STORE_UNAVAILABLE",
                    "message": store_status.get("reason") or "An OS credential manager is required.",
                },
            )
    initial_bal = payload.paper_balance
    if initial_bal is None:
        try:
            initial_bal = float(settings_service.get_setting("user_initial_balance", default="0.0") or 0.0)
        except Exception:
            initial_bal = 0.0
    requested_ai_mode = payload.ai_mode or "disabled"
    # The legacy local_gguf value represented a downloader/mock path.  Keep the
    # setting truthful until a real sidecar contract exists.
    configured_ai_mode = "disabled" if requested_ai_mode == "local_gguf" else requested_ai_mode
    updates = {
        "first_boot_completed": True,
        "trading_mode": payload.trading_mode or "paper",
        "paper_balance": initial_bal,
        "active_theme": payload.active_theme or "dark",
        "active_locale": payload.active_locale or "en",
        "ai_mode": configured_ai_mode
    }
    cfg = settings_service.update_settings(updates)

    try:
        # Store individual api_keys dict if provided.
        if payload.api_keys:
            for k, v in payload.api_keys.items():
                if k and v:
                    settings_service.store_vault_secret(k, v)

        # Backward compatibility with single api_key.
        if payload.api_key:
            provider_name = payload.provider or "OPENAI"
            settings_service.store_vault_secret(f"{provider_name.upper()}_API_KEY", payload.api_key)
    except CredentialStoreUnavailable as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "CREDENTIAL_STORE_UNAVAILABLE", "message": str(e)},
        )

    return {
        "status": "SUCCESS",
        "first_boot_completed": True,
        "ai_mode": cfg.get("ai_mode"),
        "ai_capability": build_experimental_disabled_response(
            "local_llm_inference",
            reason="REAL_MODEL_SIDECAR_NOT_CONFIGURED",
            message="Local LLM inference remains disabled until a verified sidecar is configured.",
        ),
        "config": cfg,
    }

from app.websocket.tv_sync import tv_sync_manager

class TvSyncPayload(BaseModel):
    symbol: str
    timeframe: Optional[str] = "15m"
    exchange: Optional[str] = "BINANCE"

@router.get("/tv/sync-status")
def get_tv_sync_status():
    return tv_sync_manager.get_sync_state()

@router.post("/tv/sync-symbol")
async def set_tv_sync_symbol(payload: TvSyncPayload):
    await tv_sync_manager.handle_extension_message({
        "symbol": payload.symbol,
        "timeframe": payload.timeframe,
        "exchange": payload.exchange
    })
    return {"status": "SYNCED", "state": tv_sync_manager.get_sync_state()}

from app.services.data_adapters.multi_asset_manager import multi_asset_manager

class AdapterSubscribeSchema(BaseModel):
    adapter: str # "twelvedata" | "polygon" | "mt5"
    symbols: List[str]

@router.get("/adapters/status")
def get_multi_asset_adapters_status():
    return multi_asset_manager.get_all_statuses()

@router.post("/adapters/subscribe")
def subscribe_to_adapter_symbols(payload: AdapterSubscribeSchema):
    adapter_key = payload.adapter.lower()
    if adapter_key in {"twelvedata", "polygon", "mt5"}:
        raise experimental_disabled_exception(
            f"{adapter_key}_connector",
            reason="REAL_TRANSPORT_NOT_CONFIGURED",
            message=f"{adapter_key} subscription is disabled until a verified session transport exists.",
            provenance="UNVERIFIED_ADAPTER",
        )
    raise HTTPException(status_code=404, detail=f"Unknown adapter '{payload.adapter}'.")

from app.services.execution.risk_interceptor import risk_interceptor

@router.get("/execution/status")
def get_execution_guardrail_status():
    return {
        "guardrails_active": risk_interceptor.guardrails_active,
        "max_tilt_score": risk_interceptor.max_allowed_tilt_score,
        "supported_venues": [],
        "live_execution_available": False,
        "paper_execution_available": True,
        "reason": "LIVE_EXECUTION_DISABLED_UNTIL_PHASE_4_GATES",
    }

class SwarmDebateSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    price: float = 65000.0
    stop_loss: Optional[float] = 64000.0
    take_profit: Optional[float] = 67500.0
    timeframe: Optional[str] = "15m"

@router.post("/ai/swarm/debate")
def trigger_multi_agent_swarm_debate(payload: SwarmDebateSchema):
    raise experimental_disabled_exception(
        "ai_swarm_debate",
        reason="REAL_MODEL_SIDECAR_NOT_CONFIGURED",
        message="The local AI Auditor sidecar is not configured; no synthetic consensus is exposed.",
    )

class BiometricTelemetrySchema(BaseModel):
    bpm: float
    hrv: float
    device_name: Optional[str] = "Apple Watch Ultra / BLE"

@router.get("/biometrics/status")
def get_biometric_telemetry_status():
    raise experimental_disabled_exception(
        "biometric_telemetry",
        reason="REAL_HARDWARE_NOT_CONFIGURED",
        message="Biometric telemetry is not connected and cannot influence execution.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.post("/biometrics/telemetry")
def update_biometric_telemetry(payload: BiometricTelemetrySchema):
    raise experimental_disabled_exception(
        "biometric_telemetry",
        reason="REAL_HARDWARE_NOT_CONFIGURED",
        message="Manual or synthetic biometric telemetry is not accepted by the production API.",
        provenance="UNVERIFIED_HARDWARE",
    )

from app.services.orderflow.footprint_engine import footprint_engine

@router.get("/orderflow/footprint")
def get_orderflow_footprint_bars(symbol: str = "BTCUSDT", limit: int = 20):
    return footprint_engine.get_footprint_response(symbol=symbol, limit=limit)

from app.services.orderflow.delta_heatmap import delta_heatmap_engine

@router.get("/orderflow/cvd")
def get_orderflow_cvd_series(symbol: str = "BTCUSDT", limit: int = 100):
    return delta_heatmap_engine.get_cvd_series(symbol=symbol, limit=limit)

@router.get("/orderflow/heatmap")
def get_orderflow_liquidity_heatmap(symbol: str = "BTCUSDT"):
    return delta_heatmap_engine.get_liquidity_heatmap(symbol=symbol)

from app.services.execution.fix_bridge import quickfix_dma_client

class FixOrderSchema(BaseModel):
    symbol: str = "ESM6"
    side: str = "BUY"
    qty: float = 1.0
    price: float = 5600.0

@router.get("/fix/status")
def get_quickfix_session_status():
    return quickfix_dma_client.get_session_status()

@router.post("/fix/order")
def execute_quickfix_dma_order(payload: FixOrderSchema):
    result = quickfix_dma_client.send_new_order_single(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        price=payload.price
    )
    return experimental_disabled_response(result) if result["status"] == "EXPERIMENTAL_DISABLED" else result

from app.services.p2p.mesh_node import p2p_mesh_node

class PeerConnectSchema(BaseModel):
    peer_id: str
    node_name: str
    pubkey: str
    endpoint: str
    role: Optional[str] = "FOLLOWER"

@router.get("/p2p/status")
def get_p2p_mesh_status():
    return p2p_mesh_node.get_mesh_status()

@router.post("/p2p/peers/connect")
def connect_p2p_peer(payload: PeerConnectSchema):
    p2p_mesh_node.add_peer(
        peer_id=payload.peer_id,
        node_name=payload.node_name,
        pubkey=payload.pubkey,
        endpoint=payload.endpoint,
        role=payload.role or "FOLLOWER"
    )
    return {"status": "CONNECTED", "peer_id": payload.peer_id}

from app.services.p2p.copy_engine import copy_trading_engine

class CopySignalCreateSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    entry_price: float = 64800.0
    stop_loss: float = 63900.0
    take_profit: float = 67500.0
    risk_pct: Optional[float] = 1.0
    notes: Optional[str] = ""

class CopySignalExecuteSchema(BaseModel):
    signal: Dict[str, Any]
    follower_equity: Optional[float] = None
    exchange: Optional[str] = "BINANCE"

@router.post("/p2p/copy/broadcast")
def broadcast_copy_signal(payload: CopySignalCreateSchema):
    return copy_trading_engine.create_master_signal(
        symbol=payload.symbol,
        side=payload.side,
        entry_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        risk_pct=payload.risk_pct or 1.0,
        notes=payload.notes or ""
    )

@router.post("/p2p/copy/execute")
def execute_follower_copy_trade(payload: CopySignalExecuteSchema):
    return copy_trading_engine.execute_copy_signal(
        signal=payload.signal,
        follower_equity=payload.follower_equity,
        exchange=payload.exchange or "BINANCE"
    )

@router.get("/p2p/copy/signals")
def get_p2p_copy_signals():
    return copy_trading_engine.get_signal_history()

from app.services.execution.multi_account_router import multi_account_allocator

class FanoutOrderSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    qty: float = 1.0
    price: float = 64800.0

@router.get("/accounts/list")
def list_multi_accounts():
    return {"accounts": multi_account_allocator.list_accounts()}

@router.post("/accounts/fanout")
def execute_fanout_order(payload: FanoutOrderSchema):
    return multi_account_allocator.fanout_order(payload.model_dump())

from app.api.mobile_bridge import mobile_companion_bridge

class MobilePairSchema(BaseModel):
    pairing_token: str
    device_id: str
    device_name: str
    platform: Optional[str] = "iOS"
    biometric_supported: Optional[bool] = True

class MobileRevokeSchema(BaseModel):
    device_id: str

@router.get("/mobile/pairing-qr")
def get_mobile_pairing_qr_data():
    return mobile_companion_bridge.generate_pairing_qr_payload()

@router.post("/mobile/pair")
def pair_mobile_device(payload: MobilePairSchema):
    try:
        return mobile_companion_bridge.verify_and_pair_device(
            pairing_token=payload.pairing_token,
            device_id=payload.device_id,
            device_name=payload.device_name,
            platform=payload.platform or "iOS",
            biometric_supported=payload.biometric_supported if payload.biometric_supported is not None else True
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mobile/devices")
def list_mobile_devices():
    return {"devices": mobile_companion_bridge.list_paired_devices()}

@router.post("/mobile/revoke")
def revoke_mobile_device(payload: MobileRevokeSchema):
    success = mobile_companion_bridge.revoke_device(payload.device_id)
    return {"status": "REVOKED" if success else "NOT_FOUND", "device_id": payload.device_id}

from app.services.biometrics.panic_switch import panic_kill_switch

class PanicTriggerSchema(BaseModel):
    source: Optional[str] = "WEARABLE_WATCH"
    reason: Optional[str] = "Trader emergency 1-tap activation"

class PanicDisarmSchema(BaseModel):
    pin_or_passkey: str

@router.post("/panic/trigger")
def trigger_panic_kill_switch(payload: PanicTriggerSchema):
    return panic_kill_switch.trigger_emergency_kill_switch(
        source=payload.source or "WEARABLE_WATCH",
        reason=payload.reason or "Trader emergency 1-tap activation"
    )

@router.post("/panic/disarm")
def disarm_panic_kill_switch(payload: PanicDisarmSchema):
    try:
        return panic_kill_switch.disarm_lockdown(payload.pin_or_passkey)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/panic/status")
def get_panic_kill_switch_status():
    return panic_kill_switch.get_lockdown_status()

class PasskeyVerifySchema(BaseModel):
    challenge: str
    credential_id: str
    assertion_signature: str

@router.get("/security/passkey/challenge")
def get_passkey_auth_challenge(action: Optional[str] = "HIGH_VALUE_ORDER"):
    raise experimental_disabled_exception(
        "webauthn_passkey",
        reason="REAL_WEBAUTHN_VERIFIER_NOT_CONFIGURED",
        message="Passkey challenge is disabled until authenticatorData and signature verification are implemented.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.post("/security/passkey/verify")
def verify_passkey_assertion_endpoint(payload: PasskeyVerifySchema):
    raise experimental_disabled_exception(
        "webauthn_passkey",
        reason="REAL_WEBAUTHN_VERIFIER_NOT_CONFIGURED",
        message="A length-only signature is never accepted as a production passkey assertion.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.get("/security/passkey/list")
def list_hardware_passkeys():
    raise experimental_disabled_exception(
        "webauthn_passkey",
        reason="REAL_WEBAUTHN_VERIFIER_NOT_CONFIGURED",
        message="Registered passkeys are hidden until a verified WebAuthn store exists.",
        provenance="UNVERIFIED_HARDWARE",
    )

class MCPQuerySchema(BaseModel):
    source: str
    query_type: Optional[str] = "default"
    params: Optional[Dict[str, Any]] = None

@router.get("/mcp/sources")
def get_mcp_sources():
    raise experimental_disabled_exception(
        "mcp_external_sources",
        reason="SOURCE_PROVENANCE_NOT_CONFIGURED",
        message="External MCP sources are disabled until source-linked retrieval is implemented.",
        provenance="UNVERIFIED_SOURCE",
    )

@router.post("/mcp/query")
def query_mcp_gateway(payload: MCPQuerySchema):
    raise experimental_disabled_exception(
        "mcp_external_sources",
        reason="SOURCE_PROVENANCE_NOT_CONFIGURED",
        message="MCP query results are disabled until each response has verifiable source provenance.",
        provenance="UNVERIFIED_SOURCE",
    )

@router.get("/mcp/sentiment/stream")
def get_mcp_sentiment_stream():
    raise experimental_disabled_exception(
        "mcp_sentiment_stream",
        reason="SOURCE_PROVENANCE_NOT_CONFIGURED",
        message="Sentiment streaming is disabled until a real source transport exists.",
        provenance="UNVERIFIED_SOURCE",
    )

from app.services.ai.reverse_skill import reverse_skill_engine

class PineScriptPayload(BaseModel):
    pine_code: str

class CSVAnalyzePayload(BaseModel):
    csv_content: Optional[str] = None
    trades: Optional[List[Dict[str, Any]]] = None

class DeployAgentPayload(BaseModel):
    agent_name: str
    strategy_config: Dict[str, Any]
    initial_capital: Optional[float] = 50000.0

@router.post("/reverse-skill/transpile-pinescript")
def transpile_pinescript_endpoint(payload: PineScriptPayload):
    try:
        return reverse_skill_engine.transpile_pinescript(payload.pine_code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pine Script transpilation error: {str(e)}")

@router.post("/reverse-skill/analyze-csv")
def analyze_csv_trades_endpoint(payload: CSVAnalyzePayload):
    try:
        content = payload.csv_content or payload.trades or ""
        return reverse_skill_engine.analyze_csv_trades(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV trade analysis error: {str(e)}")

@router.post("/reverse-skill/deploy-agent")
def deploy_reverse_skill_agent(payload: DeployAgentPayload):
    raise experimental_disabled_exception(
        "reverse_skill_deploy",
        reason="EXECUTION_AUTHORITY_NOT_AVAILABLE",
        message="Strategy transpilation is export-only; deploying an active agent is disabled.",
        provenance="SYNTHETIC_STRATEGY",
    )

class HardwareConfigurePayload(BaseModel):
    engine: str
    n_gpu_layers: int
    threads: int
    context_length: int

class SwarmFastEvalPayload(BaseModel):
    symbol: Optional[str] = "BTCUSDT"
    price: Optional[float] = 65000.0
    cvd_delta: Optional[float] = 420.0
    imbalance_ratio: Optional[float] = 3.2
    rsi: Optional[float] = 32.5
    account_drawdown_pct: Optional[float] = 1.2

@router.get("/hardware/gpu-status")
def get_hardware_gpu_status():
    raise experimental_disabled_exception(
        "local_llm_hardware",
        reason="REAL_MODEL_SIDECAR_NOT_CONFIGURED",
        message="GPU telemetry is not a verified inference signal in this release.",
    )

@router.post("/hardware/configure")
def configure_hardware_endpoint(payload: HardwareConfigurePayload):
    raise experimental_disabled_exception(
        "local_llm_hardware",
        reason="REAL_MODEL_SIDECAR_NOT_CONFIGURED",
        message="Hardware configuration is disabled until a real sidecar is installed and health-checked.",
    )

@router.post("/swarm/fast-eval")
def fast_eval_swarm_endpoint(payload: SwarmFastEvalPayload):
    raise experimental_disabled_exception(
        "local_llm_swarm",
        reason="REAL_MODEL_SIDECAR_NOT_CONFIGURED",
        message="Synthetic swarm evaluation cannot produce approval or execution guidance.",
    )

class ScanOpportunitiesPayload(BaseModel):
    chain: Optional[str] = "ethereum"
    min_profit_usd: Optional[float] = 50.0
    include_triangular: Optional[bool] = True

class FlashLoanSimPayload(BaseModel):
    chain: Optional[str] = "ethereum"
    protocol: Optional[str] = "BALANCER_VAULT"
    borrow_asset: Optional[str] = "WETH"
    amount_usd: Optional[float] = 100000.0
    route_spread_pct: Optional[float] = 0.58

class DeFAIEvalPayload(BaseModel):
    opportunity: Dict[str, Any]

@router.get("/dex/chains")
def get_dex_chains():
    raise experimental_disabled_exception(
        "dex_rpc",
        reason="REAL_RPC_TRANSPORT_NOT_CONFIGURED",
        message="No live chain/RPC state is exposed by the desktop product.",
        provenance="UNVERIFIED_CHAIN_DATA",
    )

@router.post("/dex/scan-opportunities")
def scan_dex_opportunities(payload: ScanOpportunitiesPayload):
    raise experimental_disabled_exception(
        "dex_opportunity_scan",
        reason="REAL_RPC_TRANSPORT_NOT_CONFIGURED",
        message="No actionable DEX opportunity is reported without verified pool state.",
        provenance="UNVERIFIED_CHAIN_DATA",
    )

@router.post("/dex/simulate-flash-loan")
def simulate_flash_loan_endpoint(payload: FlashLoanSimPayload):
    raise experimental_disabled_exception(
        "dex_flash_loan",
        reason="EXPERIMENTAL_DEFI_OUT_OF_SCOPE",
        message="Flash-loan simulation and execution are outside the production product boundary.",
        provenance="UNVERIFIED_CHAIN_DATA",
    )

@router.post("/dex/defai-evaluate")
def defai_evaluate_endpoint(payload: DeFAIEvalPayload):
    raise experimental_disabled_exception(
        "defai_execution_advisor",
        reason="EXPERIMENTAL_DEFI_OUT_OF_SCOPE",
        message="DeFAI must not produce an actionable execution decision.",
        provenance="UNVERIFIED_CHAIN_DATA",
    )

from app.services.matching.order_book import global_order_book
from app.services.fix.fix_gateway import fix_session
from app.services.fix.dma_router import dma_router

class FIXOrderSubmitPayload(BaseModel):
    symbol: Optional[str] = "BTCUSDT"
    side: str
    price: float
    qty: float
    order_type: Optional[str] = "LIMIT"
    tif: Optional[str] = "0"
    destination: Optional[str] = "INTERNAL_MATCHING_ENGINE"

class FIXOrderCancelPayload(BaseModel):
    cl_ord_id: str
    symbol: Optional[str] = "BTCUSDT"
    side: Optional[str] = "BUY"

class SimulateSweepPayload(BaseModel):
    side: str
    size: float

@router.get("/fix/sessions")
def get_fix_sessions():
    return {
        "status": "EXPERIMENTAL_DISABLED",
        "provenance": "FIX_SERIALIZATION_ONLY",
        "caveat": "The local FIX state machine is not connected to a broker transport; it cannot represent a logged-on venue session.",
        "transport_connected": False,
        "session_state": "DISCONNECTED",
        "sender_comp_id": fix_session.sender_comp_id,
        "target_comp_id": fix_session.target_comp_id,
        "begin_string": fix_session.begin_string,
        "out_seq_num": fix_session.out_seq_num,
        "in_seq_num": fix_session.in_seq_num,
        "heartbeat_interval_sec": fix_session.heartbeat_interval,
        "message_history": fix_session.message_history
    }

@router.post("/fix/session/logon")
def logon_fix_session():
    return experimental_disabled_response({
        "status": "EXPERIMENTAL_DISABLED",
        "provenance": "FIX_SERIALIZATION_ONLY",
        "caveat": "A FIX logon cannot be sent or acknowledged without a configured transport; no session state was changed.",
        "session_state": "DISCONNECTED",
        "raw_message": None,
    })

@router.post("/fix/order/submit")
def submit_fix_order(payload: FIXOrderSubmitPayload):
    try:
        result = dma_router.submit_order(
            symbol=payload.symbol or "BTCUSDT",
            side=payload.side,
            price=payload.price,
            qty=payload.qty,
            order_type=payload.order_type or "LIMIT",
            tif=payload.tif or "0",
            destination=payload.destination or "INTERNAL_MATCHING_ENGINE"
        )
        return experimental_disabled_response(result) if result["status"] == "EXPERIMENTAL_DISABLED" else result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order submission error: {str(e)}")

@router.post("/fix/order/cancel")
def cancel_fix_order(payload: FIXOrderCancelPayload):
    try:
        result = dma_router.cancel_order(
            cl_ord_id=payload.cl_ord_id,
            symbol=payload.symbol or "BTCUSDT",
            side=payload.side or "BUY"
        )
        return experimental_disabled_response(result) if result["status"] == "EXPERIMENTAL_DISABLED" else result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order cancellation error: {str(e)}")

@router.get("/orderbook/l2-snapshot")
def get_orderbook_l2_snapshot(depth: Optional[int] = 20):
    return global_order_book.get_l2_snapshot(depth=depth or 20)

@router.post("/orderbook/simulate-fill")
def simulate_orderbook_fill(payload: SimulateSweepPayload):
    return experimental_disabled_response({
        "status": "EXPERIMENTAL_DISABLED",
        "provenance": "IN_MEMORY_EXPLICIT_ORDERS",
        "caveat": "The global L2 book is not a venue feed or execution simulator; no sweep was attempted.",
        "sweep_side": payload.side.upper(),
        "requested_size": payload.size,
        "filled_size": 0.0,
        "unfilled_size": payload.size,
        "execution_vwap": None,
        "reference_bbo": None,
        "slippage_bps": None,
        "price_impact_usd": None,
        "depth_levels_swept": 0,
    })

class BiometricConnectPayload(BaseModel):
    device_id: str
    protocol: Optional[str] = "BLE"

class BiometricOverridePayload(BaseModel):
    challenge_signature: str
    passkey_user_id: Optional[str] = "TRADER_ADMIN"

@router.get("/biometrics/devices")
def get_biometric_devices():
    raise experimental_disabled_exception(
        "biometric_hardware",
        reason="REAL_HARDWARE_NOT_CONFIGURED",
        message="No wearable device inventory is asserted without a verified hardware transport.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.post("/biometrics/connect")
def connect_biometric_device(payload: BiometricConnectPayload):
    raise experimental_disabled_exception(
        "biometric_hardware",
        reason="REAL_HARDWARE_NOT_CONFIGURED",
        message="Wearable connection is disabled until BLE/HID discovery and session verification exist.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.get("/biometrics/live-telemetry")
def get_biometric_live_telemetry(bpm: Optional[float] = None, eda: Optional[float] = None):
    raise experimental_disabled_exception(
        "biometric_telemetry",
        reason="REAL_HARDWARE_NOT_CONFIGURED",
        message="Manual query parameters cannot create live biometric evidence.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.post("/biometrics/override-lockout")
def override_biometric_lockout(payload: BiometricOverridePayload):
    raise experimental_disabled_exception(
        "biometric_lockout_override",
        reason="REAL_WEBAUTHN_VERIFIER_NOT_CONFIGURED",
        message="Biometric lockout cannot be overridden through an unverified signature.",
        provenance="UNVERIFIED_HARDWARE",
    )

@router.get("/analytics/symbols")
def get_analytics_symbols():
    return duckdb_driver.get_symbol_breakdown()

from app.quant.mae_mfe import mae_mfe_analyzer

@router.get("/analytics/mae-mfe")
def get_mae_mfe_analytics(symbol: Optional[str] = None):
    return mae_mfe_analyzer.get_mae_mfe_scatter_data(symbol=symbol)

@router.get("/analytics/optimal-exits")
def get_optimal_exits_analytics(symbol: Optional[str] = None):
    data = mae_mfe_analyzer.get_mae_mfe_scatter_data(symbol=symbol)
    # Keep the legacy route, not its false implication of a validated optimizer.
    return {key: value for key, value in data.items() if key != "points"}

@router.get("/analytics/equity")
def get_analytics_equity():
    return duckdb_driver.get_equity_curve()

@router.get("/analytics/quant")
def get_analytics_quant():
    all_closed = [t for t in trade_read_adapter.list_trades(limit=10000, status="CLOSED") if t.get("pnl") is not None]
    pnls = [float(t["pnl"]) for t in all_closed]
    r_mults = [float(t["r_multiple"]) for t in all_closed if t.get("r_multiple") is not None]
    return quant_engine.calculate_full_performance_suite(pnls, r_multiples=r_mults if len(r_mults) == len(pnls) else None)

@router.get("/market/candles")
def get_market_candles(
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    limit: int = 200
):
    candles = duckdb_driver.get_candles(symbol=symbol, timeframe=timeframe, limit=limit)
    return candles

@router.get("/market/ticker")
def get_market_ticker():
    return {
        "symbol": binance_client.symbol,
        "price": binance_client.last_price,
        "event_age_ms": binance_client.event_age_ms,
        "timestamp": int(binance_client.last_tick_time * 1000) if binance_client.last_tick_time is not None else None,
        "status": binance_client.market_data_status,
        "market_data_enabled": binance_client.market_data_enabled,
    }

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "SNAPSHOT",
            "symbol": binance_client.symbol,
            "last_price": binance_client.last_price,
            "event_age_ms": binance_client.event_age_ms,
            "timestamp": int(binance_client.last_tick_time * 1000) if binance_client.last_tick_time is not None else None,
            "status": binance_client.market_data_status,
            "market_data_enabled": binance_client.market_data_enabled,
            "open_positions": binance_client._recalculate_open_positions(binance_client.last_price)
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)

# =============================================================================
# OPERATIONAL MAINTENANCE & SYSTEM TELEMETRY ENDPOINTS
# =============================================================================
from app.services.maintenance.log_sanitizer import log_sanitizer_engine
from app.services.maintenance.db_maintenance import db_maintenance_engine
from app.services.maintenance.worker import maintenance_worker
from app.core.config import settings

APP_START_TIME = time.time()

class SystemMaintenancePayload(BaseModel):
    checkpoint_wal: Optional[bool] = True
    compact_duckdb: Optional[bool] = False
    prune_logs: Optional[bool] = False
    backup_sqlite: Optional[bool] = False
    all_tasks: Optional[bool] = False

@router.get("/system/health/heartbeat")
def get_system_health_heartbeat():
    uptime = round(time.time() - APP_START_TIME, 2)
    return {
        "status": "HEALTHY",
        "service": settings.app_name,
        "version": settings.version,
        "uptime_seconds": uptime,
        "ipc_alive": True,
        "worker_status": maintenance_worker.stats.get("worker_status", "IDLE"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@router.post("/system/maintenance/run")
def run_manual_system_maintenance(payload: SystemMaintenancePayload):
    results = {}
    if payload.all_tasks:
        return maintenance_worker.execute_daily_maintenance()

    if payload.checkpoint_wal:
        results["wal_checkpoint"] = db_maintenance_engine.run_sqlite_checkpoint(truncate=True)
    if payload.compact_duckdb:
        db_maintenance_engine.enforce_duckdb_memory_limit(2048)
        results["cold_parquet_archival"] = db_maintenance_engine.archive_old_ticks_to_parquet(retention_days=7)
    if payload.prune_logs:
        results["log_rotation"] = log_sanitizer_engine.run_full_log_maintenance()
    if payload.backup_sqlite:
        results["shadow_backup"] = db_maintenance_engine.create_sqlite_shadow_backup(max_retention_days=30)

    results["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return results

@router.get("/system/storage/stats")
def get_system_storage_statistics():
    return db_maintenance_engine.get_storage_telemetry()


# ==============================================================================
# ZERO-AUTH PUBLIC MARKET DATA & SQLITE CANDLE CACHE ENDPOINTS
# ==============================================================================

@router.get("/market-data/search")
async def search_market_instruments(
    query: str = Query(..., min_length=1, max_length=64, description="Instrument name, symbol or ticker fragment"),
    limit: int = Query(20, ge=1, le=50, description="Maximum search results"),
):
    """Search exact public-provider instruments without selecting one implicitly.

    The response is a candidate list only. The client must preserve the
    selected provider symbol and require explicit user confirmation before
    requesting a quote or candle series.
    """
    cleaned_query = query.strip()
    if not cleaned_query or any(ord(character) < 32 for character in cleaned_query):
        return {
            "status": "INVALID_QUERY",
            "reason": "QUERY_INVALID",
            "query": cleaned_query,
            "results": [],
            "sources": [],
        }
    if not binance_client.market_data_enabled:
        return {
            "status": "UNAVAILABLE",
            "reason": "MARKET_DATA_DISABLED",
            "query": cleaned_query,
            "results": [],
            "sources": [],
        }
    return await public_market_fetcher.search_instruments(cleaned_query, limit=limit)

@router.get("/market-data/quote")
async def get_market_quote(
    symbol: str = Query("BTCUSDT", min_length=1, max_length=64),
    source: str = Query("auto", min_length=1, max_length=32),
):
    """Return one free quote with explicit freshness and source identity.

    An unavailable quote is a structured response so the journal can offer
    manual price entry without fabricating a value or switching to paper mode.
    Explicitly disabled market data remains unavailable and does not attempt a
    network request.
    """
    requested = symbol.strip().upper()
    if not requested or any(ord(character) < 32 for character in requested):
        raise HTTPException(status_code=422, detail="A symbol is required")
    if not binance_client.market_data_enabled:
        return {
            "requested_symbol": requested,
            "source_id": None,
            "source_symbol": None,
            "price": None,
            "status": "UNAVAILABLE",
            "price_kind": None,
            "observed_at": None,
            "reason": "MARKET_DATA_DISABLED",
            "free_source": True,
            "credentials_required": False,
        }

    quote = await public_market_fetcher.fetch_quote(requested, source=source)
    return quote.as_dict()

@router.get("/market-data/candles")
async def get_market_candles(
    symbol: str = Query("BTCUSDT", description="Market symbol (e.g. BTCUSDT, ETHUSDT, EURUSD, SPY)"),
    timeframe: str = Query("1h", description="Candle timeframe (e.g. 1m, 5m, 15m, 1h, 4h, 1d)"),
    limit: int = Query(500, ge=1, le=1000, description="Max candle records to return"),
    start_time: Optional[int] = Query(None, description="Start timestamp (ms)"),
    end_time: Optional[int] = Query(None, description="End timestamp (ms)"),
    force_refresh: bool = Query(False, description="Force fresh fetch from public APIs")
):
    """
    Returns historical OHLCV candlestick data for crypto or macro/forex assets.
    Operates with zero API keys using public REST gateways and local SQLite caching.
    """
    try:
        candles = await candles_repo.get_or_fetch_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start_ts=start_time,
            end_ts=end_time,
            force_refresh=force_refresh
        )
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles
        }
    except Exception as e:
        logger.error(f"[MARKET-DATA-API] Failed to fetch market candles for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch market candles: {str(e)}")


@router.get("/market-data/status")
def get_market_data_status():
    """Returns local candle cache status, total records, and supported public exchanges."""
    stats = candles_repo.get_cache_stats()
    return {
        "status": "HEALTHY",
        "auth_required": False,
        "live_stream_status": binance_client.market_data_status,
        "live_stream_enabled": binance_client.market_data_enabled,
        "cache_total_records": stats["total_records"],
        "symbols_count": stats["symbols_count"],
        "symbols_cached": stats["symbols"],
        "timeframes_cached": stats["timeframes"],
        "oldest_timestamp": stats["oldest_timestamp"],
        "newest_timestamp": stats["newest_timestamp"],
        "supported_exchanges": ["binance_public", "bybit_public", "yahoo_public", "stooq_public"],
        "supported_quote_sources": sorted(FREE_QUOTE_SOURCES),
        "paid_quote_sources_enabled": False,
        "quote_credentials_required": False,
    }


@router.post("/market-data/cache/clear")
def clear_market_data_cache(
    symbol: Optional[str] = Query(None, description="Symbol to clear"),
    timeframe: Optional[str] = Query(None, description="Timeframe to clear")
):
    """Clears cached candle records from local SQLite database."""
    deleted = candles_repo.clear_cache(symbol=symbol, timeframe=timeframe)
    return {
        "status": "CLEARED",
        "deleted_count": deleted,
        "symbol": symbol,
        "timeframe": timeframe
    }


# ==============================================================================
# MULTI-ASSET PORTFOLIO AGGREGATOR & RISK ANALYTICS ENDPOINTS
# ==============================================================================

@router.get("/portfolio/summary")
def get_portfolio_summary_endpoint(
    initial_balance: Optional[float] = Query(None, description="Custom starting equity balance")
):
    """
    Returns complete portfolio health, equity metrics, today's PnL,
    win rate, profit factor, max drawdown, and open R-risk exposure.
    """
    return portfolio_service.get_portfolio_summary(initial_balance=initial_balance)


@router.get("/portfolio/multi-asset-breakdown")
def get_portfolio_multi_asset_breakdown_endpoint():
    """
    Returns performance, volume, and trade metrics grouped by asset symbol
    across crypto, forex, commodities, and equities.
    """
    return portfolio_service.get_multi_asset_breakdown()


@router.get("/portfolio/equity-curve")
def get_portfolio_equity_curve_endpoint(
    initial_balance: Optional[float] = Query(None, description="Custom starting equity balance")
):
    """
    Returns chronological cumulative equity progression and peak-to-trough drawdown time-series.
    """
    return portfolio_service.get_equity_curve_series(initial_balance=initial_balance)


@router.get("/portfolio/heatmap")
def get_portfolio_heatmap_endpoint():
    """
    Returns daily calendar PnL series with normalized intensity for heatmap visualizers.
    """
    return portfolio_service.get_daily_pnl_heatmap()


class SetInitialBalanceSchema(BaseModel):
    initial_balance: float = 0.0


@router.post("/portfolio/set-initial-balance")
def set_portfolio_initial_balance_endpoint(payload: SetInitialBalanceSchema):
    """
    Explicitly configures and persists the user starting equity capital in SQLite settings.
    Recalculates equity and returns updated portfolio summary.
    """
    return portfolio_service.set_initial_balance(new_balance=payload.initial_balance)
