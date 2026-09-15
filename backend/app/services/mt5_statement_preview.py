"""MT5 HTML statement preview: safe, read-only parsing (WP40).

Supported contract (v1, explicitly bounded):

* the English MetaTrader 5 "ReportHistory" HTML export;
* required section markers ``Orders`` and ``Deals``; the known out-of-scope
  sections ``Positions``, ``Working Orders``, ``Summary`` and ``Details`` are
  reported instead of being silently dropped;
* Orders columns: Open Time, Order, Symbol, Type, Volume, Price, S/L, T/P,
  Time, State;
* Deals columns: Time, Deal, Symbol, Type, Direction, Volume, Price, Order,
  Commission, Fee, Swap, Profit, Balance.

This module is preview-only: it writes nothing, executes nothing, fetches
nothing, converts no timezone, no quantity and no money, and never invents a
missing value.  Order and deal identities stay separate.  Unsupported
templates, languages, sections and ambiguous values fail closed.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from app.core.input_limits import (
    MAX_STATEMENT_BYTES,
    MAX_STATEMENT_CELL_BYTES,
    MAX_STATEMENT_PREVIEW_ROWS,
    MAX_STATEMENT_ROW_ERRORS,
    MAX_STATEMENT_ROWS,
    MAX_STATEMENT_TABLES,
)

PARSER_VERSION = "mt5-html-preview/1"
REPORT_FORMAT = "MT5_HTML_REPORT"
REPORT_TEMPLATE = "REPORT_HISTORY_EN"
REPORT_LANGUAGE = "EN"
TIME_BASIS = "SOURCE_LOCAL_TIME_UNVERIFIED"
QUANTITY_UNIT = "SOURCE_LOT"

_REQUIRED_SECTIONS = ("Orders", "Deals")
_OUT_OF_SCOPE_SECTIONS = ("Positions", "Working Orders", "Summary", "Details")
_SECTION_MARKERS = frozenset(_REQUIRED_SECTIONS) | frozenset(_OUT_OF_SCOPE_SECTIONS)

_TIME_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2})(?::(\d{2}))?$")
_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_ACCOUNT_RE = re.compile(r"(?i)account\s*(?:number|no\.?|#|:)?\s*[:#]?\s*(\d{4,})")
_CURRENCY_RE = re.compile(r"\(([A-Z]{3})[,)]")

_ORDERS_REQUIRED = {
    "order": ("order",),
    "time": ("open time", "time"),
    "symbol": ("symbol",),
    "volume": ("volume",),
    "price": ("price",),
}
_DEALS_REQUIRED = {
    "deal": ("deal",),
    "time": ("time",),
    "symbol": ("symbol",),
    "volume": ("volume",),
    "price": ("price",),
    "order_reference": ("order",),
}
_KNOWN_LABELS = frozenset({
    "open time", "order", "symbol", "type", "volume", "price", "s/l", "t/p",
    "time", "state", "comment", "deal", "direction", "commission", "fee",
    "swap", "profit", "balance", "position",
})


class Mt5StatementPreviewError(ValueError):
    """Raised when an MT5 statement cannot be previewed safely."""

    def __init__(self, code: str, message: Optional[str] = None):
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


class _TableCollector(HTMLParser):
    """Collect table rows/cells while enforcing parse resource limits."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: List[List[List[str]]] = []
        self._table: Optional[List[List[str]]] = None
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None
        self._suppress = 0
        self._total_rows = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        tag = tag.lower()
        if tag in ("script", "style"):
            self._suppress += 1
            return
        if self._suppress:
            return
        if tag == "table":
            if len(self.tables) >= MAX_STATEMENT_TABLES:
                raise Mt5StatementPreviewError("TABLE_LIMIT_EXCEEDED")
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._total_rows += 1
            if self._total_rows > MAX_STATEMENT_ROWS:
                raise Mt5StatementPreviewError("ROW_LIMIT_EXCEEDED")
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style"):
            self._suppress = max(0, self._suppress - 1)
            return
        if self._suppress:
            return
        if tag in ("td", "th") and self._cell is not None:
            text = "".join(self._cell).strip()
            if len(text) > MAX_STATEMENT_CELL_BYTES:
                raise Mt5StatementPreviewError("CELL_LIMIT_EXCEEDED")
            if self._row is not None:
                self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._cell is not None:
                text = "".join(self._cell).strip()
                if self._row is not None:
                    self._row.append(text)
                self._cell = None
            if self._row is not None:
                self._table.append(self._row)
                self._row = None
            self.tables.append(self._table)
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._suppress or self._cell is None:
            return
        self._cell.append(data)


