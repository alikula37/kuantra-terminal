"""Read-only plan reference and close provenance for the chart trade review.

The current plan is an explicitly labelled reference, not a historical claim.
Recorded, revision-aware rendering is a separate local-evidence context.

Nothing here writes: the functions are pure readers over the recorded trade, the
local tracking plan and the append-only ledger provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CURRENT_PLAN_REFERENCE = "CURRENT_PLAN_REFERENCE"

ORIGIN_IMPORTED_FILE = "IMPORTED_FILE"
ORIGIN_JOURNAL = "JOURNAL"
ORIGIN_UNKNOWN = "UNKNOWN"

CLOSE_USER_REPORTED = "USER_REPORTED"
CLOSE_IMPORTED_FILE = "IMPORTED_FILE"
CLOSE_SIMULATION = "SIMULATION"
CLOSE_SOURCE_DECLARED = "SOURCE_DECLARED"
CLOSE_UNKNOWN = "UNKNOWN"

_IMPORT_SOURCES = {"csv", "csv_import", "file_import", "import"}
_JOURNAL_SOURCES = {"journal_external", "journal_simulation", "journal_edit", "journal_delete", "journal_create"}


def _finite(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return None
    return parsed


def _instant(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_origin(events: Optional[List[Dict[str, Any]]]) -> str:
    """Classify how the trade first entered the journal from ledger provenance."""

    for event in events or []:
        if not isinstance(event, dict):
            continue
        provenance = event.get("provenance") if isinstance(event.get("provenance"), dict) else {}
        source = str(provenance.get("source") or "").strip().lower()
        if not source:
            continue
        if source in _IMPORT_SOURCES:
            return ORIGIN_IMPORTED_FILE
        if source in _JOURNAL_SOURCES:
            return ORIGIN_JOURNAL
    return ORIGIN_UNKNOWN


def close_source_class(trade: Dict[str, Any], origin_class: str) -> str:
    """Classify the recorded close without ever upgrading a claim to proof.

    There is no broker-verification infrastructure in the product: every close
    value other than the server-written user report or a known import marker is
    a *source declaration*, kept with its raw value for traceability.  A raw
    string such as ``BROKER_VERIFIED`` can never open a verified label.
    """

    if str(trade.get("record_mode") or "").upper() == "SIMULATION":
        return CLOSE_SIMULATION
    close_source = str(trade.get("close_source") or "").strip().upper()
    if close_source == "USER_REPORTED":
        return CLOSE_USER_REPORTED
    if close_source in {"BROKER_IMPORT", "IMPORT", "IMPORTED", "FILE_IMPORT"}:
        return CLOSE_IMPORTED_FILE
    if close_source:
        return CLOSE_SOURCE_DECLARED
    return CLOSE_IMPORTED_FILE if origin_class == ORIGIN_IMPORTED_FILE else CLOSE_UNKNOWN


def close_evidence(trade: Dict[str, Any], origin_class: str) -> Dict[str, Any]:
    source_class = close_source_class(trade, origin_class)
    return {
        "price": _finite(trade.get("exit_price")),
        "time_utc": trade.get("exit_time"),
        "source": source_class,
        # No verified-close infrastructure exists; this stays False until one does.
        "broker_verified": False,
        "close_source_raw": trade.get("close_source") or None,
    }


def plan_reference(trade: Dict[str, Any], tracking_state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the labelled level set for the chart.

    A local tracking plan is used only when its entry matches the recorded trade
    entry; otherwise the recorded trade row is the level source.  Missing levels
    are omitted, never guessed, and a single recorded take-profit never receives
    an invented percentage.
    """

    entry = _finite(trade.get("entry_price"))
    reference: Dict[str, Any] = {
        "kind": "TRADE_ROW",
        "reference": True,
        "reference_code": CURRENT_PLAN_REFERENCE,
        "plan_revision": None,
        "plan_reset_count": None,
        "created_after_entry": None,
        "plan_mismatch": False,
        "levels": [],
    }
    if entry is not None:
        reference["levels"].append({"kind": "ENTRY", "price": entry})

    state = tracking_state if isinstance(tracking_state, dict) else None
    plan_usable = False
    if state is not None and str(state.get("basis") or "") == "LOCAL_ESTIMATE":
        plan_entry = _finite(state.get("entry_price"))
        if plan_entry is not None and entry is not None and abs(plan_entry - entry) <= max(1e-9, abs(entry) * 1e-9):
            plan_usable = True
        else:
            reference["plan_mismatch"] = True

    def add_level(kind: str, price: Any, weight: Any = None) -> None:
        parsed = _finite(price)
        if parsed is None or parsed <= 0:
            return
        level = {"kind": kind, "price": parsed}
        if weight is not None:
            level["weight_pct"] = _finite(weight)
        reference["levels"].append(level)

    if plan_usable:
        reference["kind"] = "LOCAL_PLAN"
        reference["plan_revision"] = state.get("revision")
        reference["plan_reset_count"] = state.get("reset_count")
        armed = _instant(state.get("armed_at"))
        entered = _instant(trade.get("entry_time"))
        if armed is not None and entered is not None:
            reference["created_after_entry"] = armed > entered
        add_level("SL", state.get("stop_loss"))
        for index, target in enumerate(state.get("targets") or [], start=1):
            if not isinstance(target, dict):
                continue
            add_level(f"TP{index}", target.get("price"), target.get("percent"))
        return reference

    add_level("SL", trade.get("stop_loss"))
    add_level("TP1", trade.get("take_profit"))
    return reference


