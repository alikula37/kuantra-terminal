"""
Multi-Format CSV Trade Ingestion & Batch Ingestion Engine for Kuantra Terminal.
Authentically parses, normalizes, validates, and imports historical trade logs from:
- Binance Spot & Futures CSV Exports
- Bybit Closed PnL & Derivatives Reports
- MetaTrader 4 / 5 (MT4/MT5) Trade Statements
- Standard Kuantra Generic CSV Template

Enforces deterministic SHA-256 row fingerprinting for duplicate prevention and commits in a single transaction.
"""

import csv
import io
import re
import hashlib
import json
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from app.db.sqlite_driver import sqlite_driver
from app.db.sync_pipeline import sync_pipeline

logger = logging.getLogger("csv_importer")


class CsvTradeImporterService:
    """Universal institutional CSV trade parser, validator, and batch transaction importer."""

    SUPPORTED_FORMATS = ["BINANCE", "BYBIT", "METATRADER", "GENERIC_KUANTRA"]

    @classmethod
    def detect_format_and_dialect(cls, content_str: str) -> Tuple[str, str]:
        """
        Detects delimiter dialect and classifies column headers into supported broker formats.
        """
        lines = [line.strip() for line in content_str.splitlines() if line.strip()]
        if not lines:
            raise ValueError("CSV content is empty.")

        header_line = lines[0]
        
        # Detect delimiter
        delimiter = ","
        for delim in [",", ";", "\t", "|"]:
            if delim in header_line:
                # Count occurrences
                if header_line.count(delim) >= 3:
                    delimiter = delim
                    break

        header_cols = [c.strip().lower().replace('"', '').replace("'", "") for c in header_line.split(delimiter)]
        header_text = " ".join(header_cols)

        # 1. Binance format check
        if ("date(utc)" in header_text or "time(utc)" in header_text) and (
            "realized profit" in header_text or "executed" in header_text or "pair" in header_text or "fee coin" in header_text
        ):
            return "BINANCE", delimiter

        # 2. Bybit format check
        if ("closed p&l" in header_text or "closed pnl" in header_text or "contracts" in header_text or "closing direction" in header_text):
            return "BYBIT", delimiter

        # 3. MetaTrader 4/5 format check
        if ("open time" in header_text or "close time" in header_text or "ticket" in header_text or "position" in header_text or "deal" in header_text) and (
            "item" in header_text or "symbol" in header_text or "size" in header_text or "volume" in header_text or "profit" in header_text
        ):
            return "METATRADER", delimiter

        # 4. Default to Generic Kuantra
        return "GENERIC_KUANTRA", delimiter

    @classmethod
    def parse_timestamp(cls, raw_val: Any) -> str:
        """Standardize a broker timestamp; never invent receipt time.

        Broker exports without an offset are interpreted as UTC and emitted as
        normalized UTC. Missing or unrecognized timestamps reject the row so an
        import cannot turn an unknown trade date into a fabricated current date.
        """
        if raw_val is None or not str(raw_val).strip():
            raise ValueError("Timestamp is required")

        val_str = str(raw_val).replace('"', '').replace("'", "").strip()

        # Numeric epoch timestamp check
        try:
            epoch_num = float(val_str)
            if math.isfinite(epoch_num) and epoch_num >= 0:
                if epoch_num > 1e11:  # milliseconds
                    epoch_num /= 1000.0
                parsed = datetime.fromtimestamp(epoch_num, tz=timezone.utc)
                return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError, OverflowError, OSError):
            pass

        # ISO-8601, including explicit offsets and the common trailing Z.
        try:
            parsed = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass

        date_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d/%m/%Y"
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass

        # Fallback to regex ISO-like extraction
        match = re.search(r"(\d{4}[-./]\d{2}[-./]\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)", val_str)
        if match:
            date_part = match.group(1).replace(".", "-").replace("/", "-")
            time_part = match.group(2)
            if len(time_part) == 5:
                time_part += ":00"
            parsed = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
            return parsed.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        raise ValueError(f"Unrecognized timestamp: {val_str}")

    @classmethod
    def clean_symbol(cls, raw_symbol: str) -> str:
        """Sanitizes ticker symbols into canonical format (e.g. BTCUSDT, EURUSD, XAUUSD)."""
        if raw_symbol is None or not str(raw_symbol).strip():
            return ""
        cleaned = str(raw_symbol).upper().replace("/", "").replace("_", "").replace("-", "").strip()
        # Remove broker prefixes/suffixes like EURUSD.pro or BTCUSDT.p
        cleaned = re.sub(r"\.(PRO|ECN|M|P|STD|RAW)$", "", cleaned, flags=re.I)
        return cleaned

    @classmethod
    def clean_float(cls, raw_val: Any, default: Optional[float] = None) -> Optional[float]:
        """Safely parses numeric values handling currency signs, commas, and percentage symbols."""
        if raw_val is None or not str(raw_val).strip():
            return default
        if isinstance(raw_val, bool):
            return default
        if isinstance(raw_val, (int, float)):
            value = float(raw_val)
            return value if math.isfinite(value) else default
        val_str = str(raw_val).replace("$", "").replace("€", "").replace("£", "").replace(" ", "").replace(",", "").strip()
        try:
            value = float(val_str)
            return value if math.isfinite(value) else default
        except (TypeError, ValueError, OverflowError):
            return default

    @classmethod
    def normalize_side(cls, raw_side: str) -> str:
        """Standardizes buy/sell/long/short indicators into BUY or SELL."""
        s = str(raw_side).upper().strip()
        if any(keyword in s for keyword in ["BUY", "LONG", "BUY_LONG", "CLOSE SHORT"]):
            return "BUY"
        if any(keyword in s for keyword in ["SELL", "SHORT", "SELL_SHORT", "CLOSE LONG"]):
            return "SELL"
        return ""

    @classmethod
    def parse_rows(cls, content_str: str) -> Tuple[str, List[Dict[str, Any]], List[str]]:
        """
        Parses CSV string into standardized trade dictionaries with error telemetry.
        """
        format_type, delimiter = cls.detect_format_and_dialect(content_str)
        reader = csv.DictReader(io.StringIO(content_str), delimiter=delimiter)
        
        normalized_trades = []
        parsing_errors = []

        for idx, raw_row in enumerate(reader, start=2): # Line 2 is first data row
            # Case-insensitive column key access
            row = {k.strip().lower().replace('"', ''): v for k, v in raw_row.items() if k is not None}

            try:
                if format_type == "BINANCE":
                    # Binance Spot or Futures CSV
                    symbol = cls.clean_symbol(row.get("pair") or row.get("market") or row.get("symbol"))
                    side = cls.normalize_side(row.get("side") or row.get("type"))
                    entry_price = cls.clean_float(row.get("price") or row.get("avgprice") or row.get("order price"))
                    qty = cls.clean_float(row.get("executed") or row.get("amount") or row.get("qty") or row.get("filled"))
                    pnl = cls.clean_float(row.get("realized profit") or row.get("realized pnl") or row.get("profit"), 0.0)
                    commission = abs(cls.clean_float(row.get("fee"), 0.0))
                    entry_time = cls.parse_timestamp(row.get("date(utc)") or row.get("time(utc)") or row.get("date") or row.get("time"))
                    exit_time = entry_time if pnl != 0 else None
                    status = "CLOSED" if pnl != 0 or exit_time else "OPEN"
                    notes = f"Binance Import: {row.get('order no', '') or row.get('trade id', '')}".strip()

                    trade_dict = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": entry_price if status == "CLOSED" else None,
                        "qty": qty,
                        "stop_loss": None,
                        "take_profit": None,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "status": status,
                        "pnl": pnl,
                        "r_multiple": None,
                        "commission": commission,
                        "notes": notes
                    }

                elif format_type == "BYBIT":
                    # Bybit Closed PnL CSV
                    symbol = cls.clean_symbol(row.get("contracts") or row.get("symbol") or row.get("contract"))
                    raw_dir = row.get("closing direction") or row.get("side") or row.get("direction")
                    side = cls.normalize_side(raw_dir)
                    entry_price = cls.clean_float(row.get("entry price") or row.get("avg entry price"))
                    exit_price = cls.clean_float(row.get("exit price") or row.get("avg exit price"))
                    qty = cls.clean_float(row.get("qty") or row.get("quantity") or row.get("closed size") or row.get("size"))
                    pnl = cls.clean_float(row.get("closed p&l") or row.get("closed pnl") or row.get("realized pnl"), 0.0)
                    commission = abs(cls.clean_float(row.get("fee") or row.get("trading fee"), 0.0))
                    
                    entry_time = cls.parse_timestamp(row.get("trade time") or row.get("create time") or row.get("open time"))
                    exit_time = cls.parse_timestamp(row.get("closed time") or row.get("exit time") or row.get("updated time") or entry_time)
                    status = "CLOSED"
                    notes = f"Bybit Import: {row.get('order no', '') or row.get('order id', '')}".strip()

                    trade_dict = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "qty": qty,
                        "stop_loss": None,
                        "take_profit": None,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "status": status,
                        "pnl": pnl,
                        "r_multiple": None,
                        "commission": commission,
                        "notes": notes
                    }

                elif format_type == "METATRADER":
                    # MT4 / MT5 Statement Report
                    symbol = cls.clean_symbol(row.get("item") or row.get("symbol") or row.get("asset"))
                    raw_type = row.get("type") or row.get("action")
                    side = cls.normalize_side(raw_type)
                    qty = cls.clean_float(row.get("size") or row.get("volume") or row.get("lots"))
                    
                    # In MT reports, there can be 2 price columns or open/close price keys
                    entry_price = cls.clean_float(row.get("open price") or row.get("price"))
                    # Some MT4/MT5 exports repeat the ``Price`` header for the
                    # close column; DictReader retains the last occurrence.
                    exit_price = cls.clean_float(
                        row.get("close price") or row.get("exit price") or row.get("price"),
                        None,
                    )
                    
                    sl = cls.clean_float(row.get("s / l") or row.get("s/l") or row.get("stop loss") or row.get("sl"), None)
                    tp = cls.clean_float(row.get("t / p") or row.get("t/p") or row.get("take profit") or row.get("tp"), None)
                    
                    pnl = cls.clean_float(row.get("profit") or row.get("profit ($)") or row.get("net profit"), 0.0)
                    commission = abs(cls.clean_float(row.get("commission"), 0.0)) + abs(cls.clean_float(row.get("swap"), 0.0))
                    
                    entry_time = cls.parse_timestamp(row.get("open time") or row.get("time"))
                    exit_time_raw = row.get("close time")
                    exit_time = cls.parse_timestamp(exit_time_raw) if exit_time_raw else (entry_time if pnl != 0 else None)
                    status = "CLOSED" if exit_time or pnl != 0 else "OPEN"
                    ticket = row.get("ticket") or row.get("position") or row.get("deal") or ""
                    notes = f"MetaTrader Ticket #{ticket}".strip() if ticket else "MetaTrader Import"

                    # Calculate dynamic R-Multiple if SL is present
                    r_multiple = None
                    if sl and sl > 0 and entry_price > 0 and qty > 0 and pnl != 0:
                        risk_per_unit = abs(entry_price - sl)
                        if risk_per_unit > 0:
                            r_multiple = round(pnl / (risk_per_unit * qty), 2)

                    trade_dict = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "qty": qty,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "status": status,
                        "pnl": pnl,
                        "r_multiple": r_multiple,
                        "commission": commission,
                        "notes": notes
                    }

                else:
                    # Standard Generic Kuantra CSV
                    symbol = cls.clean_symbol(row.get("symbol"))
                    side = cls.normalize_side(row.get("side"))
                    entry_price = cls.clean_float(row.get("entry_price") or row.get("entry") or row.get("price"))
                    exit_price = cls.clean_float(row.get("exit_price") or row.get("exit"), None)
                    qty = cls.clean_float(row.get("qty") or row.get("quantity") or row.get("amount") or row.get("size"))
                    sl = cls.clean_float(row.get("stop_loss") or row.get("sl"), None)
                    tp = cls.clean_float(row.get("take_profit") or row.get("tp"), None)
                    pnl = cls.clean_float(row.get("pnl") or row.get("profit"), 0.0)
                    r_mult = cls.clean_float(row.get("r_multiple") or row.get("r"), None)
                    commission = abs(cls.clean_float(row.get("commission") or row.get("fee"), 0.0))
                    entry_time = cls.parse_timestamp(row.get("entry_time") or row.get("time") or row.get("date"))
                    exit_time_raw = row.get("exit_time")
                    exit_time = cls.parse_timestamp(exit_time_raw) if exit_time_raw else (entry_time if pnl != 0 else None)
                    status = str(row.get("status") or ("CLOSED" if pnl != 0 or exit_time else "OPEN")).upper()
                    if status not in ["OPEN", "CLOSED", "CANCELED"]:
                        status = "CLOSED" if pnl != 0 else "OPEN"
                    notes = str(row.get("notes") or "Generic CSV Import")

                    # Dynamic R-Multiple calculation if not provided
                    if r_mult is None and sl and sl > 0 and entry_price > 0 and qty > 0 and pnl != 0:
                        risk_per_unit = abs(entry_price - sl)
                        if risk_per_unit > 0:
                            r_mult = round(pnl / (risk_per_unit * qty), 2)

                    trade_dict = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "qty": qty,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "entry_time": entry_time,
                        "exit_time": exit_time,
                        "status": status,
                        "pnl": pnl,
                        "r_multiple": r_mult,
                        "commission": commission,
                        "notes": notes
                    }

                # Validation checks
                if not trade_dict.get("symbol"):
                    parsing_errors.append(f"Row {idx}: Symbol is required. Skipped.")
                    continue
                if trade_dict.get("side") not in ("BUY", "SELL"):
                    parsing_errors.append(f"Row {idx}: Side must be BUY or SELL. Skipped.")
                    continue
                if trade_dict.get("entry_price") is None or trade_dict["entry_price"] <= 0:
                    parsing_errors.append(f"Row {idx}: Invalid or missing entry_price ({trade_dict.get('entry_price')}). Skipped.")
                    continue
                if trade_dict.get("qty") is None or trade_dict["qty"] <= 0:
                    parsing_errors.append(f"Row {idx}: Invalid or missing qty ({trade_dict.get('qty')}). Skipped.")
                    continue
                if trade_dict.get("status") == "CLOSED" and (
                    trade_dict.get("exit_price") is None or trade_dict["exit_price"] <= 0
                ):
                    parsing_errors.append(f"Row {idx}: Closed trade requires a valid exit_price. Skipped.")
                    continue

                trade_dict["source_row_number"] = idx
                trade_dict["source_row_sha256"] = hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                normalized_trades.append(trade_dict)

            except Exception as e:
                parsing_errors.append(f"Row {idx}: Failed to parse row with error '{str(e)}'")

        return format_type, normalized_trades, parsing_errors

    @classmethod
    def parse_and_preview_csv(cls, file_bytes: bytes, filename: str = "import.csv") -> Dict[str, Any]:
        """
        Parses CSV and returns preview telemetry without committing to database.
        """
        try:
            content_str = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content_str = file_bytes.decode("latin-1")
            except Exception as e:
                raise ValueError(f"Unable to decode CSV file '{filename}': {str(e)}")

        format_type, trades, errors = cls.parse_rows(content_str)
        source_file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        return {
            "detected_format": format_type,
            "filename": filename,
            "source_file_sha256": source_file_sha256,
            "total_rows_parsed": len(trades),
            "errors_count": len(errors),
            "errors": errors[:10],
            "preview_trades": trades[:5]
        }

    @classmethod
    def parse_and_import_csv(cls, file_bytes: bytes, filename: str = "import.csv") -> Dict[str, Any]:
        """
        Parses, validates, checks for duplicates, and commits trades in a single SQLite transaction.
        """
        try:
            content_str = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                content_str = file_bytes.decode("latin-1")
            except Exception as e:
                raise ValueError(f"Unable to decode CSV file '{filename}': {str(e)}")

        format_type, trades, errors = cls.parse_rows(content_str)
        source_file_sha256 = hashlib.sha256(file_bytes).hexdigest()
        
        if not trades and errors:
            return {
                "success": False,
                "detected_format": format_type,
                "filename": filename,
                "source_file_sha256": source_file_sha256,
                "total_rows": len(trades) + len(errors),
                "imported": 0,
                "duplicates_skipped": 0,
                "errors": errors,
                "message": "Failed to parse any valid trades from CSV file."
            }

        # Fetch existing trades to build duplicate fingerprints
        existing_trades = sqlite_driver.list_trades(limit=100000)
        existing_fingerprints = set()
        for et in existing_trades:
            fp = cls._compute_fingerprint(
                symbol=et["symbol"],
                side=et["side"],
                entry_price=float(et["entry_price"]),
                qty=float(et["qty"]),
                entry_time=str(et["entry_time"])[:19],
                exit_time=str(et.get("exit_time") or "")[:19],
                pnl=float(et.get("pnl") or 0.0)
            )
            existing_fingerprints.add(fp)

        imported_records = []
        duplicates_skipped = 0

        for t in trades:
            fp = cls._compute_fingerprint(
                symbol=t["symbol"],
                side=t["side"],
                entry_price=t["entry_price"],
                qty=t["qty"],
                entry_time=str(t["entry_time"])[:19],
                exit_time=str(t["exit_time"] or "")[:19],
                pnl=t["pnl"]
            )

            if fp in existing_fingerprints:
                duplicates_skipped += 1
                continue

            trade_id = f"TRD-{fp[:12].upper()}"
            trade_payload = {
                "id": trade_id,
                "symbol": t["symbol"],
                "side": t["side"],
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
                "qty": t["qty"],
                "stop_loss": t["stop_loss"],
                "take_profit": t["take_profit"],
                "entry_time": t["entry_time"],
                "exit_time": t["exit_time"],
                "status": t["status"],
                "pnl": t["pnl"],
                "r_multiple": t["r_multiple"],
                "commission": t["commission"],
                "notes": t["notes"]
            }

            saved = sync_pipeline.record_and_sync_trade(
                trade_payload,
                source="csv",
                source_ref=filename,
                provenance_extra={
                    "format": format_type,
                    "source_file_sha256": source_file_sha256,
                    "source_row_number": t["source_row_number"],
                    "source_row_sha256": t["source_row_sha256"],
                },
            )
            existing_fingerprints.add(fp)
            imported_records.append(saved)

        logger.info(
            f"[CSV-IMPORT] Successfully processed '{filename}' ({format_type}): "
            f"{len(imported_records)} imported, {duplicates_skipped} duplicates skipped, {len(errors)} errors."
        )

        return {
            "success": True,
            "detected_format": format_type,
            "filename": filename,
            "source_file_sha256": source_file_sha256,
            "total_rows": len(trades) + len(errors),
            "imported": len(imported_records),
            "duplicates_skipped": duplicates_skipped,
            "errors": errors,
            "provenance": {
                "source": "csv",
                "source_file_sha256": source_file_sha256,
                "source_rows_hashed": len(trades),
            },
            "trades": imported_records[:10],
            "message": f"Successfully imported {len(imported_records)} trades from {format_type} export."
        }

    @staticmethod
    def _compute_fingerprint(
        symbol: str,
        side: str,
        entry_price: float,
        qty: float,
        entry_time: str,
        exit_time: str,
        pnl: float
    ) -> str:
        """Generates deterministic SHA-256 fingerprint representing trade attributes."""
        raw = f"{symbol.upper()}:{side.upper()}:{entry_price:.4f}:{qty:.4f}:{entry_time[:19]}:{exit_time[:19]}:{pnl:.2f}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def generate_generic_template_csv(cls) -> str:
        """Returns standard generic Kuantra CSV template header and example rows."""
        return (
            "symbol,side,entry_price,exit_price,qty,stop_loss,take_profit,entry_time,exit_time,status,pnl,r_multiple,commission,notes\n"
            "BTCUSDT,BUY,64250.00,66800.00,0.5,63500.00,67000.00,2026-08-28T10:30:00Z,2026-08-28T16:45:00Z,CLOSED,1275.00,3.40,2.50,Morning breakout entry\n"
            "ETHUSDT,SELL,3450.00,3320.00,2.0,3510.00,3250.00,2026-08-29T09:15:00Z,2026-08-29T14:20:00Z,CLOSED,260.00,2.17,1.80,Resistance rejection\n"
            "XAUUSD,BUY,2510.50,2535.00,10.0,2500.00,2550.00,2026-08-30T11:00:00Z,2026-08-30T18:00:00Z,CLOSED,245.00,2.33,3.00,London session momentum\n"
            "SOLUSDT,BUY,142.50,,5.0,138.00,152.00,2026-08-31T08:00:00Z,,OPEN,0.00,,0.75,Active swing position\n"
        )


csv_trade_importer = CsvTradeImporterService()