def _normalized(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split()).rstrip(":")


def _has_digits(value: str) -> bool:
    return any(character.isdigit() for character in value)


def _looks_like_unknown_section_marker(table: List[List[str]], index: int) -> bool:
    row = table[index]
    non_empty = [cell for cell in row if cell]
    if len(non_empty) != 1:
        return False
    marker = non_empty[0]
    if ":" in marker or _has_digits(marker) or not 2 <= len(marker) <= 40:
        return False
    if index + 1 >= len(table):
        return False
    following = [cell for cell in table[index + 1] if cell]
    return len(following) >= 3


def _extract_sections(
    tables: List[List[List[str]]],
) -> Tuple[Dict[str, List[List[str]]], List[str]]:
    sections: Dict[str, List[List[str]]] = {}
    unknown_markers: List[str] = []
    for table in tables:
        current: Optional[str] = None
        for index, row in enumerate(table):
            non_empty = [cell for cell in row if cell]
            marker = non_empty[0] if len(non_empty) == 1 else None
            if marker in _SECTION_MARKERS:
                current = marker
                sections.setdefault(marker, [])
                continue
            if current is None:
                if marker and _looks_like_unknown_section_marker(table, index):
                    unknown_markers.append(marker)
                continue
            sections[current].append(list(row))
    return sections, unknown_markers


