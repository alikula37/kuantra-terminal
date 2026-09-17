"""Historical, recorded one-minute *bar approximation*, not tick/fill replay."""

import time
import uuid
from typing import Any

from app.quant.candle_evidence import (
    CandleEvidence, EvidenceError, excursion_metrics, finite_number,
    load_candle_evidence, provenance,
)
from app.quant.open_position_evidence import (
    MAX_OPEN_REVIEW_BARS, OpenPositionEvidence, OpenReviewError,
    declared_provider_identity, load_open_position_evidence,
)
from app.quant.trade_plan_reference import (
    classify_origin, close_evidence, close_source_class, plan_reference,
)
from app.services.trade_read_adapter import trade_read_adapter


class ReplaySession:
    """A read-only evidence snapshot; cursor state never changes the source trade."""

    def __init__(
        self,
        session_id: str,
        evidence: CandleEvidence,
        *,
        plan: dict[str, Any] | None = None,
        origin_class: str = "UNKNOWN",
    ):
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
        self.plan = plan
        self.origin_class = origin_class
        self.close_class = close_source_class(self.trade, origin_class)

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
            "review_mode": "CLOSED",
            "plan": self.plan,
            "origin_class": self.origin_class,
            # The close marker is only disclosed once the cursor reaches the exit
            # bar; earlier frames must not leak the future outcome.
            "close_evidence": close_evidence(self.trade, self.origin_class) if closed else None,
            "current_candle": current, "trade": trade_state, "visible_candles": self.candles[:self.current_index + 1],
        }


class OpenReviewSession:
    """Read-only open position snapshot over the existing market candle cache.

    No exit data, no performance numbers and no writes: stepping and seeking
    only move the cursor over the already-recorded candles.
    """

    def __init__(
        self,
        session_id: str,
        evidence: OpenPositionEvidence,
        *,
        plan: dict[str, Any] | None = None,
        origin_class: str = "UNKNOWN",
    ):
        self.session_id = session_id
        self.symbol = evidence.symbol
        self.candles = evidence.candles
        self.trade = evidence.trade
        self.entry_index = evidence.entry_index
        self.exit_index = None
        self.current_index = 0
        self.speed_multiplier = 1.0
        self.is_playing = False
        self.created_at = time.time()
        self.plan = plan
        self.origin_class = origin_class
        self.evidence_block = {
            "history_status": evidence.history_status,
            "timeframe": evidence.timeframe,
            "entry_bar_present": evidence.entry_bar_present,
            **evidence.coverage,
            **evidence.freshness,
            "provider": evidence.provenance.get("provider"),
            "provider_symbol": evidence.provenance.get("provider_symbol"),
            "declared_symbol": evidence.provenance.get("declared_symbol"),
            "identity_verified": evidence.provenance.get("identity_verified", False),
            "identity_note": evidence.provenance.get("identity_note"),
            "instrument": evidence.provenance.get("instrument"),
            "store": evidence.provenance.get("store"),
            "fetched_at": evidence.provenance.get("fetched_at"),
            "provider_note": evidence.provenance.get("provider_note"),
        }

    @staticmethod
    def _as_candle(candle: dict[str, Any]) -> dict[str, Any]:
        """The chart consumes the replay candle shape (``time``), not cache keys."""

        return {
            "time": int(candle["timestamp"]),
            "open": candle["open"], "high": candle["high"],
            "low": candle["low"], "close": candle["close"], "volume": candle["volume"],
        }

    def to_dict(self) -> dict[str, Any]:
        current = self.candles[self.current_index]
        phase = "PRE_ENTRY" if self.current_index < self.entry_index else "ACTIVE"
        direction = 1 if self.trade["side"] in ("BUY", "LONG") else -1
        trade_state = {
            "trade_id": str(self.trade["id"]), "symbol": self.symbol,
            "side": self.trade["side"], "entry_price": self.trade["entry_price"],
            "current_price": current["close"], "exit_price": None,
            "qty": self.trade.get("qty"), "stop_loss": self.trade.get("stop_loss"),
            "take_profit": self.trade.get("take_profit"),
            "risk_unit": None, "risk_reason": None, "phase": phase,
            "is_active": phase == "ACTIVE", "is_past_exit": False,
            # The open review deliberately produces no performance numbers.
            "unrealized_pnl": None, "realized_pnl": None,
            "r_multiple": None, "mae_r": None, "mfe_r": None,
            "entry_index": self.entry_index, "exit_index": None,
            "_direction": direction,
        }
        block = self.evidence_block
        return {
            "status": "READY", "reason": None, "message": None,
            "review_mode": "OPEN",
            "provenance": {
                "quality": "BAR_APPROXIMATION", "source": block.get("store", "SQLITE_CHART_CACHE"),
                "source_verified": False, "timeframe": block.get("timeframe"),
            },
            "session_id": self.session_id, "symbol": self.symbol,
            "total_bars": len(self.candles),
            "current_index": self.current_index, "entry_index": self.entry_index, "exit_index": None,
            "speed_multiplier": self.speed_multiplier, "is_playing": self.is_playing,
            "market_context": {
                "symbol": self.symbol,
                "venue": "DECLARED_PROVIDER",
                "feed": block.get("provider") or "UNKNOWN",
                "timeframe": block.get("timeframe"),
                "bar_count": len(self.candles),
                "sequence_gap_count": block.get("gap_count", 0),
                "complete_trade_window": block.get("history_status") == "FULL_SINCE_ENTRY",
            },
            "open_review": block,
            "plan": self.plan, "origin_class": self.origin_class, "close_evidence": None,
            "current_candle": self._as_candle(current), "trade": trade_state,
            "visible_candles": [self._as_candle(candle)
                                for candle in self.candles[:self.current_index + 1]],
        }


