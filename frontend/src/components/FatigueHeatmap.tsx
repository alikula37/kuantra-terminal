import React, { useState, useEffect } from "react";
import { FatigueMatrixResponse } from "../types";
import { Activity } from "lucide-react";
import { apiUrl } from "../lib/backend";

export const FatigueHeatmap: React.FC = () => {
  const [data, setData] = useState<FatigueMatrixResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    setIsLoading(true);
    fetch(apiUrl("/api/v1/psychology/fatigue-matrix"))
      .then((res) => res.json())
      .then((resData: FatigueMatrixResponse) => {
        setData(resData);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, []);

  if (isLoading || !data) {
    return <div className="p-4 text-center text-slate-500 font-mono text-xs">Computing Mental Fatigue matrix...</div>;
  }

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-surface-border pb-2">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            MENTAL FATIGUE & OVER-TRADING SEQUENCE HEATMAP
          </span>
        </div>

        <div className="flex items-center space-x-2 text-[10px]">
          <span className="text-slate-400">Inflection Threshold:</span>
          <span className="bg-amber-500/20 text-amber-400 border border-amber-500/40 px-2 py-0.5 rounded font-bold">
            {data.inflection_point}
          </span>
        </div>
      </div>

      {/* KPI Comparison Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">EARLY WIN RATE (TRADES 1-3)</span>
          <span className="text-xl font-bold text-gain">{data.early_win_rate_pct}%</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">High cognitive focus phase</span>
        </div>

        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">LATE WIN RATE (TRADES 6-8+)</span>
          <span className="text-xl font-bold text-loss">{data.late_win_rate_pct}%</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Mental fatigue & over-trading drag</span>
        </div>

        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block font-semibold">PERFORMANCE DECAY</span>
          <span className="text-xl font-bold text-amber-400">-{data.performance_decay_pct}%</span>
          <span className="text-[9px] text-slate-500 block mt-0.5">Drop in edge after extended churn</span>
        </div>
      </div>

      {/* Sequence Matrix Table */}
      <div className="overflow-x-auto rounded border border-surface-border bg-[#090d14]">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#0b0e14] text-[9px] text-slate-400 uppercase tracking-wider sticky top-0 border-b border-surface-border">
            <tr>
              <th className="px-4 py-2.5">Sequence #</th>
              <th className="px-4 py-2.5">Trades Executed</th>
              <th className="px-4 py-2.5">Win Rate %</th>
              <th className="px-4 py-2.5">Total PnL</th>
              <th className="px-4 py-2.5">Avg PnL</th>
              <th className="px-4 py-2.5">Expectancy (EV)</th>
              <th className="px-4 py-2.5 text-right">Cognitive State</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/30 text-[11px]">
            {data.matrix.map((row) => {
              const isProfit = row.total_pnl >= 0;
              const isSevere = row.fatigue_state === "SEVERE_OVERTRADING";
              const isMod = row.fatigue_state === "MODERATE_FATIGUE";

              return (
                <tr key={row.sequence_num} className="hover:bg-[#111722]">
                  <td className="px-4 py-2 font-bold text-white">{row.label}</td>
                  <td className="px-4 py-2 text-slate-300">{row.trades_count}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center space-x-2">
                      <span className={`font-bold ${row.win_rate >= 50 ? "text-gain" : "text-loss"}`}>
                        {row.win_rate}%
                      </span>
                      <div className="w-16 bg-[#111722] rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${row.win_rate >= 50 ? "bg-gain" : "bg-loss"}`}
                          style={{ width: `${Math.min(100, row.win_rate)}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className={`px-4 py-2 font-bold ${isProfit ? "text-gain" : "text-loss"}`}>
                    {isProfit ? "+" : ""}${row.total_pnl.toLocaleString()}
                  </td>
                  <td className="px-4 py-2 text-slate-300">${row.avg_pnl.toFixed(2)}</td>
                  <td className={`px-4 py-2 font-bold ${row.expectancy >= 0 ? "text-gain" : "text-loss"}`}>
                    {row.expectancy >= 0 ? "+" : ""}${row.expectancy.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <span
                      className={`px-2 py-0.5 rounded text-[9px] font-bold ${
                        isSevere
                          ? "bg-rose-950/80 border border-loss/40 text-loss"
                          : isMod
                          ? "bg-amber-950/80 border border-amber-500/40 text-amber-400"
                          : row.fatigue_state === "PEAK_FOCUS"
                          ? "bg-gain/20 border border-gain/40 text-gain"
                          : "bg-sky-500/20 border border-sky-500/40 text-accent"
                      }`}
                    >
                      {row.fatigue_state}
                    </span>
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