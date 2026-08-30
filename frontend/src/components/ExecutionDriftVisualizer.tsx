import React, { useState, useEffect } from "react";
import { ExecutionDriftResponse } from "../types";
import { GitCommit } from "lucide-react";

export const ExecutionDriftVisualizer: React.FC = () => {
  const [data, setData] = useState<ExecutionDriftResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    setIsLoading(true);
    fetch("http://127.0.0.1:8000/api/v1/analytics/execution-drift")
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
    return <div className="p-8 text-center text-slate-400 font-mono">Loading Execution Drift Analytics...</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <GitCommit className="w-4 h-4 text-rose-400" />
            <span>EXECUTION DRIFT & PANIC EXIT LEAKAGE ANALYZER</span>
          </h2>
          <p className="text-xs text-slate-400">
            Quantifying Theoretical Planned Returns vs Actual Manual Execution Slippage
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">EXECUTION FIDELITY</span>
          <span className="text-xl font-bold text-accent">{data.execution_fidelity_pct}%</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Actual Realized / Theoretical Plan</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">PANIC EXIT LEAKAGE</span>
          <span className="text-xl font-bold text-loss">-${data.total_panic_exit_leakage.toLocaleString()}</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Left on table due to early manual exit</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">EARLY EXITS COUNT</span>
          <span className="text-xl font-bold text-amber-400">{data.early_exits_count} Trades</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Exited before reaching SL / TP</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">AVG DRIFT RATIO</span>
          <span className="text-xl font-bold text-slate-200">{data.avg_drift_ratio} R</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Mean execution variance per trade</span>
        </div>
      </div>

      {/* Main Trade-by-Trade Comparison Audit Table */}
      <div className="flex-1 overflow-y-auto rounded-lg border border-surface-border bg-[#0d121c]">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#090d14] text-[10px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
            <tr>
              <th className="px-4 py-3">Trade ID / Asset</th>
              <th className="px-4 py-3">Direction</th>
              <th className="px-4 py-3">Planned SL / TP</th>
              <th className="px-4 py-3">Actual Exit Price</th>
              <th className="px-4 py-3">Actual PnL</th>
              <th className="px-4 py-3">Theoretical PnL</th>
              <th className="px-4 py-3">Panic Leakage ($)</th>
              <th className="px-4 py-3">Drift (R)</th>
              <th className="px-4 py-3 text-right">Execution Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/40 text-[11px]">
            {data.trades.map((t) => {
              const isProfit = t.actual_pnl >= 0;
              return (
                <tr key={t.trade_id} className="hover:bg-[#111722] transition">
                  <td className="px-4 py-2.5 font-bold text-white">
                    {t.trade_id} <span className="text-slate-400 text-[10px]">({t.symbol})</span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${t.side === "BUY" || t.side === "LONG" ? "bg-gain/20 text-gain" : "bg-loss/20 text-loss"}`}>
                      {t.side}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-300 text-[10px]">
                    SL: ${t.stop_loss || "None"} | TP: ${t.take_profit || "None"}
                  </td>
                  <td className="px-4 py-2.5 font-bold text-slate-200">${t.actual_exit}</td>
                  <td className={`px-4 py-2.5 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                    {isProfit ? "+" : ""}${t.actual_pnl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 font-bold text-slate-300">
                    ${t.theoretical_pnl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2.5 font-bold text-loss">
                    {t.panic_cost > 0 ? `-$${t.panic_cost.toFixed(2)}` : "$0.00"}
                  </td>
                  <td className={`px-4 py-2.5 font-bold ${t.drift_ratio >= 0 ? "text-gain" : "text-loss"}`}>
                    {t.drift_ratio >= 0 ? "+" : ""}{t.drift_ratio}R
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {t.is_early_exit ? (
                      <span className="px-2 py-0.5 bg-amber-950/80 border border-amber-500/50 text-amber-400 text-[10px] font-bold rounded">
                        EARLY EXIT
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gain/20 border border-gain/40 text-gain text-[10px] font-bold rounded">
                        DISCIPLINE KEPT
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};