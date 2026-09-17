"""Read-only plan reference and close provenance for the chart trade review.

P1 scope: the review shows the *current* recorded plan as an explicitly labelled
reference.  It never claims those levels were valid at the replay cursor; that
historical, revision-aware rendering belongs to a later package.

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
