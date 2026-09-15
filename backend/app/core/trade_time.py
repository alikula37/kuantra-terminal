"""User-facing trade time handling.

User-entered and user-displayed times use ``Europe/Istanbul``.  Storage and
provider timestamps stay timezone-aware UTC so review boundaries, ordering and
evidence do not depend on the machine's local timezone.  Naive user input is
interpreted as Istanbul wall time because that is the only clock the journal
surface shows; naive input is never silently treated as UTC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
# Small tolerance so a device clock a few seconds ahead of the server does not
# turn "just now" into a rejected future trade.  It must never accept a real
# future timestamp, so the window stays under a minute.
FUTURE_TOLERANCE = timedelta(seconds=45)


class TradeTimeError(ValueError):
    """Raised when a user-supplied time cannot be trusted for storage."""

    def __init__(self, reason: str, message: str, *, field: str = "entry_time"):
        super().__init__(message)
        self.reason = reason
        self.field = field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_user_time(
    value: str,
    *,
    field: str = "entry_time",
    now: Optional[datetime] = None,
) -> datetime:
    """Parse a user-supplied ISO-8601 time into timezone-aware UTC.

    An explicit offset is honored exactly.  A value without an offset is
    interpreted as Istanbul wall time, and one already carrying the Istanbul
    offset round-trips unchanged.  Seconds are preserved but the UI only sends
    minute precision.
    """

    raw = str(value or "").strip()
    if not raw:
        raise TradeTimeError("TIME_REQUIRED", "A trade time is required.", field=field)
    if any(ord(character) < 32 for character in raw):
        raise TradeTimeError("TIME_INVALID", "The trade time contains invalid characters.", field=field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TradeTimeError(
            "TIME_INVALID",
            "The trade time must be an ISO-8601 date and time.",
            field=field,
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ISTANBUL_TZ)
    return parsed.astimezone(timezone.utc)


def validate_not_future(
    value: datetime,
    *,
    field: str = "entry_time",
    now: Optional[datetime] = None,
) -> datetime:
    """Reject a realized event time that lies in the future.

    The journal records what already happened.  A planned order belongs to a
    different workflow, so the boundary is fail-closed instead of storing a
    timestamp the evidence cannot support.
    """

    reference = now or now_utc()
    if value > reference + FUTURE_TOLERANCE:
        raise TradeTimeError(
            "TIME_IN_FUTURE",
            "A realized trade cannot be recorded with a future time.",
            field=field,
        )
    return value


def parse_user_entry_time(
    value: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    if value is None or str(value).strip() == "":
        return None
    parsed = parse_user_time(value, field="entry_time", now=now)
    return validate_not_future(parsed, field="entry_time", now=now)


def istanbul_date(value: datetime) -> str:
    """Return the Istanbul calendar date (``YYYY-MM-DD``) for a UTC instant."""

    return value.astimezone(ISTANBUL_TZ).date().isoformat()
