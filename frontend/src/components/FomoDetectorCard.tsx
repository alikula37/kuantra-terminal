import React, { useState, useEffect } from "react";
import { AnomaliesResponse } from "../types";
import { Flame } from "lucide-react";

export const FomoDetectorCard: React.FC = () => {
  const [anomaliesData, setAnomaliesData] = useState<AnomaliesResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchAnomalies = () => {
    fetch("http://127.0.0.1:8000/api/v1/psychology/anomalies")
      .then((res) => res.json())
      .then((data: AnomaliesResponse) => {
        setAnomaliesData(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchAnomalies();
  }, []);

  if (isLoading || !anomaliesData) {
    return <div className="p-4 text-center text-slate-500 font-mono text-xs">Scanning for behavioral anomalies...</div>;
  }

  const anomalies = anomaliesData.anomalies;

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-3">
      <div className="flex items-center justify-between border-b border-surface-border pb-2">
        <div className="flex items-center space-x-2">
          <Flame className="w-4 h-4 text-amber-500" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            FOMO & BEHAVIORAL ANOMALY SCANNER
          </span>
        </div>
        <span className="text-[10px] text-slate-400 bg-[#111722] px-2 py-0.5 rounded border border-surface-border">
          {anomaliesData.total_anomalies_count} Flagged Trades
        </span>
      </div>

      {/* Formula & Detection Rules Banner */}
      <div className="bg-[#111722] p-2.5 rounded border border-surface-border text-[10px] text-slate-400 space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-white font-bold">FOMO Model: d_EMA = |P_entry - EMA₂₀| / ATR₁₄</span>
          <span className="text-amber-400 font-semibold">Trigger: d_EMA &gt; 2.5x ATR</span>
        </div>
        <p className="text-slate-400 text-[10px]">
          Identifies bad entries chasing extended momentum bars near upper/lower wick extremes.
        </p>
      </div>

      {/* Anomaly Table */}
      <div className="overflow-y-auto max-h-56 rounded border border-surface-border bg-[#090d14]">
        {anomalies.length === 0 ? (
          <div className="p-6 text-center text-slate-500 text-xs">
            No FOMO chasing or behavioral anomalies detected in database records.
          </div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0b0e14] text-[9px] text-slate-500 uppercase tracking-wider sticky top-0 border-b border-surface-border">
              <tr>
                <th className="px-3 py-2">Trade / Symbol</th>
                <th className="px-3 py-2">Anomaly Type</th>
                <th className="px-3 py-2">Metric Indicators</th>
                <th className="px-3 py-2">PnL</th>
                <th className="px-3 py-2 text-right">Severity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/30 text-[10px]">
              {anomalies.map((a, idx) => {
                const isLoss = (a.pnl || 0) < 0;
                return (
                  <tr key={idx} className="hover:bg-[#111722]">
                    <td className="px-3 py-2 font-bold text-white">
                      {a.trade_id} <span className="text-slate-500 text-[9px]">({a.symbol})</span>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded font-bold text-[9px] ${
                          a.type === "FOMO_CHASE"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : a.type === "REVENGE_TRADING"
                            ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            : "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                        }`}
                      >
                        {a.type}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-300 font-mono">{a.metric_detail}</td>
                    <td className={`px-3 py-2 font-bold ${isLoss ? "text-loss" : "text-gain"}`}>
                      {a.pnl != null ? `${a.pnl >= 0 ? "+" : ""}$${a.pnl.toFixed(2)}` : "-"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                          a.severity === "CRITICAL"
                            ? "bg-loss text-white"
                            : a.severity === "HIGH"
                            ? "bg-amber-500 text-black font-bold"
                            : "bg-slate-800 text-slate-300"
                        }`}
                      >
                        {a.severity}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};