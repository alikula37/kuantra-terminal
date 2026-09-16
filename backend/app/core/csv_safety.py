"""Shared CSV cell safety used by every journal export artifact.

Spreadsheet software evaluates a cell as a formula when it starts with ``=``,
``+``, ``-`` or ``@`` (and some engines also treat leading control characters as
whitespace to skip).  The export must keep the user's text readable while never
handing an evaluating engine a live formula, so such cells are prefixed with an
apostrophe.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.db.repositories.evidence_ledger_repo import canonical_json


def safe_csv_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (dict, list)):
        text = canonical_json(value)
    else:
        text = str(value)
    if text.startswith(("=", "@")):
        return f"'{text}"
    if text.startswith(("+", "-")):
        try:
            Decimal(text)
        except InvalidOperation:
            return f"'{text}"
    return text