def _header_map(header: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for index, cell in enumerate(header):
        mapping.setdefault(_normalized(cell), index)
    return mapping


def _require_columns(
    mapping: Dict[str, int],
    required: Dict[str, Tuple[str, ...]],
    *,
    section: str,
) -> Dict[str, int]:
    resolved: Dict[str, int] = {}
    for field, aliases in required.items():
        for alias in aliases:
            if alias in mapping:
                resolved[field] = mapping[alias]
                break
        if field not in resolved:
            raise Mt5StatementPreviewError(
                "MISSING_COLUMN", f"{section} is missing the {field} column"
            )
    return resolved


def _check_known_labels(header: List[str], *, section: str) -> None:
    normalized = [_normalized(cell) for cell in header if cell]
    if not normalized:
        raise Mt5StatementPreviewError("MISSING_COLUMN", f"{section} has no header row")
    known = sum(1 for label in normalized if label in _KNOWN_LABELS)
    if known / len(normalized) < 0.5:
        raise Mt5StatementPreviewError(
            "UNSUPPORTED_LANGUAGE", f"{section} header is not the supported English template"
        )


def _cell(row: List[str], index: Optional[int]) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _canonical_number(value: str) -> str:
    rendered = value
    if rendered.startswith("-") and float(rendered) == 0:
        return "0"
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _parse_time(value: str, *, section: str, source_row: int, errors: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    if not value:
        errors.append({"section": section, "source_row": source_row, "reason": "MISSING_TIME", "fields": ["time"]})
        return None, None
    match = _TIME_RE.match(value)
    if not match:
        errors.append({"section": section, "source_row": source_row, "reason": "UNPARSED_TIME", "fields": ["time"]})
        return None, value
    year, month, day, hour, minute, second = match.groups()
    local = f"{year}-{month}-{day}T{hour}:{minute}:{second or '00'}"
    return local, value


def _required_number(
    value: str,
    *,
    field: str,
    section: str,
    source_row: int,
    errors: List[Dict[str, Any]],
) -> Optional[str]:
    if not value:
        errors.append({"section": section, "source_row": source_row, "reason": "MISSING_NUMBER", "fields": [field]})
        return None
    if not _NUMBER_RE.match(value):
        errors.append({"section": section, "source_row": source_row, "reason": "UNPARSED_NUMBER", "fields": [field]})
        return None
    return _canonical_number(value)


def _optional_number(
    value: str,
    *,
    field: str,
    section: str,
    source_row: int,
    errors: List[Dict[str, Any]],
) -> Optional[str]:
    if not value:
        return None
    if not _NUMBER_RE.match(value):
        errors.append({"section": section, "source_row": source_row, "reason": "UNPARSED_NUMBER", "fields": [field]})
        return None
    return _canonical_number(value)


def _mask_account(account_number: str) -> str:
    tail = account_number[-4:] if len(account_number) >= 4 else account_number
    return "*" * max(0, len(account_number) - len(tail)) + tail


def _extract_header(tables: List[List[List[str]]]) -> Tuple[Optional[str], Optional[str]]:
    for table in tables:
        for row in table:
            for index, cell in enumerate(row):
                account_match = _ACCOUNT_RE.search(cell)
                if account_match:
                    currency_match = _CURRENCY_RE.search(cell)
                    return account_match.group(1), currency_match.group(1) if currency_match else None
                if _normalized(cell) == "deposit currency":
                    for follower in row[index + 1:]:
                        currency_match = re.match(r"^([A-Z]{3})$", follower.strip())
                        if currency_match:
                            return None, currency_match.group(1)
    return None, None


def _parse_orders(
    rows: List[List[str]],
    errors: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    if not rows:
        raise Mt5StatementPreviewError("MISSING_SECTION", "Orders has no header row")
    header = rows[0]
    _check_known_labels(header, section="Orders")
    columns = _require_columns(_header_map(header), _ORDERS_REQUIRED, section="Orders")
    parsed: List[Dict[str, Any]] = []
    ok_count = 0
    parsed_times: List[Tuple[str, str]] = []
    for source_row, row in enumerate(rows[1:], start=1):
        row_errors_start = len(errors)
        order_id = _cell(row, columns.get("order"))
        if not order_id:
            errors.append({"section": "order", "source_row": source_row, "reason": "MISSING_ORDER_ID", "fields": ["order"]})
        time_local, time_source = _parse_time(_cell(row, columns.get("time")), section="order", source_row=source_row, errors=errors)
        symbol = _cell(row, columns.get("symbol"))
        if not symbol:
            errors.append({"section": "order", "source_row": source_row, "reason": "MISSING_SYMBOL", "fields": ["symbol"]})
        volume = _required_number(_cell(row, columns.get("volume")), field="volume", section="order", source_row=source_row, errors=errors)
        price = _required_number(_cell(row, columns.get("price")), field="price", section="order", source_row=source_row, errors=errors)
        if len(errors) > row_errors_start:
            continue
        ok_count += 1
        parsed_times.append((time_local or "", time_source or ""))
        parsed.append({
            "source_identity": order_id,
            "source_identity_kind": "SOURCE_ORDER_ID",
            "open_time_source": time_source,
            "open_time_local": time_local,
            "symbol": symbol,
            "type": _cell(row, columns.get("type")),
            "volume_source": _cell(row, columns.get("volume")) or None,
            "volume": volume,
            "volume_unit": QUANTITY_UNIT,
            "price_source": _cell(row, columns.get("price")) or None,
            "price": price,
            "sl_source": _cell(row, columns.get("sl")) or None,
            "tp_source": _cell(row, columns.get("tp")) or None,
            "state": _cell(row, columns.get("state")),
        })
    return parsed, ok_count, parsed_times


def _parse_deals(
    rows: List[List[str]],
    errors: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int, List[Tuple[str, str]]]:
    if not rows:
        raise Mt5StatementPreviewError("MISSING_SECTION", "Deals has no header row")
    header = rows[0]
    _check_known_labels(header, section="Deals")
    mapping = _header_map(header)
    columns = _require_columns(mapping, _DEALS_REQUIRED, section="Deals")
    optional_columns = {
        "type": mapping.get("type"),
        "direction": mapping.get("direction"),
        "commission": mapping.get("commission"),
        "fee": mapping.get("fee"),
        "swap": mapping.get("swap"),
        "profit": mapping.get("profit"),
        "balance": mapping.get("balance"),
    }
    parsed: List[Dict[str, Any]] = []
    ok_count = 0
    parsed_times: List[Tuple[str, str]] = []
    for source_row, row in enumerate(rows[1:], start=1):
        row_errors_start = len(errors)
        deal_id = _cell(row, columns.get("deal"))
        if not deal_id:
            errors.append({"section": "deal", "source_row": source_row, "reason": "MISSING_DEAL_ID", "fields": ["deal"]})
        order_reference = _cell(row, columns.get("order_reference"))
        if not order_reference:
            errors.append({"section": "deal", "source_row": source_row, "reason": "MISSING_ORDER_REFERENCE", "fields": ["order"]})
        time_local, time_source = _parse_time(_cell(row, columns.get("time")), section="deal", source_row=source_row, errors=errors)
        symbol = _cell(row, columns.get("symbol"))
        if not symbol:
            errors.append({"section": "deal", "source_row": source_row, "reason": "MISSING_SYMBOL", "fields": ["symbol"]})
        volume = _required_number(_cell(row, columns.get("volume")), field="volume", section="deal", source_row=source_row, errors=errors)
        price = _required_number(_cell(row, columns.get("price")), field="price", section="deal", source_row=source_row, errors=errors)
        money_values = {
            field: _optional_number(_cell(row, index), field=field, section="deal", source_row=source_row, errors=errors)
            for field, index in optional_columns.items()
            if field in ("commission", "fee", "swap", "profit", "balance")
        }
        if len(errors) > row_errors_start:
            continue
        ok_count += 1
        parsed_times.append((time_local or "", time_source or ""))
        parsed.append({
            "source_identity": deal_id,
            "source_identity_kind": "SOURCE_DEAL_ID",
            "related_order_id": order_reference,
            "time_source": time_source,
            "time_local": time_local,
            "symbol": symbol,
            "type": _cell(row, optional_columns.get("type")),
            "direction": _cell(row, optional_columns.get("direction")),
            "volume_source": _cell(row, columns.get("volume")) or None,
            "volume": volume,
            "volume_unit": QUANTITY_UNIT,
            "price_source": _cell(row, columns.get("price")) or None,
            "price": price,
            "commission_source": _cell(row, optional_columns.get("commission")) or None,
            "commission": money_values.get("commission"),
            "fee_source": _cell(row, optional_columns.get("fee")) or None,
            "fee": money_values.get("fee"),
            "swap_source": _cell(row, optional_columns.get("swap")) or None,
            "swap": money_values.get("swap"),
            "reported_profit_source": _cell(row, optional_columns.get("profit")) or None,
            "reported_profit": money_values.get("profit"),
            "balance_source": _cell(row, optional_columns.get("balance")) or None,
            "balance": money_values.get("balance"),
        })
    return parsed, ok_count, parsed_times


def preview_mt5_html_report(content: bytes) -> Dict[str, Any]:
    """Parse a supported MT5 HTML report into a preview-only structure."""

    if not isinstance(content, bytes):
        raise Mt5StatementPreviewError("INVALID_INPUT", "content must be bytes")
    if len(content) > MAX_STATEMENT_BYTES:
        raise Mt5StatementPreviewError("FILE_LIMIT_EXCEEDED")
    if not content.strip():
        raise Mt5StatementPreviewError("UNSUPPORTED_TEMPLATE")

    collector = _TableCollector()
    try:
        collector.feed(content.decode("utf-8", errors="strict"))
        collector.close()
    except UnicodeDecodeError as exc:
        raise Mt5StatementPreviewError("UNSUPPORTED_ENCODING") from exc
    except Mt5StatementPreviewError:
        raise
    except Exception as exc:  # malformed markup never crashes the preview
        raise Mt5StatementPreviewError("MALFORMED_HTML") from exc

    sections, unknown_markers = _extract_sections(collector.tables)
    if not sections:
        raise Mt5StatementPreviewError("UNSUPPORTED_TEMPLATE")
    if unknown_markers:
        raise Mt5StatementPreviewError("UNSUPPORTED_LANGUAGE")
    if "Orders" not in sections or "Deals" not in sections:
        missing = "Orders" if "Orders" not in sections else "Deals"
        raise Mt5StatementPreviewError("MISSING_SECTION", missing)

    errors: List[Dict[str, Any]] = []
    orders, orders_ok, order_times = _parse_orders(sections["Orders"], errors)
    deals, deals_ok, deal_times = _parse_deals(sections["Deals"], errors)

    source_account, account_currency = _extract_header(collector.tables)
    all_times = [pair for pair in order_times + deal_times if pair[0]]
    all_times.sort(key=lambda pair: pair[0])
    date_range = None
    if all_times:
        date_range = {"start_source": all_times[0][1], "end_source": all_times[-1][1]}

    unsupported_sections = [
        section for section in _OUT_OF_SCOPE_SECTIONS if section in sections
    ]
    warnings = ["SOURCE_TIME_BASIS_UNVERIFIED", "SOURCE_ACCOUNT_NOT_VERIFIED"]
    if unsupported_sections:
        warnings.append("OUT_OF_SCOPE_SECTIONS_PRESENT")

    orders_total = max(0, len(sections["Orders"]) - 1)
    deals_total = max(0, len(sections["Deals"]) - 1)
    return {
        "preview_only": True,
        "format": REPORT_FORMAT,
        "template": REPORT_TEMPLATE,
        "language": REPORT_LANGUAGE,
        "parser_version": PARSER_VERSION,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "source_size_bytes": len(content),
        "account": {
            "masked": _mask_account(source_account) if source_account else None,
            "basis": "SOURCE_DECLARED",
            "verified": False,
        },
        "account_currency": account_currency,
        "time_basis": TIME_BASIS,
        "quantity_unit": QUANTITY_UNIT,
        "counts": {
            "orders": orders_total,
            "deals": deals_total,
            "rows_total": orders_total + deals_total,
            "rows_ok": orders_ok + deals_ok,
            "rows_with_errors": len({(error["section"], error["source_row"]) for error in errors}),
        },
        "date_range": date_range,
        "orders": orders[:MAX_STATEMENT_PREVIEW_ROWS],
        "deals": deals[:MAX_STATEMENT_PREVIEW_ROWS],
        "orders_truncated": len(orders) > MAX_STATEMENT_PREVIEW_ROWS,
        "deals_truncated": len(deals) > MAX_STATEMENT_PREVIEW_ROWS,
        "row_errors": errors[:MAX_STATEMENT_ROW_ERRORS],
        "row_errors_truncated": len(errors) > MAX_STATEMENT_ROW_ERRORS,
        "unsupported_sections": unsupported_sections,
        "warnings": warnings,
        "parse_settings": {
            "template": REPORT_TEMPLATE,
            "language": REPORT_LANGUAGE,
            "timezone_conversion": "NONE",
            "financial_recalculation": "NONE",
            "quantity_conversion": "NONE",
            "sections_required": list(_REQUIRED_SECTIONS),
            "sections_out_of_scope": list(_OUT_OF_SCOPE_SECTIONS),
            "preview_persists_nothing": True,
        },
        "limits": {
            "max_statement_bytes": MAX_STATEMENT_BYTES,
            "max_tables": MAX_STATEMENT_TABLES,
            "max_rows": MAX_STATEMENT_ROWS,
            "max_cell_bytes": MAX_STATEMENT_CELL_BYTES,
            "max_preview_rows": MAX_STATEMENT_PREVIEW_ROWS,
            "max_row_errors": MAX_STATEMENT_ROW_ERRORS,
        },
    }
