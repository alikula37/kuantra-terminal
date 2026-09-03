import React, { useState, useEffect } from "react";
import { ComplianceStatusResponse } from "../types";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";

export const PropFirmShield: React.FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ComplianceStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchStatus = () => {
    apiFetch(apiUrl("/api/v1/compliance/status"))
      .then((res) => res.json())
      .then((resData) => {
        setStatus(resData);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !status) {
    return <div className="p-8 text-center text-slate-400 font-mono">{t("prop_shield.loading")}</div>;
  }

  const isBreached = status.overall_status === "BREACHED";
  const isCritical = status.overall_status === "CRITICAL";
  const isWarning = status.overall_status === "WARNING";

  const dailyRule = (status.rules || []).find((r) => r.rule === "Daily Max Loss");
  const ddRule = (status.rules || []).find((r) => r.rule.includes("Max Drawdown"));

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Top Banner Alert Strip if Risk Approaching Limit */}
      {(isBreached || isCritical || isWarning) && (
        <div
          className={`p-3.5 rounded-lg border flex items-center justify-between animate-pulse ${
            isBreached
              ? "bg-rose-950/80 border-loss text-loss"
              : isCritical
              ? "bg-amber-950/80 border-amber-500 text-amber-400"
              : "bg-yellow-950/40 border-yellow-500/60 text-yellow-300"
          }`}
        >
          <div className="flex items-center space-x-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <div>
              <span className="font-black tracking-wide block text-xs">
                {isBreached
                  ? t("prop_shield.breached_banner")
                  : isCritical
                  ? t("prop_shield.critical_banner")
                  : t("prop_shield.warning_banner")}
              </span>
              <span className="text-[11px] opacity-90">
                {isBreached
                  ? t("prop_shield.breached_desc")
                  : t("prop_shield.warning_desc")}
              </span>
            </div>
          </div>
          <span className="px-2.5 py-1 bg-black/40 rounded font-black text-xs">
            {t("prop_shield.status_label", { status: status.overall_status })}
          </span>
        </div>
      )}

      {/* Main Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-gain" />
            <span>{t("prop_shield.title")}</span>
          </h2>
          <p className="text-xs text-slate-400">
            {t("prop_shield.subtitle")}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <div
            className={`px-3 py-1 rounded text-xs font-bold border ${
              isBreached
                ? "bg-loss/20 text-loss border-loss/40"
                : isCritical
                ? "bg-amber-500/20 text-amber-400 border-amber-500/40"
                : "bg-gain/20 text-gain border-gain/40"
            }`}
          >
            {status.overall_status}
          </div>
        </div>
      </div>

      {/* Top Level Account Balances */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">{t("prop_shield.starting_size")}</span>
          <span className="text-xl font-bold text-white">${status.account_size.toLocaleString()}</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">{t("prop_shield.funded_base")}</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">{t("prop_shield.current_equity")}</span>
          <span className="text-xl font-bold text-gain">${status.current_equity.toLocaleString()}</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">{t("prop_shield.high_watermark", { val: status.high_watermark.toLocaleString() })}</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">{t("prop_shield.today_pnl")}</span>
          <span className={`text-xl font-bold ${status.today_pnl >= 0 ? "text-gain" : "text-loss"}`}>
            {status.today_pnl >= 0 ? "+" : ""}${status.today_pnl.toLocaleString()}
          </span>
          <span className="text-[9px] text-slate-500 block mt-0.5">{t("prop_shield.closed_unrealized")}</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">{t("prop_shield.all_time_pnl")}</span>
          <span className={`text-xl font-bold ${status.all_time_pnl >= 0 ? "text-gain" : "text-loss"}`}>
            {status.all_time_pnl >= 0 ? "+" : ""}${status.all_time_pnl.toLocaleString()}
          </span>
          <span className="text-[9px] text-slate-500 block mt-0.5">{t("prop_shield.cumulative_perf")}</span>
        </div>
      </div>

      {/* Primary Risk Gauges: Daily Loss & Max Drawdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Daily Loss Gauge */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-white block">{t("prop_shield.daily_budget_title")}</span>
              <span className="text-[11px] text-slate-400">
                {t("prop_shield.daily_limit_sub", { limit: status.daily_loss_budget.toLocaleString(), pct: status.config.daily_loss_limit_pct })}
              </span>
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                dailyRule?.status === "BREACH"
                  ? "bg-loss text-white"
                  : dailyRule?.status === "CRITICAL"
                  ? "bg-amber-500 text-black"
                  : "bg-[#111722] text-gain"
              }`}
            >
              {dailyRule?.status || "PASS"}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-bold">
              <span className="text-slate-400">{t("prop_shield.consumed", { val: dailyRule?.current || "$0.00" })}</span>
              <span className="text-slate-200">{t("prop_shield.utilized", { pct: dailyRule?.utilization_pct || 0 })}</span>
            </div>
            <div className="w-full bg-[#111722] rounded-full h-3 overflow-hidden border border-surface-border p-0.5">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  (dailyRule?.utilization_pct || 0) >= 90
                    ? "bg-loss"
                    : (dailyRule?.utilization_pct || 0) >= 70
                    ? "bg-amber-400"
                    : "bg-gain"
                }`}
                style={{ width: `${Math.min(100, dailyRule?.utilization_pct || 0)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>$0.00</span>
              <span>{t("prop_shield.remaining_buffer", { val: status.daily_loss_remaining.toLocaleString() })}</span>
            </div>
          </div>
        </div>

        {/* Max Drawdown Gauge */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-white block">{t("prop_shield.max_dd_title")}</span>
              <span className="text-[11px] text-slate-400">
                {t("prop_shield.max_dd_limit_sub", { limit: status.max_dd_budget.toLocaleString(), pct: status.config.max_drawdown_pct })}
              </span>
            </div>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                ddRule?.status === "BREACH"
                  ? "bg-loss text-white"
                  : ddRule?.status === "CRITICAL"
                  ? "bg-amber-500 text-black"
                  : "bg-[#111722] text-gain"
              }`}
            >
              {ddRule?.status || "PASS"}
            </span>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-bold">
              <span className="text-slate-400">{t("prop_shield.current_dd", { val: status.current_drawdown_amount.toLocaleString() })}</span>
              <span className="text-slate-200">{t("prop_shield.utilized", { pct: ddRule?.utilization_pct || 0 })}</span>
            </div>
            <div className="w-full bg-[#111722] rounded-full h-3 overflow-hidden border border-surface-border p-0.5">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  (ddRule?.utilization_pct || 0) >= 90
                    ? "bg-loss"
                    : (ddRule?.utilization_pct || 0) >= 70
                    ? "bg-amber-400"
                    : "bg-gain"
                }`}
                style={{ width: `${Math.min(100, ddRule?.utilization_pct || 0)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-slate-500">
              <span>$0.00</span>
              <span>{t("prop_shield.remaining_buffer", { val: status.max_dd_remaining.toLocaleString() })}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Rules Checklist Grid */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <h3 className="text-xs font-bold text-white">{t("prop_shield.rules_audit_title")}</h3>
        <div className="divide-y divide-surface-border/50 text-xs">
          {(status.rules || []).map((r, idx) => (
            <div key={idx} className="py-2.5 flex items-center justify-between hover:bg-[#111722] px-2 rounded">
              <div className="space-y-0.5">
                <span className="font-bold text-slate-200 block">{r.rule}</span>
                <span className="text-[11px] text-slate-400">{t("prop_shield.requirement", { limit: r.limit })}</span>
              </div>
              <div className="flex items-center space-x-4">
                <span className="text-slate-300 text-xs">{r.current}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    r.status === "PASS" || r.status === "PASSED"
                      ? "bg-gain/20 text-gain border border-gain/30"
                      : r.status === "BREACH"
                      ? "bg-loss text-white"
                      : r.status === "CRITICAL"
                      ? "bg-amber-500 text-black font-bold"
                      : "bg-slate-800 text-slate-300"
                  }`}
                >
                  {r.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};