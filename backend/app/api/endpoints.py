from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.db.sqlite_driver import sqlite_driver
from app.db.duckdb_driver import duckdb_driver
from app.db.sync_pipeline import sync_pipeline
from app.websocket.connection_manager import ws_manager
from app.websocket.binance_client import binance_client
from app.quant.quant_engine import quant_engine

router = APIRouter(prefix="/api/v1")

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