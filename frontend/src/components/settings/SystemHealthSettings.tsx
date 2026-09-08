import React from "react";
import { useTelemetry } from "../../hooks/useTelemetry";
import { Shield, FileText, Download, RefreshCw } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";

export function telemetryQueueCopy(queuedCrashes: number, deliveryStatus: string): { key: string; params?: { count: number } } {
  if (queuedCrashes === 0) return { key: "settings.telemetry_queue_empty" };
  if (deliveryStatus === "NO_TRANSPORT") {
    return { key: "settings.telemetry_queue_no_transport", params: { count: queuedCrashes } };
  }
  if (deliveryStatus === "OPT_OUT") {
    return { key: "settings.telemetry_queue_opt_out", params: { count: queuedCrashes } };
  }
  return { key: "settings.telemetry_queue_pending", params: { count: queuedCrashes } };
}

export const SystemHealthSettings: React.FC = () => {
  const { t } = useTranslation();
  const {
    isOptedIn,
    queuedCrashes,
    deliveryStatus,
    isLoading,
    updateConsent,
    exportRedactedLogs,
    refreshStatus,
  } = useTelemetry();
  const queueCopy = telemetryQueueCopy(queuedCrashes, deliveryStatus);

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-4">
      <div className="flex items-center justify-between border-b border-surface-border pb-2">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-purple-400" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            {t("settings.privacy_title")}
          </span>
        </div>

        <span className="text-[10px] text-slate-400 bg-[#111722] px-2 py-0.5 rounded border border-surface-border">
          {t("settings.pii_redaction_active")}
        </span>
      </div>

      {/* Opt-in Toggle */}
      <div className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-white">{t("settings.telemetry_label")}</span>
            <span
              className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                isOptedIn
                  ? "bg-gain/20 text-gain border border-gain/30"
                  : "bg-slate-800 text-slate-400 border border-slate-700"
              }`}
            >
              {isOptedIn ? t("settings.telemetry_enabled") : t("settings.telemetry_disabled")}
            </span>
          </div>
          <p className="text-[10px] text-slate-400">
            {t("settings.telemetry_description")}
          </p>
        </div>

        <label className="relative inline-flex items-center cursor-pointer ml-4">
          <input
            type="checkbox"
            checked={isOptedIn}
            onChange={(e) => updateConsent(e.target.checked)}
            className="sr-only peer"
            disabled={isLoading}
          />
          <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent"></div>
        </label>
      </div>

      {/* Offline Crash Spooler Status */}
      <div className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <FileText className="w-4 h-4 text-accent flex-shrink-0" />
          <div>
            <span className="text-white font-bold block text-[11px]">{t("settings.telemetry_queue_title")}</span>
            <span className="text-slate-400 text-[10px]">
              {t(queueCopy.key, queueCopy.params)}
            </span>
          </div>
        </div>

        <button
          onClick={refreshStatus}
          className="flex items-center space-x-1 bg-[#0d121c] hover:bg-[#1a2234] border border-surface-border text-slate-300 text-[10px] px-2.5 py-1 rounded transition"
        >
          <RefreshCw className="w-3 h-3" />
          <span>{t("settings.telemetry_refresh")}</span>
        </button>
      </div>

      {/* 1-Click Redacted Logs Export */}
      <div className="flex items-center justify-between pt-1">
        <div className="text-[10px] text-slate-400">
          {t("settings.telemetry_export_description")}
        </div>

        <button
          onClick={exportRedactedLogs}
          className="flex items-center space-x-1.5 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold px-3 py-1.5 rounded text-xs transition"
        >
          <Download className="w-3.5 h-3.5" />
          <span>{t("settings.telemetry_export_btn")}</span>
        </button>
      </div>
    </div>
  );
};
