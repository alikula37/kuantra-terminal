import React, { useEffect, useState, useRef } from "react";
import { Upload, FileText, CheckCircle2, AlertTriangle, Download, X, RefreshCw } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { apiFetch, apiUrl } from "../../lib/backend";
import { downloadFromBackend } from "../../lib/desktop";
import { useDialogAccessibility } from "../../hooks/useDialogAccessibility";

interface CsvImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportSuccess?: () => void;
}

type ImportReview = {
  status: "READY" | "PARTIAL" | "REJECTED" | string;
  decision: string;
  reconciliation?: {
    status: string;
    discrepancy_count?: number;
  } | null;
  coverage?: Record<string, string | number> | null;
  discrepancies?: Array<{ type?: string; source_row_number?: number }> | null;
  source_file_sha256?: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPreviewTrade(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const numeric = (candidate: unknown): boolean => typeof candidate === "number" && Number.isFinite(candidate);
  return typeof value.symbol === "string"
    && typeof value.side === "string"
    && numeric(value.entry_price)
    && numeric(value.qty)
    && typeof value.entry_time === "string"
    && (value.exit_price == null || numeric(value.exit_price))
    && (value.pnl == null || numeric(value.pnl));
}

function isImportReview(value: unknown): value is ImportReview {
  if (!isRecord(value) || typeof value.status !== "string" || typeof value.decision !== "string") return false;
  if (value.reconciliation != null && (!isRecord(value.reconciliation)
    || typeof value.reconciliation.status !== "string"
    || (value.reconciliation.discrepancy_count != null
      && (typeof value.reconciliation.discrepancy_count !== "number" || !Number.isFinite(value.reconciliation.discrepancy_count))))) {
    return false;
  }
  if (value.coverage != null && (!isRecord(value.coverage)
    || !Object.values(value.coverage).every((item) =>
      typeof item === "string" || (typeof item === "number" && Number.isFinite(item))))) {
    return false;
  }
  if (value.discrepancies != null && (!Array.isArray(value.discrepancies)
    || !value.discrepancies.every((item) => isRecord(item)
      && (item.type == null || typeof item.type === "string")
      && (item.source_row_number == null
        || (typeof item.source_row_number === "number" && Number.isFinite(item.source_row_number)))))) {
    return false;
  }
  return value.source_file_sha256 == null || typeof value.source_file_sha256 === "string";
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

export const CsvImportModal: React.FC<CsvImportModalProps> = ({ isOpen, onClose, onImportSuccess }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previewControllerRef = useRef<AbortController | null>(null);

  useDialogAccessibility(dialogRef, onClose, closeRef);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [detectedFormat, setDetectedFormat] = useState<string | null>(null);
  const [previewTrades, setPreviewTrades] = useState<any[]>([]);
  const [previewReview, setPreviewReview] = useState<ImportReview | null>(null);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    imported: number;
    duplicates_skipped: number;
    errors: string[];
    message: string;
    import_review?: ImportReview;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen) {
      previewControllerRef.current?.abort();
      previewControllerRef.current = null;
    }
    return () => {
      previewControllerRef.current?.abort();
      previewControllerRef.current = null;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const resetState = () => {
    previewControllerRef.current?.abort();
    previewControllerRef.current = null;
    setSelectedFile(null);
    setDetectedFormat(null);
    setPreviewTrades([]);
    setPreviewReview(null);
    setTotalRows(0);
    setIsLoadingPreview(false);
    setIsImporting(false);
    setImportResult(null);
    setErrorMessage(null);
    setIsDragOver(false);
  };

  const handleClose = () => {
    if (isImporting) return;
    resetState();
    onClose();
  };

  const handleFileChange = async (file: File) => {
    previewControllerRef.current?.abort();
    previewControllerRef.current = null;
    setSelectedFile(null);
    setDetectedFormat(null);
    setPreviewTrades([]);
    setPreviewReview(null);
    setTotalRows(0);
    setIsLoadingPreview(false);
    setImportResult(null);
    if (!/\.(csv|txt)$/i.test(file.name)) {
      setErrorMessage(t("csv_import.error_invalid_format"));
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setImportResult(null);
    setIsLoadingPreview(true);
    const controller = new AbortController();
    previewControllerRef.current = controller;

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await apiFetch(apiUrl("/api/v1/journal/preview-csv"), {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: t("csv_import.error_generic") }));
        throw new Error(errData.detail || t("csv_import.error_generic"));
      }

      const data = await res.json();
      if (!isRecord(data)
        || typeof data.detected_format !== "string"
        || !Array.isArray(data.preview_trades)
        || !data.preview_trades.every(isPreviewTrade)
        || !isCount(data.total_rows_parsed)
        || (data.import_review != null && !isImportReview(data.import_review))) {
        throw new Error(t("csv_import.error_malformed_preview"));
      }
      if (previewControllerRef.current === controller && !controller.signal.aborted) {
        setDetectedFormat(data.detected_format);
        setPreviewTrades(data.preview_trades);
        setTotalRows(data.total_rows_parsed);
        setPreviewReview(data.import_review || null);
      }
    } catch (err: any) {
      if (previewControllerRef.current === controller && !controller.signal.aborted) {
        setErrorMessage(err.message || t("csv_import.error_generic"));
        setSelectedFile(null);
      }
    } finally {
      if (previewControllerRef.current === controller) {
        previewControllerRef.current = null;
        if (!controller.signal.aborted) setIsLoadingPreview(false);
      }
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleExecuteImport = async () => {
    if (!selectedFile) return;
    setIsImporting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const res = await apiFetch(apiUrl("/api/v1/journal/import-csv"), {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: t("csv_import.error_generic") }));
        throw new Error(errData.detail || t("csv_import.error_generic"));
      }

      const data = await res.json();
      if (!isRecord(data)
        || typeof data.success !== "boolean"
        || !isCount(data.imported)
        || !isCount(data.duplicates_skipped)
        || !Array.isArray(data.errors)
        || !data.errors.every((item) => typeof item === "string")
        || typeof data.message !== "string"
        || (data.import_review != null && !isImportReview(data.import_review))) {
        throw new Error(t("csv_import.error_malformed_result"));
      }
      setImportResult({
        success: data.success,
        imported: data.imported,
        duplicates_skipped: data.duplicates_skipped,
        errors: data.errors || [],
        message: data.message,
        import_review: data.import_review || undefined,
      });

      if (onImportSuccess) {
        onImportSuccess();
      }
    } catch (err: any) {
      setErrorMessage(err.message || t("csv_import.error_generic"));
    } finally {
      setIsImporting(false);
    }
  };

  const handleDownloadTemplate = () => {
    downloadFromBackend("/api/v1/journal/template-csv", "kuantra_trade_template.csv").then((ok) => {
      if (!ok) console.warn("CSV template download was cancelled or failed.");
    });
  };

  const getFormatBadgeText = (format: string | null) => {
    switch (format) {
      case "BINANCE":
        return t("csv_import.format_binance");
      case "BYBIT":
        return t("csv_import.format_bybit");
      case "METATRADER":
        return t("csv_import.format_metatrader");
      case "GENERIC_KUANTRA":
        return t("csv_import.format_generic");
      default:
        return t("csv_import.format_unknown");
    }
  };

  const importNeedsReview = Boolean(
    importResult && (
      !importResult.success ||
      (importResult.import_review && importResult.import_review.status !== "READY")
    ),
  );

  const renderReviewSummary = (review: ImportReview | null, testId: string) => {
    if (!review) return null;
    const coverage = review.coverage || {};
    const statusClass = review.status === "READY"
      ? "text-gain border-gain/40 bg-gain/10"
      : "text-amber-300 border-amber-400/40 bg-amber-400/10";
    return (
      <div data-testid={testId} className="p-3 bg-[#111722] border border-surface-border rounded-lg text-[10px] space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-slate-400 uppercase">{t("csv_import.review_status")}</span>
          <span className={`px-2 py-0.5 rounded border font-bold ${statusClass}`}>{review.status}</span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-400">
          <span>{t("csv_import.review_decision")}: {review.decision}</span>
          <span>{t("csv_import.review_reconciliation")}: {review.reconciliation?.status || "UNKNOWN"}</span>
          <span>{t("csv_import.review_coverage")}: {String(coverage.status || "UNKNOWN")}</span>
        </div>
        {review.discrepancies && review.discrepancies.length > 0 && (
          <div className="text-amber-300/90">
            {review.discrepancies.map((item, index) => (
              <div key={`${item.type || "discrepancy"}-${item.source_row_number || index}`}>
                {item.type || t("csv_import.discrepancy")}{item.source_row_number ? ` · ${t("csv_import.row", { count: item.source_row_number })}` : ""}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none animate-fadeIn" aria-busy={isLoadingPreview || isImporting} role="dialog" aria-modal="true" aria-labelledby="csv-import-title" aria-describedby="csv-import-description">
      <div ref={dialogRef} className="relative w-full max-w-2xl bg-[#0b0e14] border border-surface-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border bg-[#0d121c]">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h3 id="csv-import-title" className="text-sm font-bold text-white uppercase tracking-wider">
                {t("csv_import.modal_title")}
              </h3>
              <p id="csv-import-description" className="text-[11px] text-slate-400">
                {t("csv_import.modal_subtitle")}
              </p>
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={handleClose}
            disabled={isImporting}
            aria-label={t("common.close")}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#162032] transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {errorMessage && (
            <div role="alert" className="flex items-center space-x-2 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {importResult ? (
            /* Result Summary Card */
            <div className={`p-5 bg-[#0e1626] rounded-xl space-y-4 text-xs ${importNeedsReview ? "border border-amber-400/40" : "border border-accent/30"}`}>
              <div className={`flex items-center space-x-3 ${importNeedsReview ? "text-amber-300" : "text-gain"}`}>
                {importNeedsReview ? <AlertTriangle className="w-6 h-6 shrink-0" /> : <CheckCircle2 className="w-6 h-6 shrink-0" />}
                <div>
                  <h4 className="font-bold text-white text-sm">
                    {t(importNeedsReview ? "csv_import.result_review_title" : "csv_import.result_title")}
                  </h4>
                  <p className="text-slate-300 text-[11px]">
                    {t(importNeedsReview ? "csv_import.result_review_msg" : "csv_import.result_success_msg")}
                  </p>
                </div>
              </div>

              {renderReviewSummary(importResult.import_review || null, "csv-import-result-review")}

              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-surface-border/50">
                <div className="p-3 bg-[#090d14] rounded-lg border border-surface-border">
                  <span className="text-[10px] text-slate-400 block uppercase">
                    {t("csv_import.result_imported")}
                  </span>
                  <span className="text-base font-bold text-gain">
                    {importResult.imported}
                  </span>
                </div>
                <div className="p-3 bg-[#090d14] rounded-lg border border-surface-border">
                  <span className="text-[10px] text-slate-400 block uppercase">
                    {t("csv_import.result_skipped")}
                  </span>
                  <span className="text-base font-bold text-amber-400">
                    {importResult.duplicates_skipped}
                  </span>
                </div>
                <div className="p-3 bg-[#090d14] rounded-lg border border-surface-border">
                  <span className="text-[10px] text-slate-400 block uppercase">
                    {t("csv_import.result_errors")}
                  </span>
                  <span className="text-base font-bold text-slate-400">
                    {importResult.errors.length}
                  </span>
                </div>
              </div>

              {importResult.errors.length > 0 && (
                <div className="p-3 bg-black/40 rounded-lg border border-surface-border text-[10px] text-amber-300/80 max-h-24 overflow-y-auto space-y-1">
                  {importResult.errors.map((err, i) => (
                    <div key={i}>• {err}</div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Dropzone */}
              <div
                role="button"
                tabIndex={0}
                aria-label={t("csv_import.select_file")}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center space-y-2 ${
                  isDragOver
                    ? "border-accent bg-accent/10"
                    : selectedFile
                    ? "border-accent/40 bg-[#111722]"
                    : "border-surface-border hover:border-slate-500 bg-[#0d121c]"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.txt"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      handleFileChange(e.target.files[0]);
                    }
                  }}
                />
                <div className="w-10 h-10 rounded-full bg-[#162032] flex items-center justify-center text-accent border border-surface-border">
                  {isLoadingPreview ? (
                    <RefreshCw className="w-5 h-5 animate-spin text-accent" />
                  ) : (
                    <FileText className="w-5 h-5" />
                  )}
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-xs font-bold text-white">{selectedFile.name}</p>
                    <p className="text-[10px] text-slate-400">
                      {(selectedFile.size / 1024).toFixed(1)} KB &bull; {t("csv_import.trades_found", { count: totalRows })}
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-xs font-bold text-white">
                      {t("csv_import.dropzone_title")}
                    </p>
                    <p className="text-[10px] text-slate-400">
                      {t("csv_import.dropzone_subtitle")}
                    </p>
                  </div>
                )}
              </div>

              {/* Format Badge Indicator */}
              {detectedFormat && (
                <div className="flex items-center justify-between px-3 py-2 bg-[#111722] border border-surface-border rounded-lg text-xs">
                  <span className="text-slate-400 text-[11px]">
                    {t("csv_import.detected_format")}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-accent/20 border border-accent/40 text-accent font-bold text-[10px] uppercase">
                    {getFormatBadgeText(detectedFormat)}
                  </span>
                </div>
              )}

              {renderReviewSummary(previewReview, "csv-import-preview-review")}

              {/* Preview Table */}
              {previewTrades.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-semibold text-white">
                      {t("csv_import.preview_title")}
                    </span>
                    <span>{t("csv_import.total_records", { count: totalRows })}</span>
                  </div>
                  <div className="overflow-x-auto rounded-lg border border-surface-border bg-[#090d14]">
                    <table className="w-full text-left text-[10px]">
                      <thead className="bg-[#0b0e14] text-slate-400 uppercase border-b border-surface-border">
                        <tr>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_symbol")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_side")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_entry")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_exit")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_qty")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_pnl")}</th>
                          <th className="px-2.5 py-1.5">{t("csv_import.col_time")}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-surface-border/30">
                        {previewTrades.map((pTrade, idx) => (
                          <tr key={idx} className="hover:bg-[#111722]">
                            <td className="px-2.5 py-1.5 font-bold text-white">{pTrade.symbol}</td>
                            <td className="px-2.5 py-1.5">
                              <span
                                className={`px-1 py-0.2 rounded font-bold ${
                                  pTrade.side === "BUY" ? "text-gain" : "text-loss"
                                }`}
                              >
                                {pTrade.side}
                              </span>
                            </td>
                            <td className="px-2.5 py-1.5 text-slate-200">
                              ${Number(pTrade.entry_price).toFixed(2)}
                            </td>
                            <td className="px-2.5 py-1.5 text-slate-200">
                              {pTrade.exit_price ? `$${Number(pTrade.exit_price).toFixed(2)}` : "-"}
                            </td>
                            <td className="px-2.5 py-1.5 text-slate-300">{pTrade.qty}</td>
                            <td className={`px-2.5 py-1.5 font-bold ${
                              pTrade.pnl == null ? "text-slate-400" : pTrade.pnl > 0 ? "text-gain" : pTrade.pnl < 0 ? "text-loss" : "text-slate-400"
                            }`}>
                              {pTrade.pnl == null ? t("csv_import.unknown_value") : `$${Number(pTrade.pnl).toFixed(2)}`}
                            </td>
                            <td className="px-2.5 py-1.5 text-slate-400 text-[9px]">
                              {String(pTrade.entry_time).slice(0, 16).replace("T", " ")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-surface-border bg-[#0d121c] text-xs">
          <button
            type="button"
            onClick={handleDownloadTemplate}
            className="flex items-center space-x-1.5 text-slate-400 hover:text-white transition cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-accent" />
            <span>{t("csv_import.download_template")}</span>
          </button>

          <div className="flex items-center space-x-3">
            {importResult ? (
              <button
                onClick={handleClose}
                className="px-4 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded-lg transition cursor-pointer"
              >
                {t("csv_import.close_btn")}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={handleClose}
                  data-testid="csv-import-cancel"
                  disabled={isImporting}
                  className="px-4 py-2 bg-[#162032] hover:bg-[#1f2d47] text-slate-300 font-semibold rounded-lg border border-surface-border transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t("csv_import.cancel_btn")}
                </button>
                <button
                  disabled={!selectedFile || isImporting || isLoadingPreview}
                  onClick={handleExecuteImport}
                  className={`flex items-center space-x-1.5 px-4 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded-lg transition shadow-md ${
                    !selectedFile || isImporting || isLoadingPreview
                      ? "opacity-50 cursor-not-allowed"
                      : "cursor-pointer"
                  }`}
                >
                  {isImporting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>{t("csv_import.importing_btn")}</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>{t("csv_import.import_btn", { count: totalRows })}</span>
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
