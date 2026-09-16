import React, { useEffect, useMemo, useState } from "react";
import { Download, X } from "lucide-react";
import { apiFetch, apiUrl } from "../../lib/backend";
import { downloadFromBackendDetailed } from "../../lib/desktop";
import { useTranslation } from "../../context/I18nContext";

export interface JournalExportFilters {
  symbols: string[];
  statuses: string[];
  dateFrom: string;
  dateTo: string;
}

interface JournalExportPreview {
  record_count: number;
  counts: { total: number; open: number; closed: number; canceled: number };
  warnings: string[];
  exceeds_limit: boolean;
  max_records: number;
  unknown_pnl_closed: number;
  unverified_currency_records: number;
  estimated_trades: number;
  snapshot_sha256: string;
}

type PreviewState = "loading" | "ready" | "error";
type ExportState = "idle" | "exporting" | "saved" | "cancelled" | "limit" | "failed";

const monthBounds = (month: string): { from: string; to: string } | null => {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return null;
  const year = Number(match[1]);
  const index = Number(match[2]);
  if (index < 1 || index > 12) return null;
  const lastDay = new Date(year, index, 0).getDate();
  return { from: `${match[1]}-${match[2]}-01`, to: `${match[1]}-${match[2]}-${String(lastDay).padStart(2, "0")}` };
};