def recorded_plan_context(trade: Dict[str, Any], history: Optional[List[Dict[str, Any]]],
                          as_of: str) -> Dict[str, Any]:
    """Only hash-verified local revisions at/before the cursor's UTC instant.

    Callers obtain history from LocalTrackingService.history (chain verified).
    No current trade-row levels backfill missing history. No closures or PnL
    leave this reader. Same-time revisions use verified chain order, not UUIDs.
    Candle *opening* time is intentionally conservative: a plan written inside
    a bar cannot appear before its recording time or be assumed active all bar.
    """
    from app.services.local_tracking import timestamp, validate_snapshot

    result = {"status": "NOT_AVAILABLE", "as_of_utc": as_of,
              "available_revisions": [], "plan": None}
    if history is None:
        return {**result, "status": "UNKNOWN"}
    try:
        cutoff = timestamp(as_of)
        result["as_of_utc"] = cutoff.isoformat()
        previous, previous_time, reset_index = None, None, 0
        available = []
        for record in history:
            state = record["state"]
            validate_snapshot(state)
            if (state["trade_id"] != str(trade["id"]) or state["symbol"] != trade["symbol"]
                    or state["side"] != trade["side"]):
                raise ValueError("Plan review scope mismatch")
            if not record["event_id"] or len(record["event_hash"]) != 64:
                raise ValueError("Missing source evidence")
            recorded = timestamp(record["recorded_at_utc"])
            if previous_time is not None and recorded < previous_time:
                raise ValueError("Nonmonotonic local recording clock")
            action = record["action"]
            if action == "PLAN_RESET":
                if state["revision"] != 1 or state["closures"] or (previous and previous["state"]["closures"]):
                    raise ValueError("Invalid reset")
                reset_index += 1
            elif action not in {"PLAN_SAVED", "LOCAL_CLOSE"} or state["revision"] != (previous["state"]["revision"] + 1 if previous else 1):
                raise ValueError("Invalid revision")
            elif previous:
                old = previous["state"]
                if (state["closures"][:len(old["closures"])] != old["closures"]
                        or any(state.get(key) != old.get(key) for key in ("initial_qty", "entry_price", "symbol", "side", "qty_unit"))):
                    raise ValueError("History changed")
            if (record["reset_index"] != reset_index
                    or record["causation_id"] != (previous["event_id"] if previous else None)):
                raise ValueError("Broken lineage")
            if recorded <= cutoff:
                # Use only that snapshot's basis. A later trade correction must
                # not rewrite an older entry line. Unknown units stay unknown.
                basis = {**trade, "entry_price": state["entry_price"]}
                plan = plan_reference(basis, state)
                plan.update(reference_code="RECORDED_LOCAL_PLAN", plan_reset_count=reset_index,
                            source_event_id=record["event_id"], source_event_hash=record["event_hash"],
                            recorded_at_utc=recorded.isoformat(), broker_verified=False)
                available.append(plan)
            previous, previous_time = record, recorded
        result["available_revisions"] = available
        result["plan"] = available[-1] if available else None
        result["status"] = "READY" if available else "NOT_AVAILABLE"
        return result
    except (KeyError, TypeError, ValueError, OverflowError):
        return {**result, "status": "UNKNOWN", "available_revisions": [], "plan": None}
