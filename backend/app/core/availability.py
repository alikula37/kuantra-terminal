"""Truth-safe capability availability contracts.

Experimental services must never emit a normal-looking success payload when the
real transport, model, hardware, or source provenance is not present.  The
helpers in this module keep the response shape consistent across API surfaces;
they intentionally contain no feature flag that enables execution.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException


def experimental_disabled_response(
    capability: str,
    *,
    reason: str = "REAL_INTEGRATION_NOT_CONFIGURED",
    message: str | None = None,
    provenance: str = "SYNTHETIC_MODEL",
) -> Dict[str, Any]:
    """Return the canonical body for an unavailable experimental capability."""

    return {
        "status": "EXPERIMENTAL_DISABLED",
        "capability": capability,
        "provenance": provenance,
        "reason": reason,
        "message": message or f"{capability} is disabled until a verified production integration exists.",
        "execution_authority": False,
        "data_connected": False,
        "transport_connected": False,
        "model_loaded": False,
    }


def experimental_disabled_exception(
    capability: str,
    *,
    reason: str = "REAL_INTEGRATION_NOT_CONFIGURED",
    message: str | None = None,
    provenance: str = "SYNTHETIC_MODEL",
) -> HTTPException:
    """Build a 503 exception for an API surface without a real integration."""

    return HTTPException(
        status_code=503,
        detail=experimental_disabled_response(
            capability,
            reason=reason,
            message=message,
            provenance=provenance,
        ),
    )


def is_explicit_experimental_mode() -> bool:
    """Whether a developer explicitly opted into prototype-only surfaces.

    The application never sets this value.  It exists only for isolated local
    research sessions and is deliberately not a production fallback.
    """

    import os

    return os.getenv("KUANTRA_ALLOW_EXPERIMENTAL", "0") == "1"
