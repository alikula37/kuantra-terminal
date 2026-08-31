from app.api.webhook_tv import webhook_router
from app.api.plugin_endpoints import router as plugin_router
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time
from datetime import datetime
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.db.sync_pipeline import sync_pipeline
from app.db.repositories.candles_repo import candles_repo
from app.services.market_data.public_fetcher import public_market_fetcher
from app.services.portfolio_service import portfolio_service
from app.websocket.connection_manager import ws_manager
from app.websocket.binance_client import binance_client
from app.quant.quant_engine import quant_engine

router = APIRouter(prefix="/api/v1")
router.include_router(webhook_router)
router.include_router(plugin_router)

class TradeCreateSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    entry_price: float
    qty: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: Optional[str] = ""

class TradeCloseSchema(BaseModel):
    exit_price: float
    exit_time: Optional[str] = None
    commission: Optional[float] = 0.0

@router.get("/trades")
def list_trades(
    limit: int = 100,
    offset: int = 0,
    symbol: Optional[str] = None,
    status: Optional[str] = None
):
    return sqlite_driver.list_trades(limit=limit, offset=offset, symbol=symbol, status=status)

@router.get("/trades/open")
def get_open_trades():
    return sqlite_driver.get_open_trades()

@router.get("/trades/{trade_id}")
def get_trade(trade_id: str):
    trade = sqlite_driver.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

@router.post("/trades")
def create_trade(trade: TradeCreateSchema):
    now = datetime.utcnow().isoformat()
    trade_data = {
        "symbol": trade.symbol.upper(),
        "side": trade.side.upper(),
        "entry_price": trade.entry_price,
        "qty": trade.qty,
        "stop_loss": trade.stop_loss,
        "take_profit": trade.take_profit,
        "entry_time": now,
        "status": "OPEN",
        "notes": trade.notes,
        "pnl": 0.0,
        "commission": 0.0
    }
    saved = sync_pipeline.record_and_sync_trade(trade_data)
    return saved

@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: str, close_data: TradeCloseSchema):
    existing = sqlite_driver.get_trade(trade_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    entry_price = float(existing["entry_price"])
    qty = float(existing["qty"])
    side = existing["side"].upper()
    exit_price = close_data.exit_price
    sl = float(existing["stop_loss"]) if existing.get("stop_loss") else None

    if side in ("BUY", "LONG"):
        pnl = (exit_price - entry_price) * qty - (close_data.commission or 0.0)
        r_unit = (entry_price - sl) if sl and (entry_price > sl) else None
    else:
        pnl = (entry_price - exit_price) * qty - (close_data.commission or 0.0)
        r_unit = (sl - entry_price) if sl and (sl > entry_price) else None

    r_multiple = (pnl / (r_unit * qty)) if (r_unit and qty > 0) else None

    update_payload = {
        "status": "CLOSED",
        "exit_price": exit_price,
        "exit_time": close_data.exit_time or datetime.utcnow().isoformat(),
        "pnl": round(pnl, 2),
        "r_multiple": round(r_multiple, 2) if r_multiple is not None else None,
        "commission": close_data.commission or 0.0
    }

    updated = sync_pipeline.record_and_sync_trade({"id": trade_id, **update_payload})
    return updated

@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: str):
    success = sqlite_driver.delete_trade(trade_id)
    if not success:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {"status": "deleted", "id": trade_id}

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
    speed: float

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
            data = json.loads(raw_msg)
            action = data.get("action")
            
            if action == "INIT":
                trade_id = data.get("trade_id", "TRD-DEFAULT")
                session_dict = replay_service.create_session_for_trade(trade_id)
                session_id = session_dict["session_id"]
                await websocket.send_json({"type": "REPLAY_STATE", "data": session_dict})
            elif action == "STEP" and session_id:
                step_dir = data.get("direction", 1)
                res = replay_service.step(session_id, direction=step_dir)
                await websocket.send_json({"type": "REPLAY_STATE", "data": res})
            elif action == "SEEK" and session_id:
                idx = data.get("index", 0)
                res = replay_service.seek(session_id, target_index=idx)
                await websocket.send_json({"type": "REPLAY_STATE", "data": res})
            elif action == "SPEED" and session_id:
                speed_val = data.get("speed", 1.0)
                res = replay_service.set_speed(session_id, speed=speed_val)
                await websocket.send_json({"type": "REPLAY_STATE", "data": res})
    except WebSocketDisconnect:
        pass
    except Exception:
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
            checked_rule_ids=payload.checked_rule_ids
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
        "queued_crashes": telemetry_manager.get_queued_crashes_count()
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
    ai_mode: Optional[str] = "local_gguf"
    api_key: Optional[str] = None
    provider: Optional[str] = "openai"
    trading_mode: Optional[str] = "paper"
    paper_balance: Optional[float] = 100000.0
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
    settings_service.store_vault_secret(key, val)
    return {"status": "STORED", "key": key.upper()}

