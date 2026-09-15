import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, FileText, RefreshCw, ShieldCheck } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { apiFetch, apiUrl } from "../../lib/backend";

type PreviewRow = Record<string, unknown>;

type RowError = {
  section?: string;
  source_row?: number;
  reason?: string;
  fields?: unknown;
};

type Mt5Preview = {
  preview_only: boolean;
  format: string;
  template?: string;
  language?: string;
  parser_version: string;
  source_sha256: string;
  source_size_bytes: number;
  account: { masked?: string | null; basis?: string; verified?: boolean };
  account_currency?: string | null;
  time_basis?: string;
  quantity_unit?: string;
  counts: {
    orders: number;
    deals: number;
    rows_total: number;
    rows_ok: number;
    rows_with_errors: number;
  };
  date_range?: { start_source?: string; end_source?: string } | null;
  orders: PreviewRow[];
  deals: PreviewRow[];
  orders_truncated?: boolean;
  deals_truncated?: boolean;
  row_errors: RowError[];
  row_errors_truncated?: boolean;
  unsupported_sections: string[];
  warnings: string[];
  limits?: Record<string, number>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isMt5Preview(value: unknown): value is Mt5Preview {
  if (!isRecord(value) || value.preview_only !== true) return false;
  if (value.format !== "MT5_HTML_REPORT") return false;
  if (typeof value.parser_version !== "string") return false;
  if (typeof value.source_sha256 !== "string") return false;
  if (!isCount(value.source_size_bytes)) return false;
  if (!Array.isArray(value.orders) || !Array.isArray(value.deals)) return false;
  if (!Array.isArray(value.row_errors) || !Array.isArray(value.unsupported_sections)) return false;
  if (!Array.isArray(value.warnings)) return false;
  const counts = value.counts;
  if (!isRecord(counts)) return false;
  return (
    isCount(counts.orders)
    && isCount(counts.deals)
    && isCount(counts.rows_total)
    && isCount(counts.rows_ok)
    && isCount(counts.rows_with_errors)
  );
}

function text(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "—";
}

const MAX_RENDERED_ROWS = 20;

export const Mt5StatementPreview: React.FC = () => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [preview, setPreview] = useState<Mt5Preview | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  const handleFileChange = useCallback(async (file: File) => {
    controllerRef.current?.abort();
    const requestId = ++requestIdRef.current;
    setPreview(null);
    setErrorMessage(null);
    setSelectedFileName(null);

    if (!/\.(html|htm)$/i.test(file.name)) {
      setErrorMessage(t("mt5_preview.error_invalid_format"));
      return;
    }

    setSelectedFileName(file.name);
    setIsLoading(true);
    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await apiFetch(apiUrl("/api/v1/broker/statement/preview-html"), {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        const detail = isRecord(errData) && isRecord(errData.detail) && typeof errData.detail.message === "string"
          ? errData.detail.message
          : t("mt5_preview.error_generic");
        throw new Error(detail);
      }
      const data = await res.json();
      if (!isMt5Preview(data)) {
        throw new Error(t("mt5_preview.error_malformed_preview"));
      }
      if (requestId !== requestIdRef.current || controller.signal.aborted) return;
      setPreview(data);
    } catch (err: any) {
      if (requestId !== requestIdRef.current || controller.signal.aborted) return;
      setPreview(null);
      setErrorMessage(err?.message || t("mt5_preview.error_generic"));
    } finally {
      if (requestId === requestIdRef.current) {
        if (controllerRef.current === controller) controllerRef.current = null;
        if (!controller.signal.aborted) setIsLoading(false);
      }
    }
  }, [t]);

  return (
    <div className="space-y-4" data-testid="mt5-preview">
      <div
        role="status"
        data-testid="mt5-preview-only-notice"
        className="flex items-start space-x-2 p-3 rounded-lg border border-amber-400/40 bg-amber-400/10 text-amber-200 text-[11px]"
      >
        <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{t("mt5_preview.preview_only_notice")}</span>
      </div>

      <div
        role="button"
        tabIndex={0}
        aria-label={t("mt5_preview.select_file")}
        data-testid="mt5-preview-drop"
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition flex flex-col items-center justify-center space-y-2 ${
          selectedFileName ? "border-accent/40 bg-[#111722]" : "border-surface-border hover:border-slate-500 bg-[#0d121c]"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".html,.htm"
          className="hidden"
          data-testid="mt5-preview-file-input"
          onChange={(event) => {
            if (event.target.files && event.target.files.length > 0) {
              void handleFileChange(event.target.files[0]);
            }
            event.target.value = "";
          }}
        />
        <div className="w-10 h-10 rounded-full bg-[#162032] flex items-center justify-center text-accent border border-surface-border">
          {isLoading ? <RefreshCw className="w-5 h-5 animate-spin" /> : <FileText className="w-5 h-5" />}
        </div>
        {selectedFileName ? (
          <p className="text-xs font-bold text-white">{selectedFileName}</p>
        ) : (
          <div>
            <p className="text-xs font-bold text-white">{t("mt5_preview.dropzone_title")}</p>
            <p className="text-[10px] text-slate-400">{t("mt5_preview.dropzone_subtitle")}</p>
          </div>
        )}
      </div>

      {errorMessage && (
        <div role="alert" data-testid="mt5-preview-error" className="flex items-center space-x-2 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-xs">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {preview && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <span className="px-2 py-0.5 rounded bg-accent/20 border border-accent/40 text-accent font-bold uppercase">
              {t("mt5_preview.format_badge")}
            </span>
            <span className="text-slate-400">{t("mt5_preview.parser_version", { version: preview.parser_version })}</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[10px]" data-testid="mt5-preview-account">
            <div className="p-2 bg-[#111722] border border-surface-border rounded">
              <span className="text-slate-400 block uppercase">{t("mt5_preview.account_label")}</span>
              <span className="text-white font-bold">{text(preview.account?.masked)}</span>
              <span className="text-amber-300 block">{t("mt5_preview.account_basis")}</span>
            </div>
            <div className="p-2 bg-[#111722] border border-surface-border rounded">
              <span className="text-slate-400 block uppercase">{t("mt5_preview.currency_label")}</span>
              <span className="text-white font-bold">{text(preview.account_currency)}</span>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2 text-center text-[10px]" data-testid="mt5-preview-counts">
            {([
              ["counts_orders", preview.counts.orders, "text-white"],
              ["counts_deals", preview.counts.deals, "text-white"],
              ["counts_rows_ok", preview.counts.rows_ok, "text-gain"],
              ["counts_rows_errors", preview.counts.rows_with_errors, "text-amber-300"],
            ] as const).map(([key, value, className]) => (
              <div key={key} className="p-2 bg-[#111722] border border-surface-border rounded">
                <span className="text-slate-400 block uppercase">{t(`mt5_preview.${key}`)}</span>
                <span className={`text-base font-bold ${className}`}>{value}</span>
              </div>
            ))}
          </div>

          <div className="text-[10px] text-slate-400 space-y-1">
            <div>
              {t("mt5_preview.date_range_label")}: {preview.date_range?.start_source || "—"} – {preview.date_range?.end_source || "—"}
            </div>
            <div className="text-amber-300" data-testid="mt5-preview-time-basis">
              {t("mt5_preview.time_basis_warning")}
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-[11px] font-semibold text-white">{t("mt5_preview.orders_title")}</p>
            <div className="overflow-x-auto rounded-lg border border-surface-border bg-[#090d14]">
              <table className="w-full text-left text-[10px]" data-testid="mt5-preview-orders">
                <thead className="bg-[#0b0e14] text-slate-400 uppercase border-b border-surface-border">
                  <tr>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_order")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_time")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_symbol")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_type")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_volume")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_price")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/30">
                  {preview.orders.slice(0, MAX_RENDERED_ROWS).map((row, index) => (
                    <tr key={`order-${index}`}>
                      <td className="px-2 py-1.5 font-bold text-white">{text(row.source_identity)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.open_time_source)}</td>
                      <td className="px-2 py-1.5 text-slate-200">{text(row.symbol)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.type)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.volume_source)} <span className="text-slate-500">{String(row.volume_unit || "")}</span></td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.price_source)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.orders_truncated && (
              <p className="text-[10px] text-slate-400">{t("mt5_preview.truncated_note", { count: MAX_RENDERED_ROWS })}</p>
            )}
          </div>

          <div className="space-y-1">
            <p className="text-[11px] font-semibold text-white">{t("mt5_preview.deals_title")}</p>
            <div className="overflow-x-auto rounded-lg border border-surface-border bg-[#090d14]">
              <table className="w-full text-left text-[10px]" data-testid="mt5-preview-deals">
                <thead className="bg-[#0b0e14] text-slate-400 uppercase border-b border-surface-border">
                  <tr>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_deal")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_order_ref")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_time")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_symbol")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_volume")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_price")}</th>
                    <th className="px-2 py-1.5">{t("mt5_preview.col_reported_profit")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/30">
                  {preview.deals.slice(0, MAX_RENDERED_ROWS).map((row, index) => (
                    <tr key={`deal-${index}`}>
                      <td className="px-2 py-1.5 font-bold text-white">{text(row.source_identity)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.related_order_id)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.time_source)}</td>
                      <td className="px-2 py-1.5 text-slate-200">{text(row.symbol)}</td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.volume_source)} <span className="text-slate-500">{String(row.volume_unit || "")}</span></td>
                      <td className="px-2 py-1.5 text-slate-300">{text(row.price_source)}</td>
                      <td className="px-2 py-1.5 text-slate-300">
                        {row.reported_profit_source == null
                          ? t("mt5_preview.value_absent")
                          : String(row.reported_profit_source)}
                        <span className="block text-slate-500">{t("mt5_preview.reported_profit_label")}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.deals_truncated && (
              <p className="text-[10px] text-slate-400">{t("mt5_preview.truncated_note", { count: MAX_RENDERED_ROWS })}</p>
            )}
          </div>

          {preview.row_errors.length > 0 && (
            <div className="p-2 rounded border border-amber-400/30 bg-amber-400/5 text-[10px] text-amber-200 space-y-1" data-testid="mt5-preview-errors">
              <p className="font-semibold uppercase">{t("mt5_preview.row_errors_title")}</p>
              {preview.row_errors.slice(0, MAX_RENDERED_ROWS).map((error, index) => (
                <div key={`row-error-${index}`}>
                  {error.section} · {t("mt5_preview.row_label", { count: error.source_row ?? 0 })} · {error.reason}
                </div>
              ))}
            </div>
          )}

          {preview.unsupported_sections.length > 0 && (
            <div className="p-2 rounded border border-surface-border bg-[#111722] text-[10px] text-slate-300" data-testid="mt5-preview-unsupported">
              {t("mt5_preview.unsupported_sections_title")}: {preview.unsupported_sections.join(", ")}
            </div>
          )}

          {preview.warnings.length > 0 && (
            <div className="text-[10px] text-slate-400 space-y-0.5" data-testid="mt5-preview-warnings">
              {preview.warnings.map((warning) => (
                <div key={warning}>{t(`mt5_preview.warning_${warning}`)}</div>
              ))}
            </div>
          )}

          <div className="text-[9px] text-slate-500 break-all">
            {t("mt5_preview.sha_label")}: {preview.source_sha256} · {(preview.source_size_bytes / 1024).toFixed(1)} KB
          </div>
        </div>
      )}
    </div>
  );
};