class ReplayService:
    def __init__(self, trade_reader=None, tracking_reader=None, provider_fetcher=None):
        self.sessions: dict[str, Any] = {}
        self.trade_reader = trade_reader or trade_read_adapter
        if tracking_reader is None:
            from app.db.sqlite_driver import sqlite_driver
            from app.services.local_tracking import LocalTrackingService

            tracking_reader = LocalTrackingService(sqlite_driver)
        self.tracking_reader = tracking_reader
        self.provider_fetcher = provider_fetcher or _default_provider_fetcher

    def create_session_for_trade(self, trade_id: str, lookback_bars: int = 30, lookforward_bars: int = 20) -> dict[str, Any]:
        try:
            try:
                trade = self.trade_reader.get_trade(trade_id)
            except Exception as exc:
                raise EvidenceError("TRADE_STORE_UNAVAILABLE", "The recorded trade store could not be read.", "UNAVAILABLE") from exc
            if trade and str(trade.get("status") or "").upper() == "OPEN":
                return self._open_review_state(trade)
            evidence = load_candle_evidence(trade, lookback_bars=lookback_bars, lookforward_bars=lookforward_bars)
        except EvidenceError as error:
            return {
                **error.to_dict(), "session_id": None, "symbol": None,
                "total_bars": 0, "current_index": None, "entry_index": None, "exit_index": None,
                "speed_multiplier": 1.0, "is_playing": False,
                "plan": None, "close_evidence": None, "origin_class": None,
                "current_candle": None, "trade": None, "visible_candles": [],
            }
        origin_class = classify_origin(self._trade_events(trade_id))
        plan = self._plan_reference(trade)
        session_id = f"REP-{uuid.uuid4().hex}"
        session = ReplaySession(session_id, evidence, plan=plan, origin_class=origin_class)
        # These UI snapshots are not a canonical ledger. Bound memory in the
        # long-running desktop; evicted sessions return an explicit 404 on use.
        if len(self.sessions) >= 32:
            del self.sessions[next(iter(self.sessions))]
        self.sessions[session_id] = session
        return session.to_dict()

    @staticmethod
    def _open_review_unmatched_payload(trade: dict[str, Any]) -> dict[str, Any]:
        """No provider match is established yet: show why, never cache rows."""

        declared = declared_provider_identity(trade)
        symbol = str(trade.get("symbol") or "").upper() or None
        if declared is None:
            reason = "PROVIDER_NOT_DECLARED"
            message = ("The trade has no declared free public provider and instrument symbol; "
                       "a chart match cannot be established.")
        else:
            reason = "PROVIDER_MATCH_REQUIRED"
            message = ("No session-verified candles exist for this provider identity yet; "
                       "refresh to fetch them from the declared provider.")
        return {
            "status": "NO_DATA", "reason": reason, "message": message,
            "review_mode": "OPEN", "session_id": None, "symbol": symbol, "instrument": symbol,
            "provider": declared["provider"] if declared else None,
            "provider_symbol": declared["provider_symbol"] if declared else None,
            "total_bars": 0, "current_index": None, "entry_index": None, "exit_index": None,
            "speed_multiplier": 1.0, "is_playing": False, "plan": None,
            "close_evidence": None, "origin_class": None, "open_review": None,
            "current_candle": None, "trade": None, "visible_candles": [],
        }

    def _open_review_state(self, trade: dict[str, Any]) -> dict[str, Any]:
        """Session creation never fetches: the user must request the refresh."""

        return self._open_review_unmatched_payload(trade)

    def _create_open_review_session(self, trade: dict[str, Any], *,
                                    snapshot: dict[str, Any]) -> dict[str, Any]:
        try:
            evidence = load_open_position_evidence(trade, snapshot=snapshot)
        except OpenReviewError as error:
            payload = self._open_review_unmatched_payload(trade)
            payload.update({
                "status": error.status, "reason": error.reason, "message": error.message,
            })
            return payload
        origin_class = classify_origin(self._trade_events(str(trade.get("id") or "")))
        plan = self._plan_reference(trade)
        session_id = f"OPR-{uuid.uuid4().hex}"
        session = OpenReviewSession(session_id, evidence, plan=plan, origin_class=origin_class)
        if len(self.sessions) >= 32:
            del self.sessions[next(iter(self.sessions))]
        self.sessions[session_id] = session
        return session.to_dict()

    async def create_open_review_session(self, trade_id: str, *, refresh: bool = False) -> dict[str, Any]:
        """Manual refresh: fetch from the trade's declared provider only.

        The fetched snapshot is what the chart displays; earlier cache rows are
        never presented as this trade's matched chart.  The market cache may be
        updated as a side effect, but no journal/plan/ledger record is written.
        """

        try:
            trade = self.trade_reader.get_trade(trade_id)
        except Exception:
            trade = None
        if not trade:
            payload = self._open_review_unmatched_payload({})
            payload.update({"reason": "TRADE_NOT_FOUND", "message": "The recorded trade was not found."})
            return payload
        if str(trade.get("status") or "").upper() != "OPEN" or not refresh:
            return self.create_session_for_trade(trade_id)
        declared = declared_provider_identity(trade)
        if declared is None:
            return self._open_review_unmatched_payload(trade)
        try:
            snapshot = await self.provider_fetcher(
                declared["provider"], declared["provider_symbol"], interval="1m", limit=MAX_OPEN_REVIEW_BARS + 1)
        except Exception as exc:  # noqa: BLE001 - provider failures are reported, never substituted
            payload = self._open_review_unmatched_payload(trade)
            payload.update({
                "status": "UNAVAILABLE", "reason": getattr(exc, "reason", "PROVIDER_FETCH_FAILED"),
                "message": getattr(exc, "message", str(exc) or "The declared provider fetch failed."),
            })
            return payload
        snapshot_provider = str(snapshot.get("provider") or "").strip().lower()
        snapshot_symbol = str(snapshot.get("provider_symbol") or "").strip().upper()
        if snapshot_provider != declared["provider"] or snapshot_symbol != declared["provider_symbol"]:
            payload = self._open_review_unmatched_payload(trade)
            payload.update({
                "status": "UNAVAILABLE", "reason": "PROVIDER_IDENTITY_MISMATCH",
                "message": "The fetched candles do not match the trade's declared provider identity.",
            })
            return payload
        self._cache_snapshot_best_effort(declared["provider_symbol"], snapshot)
        return self._create_open_review_session(trade, snapshot=snapshot)

    @staticmethod
    def _cache_snapshot_best_effort(provider_symbol: str, snapshot: dict[str, Any]) -> None:
        """The market cache may be refreshed; it is never read back as proof."""

        try:
            from app.db.repositories.candles_repo import candles_repo

            candles_repo.save_candles_batch(
                snapshot.get("candles") or [], symbol=provider_symbol,
                timeframe=str(snapshot.get("interval") or "1m"))
        except Exception:  # noqa: BLE001 - cache write is a convenience, not evidence
            pass

    def _trade_events(self, trade_id: str) -> list[dict[str, Any]]:
        """Read-only ledger provenance lookup; a failure degrades to UNKNOWN.

        The read adapter does not expose the event list directly, so the
        adapter's own ledger repository is used with the same account/venue
        scoping as its evidence pack reads.
        """

        reader = getattr(self.trade_reader, "list_events_for_trade", None)
        try:
            if callable(reader):
                return list(reader(trade_id) or [])
            ledger = getattr(self.trade_reader, "ledger_repo", None)
            if ledger is None:
                return []
            return list(
                ledger.list_events_for_trade(
                    trade_id,
                    account_id=str(getattr(self.trade_reader, "account_id", "local-journal") or "local-journal"),
                    venues=getattr(self.trade_reader, "projection_venues", None),
                )
                or []
            )
        except Exception:  # noqa: BLE001 - review must not fail on a lookup
            return []

    def _plan_reference(self, trade: dict[str, Any]) -> dict[str, Any]:
        """Build the labelled level set; the plan lookup is strictly read-only."""

        state = None
        try:
            state = self.tracking_reader.get(str(trade.get("id") or ""))
        except Exception:  # noqa: BLE001 - missing plan falls back to the trade row
            state = None
        return plan_reference(trade, state)
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


async def _default_provider_fetcher(provider: str, provider_symbol: str, **kwargs: Any) -> dict[str, Any]:
    from app.services.market_data.public_fetcher import public_market_fetcher

    return await public_market_fetcher.fetch_declared_provider_candles(
        provider, provider_symbol, **kwargs)


replay_service = ReplayService()