export const JournalExportModal: React.FC<{ onClose: () => void; filters: JournalExportFilters }> = ({ onClose, filters }) => {
  const { t, locale } = useTranslation();
  const [scope, setScope] = useState<"filtered" | "all">("filtered");
  const [format, setFormat] = useState<"csv" | "pdf">("csv");
  const [dateBasis, setDateBasis] = useState<"entry" | "close">("entry");
  const [dateFrom, setDateFrom] = useState(filters.dateFrom);
  const [dateTo, setDateTo] = useState(filters.dateTo);
  const [month, setMonth] = useState(filters.dateFrom ? filters.dateFrom.slice(0, 7) : "");
  const [preview, setPreview] = useState<JournalExportPreview | null>(null);
  const [previewState, setPreviewState] = useState<PreviewState>("loading");
  const [exportState, setExportState] = useState<ExportState>("idle");

  const lang = locale === "tr" || locale === "de" ? locale : "en";

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("scope", scope);
    params.set("date_basis", dateBasis);
    if (scope === "filtered") {
      if (filters.symbols.length > 0) params.set("symbols", [...filters.symbols].sort().join(","));
      if (filters.statuses.length > 0) params.set("statuses", [...filters.statuses].sort().join(","));
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
    }
    return params.toString();
  }, [scope, dateBasis, filters.symbols, filters.statuses, dateFrom, dateTo]);

  useEffect(() => {
    let cancelled = false;
    setPreviewState("loading");
    setPreview(null);
    setExportState("idle");
    apiFetch(apiUrl(`/api/v1/journal/export/preview?${query}`))
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = (await response.json()) as JournalExportPreview;
        if (!cancelled) {
          setPreview(data);
          setPreviewState("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPreview(null);
          setPreviewState("error");
        }
      });
    return () => { cancelled = true; };
  }, [query]);

  const warningLabel = (warning: string): string => {
    const [code, rawCount] = warning.split(":");
    const count = Number(rawCount || 0);
    if (code === "unknown_pnl") return t("journal_export.warn_unknown_pnl", { count });
    if (code === "unverified_currency") return t("journal_export.warn_unverified_currency", { count });
    if (code === "local_estimates") return t("journal_export.warn_local_estimates", { count });
    if (code === "canceled_records") return t("journal_export.warn_canceled", { count });
    return warning;
  };

  const runExport = async () => {
    setExportState("exporting");
    const exportQuery = `${query}&format=${encodeURIComponent(format)}&lang=${encodeURIComponent(lang)}`;
    const outcome = await downloadFromBackendDetailed("/api/v1/journal/export", undefined, exportQuery);
    if (outcome.saved) { setExportState("saved"); return; }
    if (outcome.status === 413) { setExportState("limit"); return; }
    if (outcome.status === undefined || outcome.status === 200) { setExportState("cancelled"); return; }
    setExportState("failed");
  };

  const exportDisabled = previewState !== "ready" || preview === null || preview.exceeds_limit || exportState === "exporting";

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={t("journal_export.title")}>
      <div className="w-full max-w-xl max-h-[90vh] overflow-y-auto bg-[#0b0e14] border border-surface-border rounded-lg shadow-2xl font-sans">
        <div className="sticky top-0 bg-[#0d121c] border-b border-surface-border px-4 py-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">{t("journal_export.title")}</h2>
          <button type="button" onClick={onClose} aria-label={t("journal_export.close")} className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4 text-xs">
          <section className="space-y-2">
            <h3 className="text-slate-300 font-bold uppercase tracking-wide">{t("journal_export.scope")}</h3>
            <label className="flex items-start gap-2 text-slate-200">
              <input type="radio" name="journal-export-scope" data-testid="journal-export-scope-filtered" checked={scope === "filtered"} onChange={() => setScope("filtered")} />
              <span>
                <span className="block font-semibold">{t("journal_export.scope_filtered")}</span>
                <span className="block text-slate-400">{t("journal_export.scope_filtered_hint")}</span>
              </span>
            </label>
            <label className="flex items-start gap-2 text-slate-200">
              <input type="radio" name="journal-export-scope" data-testid="journal-export-scope-all" checked={scope === "all"} onChange={() => setScope("all")} />
              <span>
                <span className="block font-semibold">{t("journal_export.scope_all")}</span>
                <span className="block text-slate-400">{t("journal_export.scope_all_hint")}</span>
              </span>
            </label>
          </section>

          <section className="space-y-2">
            <h3 className="text-slate-300 font-bold uppercase tracking-wide">{t("journal_export.period")}</h3>
            <div className="flex flex-wrap items-center gap-2">
              <input type="date" data-testid="journal-export-date-from" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} aria-label={t("journal_export.date_from")} className="bg-[#111722] border border-surface-border rounded px-2 py-1.5 text-white" />
              <span className="text-slate-500">–</span>
              <input type="date" data-testid="journal-export-date-to" value={dateTo} onChange={(event) => setDateTo(event.target.value)} aria-label={t("journal_export.date_to")} className="bg-[#111722] border border-surface-border rounded px-2 py-1.5 text-white" />
              <input type="month" data-testid="journal-export-month" value={month} onChange={(event) => {
                setMonth(event.target.value);
                const bounds = monthBounds(event.target.value);
                if (bounds) { setDateFrom(bounds.from); setDateTo(bounds.to); }
              }} aria-label={t("journal_export.month")} className="bg-[#111722] border border-surface-border rounded px-2 py-1.5 text-white" />
            </div>
            <p className="text-slate-400">{t("journal_export.timezone_note")}</p>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-1.5 text-slate-200">
                <input type="radio" name="journal-export-basis" data-testid="journal-export-basis-entry" checked={dateBasis === "entry"} onChange={() => setDateBasis("entry")} />
                {t("journal_export.date_basis_entry")}
              </label>
              <label className="flex items-center gap-1.5 text-slate-200">
                <input type="radio" name="journal-export-basis" data-testid="journal-export-basis-close" checked={dateBasis === "close"} onChange={() => setDateBasis("close")} />
                {t("journal_export.date_basis_close")}
              </label>
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-slate-300 font-bold uppercase tracking-wide">{t("journal_export.format")}</h3>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-1.5 text-slate-200">
                <input type="radio" name="journal-export-format" data-testid="journal-export-format-csv" checked={format === "csv"} onChange={() => setFormat("csv")} />
                {t("journal_export.format_csv")}
              </label>
              <label className="flex items-center gap-1.5 text-slate-200">
                <input type="radio" name="journal-export-format" data-testid="journal-export-format-pdf" checked={format === "pdf"} onChange={() => setFormat("pdf")} />
                {t("journal_export.format_pdf")}
              </label>
            </div>
          </section>

          <section className="space-y-1" aria-live="polite">
            {previewState === "loading" && <p className="text-slate-400">{t("journal_export.preview_loading")}</p>}
            {previewState === "error" && <p role="alert" className="text-loss">{t("journal_export.preview_failed")}</p>}
            {previewState === "ready" && preview && (
              <>
                <p className="text-slate-200 font-semibold">
                  {t("journal_export.preview_counts", {
                    total: preview.counts.total,
                    open: preview.counts.open,
                    closed: preview.counts.closed,
                    canceled: preview.counts.canceled,
                  })}
                </p>
                {preview.warnings.map((warning) => (
                  <p key={warning} data-warning={warning} className="text-amber-300">{warningLabel(warning)}</p>
                ))}
                {preview.exceeds_limit && (
                  <p role="alert" className="text-loss">
                    {t("journal_export.limit_exceeded", { count: preview.record_count, max: preview.max_records })}
                  </p>
                )}
              </>
            )}
          </section>

          {exportState !== "idle" && exportState !== "exporting" && (
            <p role={exportState === "saved" ? "status" : "alert"} className={exportState === "saved" ? "text-gain" : "text-loss"}>
              {exportState === "saved" && t("journal_export.saved")}
              {exportState === "cancelled" && t("journal_export.cancelled")}
              {exportState === "limit" && t("journal_export.limit_exceeded", { count: preview?.record_count ?? 0, max: preview?.max_records ?? 0 })}
              {exportState === "failed" && t("journal_export.failed")}
            </p>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 rounded border border-surface-border text-slate-300 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              {t("journal_export.close")}
            </button>
            <button type="button" data-testid="journal-export-submit" onClick={() => void runExport()} disabled={exportDisabled} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-accent/50 text-accent hover:bg-accent/10 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
              <Download className="w-3.5 h-3.5" />
              {exportState === "exporting" ? t("journal_export.exporting") : t("journal_export.export")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
