import React, { useState, useEffect } from "react";
import { ExecutionDriftResponse } from "../types";
import { GitCommit, Target } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiUrl } from "../lib/backend";

export const ExecutionDriftVisualizer: React.FC = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<ExecutionDriftResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    setIsLoading(true);
    fetch(apiUrl("/api/v1/analytics/execution-drift"))
      .then((res) => res.json())
      .then((resData: ExecutionDriftResponse) => {
        setData(resData);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, []);

  if (isLoading || !data) {
    return <div className="p-8 text-center text-slate-400 font-mono">{t("drift.loading")}</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <GitCommit className="w-4 h-4 text-rose-400" />
            <span>{t("drift.title")}</span>
          </h2>
          <p className="text-xs text-slate-400">
            {t("drift.subtitle")}
          </p>
        </div>
      </div>

      {!data.trades || data.trades.length === 0 ? (
        <div className="flex-1 bg-[#0d121c] p-12 rounded-lg border border-surface-border flex flex-col items-center justify-center text-center select-none font-mono">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <Target className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
            {t("drift.waiting_title")}
          </h3>
          <p className="text-xs text-slate-400 max-w-md leading-relaxed">
            {t("drift.waiting_desc")}
          </p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">{t("drift.execution_fidelity")}</span>
              <span className="text-xl font-bold text-accent">{data.execution_fidelity_pct}%</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">{t("drift.fidelity_sub")}</span>
            </div>

            <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">{t("drift.panic_leakage")}</span>
              <span className="text-xl font-bold text-loss">-${data.total_panic_exit_leakage.toLocaleString()}</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">{t("drift.leakage_sub")}</span>
            </div>

            <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">{t("drift.early_exits")}</span>
              <span className="text-xl font-bold text-amber-400">{t("drift.trades_count", { count: data.early_exits_count })}</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">{t("drift.early_exits_sub")}</span>
            </div>

            <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">{t("drift.avg_drift")}</span>
              <span className="text-xl font-bold text-slate-200">{data.avg_drift_ratio} R</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">{t("drift.avg_drift_sub")}</span>
            </div>
          </div>

          {/* Main Trade-by-Trade Comparison Audit Table */}
          <div className="flex-1 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
                <tr>
                  <th className="px-4 py-3">{t("drift.col_trade_asset")}</th>
                  <th className="px-4 py-3">{t("drift.col_direction")}</th>
                  <th className="px-4 py-3">{t("drift.col_planned")}</th>
                  <th className="px-4 py-3">{t("drift.col_actual_exit")}</th>
                  <th className="px-4 py-3">{t("drift.col_actual_pnl")}</th>
                  <th className="px-4 py-3">{t("drift.col_theoretical_pnl")}</th>
                  <th className="px-4 py-3">{t("drift.col_panic_leakage")}</th>
                  <th className="px-4 py-3">{t("drift.col_drift_r")}</th>
                  <th className="px-4 py-3 text-right">{t("drift.col_status")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/40 text-[11px]">
                {data.trades.map((tItem) => {
                  const isProfit = tItem.actual_pnl >= 0;
                  return (
                    <tr key={tItem.trade_id} className="hover:bg-[#111722] transition">
                      <td className="px-4 py-2.5 font-bold text-white">
                        {tItem.trade_id} <span className="text-slate-400 text-[10px]">({tItem.symbol})</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${tItem.side === "BUY" || tItem.side === "LONG" ? "bg-gain/20 text-gain" : "bg-loss/20 text-loss"}`}>
                          {tItem.side}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-300 text-[10px]">
                        SL: ${tItem.stop_loss || t("drift.none")} | TP: ${tItem.take_profit || t("drift.none")}
                      </td>
                      <td className="px-4 py-2.5 font-bold text-slate-200">${tItem.actual_exit}</td>
                      <td className={`px-4 py-2.5 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                        {isProfit ? "+" : ""}${tItem.actual_pnl.toFixed(2)}
                      </td>
                      <td className="px-4 py-2.5 text-slate-400">
                        ${tItem.theoretical_pnl.toFixed(2)}
                      </td>
                      <td className="px-4 py-2.5 font-bold text-loss">
                        {tItem.panic_cost > 0 ? `-$${tItem.panic_cost.toFixed(2)}` : "$0.00"}
                      </td>
                      <td className="px-4 py-2.5 text-slate-300">
                        {tItem.drift_ratio > 0 ? `+${tItem.drift_ratio}` : tItem.drift_ratio} R
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          !tItem.is_early_exit ? "bg-gain/20 text-gain" : "bg-amber-500/20 text-amber-400"
                        }`}>
                          {!tItem.is_early_exit ? "DISCIPLINED" : "EARLY EXIT"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};