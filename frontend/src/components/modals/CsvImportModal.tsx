import React, { useState, useRef } from "react";
import { Upload, FileText, CheckCircle2, AlertTriangle, Download, X, RefreshCw } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { useTradeStore } from "../../stores/tradeStore";
import { apiFetch, apiUrl } from "../../lib/backend";
import { downloadFromBackend } from "../../lib/desktop";

interface CsvImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportSuccess?: () => void;
}

export const CsvImportModal: React.FC<CsvImportModalProps> = ({ isOpen, onClose, onImportSuccess }) => {
  const { t } = useTranslation();
  const { setTrades } = useTradeStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [detectedFormat, setDetectedFormat] = useState<string | null>(null);
  const [previewTrades, setPreviewTrades] = useState<any[]>([]);
  const [totalRows, setTotalRows] = useState<number>(0);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    imported: number;
    duplicates_skipped: number;
    errors: string[];
    message: string;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  if (!isOpen) return null;

  const resetState = () => {
    setSelectedFile(null);
    setDetectedFormat(null);
    setPreviewTrades([]);
    setTotalRows(0);
    setIsLoadingPreview(false);
    setIsImporting(false);
    setImportResult(null);
    setErrorMessage(null);
    setIsDragOver(false);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleFileChange = async (file: File) => {
    if (!file.name.endsWith(".csv") && !file.name.endsWith(".txt")) {
      setErrorMessage(t("csv_import.error_invalid_format"));
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    setImportResult(null);
    setIsLoadingPreview(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await apiFetch(apiUrl("/api/v1/journal/preview-csv"), {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: t("csv_import.error_generic") }));
        throw new Error(errData.detail || t("csv_import.error_generic"));
      }

      const data = await res.json();
      setDetectedFormat(data.detected_format);
      setPreviewTrades(data.preview_trades || []);
      setTotalRows(data.total_rows_parsed || 0);
    } catch (err: any) {
      setErrorMessage(err.message || t("csv_import.error_generic"));
      setSelectedFile(null);
    } finally {
      setIsLoadingPreview(false);
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
      setImportResult({
        success: data.success,
        imported: data.imported,
        duplicates_skipped: data.duplicates_skipped,
        errors: data.errors || [],
        message: data.message,
      });

      // Refetch trades in store
      apiFetch(apiUrl("/api/v1/trades?limit=200"))
        .then((r) => r.json())
        .then((tradesData) => {
          if (Array.isArray(tradesData)) {
            setTrades(tradesData);
          }
        })
        .catch(() => {});

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none animate-fadeIn">
      <div className="relative w-full max-w-2xl bg-[#0b0e14] border border-surface-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border bg-[#0d121c]">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                {t("csv_import.modal_title")}
              </h3>
              <p className="text-[11px] text-slate-400">
                {t("csv_import.modal_subtitle")}
              </p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#162032] transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1">
          {errorMessage && (
            <div className="flex items-center space-x-2 p-3 bg-loss/15 border border-loss/30 rounded-lg text-loss text-xs">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {importResult ? (
            /* Result Summary Card */
            <div className="p-5 bg-[#0e1626] border border-accent/30 rounded-xl space-y-4 text-xs">
              <div className="flex items-center space-x-3 text-gain">
                <CheckCircle2 className="w-6 h-6 shrink-0" />
                <div>
                  <h4 className="font-bold text-white text-sm">
                    {t("csv_import.result_title")}
                  </h4>
                  <p className="text-slate-300 text-[11px]">
                    {t("csv_import.result_success_msg")}
                  </p>
                </div>
              </div>

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
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
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
                      {(selectedFile.size / 1024).toFixed(1)} KB &bull; {totalRows} Trades Found
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

              {/* Preview Table */}
              {previewTrades.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span className="font-semibold text-white">
                      {t("csv_import.preview_title")}
                    </span>
                    <span>{totalRows} Total Records</span>
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
                            <td
                              className={`px-2.5 py-1.5 font-bold ${
                                pTrade.pnl > 0
                                  ? "text-gain"
                                  : pTrade.pnl < 0
                                  ? "text-loss"
                                  : "text-slate-400"
                              }`}
                            >
                              ${Number(pTrade.pnl || 0).toFixed(2)}
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
                  onClick={handleClose}
                  className="px-4 py-2 bg-[#162032] hover:bg-[#1f2d47] text-slate-300 font-semibold rounded-lg border border-surface-border transition cursor-pointer"
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
