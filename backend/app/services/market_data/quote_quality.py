"""Display freshness, never a substitute for the local-tracking authority gate."""
from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional


def quote_age(observed_at: Optional[str], now: datetime) -> Optional[float]:
    try:
        parsed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        age = (now - parsed.astimezone(timezone.utc)).total_seconds()
        return round(age, 3) if math.isfinite(age) else None
    except (ValueError, TypeError, OverflowError):
        return None


def quote_quality(quote: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    result = dict(quote)
    basis = quote.get("timestamp_basis", "UNKNOWN")
    if basis not in {"PROVIDER_EVENT", "CANDLE_OPEN", "REQUEST_TIME"}:
        basis = "UNKNOWN"
    age = quote_age(quote.get("observed_at"), now)
    freshness = "UNKNOWN"
    if basis == "PROVIDER_EVENT" and age is not None and age >= -5:
        freshness = "FRESH" if age <= 60 else "STALE"
    elif basis == "CANDLE_OPEN":
        freshness = "DISPLAY_ONLY"
    status = quote.get("status") or "UNAVAILABLE"
    if status == "LIVE" and freshness != "FRESH":
        status = "DELAYED"
    if status == "UNAVAILABLE":
        freshness = "UNKNOWN"
    result.update(status=status, timestamp_basis=basis, age_seconds=age, freshness=freshness)
    return result