@router.get("/onboarding/status")
def get_onboarding_status():
    cfg = settings_service.get_settings()
    hw = hardware_detector.detect_hardware()
    return {
        "first_boot_completed": cfg["first_boot_completed"],
        "config": cfg,
        "ai_mode": cfg.get("ai_mode", "local_gguf"),
        "hardware": hw
    }

@router.post("/onboarding/complete")
def complete_onboarding(payload: OnboardingCompleteSchema):
    updates = {
        "first_boot_completed": True,
        "trading_mode": payload.trading_mode or "paper",
        "paper_balance": payload.paper_balance if payload.paper_balance is not None else 100000.0,
        "active_theme": payload.active_theme or "dark",
        "active_locale": payload.active_locale or "en",
        "ai_mode": payload.ai_mode or "local_gguf"
    }
    cfg = settings_service.update_settings(updates)

    # Store individual api_keys dict if provided
    if payload.api_keys:
        for k, v in payload.api_keys.items():
            if k and v:
                settings_service.store_vault_secret(k, v)

    # Backward compatibility with single api_key
    if payload.api_key:
        provider_name = payload.provider or "OPENAI"
        settings_service.store_vault_secret(f"{provider_name.upper()}_API_KEY", payload.api_key)

    if payload.ai_mode == "local_gguf":
        model_downloader.start_download(mock_mode=True)

    return {"status": "SUCCESS", "first_boot_completed": True, "ai_mode": cfg.get("ai_mode"), "config": cfg}

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
    if adapter_key == "twelvedata":
        from app.services.data_adapters.twelvedata_adapter import twelvedata_adapter
        return twelvedata_adapter.subscribe(payload.symbols)
    elif adapter_key == "polygon":
        from app.services.data_adapters.polygon_adapter import polygon_adapter
        return polygon_adapter.subscribe(payload.symbols)
    return {"status": "SUCCESS", "adapter": adapter_key, "symbols": payload.symbols}

from app.services.execution.order_router import order_router
from app.services.execution.risk_interceptor import risk_interceptor

class LiveOrderSchema(BaseModel):
    symbol: str
    side: str
    qty: float
    price: float
    exchange: Optional[str] = "BINANCE"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

@router.post("/execution/order")
def execute_live_order(payload: LiveOrderSchema):
    return order_router.route_order(payload.model_dump())

@router.get("/execution/status")
def get_execution_guardrail_status():
    return {
        "guardrails_active": risk_interceptor.guardrails_active,
        "max_tilt_score": risk_interceptor.max_allowed_tilt_score,
        "supported_venues": ["BINANCE_FUTURES", "OKX_V5"]
    }

from app.services.ai.agent_swarm import swarm_consensus_engine

