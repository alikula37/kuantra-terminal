"""Historical, recorded one-minute *bar approximation*, not tick/fill replay."""

import time
import uuid
from typing import Any

from app.quant.candle_evidence import (
    CandleEvidence, EvidenceError, excursion_metrics, finite_number,
    load_candle_evidence, provenance,
)
from app.services.trade_read_adapter import trade_read_adapter


class ReplaySession:
    """A read-only evidence snapshot; cursor state never changes the source trade."""

    def __init__(self, session_id: str, evidence: CandleEvidence):
        self.session_id = session_id
        self.symbol = evidence.trade["symbol"]
        self.candles, self.trade = evidence.candles, evidence.trade
        self.entry_index, self.exit_index = evidence.entry_index, evidence.exit_index
        self.current_index = self.entry_index
        self.speed_multiplier = 1.0
        self.is_playing = False
        self.created_at = time.time()
        self.market_context = evidence.market_context
        self.replay_fingerprint = self.market_context["fingerprint_sha256"]

    def to_dict(self) -> dict[str, Any]:
        current = self.candles[self.current_index]
        # A frame shows a completed bar. At the exit bar the recorded trade has
        # closed, including intrabar exits; boundary uncertainty is disclosed.
        phase = "PRE_ENTRY" if self.current_index < self.entry_index else "CLOSED" if self.current_index >= self.exit_index else "ACTIVE"
        started, closed = phase != "PRE_ENTRY", phase == "CLOSED"
        direction = 1 if self.trade["side"] in ("BUY", "LONG") else -1
        metrics = {"mae_r": None, "mfe_r": None, "r_multiple": None}
        if started:
            metrics = excursion_metrics(
                self.trade, self.candles[self.entry_index:min(self.current_index, self.exit_index) + 1], closed=closed,
            )
        trade_state = {
            "trade_id": str(self.trade["id"]), "symbol": self.symbol,
            "side": self.trade["side"], "entry_price": self.trade["entry_price"],
            "current_price": current["close"], "exit_price": self.trade["exit_price"],
            "qty": self.trade["qty"], "stop_loss": self.trade["stop_loss"],
            "take_profit": self.trade["take_profit"], "risk_unit": self.trade["risk_unit"],
            "risk_reason": self.trade["risk_reason"], "phase": phase,
            "is_active": phase == "ACTIVE", "is_past_exit": closed,
            "unrealized_pnl": finite_number(direction * (current["close"] - self.trade["entry_price"]) * self.trade["qty"]) if phase == "ACTIVE" else None,
            "realized_pnl": self.trade["pnl"] if closed else None,
            "r_multiple": metrics["r_multiple"], "mae_r": metrics["mae_r"], "mfe_r": metrics["mfe_r"],
            "entry_index": self.entry_index, "exit_index": self.exit_index,
        }
        return {
            "status": "READY", "reason": None, "message": None, "provenance": provenance(),
            "session_id": self.session_id, "symbol": self.symbol, "total_bars": len(self.candles),
            "current_index": self.current_index, "entry_index": self.entry_index, "exit_index": self.exit_index,
            "speed_multiplier": self.speed_multiplier, "is_playing": self.is_playing,
            "replay_fingerprint": self.replay_fingerprint,
            "market_context": self.market_context,
            "current_candle": current, "trade": trade_state, "visible_candles": self.candles[:self.current_index + 1],
        }


class ReplayService:
    def __init__(self, trade_reader=None):
        self.sessions: dict[str, ReplaySession] = {}
        self.trade_reader = trade_reader or trade_read_adapter

    def create_session_for_trade(self, trade_id: str, lookback_bars: int = 30, lookforward_bars: int = 20) -> dict[str, Any]:
        try:
            try:
                trade = self.trade_reader.get_trade(trade_id)
            except Exception as exc:
                raise EvidenceError("TRADE_STORE_UNAVAILABLE", "The recorded trade store could not be read.", "UNAVAILABLE") from exc
            evidence = load_candle_evidence(trade, lookback_bars=lookback_bars, lookforward_bars=lookforward_bars)
        except EvidenceError as error:
            return {
                **error.to_dict(), "session_id": None, "symbol": None,
                "total_bars": 0, "current_index": None, "entry_index": None, "exit_index": None,
                "speed_multiplier": 1.0, "is_playing": False,
                "current_candle": None, "trade": None, "visible_candles": [],
            }
        session_id = f"REP-{uuid.uuid4().hex}"
        session = ReplaySession(session_id, evidence)
        # These UI snapshots are not a canonical ledger. Bound memory in the
        # long-running desktop; evicted sessions return an explicit 404 on use.
        if len(self.sessions) >= 32:
            del self.sessions[next(iter(self.sessions))]
        self.sessions[session_id] = session
        return session.to_dict()

    def _require_session(self, session_id: str) -> ReplaySession:
        session = self.sessions.get(session_id)
        if session is None:
            raise ValueError("Replay session not found")
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self.sessions.get(session_id)
        return session.to_dict() if session else None

    def step(self, session_id: str, direction: int = 1) -> dict[str, Any]:
        session = self._require_session(session_id)
        return self.seek(session_id, session.current_index + direction)

    def seek(self, session_id: str, target_index: int) -> dict[str, Any]:
        session = self._require_session(session_id)
        session.current_index = max(0, min(len(session.candles) - 1, target_index))
        if session.current_index == len(session.candles) - 1:
            session.is_playing = False
        return session.to_dict()

    def set_speed(self, session_id: str, speed: float) -> dict[str, Any]:
        session = self._require_session(session_id)
        if finite_number(speed) is None:
            raise ValueError("Replay speed must be finite")
        session.speed_multiplier = max(0.25, min(20.0, speed))
        return session.to_dict()

    def set_playing(self, session_id: str, is_playing: bool) -> dict[str, Any]:
        session = self._require_session(session_id)
        session.is_playing = bool(is_playing) and session.current_index < len(session.candles) - 1
        return session.to_dict()


replay_service = ReplayService()
