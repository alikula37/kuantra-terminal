"""Bulk journal export: one filtered snapshot, two deterministic artifacts.

CSV and the PDF report are built from the same snapshot object, so a given
filter selection produces the same records, the same totals and the same
snapshot hash in both formats.  The service never runs its own PnL engine: it
reads the journal through the read adapter, classifies provenance explicitly and
reuses the server-verified instrument catalog for currency grouping.

Rules encoded here:

- Europe/Istanbul is the display and filter timezone; the date basis (entry or
  close) is always stated in the artifact.
- OPEN, CLOSED and CANCELED records are separated; CANCELED records never join
  performance figures.
- An unknown PnL stays unknown (counted, never zero-filled).
- Money totals are produced only inside one server-verified quote asset; records
  without a verified quote asset are counted and excluded from totals.
- Local TP/SL estimates (basis ``LOCAL_ESTIMATE``) are reported in their own
  section and are never added to realized results.
- Limits fail closed: exceeding the record or byte ceiling raises instead of
  silently truncating.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.core.csv_safety import safe_csv_cell
from app.core.trade_time import ISTANBUL_TZ
from app.db.repositories.evidence_ledger_repo import canonical_json
from app.services.pdf_report import TableBlock, render_report_pdf
from app.services.trade_read_adapter import trade_read_adapter

MAX_EXPORT_TRADES = 2_000
MAX_EXPORT_BYTES = 8 * 1024 * 1024
PAGE_SIZE = 1_000
SUPPORTED_LANGS = ("en", "tr", "de")
SUPPORTED_FORMATS = ("csv", "pdf")
SUPPORTED_SCOPES = ("filtered", "all")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class JournalExportError(ValueError):
    """Base class for journal export failures."""


class JournalExportRequestError(JournalExportError):
    """Raised when the requested format/scope/filter combination is invalid."""


class JournalExportLimitError(JournalExportError):
    """Raised when the snapshot exceeds a safety ceiling (never truncated)."""


_COLUMN_KEYS = (
    "record_no", "trade_id", "status", "symbol", "side", "position_type",
    "entry_time_istanbul", "entry_time_utc", "entry_price", "qty", "qty_unit",
    "close_time_istanbul", "close_time_utc", "exit_price", "pnl_recorded",
    "pnl_known", "pnl_basis", "commission", "close_source", "record_mode",
    "verified_quote_asset", "estimated_gross_pnl", "notes", "snapshot_sha256",
)

_TR_HEADERS = (
    "kayit_no", "trade_id", "durum", "sembol", "yon", "pozisyon_tipi",
    "giris_zamani_istanbul", "giris_zamani_utc", "giris_fiyati", "miktar",
    "miktar_birimi", "kapanis_zamani_istanbul", "kapanis_zamani_utc",
    "kapanis_fiyati", "pnl_kayitli", "pnl_biliniyor", "pnl_kaynagi", "komisyon",
    "kapanis_kaynagi", "kayit_modu", "dogrulanmis_kotasyon",
    "tahmini_brut_pnl", "notlar", "snapshot_sha256",
)
_DE_HEADERS = (
    "datensatz_nr", "trade_id", "status", "symbol", "seite", "positionstyp",
    "einstiegszeit_istanbul", "einstiegszeit_utc", "einstiegspreis", "menge",
    "mengeneinheit", "schlusszeit_istanbul", "schlusszeit_utc", "ausstiegspreis",
    "pnl_erfasst", "pnl_bekannt", "pnl_basis", "provision", "schlussquelle",
    "aufzeichnungsmodus", "verifizierte_notierung", "geschaetzter_brutto_pnl",
    "notizen", "snapshot_sha256",
)
CSV_HEADERS = {"en": _COLUMN_KEYS, "tr": _TR_HEADERS, "de": _DE_HEADERS}

_LABELS = {
    "en": {
        "title": "Kuantra Journal Report",
        "period_all": "Period: all records",
        "period_range": "Period: {start} – {end} (inclusive)",
        "basis_entry": "Date basis: entry date",
        "basis_close": "Date basis: close date",
        "timezone": "Time zone: Europe/Istanbul",
        "generated": "Generated: {istanbul} (Istanbul) / {utc} UTC",
        "records": "Records: {total} total · {open} open · {closed} closed · {canceled} canceled",
        "realized_heading": "Realized results (recorded)",
        "realized_line": "{quote}: {amount} ({count} records)",
        "realized_split": "of which user-reported (net of fees): {user_amount}; source-declared: {source_amount}",
        "realized_none": "No verified-currency realized total could be produced.",
        "unknown": "Unknown PnL (not counted in totals): {count}",
        "unverified": "Records without a verified quote asset (excluded from money totals): {count}",
        "estimated_heading": "Estimated gross result (local TP/SL, fees excluded)",
        "estimated_line": "{quote}: {amount} ({count} records)",
        "estimated_note": "These values are local estimates and are not added to realized results.",
        "open_heading": "Open trades",
        "closed_heading": "Closed trades",
        "canceled_heading": "Canceled records (excluded from performance): {count}",
        "canceled_ids": "Canceled record ids: {ids}",
        "notes_heading": "Notes",
        "empty": "No trades match this period; nothing was reported as profit or loss.",
        "footer": "Local journal snapshot · not an exchange statement",
        "page": "Page",
        "closed_cols": ["ID", "Close (Istanbul)", "Symbol", "Side", "Qty", "Entry", "Exit", "PnL", "Source"],
        "open_cols": ["ID", "Entry (Istanbul)", "Symbol", "Side", "Qty", "Entry", "SL", "TP"],
        "unknown_basis": "unknown",
        "pdf_source_user": "user-reported",
        "pdf_source_other": "source-declared",
        "pdf_source_unknown": "unknown",
    },
    "tr": {
        "title": "Kuantra İşlem Raporu",
        "period_all": "Dönem: tüm kayıtlar",
        "period_range": "Dönem: {start} – {end} (dahil)",
        "basis_entry": "Tarih bazı: giriş tarihi",
        "basis_close": "Tarih bazı: kapanış tarihi",
        "timezone": "Saat dilimi: Europe/Istanbul",
        "generated": "Oluşturuldu: {istanbul} (İstanbul) / {utc} UTC",
        "records": "Kayıtlar: {total} toplam · {open} açık · {closed} kapanmış · {canceled} iptal",
        "realized_heading": "Gerçekleşmiş sonuçlar (kayıtlı)",
        "realized_line": "{quote}: {amount} ({count} kayıt)",
        "realized_split": "bunun kullanıcı bildirimi (ücretler düşülmüş): {user_amount}; kaynak bildirimi: {source_amount}",
        "realized_none": "Doğrulanmış para birimi için gerçekleşmiş toplam üretilemedi.",
        "unknown": "Bilinmeyen PnL (toplama katılmadı): {count}",
        "unverified": "Doğrulanmış kotasyon birimi olmayan kayıtlar (para toplamlarına katılmadı): {count}",
        "estimated_heading": "Tahmini brüt sonuç (yerel TP/SL, ücretler hariç)",
        "estimated_line": "{quote}: {amount} ({count} kayıt)",
        "estimated_note": "Bu değerler yerel tahminlerdir; gerçekleşmiş sonuçlara eklenmez.",
        "open_heading": "Açık işlemler",
        "closed_heading": "Kapanmış işlemler",
        "canceled_heading": "İptal edilen kayıtlar (performans dışı): {count}",
        "canceled_ids": "İptal kayıt kimlikleri: {ids}",
        "notes_heading": "Notlar",
        "empty": "Bu dönemde kayıt yok; kazanç veya zarar olarak raporlanacak bir sonuç üretilmedi.",
        "footer": "Yerel günlük anlık görüntüsü · borsa ekstresi değildir",
        "page": "Sayfa",
        "closed_cols": ["ID", "Kapanış (İstanbul)", "Sembol", "Yön", "Miktar", "Giriş", "Çıkış", "PnL", "Kaynak"],
        "open_cols": ["ID", "Giriş (İstanbul)", "Sembol", "Yön", "Miktar", "Giriş", "SL", "TP"],
        "unknown_basis": "bilinmiyor",
        "pdf_source_user": "kullanıcı bildirimi",
        "pdf_source_other": "kaynak bildirimi",
        "pdf_source_unknown": "bilinmiyor",
    },
    "de": {
        "title": "Kuantra Journal-Bericht",
        "period_all": "Zeitraum: alle Datensätze",
        "period_range": "Zeitraum: {start} – {end} (einschließlich)",
        "basis_entry": "Datumsbasis: Einstiegsdatum",
        "basis_close": "Datumsbasis: Schlussdatum",
        "timezone": "Zeitzone: Europe/Istanbul",
        "generated": "Erstellt: {istanbul} (Istanbul) / {utc} UTC",
        "records": "Datensätze: {total} gesamt · {open} offen · {closed} geschlossen · {canceled} storniert",
        "realized_heading": "Realisierte Ergebnisse (erfasst)",
        "realized_line": "{quote}: {amount} ({count} Datensätze)",
        "realized_split": "davon nutzerberichtet (netto nach Gebühren): {user_amount}; quellenbasiert: {source_amount}",
        "realized_none": "Für verifizierte Notierungen konnte keine realisierte Summe erstellt werden.",
        "unknown": "Unbekannter PnL (nicht in Summen): {count}",
        "unverified": "Datensätze ohne verifizierte Notierung (von Geldsummen ausgeschlossen): {count}",
        "estimated_heading": "Geschätztes Bruttoergebnis (lokale TP/SL, ohne Gebühren)",
        "estimated_line": "{quote}: {amount} ({count} Datensätze)",
        "estimated_note": "Diese Werte sind lokale Schätzungen und werden nicht zu realisierten Ergebnissen addiert.",
        "open_heading": "Offene Trades",
        "closed_heading": "Geschlossene Trades",
        "canceled_heading": "Stornierte Datensätze (nicht in der Performance): {count}",
        "canceled_ids": "IDs stornierter Datensätze: {ids}",
        "notes_heading": "Notizen",
        "empty": "Keine Trades in diesem Zeitraum; es wird kein Gewinn oder Verlust ausgewiesen.",
        "footer": "Lokale Journal-Momentaufnahme · kein Börsenauszug",
        "page": "Seite",
        "closed_cols": ["ID", "Schluss (Istanbul)", "Symbol", "Seite", "Menge", "Einstieg", "Ausstieg", "PnL", "Quelle"],
        "open_cols": ["ID", "Einstieg (Istanbul)", "Symbol", "Seite", "Menge", "Einstieg", "SL", "TP"],
        "unknown_basis": "unbekannt",
        "pdf_source_user": "nutzerberichtet",
        "pdf_source_other": "quellenbasiert",
        "pdf_source_unknown": "unbekannt",
    },
}


@dataclass(frozen=True)
class JournalExportArtifact:
    content: bytes
    media_type: str
    filename: str
    record_count: int
    snapshot_sha256: str
    artifact_sha256: str


@dataclass
class JournalSnapshot:
    records: List[Dict[str, Any]]
    filters: Dict[str, Any]
    summary: Dict[str, Any] = field(default_factory=dict)
    snapshot_sha256: str = ""


def _parse_instant(value: Any) -> Optional[datetime]:
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


def _istanbul_label(value: Any) -> str:
    parsed = _parse_instant(value)
    if parsed is None:
        return ""
    return parsed.astimezone(ISTANBUL_TZ).strftime("%Y-%m-%d %H:%M")


def _istanbul_day(value: Any) -> Optional[str]:
    parsed = _parse_instant(value)
    if parsed is None:
        return None
    return parsed.astimezone(ISTANBUL_TZ).date().isoformat()


def _utc_label(value: Any) -> str:
    parsed = _parse_instant(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_amount(value: float, lang: str) -> str:
    text = f"{value:,.2f}"
    if lang in {"tr", "de"}:
        text = text.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")
    return text


def _number(value: Any, lang: str) -> str:
    parsed = _amount(value)
    if parsed is None:
        return ""
    return _format_amount(parsed, lang)


class JournalExportService:
    """Build one snapshot and render it as CSV or PDF."""

    def __init__(
        self,
        adapter: Any = None,
        catalog: Any = None,
        tracking_service: Any = None,
    ):
        self.adapter = adapter or trade_read_adapter
        if catalog is None:
            from app.services.market_data.instrument_catalog import instrument_catalog

            catalog = instrument_catalog
        self.catalog = catalog
        if tracking_service is None:
            from app.db.sqlite_driver import sqlite_driver
            from app.services.local_tracking import LocalTrackingService

            tracking_service = LocalTrackingService(sqlite_driver)
        self.tracking_service = tracking_service

    # -- request handling -------------------------------------------------

    @staticmethod
    def _validate(
        *,
        format: str,
        lang: str,
        scope: str,
        date_from: Optional[str],
        date_to: Optional[str],
        date_basis: str,
    ) -> None:
        if format not in SUPPORTED_FORMATS:
            raise JournalExportRequestError("format must be csv or pdf")
        if lang not in SUPPORTED_LANGS:
            raise JournalExportRequestError("lang must be en, tr or de")
        if scope not in SUPPORTED_SCOPES:
            raise JournalExportRequestError("scope must be filtered or all")
        if date_basis not in {"entry", "close"}:
            raise JournalExportRequestError("date_basis must be entry or close")
        for value, label in ((date_from, "date_from"), (date_to, "date_to")):
            if value in (None, ""):
                continue
            if not _DATE_RE.fullmatch(str(value)):
                raise JournalExportRequestError(f"{label} must be YYYY-MM-DD")
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError as exc:
                raise JournalExportRequestError(f"{label} must be a real calendar date") from exc
        if date_from and date_to and str(date_from) > str(date_to):
            raise JournalExportRequestError("date_from must not be after date_to")

    # -- snapshot ---------------------------------------------------------

    def _load_trades(self) -> List[Dict[str, Any]]:
        collected: List[Dict[str, Any]] = []
        offset = 0
        while True:
            page = self.adapter.list_trades(limit=PAGE_SIZE, offset=offset)
            if not page:
                break
            collected.extend(page)
            if len(collected) > MAX_EXPORT_TRADES:
                raise JournalExportLimitError(
                    f"export would cover {len(collected)}+ records; "
                    f"the safety limit is {MAX_EXPORT_TRADES} records — narrow the date range"
                )
            if len(page) < PAGE_SIZE:
                break
            offset += len(page)
        return collected

    def _estimates(self) -> Dict[str, Dict[str, Any]]:
        estimates: Dict[str, Dict[str, Any]] = {}
        for state in self.tracking_service.list():
            if not isinstance(state, dict) or state.get("basis") != "LOCAL_ESTIMATE":
                continue
            trade_id = str(state.get("trade_id") or "")
            gross = _amount(state.get("gross_pnl"))
            if not trade_id or gross is None:
                continue
            estimates[trade_id] = {"gross_pnl": gross, "state": state}
        return estimates

    def snapshot(
        self,
        *,
        scope: str,
        symbols: Optional[Sequence[str]] = None,
        statuses: Optional[Sequence[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        date_basis: str = "entry",
    ) -> JournalSnapshot:
        symbols_filter = {str(item).strip().upper() for item in (symbols or []) if str(item).strip()}
        statuses_filter = {str(item).strip().upper() for item in (statuses or []) if str(item).strip()}
        estimates = self._estimates()
        records: List[Dict[str, Any]] = []
        for trade in self._load_trades():
            status = str(trade.get("status") or "UNKNOWN").upper()
            symbol = str(trade.get("symbol") or "").upper()
            if scope == "filtered":
                if symbols_filter and symbol not in symbols_filter:
                    continue
                if statuses_filter and status not in statuses_filter:
                    continue
                if date_from or date_to:
                    basis_value = trade.get("exit_time") if date_basis == "close" else trade.get("entry_time")
                    day = _istanbul_day(basis_value)
                    if day is None:
                        continue
                    if date_from and day < str(date_from):
                        continue
                    if date_to and day > str(date_to):
                        continue
            verified = bool(self.catalog.is_verified(symbol)) if symbol else False
            catalog_row = self.catalog.get(symbol) if verified else None
            quote = str((catalog_row or {}).get("quote_asset") or "").upper() or None
            pnl = _amount(trade.get("pnl"))
            close_source = str(trade.get("close_source") or "").upper()
            estimate = estimates.get(str(trade.get("id")))
            records.append({
                "id": str(trade.get("id") or ""),
                "trade_id": str(trade.get("id") or ""),
                "status": status,
                "symbol": symbol,
                "side": str(trade.get("side") or "").upper(),
                "position_type": str(trade.get("position_type") or "UNKNOWN").upper(),
                "entry_price": _amount(trade.get("entry_price")),
                "exit_price": _amount(trade.get("exit_price")),
                "qty": _amount(trade.get("qty")),
                "qty_unit": str(trade.get("qty_unit") or "UNKNOWN").upper(),
                "stop_loss": _amount(trade.get("stop_loss")),
                "take_profit": _amount(trade.get("take_profit")),
                "entry_time_istanbul": _istanbul_label(trade.get("entry_time")),
                "entry_time_utc": _utc_label(trade.get("entry_time")),
                "close_time_istanbul": _istanbul_label(trade.get("exit_time")),
                "close_time_utc": _utc_label(trade.get("exit_time")),
                "pnl_recorded": pnl,
                "pnl_known": pnl is not None,
                "pnl_basis": (
                    "USER_REPORTED_NET" if close_source == "USER_REPORTED"
                    else "SOURCE_DECLARED" if pnl is not None
                    else ""
                ),
                "commission": _amount(trade.get("commission")),
                "close_source": close_source or "UNKNOWN",
                "record_mode": str(trade.get("record_mode") or "UNKNOWN").upper(),
                "verified_quote_asset": quote,
                "estimated_gross_pnl": estimate["gross_pnl"] if estimate else None,
                "notes": str(trade.get("notes") or ""),
            })
        snapshot_payload = {
            "scope": scope,
            "symbols": sorted(symbols_filter) if scope == "filtered" else [],
            "statuses": sorted(statuses_filter) if scope == "filtered" else [],
            "date_from": date_from if scope == "filtered" else None,
            "date_to": date_to if scope == "filtered" else None,
            "date_basis": date_basis,
            "records": records,
        }
        snapshot_sha256 = hashlib.sha256(canonical_json(snapshot_payload).encode("utf-8")).hexdigest()
        snap = JournalSnapshot(
            records=records,
            filters={
                "scope": scope,
                "symbols": sorted(symbols_filter),
                "statuses": sorted(statuses_filter),
                "date_from": date_from,
                "date_to": date_to,
                "date_basis": date_basis,
            },
            snapshot_sha256=snapshot_sha256,
        )
        snap.summary = self._summarize(snap)
        if len(records) > MAX_EXPORT_TRADES:
            raise JournalExportLimitError(
                f"export would cover {len(records)} records; the safety limit is {MAX_EXPORT_TRADES}"
            )
        return snap

    # -- summary ----------------------------------------------------------

    @staticmethod
    def _summarize(snap: JournalSnapshot) -> Dict[str, Any]:
        counts = {"total": len(snap.records), "open": 0, "closed": 0, "canceled": 0}
        realized: Dict[str, Dict[str, Any]] = {}
        unknown_pnl_closed = 0
        unverified_currency_records = 0
        estimated_trades = 0
        estimated_gross: Dict[str, float] = {}
        estimated_unverified = 0
        canceled_ids: List[str] = []

        for record in snap.records:
            status = record["status"]
            if status == "OPEN":
                counts["open"] += 1
            elif status == "CLOSED":
                counts["closed"] += 1
            elif status == "CANCELED":
                counts["canceled"] += 1
                if len(canceled_ids) < 20:
                    canceled_ids.append(record["trade_id"])

            if status == "CLOSED":
                pnl = record["pnl_recorded"]
                if pnl is None:
                    unknown_pnl_closed += 1
                elif record["verified_quote_asset"]:
                    bucket = realized.setdefault(
                        record["verified_quote_asset"],
                        {"user_reported_net": 0.0, "source_declared": 0.0, "count": 0},
                    )
                    if record["close_source"] == "USER_REPORTED":
                        bucket["user_reported_net"] += pnl
                    else:
                        bucket["source_declared"] += pnl
                    bucket["count"] += 1
                else:
                    unverified_currency_records += 1

            if record["estimated_gross_pnl"] is not None:
                estimated_trades += 1
                if record["verified_quote_asset"]:
                    estimated_gross[record["verified_quote_asset"]] = (
                        estimated_gross.get(record["verified_quote_asset"], 0.0)
                        + record["estimated_gross_pnl"]
                    )
                else:
                    estimated_unverified += 1

        for bucket in realized.values():
            bucket["user_reported_net"] = round(bucket["user_reported_net"], 2)
            bucket["source_declared"] = round(bucket["source_declared"], 2)
        estimated_gross = {quote: round(value, 2) for quote, value in estimated_gross.items()}

        warnings: List[str] = []
        if unknown_pnl_closed:
            warnings.append(f"unknown_pnl:{unknown_pnl_closed}")
        if unverified_currency_records or estimated_unverified:
            warnings.append(
                f"unverified_currency:{unverified_currency_records + estimated_unverified}"
            )
        if estimated_trades:
            warnings.append(f"local_estimates:{estimated_trades}")
        if counts["canceled"]:
            warnings.append(f"canceled_records:{counts['canceled']}")

        return {
            "counts": counts,
            "realized_total_by_quote": realized,
            "money_totals_available": bool(realized),
            "unknown_pnl_closed": unknown_pnl_closed,
            "unverified_currency_records": unverified_currency_records,
            "estimated_trades": estimated_trades,
            "estimated_gross_by_quote": estimated_gross,
            "estimated_unverified_currency_trades": estimated_unverified,
            "canceled_ids": canceled_ids,
            "warnings": warnings,
            "record_count": counts["total"],
            "max_records": MAX_EXPORT_TRADES,
            "exceeds_limit": counts["total"] > MAX_EXPORT_TRADES,
            "snapshot_sha256": snap.snapshot_sha256,
        }

    # -- artifacts --------------------------------------------------------

    def preview(
        self,
        *,
        scope: str,
        symbols: Optional[Sequence[str]] = None,
        statuses: Optional[Sequence[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        date_basis: str = "entry",
    ) -> Dict[str, Any]:
        self._validate(
            format="csv", lang="en", scope=scope,
            date_from=date_from, date_to=date_to, date_basis=date_basis,
        )
        snapshot = self.snapshot(
            scope=scope, symbols=symbols, statuses=statuses,
            date_from=date_from, date_to=date_to, date_basis=date_basis,
        )
        summary = dict(snapshot.summary)
        if summary["exceeds_limit"]:
            raise JournalExportLimitError(
                f"export would cover {summary['record_count']} records; "
                f"the safety limit is {MAX_EXPORT_TRADES} records — narrow the date range"
            )
        return summary

    def export(
        self,
        *,
        format: str,
        lang: str,
        scope: str,
        symbols: Optional[Sequence[str]] = None,
        statuses: Optional[Sequence[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        date_basis: str = "entry",
    ) -> JournalExportArtifact:
        self._validate(
            format=format, lang=lang, scope=scope,
            date_from=date_from, date_to=date_to, date_basis=date_basis,
        )
        snapshot = self.snapshot(
            scope=scope, symbols=symbols, statuses=statuses,
            date_from=date_from, date_to=date_to, date_basis=date_basis,
        )
        if snapshot.summary["exceeds_limit"]:
            raise JournalExportLimitError(
                f"export would cover {snapshot.summary['record_count']} records; "
                f"the safety limit is {MAX_EXPORT_TRADES} records — narrow the date range"
            )
        if format == "csv":
            content = self._csv(snapshot, lang)
            media_type = "text/csv; charset=utf-8"
        else:
            content = self._pdf(snapshot, lang)
            media_type = "application/pdf"
        if len(content) > MAX_EXPORT_BYTES:
            raise JournalExportLimitError(
                f"export artifact would be {len(content)} bytes; the safety limit is "
                f"{MAX_EXPORT_BYTES} bytes — narrow the date range"
            )
        suffix = "csv" if format == "csv" else "pdf"
        period = self._period_token(snapshot.filters)
        filename = f"kuantra-journal-{period}-{snapshot.snapshot_sha256[:8]}.{suffix}"
        return JournalExportArtifact(
            content=content,
            media_type=media_type,
            filename=filename,
            record_count=snapshot.summary["record_count"],
            snapshot_sha256=snapshot.snapshot_sha256,
            artifact_sha256=hashlib.sha256(content).hexdigest(),
        )

    @staticmethod
    def _period_token(filters: Dict[str, Any]) -> str:
        date_from = str(filters.get("date_from") or "").replace("-", "") or "all"
        date_to = str(filters.get("date_to") or "").replace("-", "") or "all"
        return f"{date_from}-{date_to}"

    def _csv(self, snapshot: JournalSnapshot, lang: str) -> bytes:
        headers = CSV_HEADERS[lang]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for index, record in enumerate(snapshot.records, start=1):
            values = {
                "record_no": index,
                "trade_id": record["trade_id"],
                "status": record["status"],
                "symbol": record["symbol"],
                "side": record["side"],
                "position_type": record["position_type"],
                "entry_time_istanbul": record["entry_time_istanbul"],
                "entry_time_utc": record["entry_time_utc"],
                "entry_price": record["entry_price"],
                "qty": record["qty"],
                "qty_unit": record["qty_unit"],
                "close_time_istanbul": record["close_time_istanbul"],
                "close_time_utc": record["close_time_utc"],
                "exit_price": record["exit_price"],
                "pnl_recorded": record["pnl_recorded"],
                "pnl_known": "true" if record["pnl_known"] else "false",
                "pnl_basis": record["pnl_basis"],
                "commission": record["commission"],
                "close_source": record["close_source"],
                "record_mode": record["record_mode"],
                "verified_quote_asset": record["verified_quote_asset"] or "",
                "estimated_gross_pnl": record["estimated_gross_pnl"],
                "notes": record["notes"],
                "snapshot_sha256": snapshot.snapshot_sha256,
            }
            writer.writerow({
                headers[index]: safe_csv_cell(values.get(_COLUMN_KEYS[index]))
                for index in range(len(_COLUMN_KEYS))
            })
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    def _pdf(self, snapshot: JournalSnapshot, lang: str) -> bytes:
        labels = _LABELS[lang]
        summary = snapshot.summary
        filters = snapshot.filters
        blocks: List[tuple[str, Any]] = []
        if filters.get("date_from") or filters.get("date_to"):
            period = labels["period_range"].format(
                start=filters.get("date_from") or "…", end=filters.get("date_to") or "…")
        else:
            period = labels["period_all"]
        meta = [
            period,
            labels["basis_close"] if filters.get("date_basis") == "close" else labels["basis_entry"],
            labels["timezone"],
            labels["generated"].format(
                istanbul=datetime.now(ISTANBUL_TZ).strftime("%Y-%m-%d %H:%M"),
                utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            ),
            labels["records"].format(**summary["counts"]),
        ]

        if not snapshot.records:
            blocks.append(("paragraph", labels["empty"]))
        else:
            blocks.append(("heading", labels["realized_heading"]))
            if summary["realized_total_by_quote"]:
                for quote, bucket in sorted(summary["realized_total_by_quote"].items()):
                    total = bucket["user_reported_net"] + bucket["source_declared"]
                    blocks.append(("paragraph", labels["realized_line"].format(
                        quote=quote, amount=_format_amount(total, lang), count=bucket["count"])))
                    blocks.append(("paragraph", labels["realized_split"].format(
                        user_amount=_format_amount(bucket["user_reported_net"], lang),
                        source_amount=_format_amount(bucket["source_declared"], lang))))
            else:
                blocks.append(("warning", labels["realized_none"]))
            if summary["unknown_pnl_closed"]:
                blocks.append(("warning", labels["unknown"].format(count=summary["unknown_pnl_closed"])))
            if summary["unverified_currency_records"]:
                blocks.append(("warning", labels["unverified"].format(
                    count=summary["unverified_currency_records"])))

            if summary["estimated_trades"]:
                blocks.append(("heading", labels["estimated_heading"]))
                for quote, total in sorted(summary["estimated_gross_by_quote"].items()):
                    blocks.append(("paragraph", labels["estimated_line"].format(
                        quote=quote, amount=_format_amount(total, lang), count=summary["estimated_trades"])))
                if summary["estimated_unverified_currency_trades"]:
                    blocks.append(("warning", labels["unverified"].format(
                        count=summary["estimated_unverified_currency_trades"])))
                blocks.append(("paragraph", labels["estimated_note"]))

            if summary["counts"]["canceled"]:
                blocks.append(("paragraph", labels["canceled_heading"].format(
                    count=summary["counts"]["canceled"])))
                if summary["canceled_ids"]:
                    blocks.append(("paragraph", labels["canceled_ids"].format(
                        ids=", ".join(summary["canceled_ids"]))))

            open_records = [record for record in snapshot.records if record["status"] == "OPEN"]
            if open_records:
                blocks.append(("heading", labels["open_heading"]))
                blocks.append(("table", TableBlock(
                    headers=labels["open_cols"],
                    widths=[64, 74, 62, 34, 46, 58, 62, 62],
                    rows=[
                        [
                            record["trade_id"], record["entry_time_istanbul"], record["symbol"], record["side"],
                            _number(record["qty"], lang), _number(record["entry_price"], lang),
                            _number(record["stop_loss"], lang), _number(record["take_profit"], lang),
                        ]
                        for record in open_records
                    ],
                )))

            closed_records = [record for record in snapshot.records if record["status"] == "CLOSED"]
            if closed_records:
                blocks.append(("heading", labels["closed_heading"]))
                blocks.append(("table", TableBlock(
                    headers=labels["closed_cols"],
                    widths=[56, 72, 60, 38, 42, 50, 50, 46, 90],
                    rows=[
                        [
                            record["trade_id"], record["close_time_istanbul"], record["symbol"], record["side"],
                            _number(record["qty"], lang), _number(record["entry_price"], lang),
                            _number(record["exit_price"], lang), _number(record["pnl_recorded"], lang),
                            self._source_label(record, labels),
                        ]
                        for record in closed_records
                    ],
                )))

            notes = [record for record in snapshot.records if record["notes"].strip()]
            if notes:
                blocks.append(("heading", labels["notes_heading"]))
                for record in notes:
                    blocks.append(("note", f"{record['trade_id']} — {record['symbol']}"))
                    blocks.append(("paragraph", record["notes"]))

        return render_report_pdf(
            title=labels["title"],
            meta_lines=meta,
            blocks=blocks,
            footer_text=f"{labels['footer']} · {snapshot.snapshot_sha256[:16]}",
            page_word=labels["page"],
        )

    @staticmethod
    def _source_label(record: Dict[str, Any], labels: Dict[str, Any]) -> str:
        if record["close_source"] == "USER_REPORTED":
            return labels["pdf_source_user"]
        if record["close_source"] in {"", "UNKNOWN"}:
            return labels["pdf_source_unknown"]
        return labels["pdf_source_other"]


journal_export_service = JournalExportService()