class SwarmDebateSchema(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"
    price: float = 65000.0
    stop_loss: Optional[float] = 64000.0
    take_profit: Optional[float] = 67500.0
    timeframe: Optional[str] = "15m"

@router.post("/ai/swarm/debate")
def trigger_multi_agent_swarm_debate(payload: SwarmDebateSchema):
    return swarm_consensus_engine.conduct_debate(payload.model_dump())

from app.services.biometrics.watch_bridge import biometric_watch_bridge

class BiometricTelemetrySchema(BaseModel):
    bpm: float
    hrv: float
    device_name: Optional[str] = "Apple Watch Ultra / BLE"

@router.get("/biometrics/status")
def get_biometric_telemetry_status():
    return biometric_watch_bridge.get_biometric_state()

@router.post("/biometrics/telemetry")
def update_biometric_telemetry(payload: BiometricTelemetrySchema):
    return biometric_watch_bridge.update_telemetry(
        bpm=payload.bpm,
        hrv=payload.hrv,
        device_name=payload.device_name
    )

from app.services.orderflow.footprint_engine import footprint_engine

@router.get("/orderflow/footprint")
def get_orderflow_footprint_bars(symbol: str = "BTCUSDT", limit: int = 20):
    return {
        "symbol": symbol.upper(),
        "bars": footprint_engine.get_footprint_candles(symbol=symbol, limit=limit)
    }

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
    return quickfix_dma_client.send_new_order_single(
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        price=payload.price
    )

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
    follower_equity: Optional[float] = 100000.0
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

from app.services.security.passkey_vault import webauthn_passkey_vault

class PasskeyVerifySchema(BaseModel):
    challenge: str
    credential_id: str
    assertion_signature: str

@router.get("/security/passkey/challenge")
def get_passkey_auth_challenge(action: Optional[str] = "HIGH_VALUE_ORDER"):
    return webauthn_passkey_vault.generate_auth_challenge(action=action or "HIGH_VALUE_ORDER")

@router.post("/security/passkey/verify")
def verify_passkey_assertion_endpoint(payload: PasskeyVerifySchema):
    is_valid = webauthn_passkey_vault.verify_passkey_assertion(
        challenge=payload.challenge,
        credential_id=payload.credential_id,
        assertion_signature=payload.assertion_signature
    )
    if not is_valid:
        raise HTTPException(status_code=401, detail="Hardware Passkey verification failed.")
    return {"status": "PASSED", "message": "FIDO2 Hardware Challenge Cleared."}

@router.get("/security/passkey/list")
def list_hardware_passkeys():
    return {"passkeys": webauthn_passkey_vault.list_passkeys()}

from app.services.mcp.client_gateway import mcp_gateway

class MCPQuerySchema(BaseModel):
    source: str
    query_type: Optional[str] = "default"
    params: Optional[Dict[str, Any]] = None

@router.get("/mcp/sources")
def get_mcp_sources():
    return mcp_gateway.list_sources()

@router.post("/mcp/query")
def query_mcp_gateway(payload: MCPQuerySchema):
    try:
        res = mcp_gateway.dispatch_query(
            source=payload.source,
            query_type=payload.query_type or "default",
            params=payload.params or {}
        )
        return {"status": "SUCCESS", "source": payload.source, "data": res}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/mcp/sentiment/stream")
def get_mcp_sentiment_stream():
    return mcp_gateway.get_sentiment_stream()

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
    try:
        return reverse_skill_engine.deploy_agent(
            agent_name=payload.agent_name,
            strategy_config=payload.strategy_config,
            initial_capital=payload.initial_capital if payload.initial_capital is not None else 50000.0
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Agent deployment error: {str(e)}")

from app.services.ai.hardware_engine import hardware_engine, gguf_inference_engine
from app.services.ai.accelerated_swarm import accelerated_swarm

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
    return hardware_engine.get_realtime_metrics()

@router.post("/hardware/configure")
def configure_hardware_endpoint(payload: HardwareConfigurePayload):
    try:
        return hardware_engine.configure_hardware(
            engine=payload.engine,
            n_gpu_layers=payload.n_gpu_layers,
            threads=payload.threads,
            context_length=payload.context_length
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/swarm/fast-eval")
def fast_eval_swarm_endpoint(payload: SwarmFastEvalPayload):
    try:
        return accelerated_swarm.evaluate_market_state(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Accelerated Swarm evaluation error: {str(e)}")

from app.services.dex.rpc_gateway import rpc_gateway
from app.services.dex.arbitrage_engine import arbitrage_engine
from app.services.dex.defai_agent import defai_agent

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
    return rpc_gateway.list_chains()

@router.post("/dex/scan-opportunities")
def scan_dex_opportunities(payload: ScanOpportunitiesPayload):
    try:
        chain = payload.chain or "ethereum"
        spatial_opps = arbitrage_engine.scan_spatial_opportunities(chain=chain)
        tri_opps = arbitrage_engine.scan_triangular_opportunities(chain=chain) if payload.include_triangular else []
        all_opps = spatial_opps + tri_opps
        return {
            "chain": chain.upper(),
            "total_opportunities": len(all_opps),
            "opportunities": all_opps,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"DEX scan error: {str(e)}")

@router.post("/dex/simulate-flash-loan")
def simulate_flash_loan_endpoint(payload: FlashLoanSimPayload):
    try:
        return arbitrage_engine.simulate_flash_loan(
            chain=payload.chain or "ethereum",
            protocol=payload.protocol or "BALANCER_VAULT",
            borrow_asset=payload.borrow_asset or "WETH",
            amount_usd=payload.amount_usd or 100000.0,
            route_spread_pct=payload.route_spread_pct or 0.58
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Flash loan simulation error: {str(e)}")

@router.post("/dex/defai-evaluate")
def defai_evaluate_endpoint(payload: DeFAIEvalPayload):
    try:
        return defai_agent.evaluate_opportunity(opportunity=payload.opportunity)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"DeFAI evaluation error: {str(e)}")

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
        "status": fix_session.state,
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
    raw_logon = fix_session.create_logon()
    # Confirm logon
    fix_session.process_incoming("8=FIX.4.4|9=45|35=A|49=CME_DMA_GATEWAY|56=KUANTRA_DMA|34=1|52=20260215-12:00:00.000|10=084|")
    return {
        "status": "LOGON_COMPLETED",
        "session_state": fix_session.state,
        "raw_message": raw_logon
    }

@router.post("/fix/order/submit")
def submit_fix_order(payload: FIXOrderSubmitPayload):
    try:
        return dma_router.submit_order(
            symbol=payload.symbol or "BTCUSDT",
            side=payload.side,
            price=payload.price,
            qty=payload.qty,
            order_type=payload.order_type or "LIMIT",
            tif=payload.tif or "0",
            destination=payload.destination or "INTERNAL_MATCHING_ENGINE"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order submission error: {str(e)}")

@router.post("/fix/order/cancel")
def cancel_fix_order(payload: FIXOrderCancelPayload):
    try:
        return dma_router.cancel_order(
            cl_ord_id=payload.cl_ord_id,
            symbol=payload.symbol or "BTCUSDT",
            side=payload.side or "BUY"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order cancellation error: {str(e)}")

@router.get("/orderbook/l2-snapshot")
def get_orderbook_l2_snapshot(depth: Optional[int] = 20):
    return global_order_book.get_l2_snapshot(depth=depth or 20)

@router.post("/orderbook/simulate-fill")
def simulate_orderbook_fill(payload: SimulateSweepPayload):
    try:
        return global_order_book.simulate_sweep(side=payload.side, size=payload.size)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order book sweep error: {str(e)}")

from app.services.biometrics.hardware_driver import hardware_biometrics_driver
from app.services.biometrics.stress_interceptor import stress_interceptor

class BiometricConnectPayload(BaseModel):
    device_id: str
    protocol: Optional[str] = "BLE"

class BiometricOverridePayload(BaseModel):
    challenge_signature: str
    passkey_user_id: Optional[str] = "TRADER_ADMIN"

@router.get("/biometrics/devices")
def get_biometric_devices():
    return {
        "devices": hardware_biometrics_driver.scan_devices(),
        "active_device_id": hardware_biometrics_driver.active_device_id,
        "is_connected": hardware_biometrics_driver.is_connected
    }

@router.post("/biometrics/connect")
def connect_biometric_device(payload: BiometricConnectPayload):
    try:
        return hardware_biometrics_driver.connect_device(
            device_id=payload.device_id,
            protocol=payload.protocol or "BLE"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Biometric connect error: {str(e)}")

@router.get("/biometrics/live-telemetry")
def get_biometric_live_telemetry(bpm: Optional[float] = None, eda: Optional[float] = None):
    try:
        return stress_interceptor.evaluate_live_state(manual_bpm=bpm, manual_eda=eda)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Biometric telemetry error: {str(e)}")

@router.post("/biometrics/override-lockout")
def override_biometric_lockout(payload: BiometricOverridePayload):
    try:
        res = stress_interceptor.override_lockout_fido2(
            challenge_signature=payload.challenge_signature,
            passkey_user_id=payload.passkey_user_id or "TRADER_ADMIN"
        )
        if res.get("status") == "OVERRIDE_REJECTED":
            raise HTTPException(status_code=403, detail=res.get("reason"))
        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Override error: {str(e)}")

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
    return {
        "recommended_target_r": data["recommended_target_r"],
        "average_exit_efficiency_pct": data["average_exit_efficiency_pct"],
        "trades_left_money_on_table": data["trades_left_money_on_table"],
        "stop_loss_sensitivities": data["stop_loss_sensitivities"]
    }

@router.get("/analytics/equity")
def get_analytics_equity():
    return duckdb_driver.get_equity_curve()

@router.get("/analytics/quant")
def get_analytics_quant():
    all_closed = [t for t in sqlite_driver.list_trades(limit=10000, status="CLOSED") if t.get("pnl") is not None]
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
        "latency_ms": binance_client.latency_ms,
        "timestamp": int(binance_client.last_tick_time * 1000)
    }

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "SNAPSHOT",
            "symbol": binance_client.symbol,
            "last_price": binance_client.last_price,
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
        "cache_total_records": stats["total_records"],
        "symbols_count": stats["symbols_count"],
        "symbols_cached": stats["symbols"],
        "timeframes_cached": stats["timeframes"],
        "oldest_timestamp": stats["oldest_timestamp"],
        "newest_timestamp": stats["newest_timestamp"],
        "supported_exchanges": ["binance_public", "bybit_public", "yahoo_public", "stooq_public"]
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