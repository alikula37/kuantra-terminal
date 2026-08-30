import React from "react";
import { useTelemetry } from "../../hooks/useTelemetry";
import { Shield, FileText, Download, RefreshCw } from "lucide-react";

export const SystemHealthSettings: React.FC = () => {
  const {
    isOptedIn,
    queuedCrashes,
    isLoading,
    updateConsent,
    exportRedactedLogs,
    refreshStatus,
  } = useTelemetry();

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-4">
      <div className="flex items-center justify-between border-b border-surface-border pb-2">
        <div className="flex items-center space-x-2">
          <Shield className="w-4 h-4 text-purple-400" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            PRIVACY TELEMETRY & SYSTEM DIAGNOSTICS
          </span>
        </div>

        <span className="text-[10px] text-slate-400 bg-[#111722] px-2 py-0.5 rounded border border-surface-border">
          PII Redaction: Active
        </span>
      </div>

      {/* Opt-in Toggle */}
      <div className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold text-white">Anonymous Error & Crash Reporting</span>
            <span
              className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                isOptedIn
                  ? "bg-gain/20 text-gain border border-gain/30"
                  : "bg-slate-800 text-slate-400 border border-slate-700"
              }`}
            >
              {isOptedIn ? "OPT-IN ENABLED" : "DISABLED (DEFAULT)"}
            </span>
          </div>
          <p className="text-[10px] text-slate-400">
            Automatically scrubs API keys, auth headers, and account balances before spooling anonymous stack traces.
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
            <span className="text-white font-bold block text-[11px]">Offline Crash Spool Queue</span>
            <span className="text-slate-400 text-[10px]">
              {queuedCrashes === 0
                ? "No pending crash traces queued locally."
                : `${queuedCrashes} crash reports queued for anonymous sync upon network reconnect.`}
            </span>
          </div>
        </div>

        <button
          onClick={refreshStatus}
          className="flex items-center space-x-1 bg-[#0d121c] hover:bg-[#1a2234] border border-surface-border text-slate-300 text-[10px] px-2.5 py-1 rounded transition"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Refresh</span>
        </button>
      </div>

      {/* 1-Click Redacted Logs Export */}
      <div className="flex items-center justify-between pt-1">
        <div className="text-[10px] text-slate-400">
          Package all 10MB/50MB rotating logs with verified PII scrubbing for technical support.
        </div>

        <button
          onClick={exportRedactedLogs}
          className="flex items-center space-x-1.5 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold px-3 py-1.5 rounded text-xs transition"
        >
          <Download className="w-3.5 h-3.5" />
          <span>EXPORT REDACTED LOGS (.ZIP)</span>
        </button>
      </div>
    </div>
  );
};