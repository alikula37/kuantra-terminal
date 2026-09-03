import React, { useEffect, useState } from "react";
import { QuantScorecard, SymbolBreakdown } from "../types";
import { Award, TrendingUp, ShieldAlert, Target, PieChart } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiUrl } from "../lib/backend";

export const AnalyticsView: React.FC = () => {
  const { t } = useTranslation();
  const [scorecard, setScorecard] = useState<QuantScorecard | null>(null);
  const [symbols, setSymbols] = useState<SymbolBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([
      fetch(apiUrl("/api/v1/analytics/quant"))
        .then((res) => res.json())
        .catch(() => null),
      fetch(apiUrl("/api/v1/analytics/symbols"))
        .then((res) => res.json())
        .catch(() => []),
    ]).then(([quantData, symData]) => {
      if (quantData) {
        setScorecard(quantData);
      } else {
        setScorecard({
          total_trades: 0,
          win_rate: 0.0,
          loss_rate: 0.0,
          total_pnl: 0.0,
          avg_win: 0.0,
          avg_loss: 0.0,
          profit_factor: 0.0,
          expectancy: 0.0,
          sqn: 0.0,
          sharpe_ratio: 0.0,
          sortino_ratio: 0.0,
          max_drawdown_amount: 0.0,
          max_drawdown_pct: 0.0,
          half_kelly_pct: 0.0,
        });
      }
      setSymbols(Array.isArray(symData) ? symData : []);
      setIsLoading(false);
    });
  }, []);

  if (isLoading || !scorecard) {
    return <div className="p-8 text-center text-slate-400 font-mono">{t("analytics.loading")}</div>;
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white">{t("analytics.title")}</h2>
          <p className="text-xs text-slate-400">{t("analytics.subtitle")}</p>
        </div>
        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border text-xs text-accent font-bold">
          {t("analytics.total_closed", { count: scorecard.total_trades })}
        </div>
      </div>

      {scorecard.total_trades === 0 ? (
        <div className="flex-1 bg-[#0d121c] p-12 rounded-lg border border-surface-border flex flex-col items-center justify-center text-center select-none font-mono">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <Target className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
            {t("analytics.waiting_title")}
          </h3>
          <p className="text-xs text-slate-400 max-w-md leading-relaxed">
            {t("analytics.waiting_desc")}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-semibold">SYSTEM QUALITY NUMBER</span>
            <Award className="w-4 h-4 text-accent" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold text-white">{scorecard.sqn}</span>
            <span className="text-[10px] text-gain ml-2 font-bold">
              {scorecard.sqn >= 3.0 ? "HOLY GRAIL" : scorecard.sqn >= 2.0 ? "EXCELLENT" : scorecard.sqn >= 1.6 ? "GOOD" : "AVERAGE"}
            </span>
          </div>
          <span className="text-[9px] text-slate-500 mt-1">SQN = sqrt(N) * (mean(R) / std(R))</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-semibold">SHARPE / SORTINO</span>
            <TrendingUp className="w-4 h-4 text-gain" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{scorecard.sharpe_ratio}</span>
            <span className="text-xs text-slate-500">/</span>
            <span className="text-xl font-bold text-accent">{scorecard.sortino_ratio}</span>
          </div>
          <span className="text-[9px] text-slate-500 mt-1">Downside-only variance isolation</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-semibold">EXPECTANCY (EV / TRADE)</span>
            <Target className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2">
            <span className="text-2xl font-bold text-gain">+${scorecard.expectancy}</span>
          </div>
          <span className="text-[9px] text-slate-500 mt-1">EV = (Win% * AvgWin) - (Loss% * AvgLoss)</span>
        </div>

        <div className="bg-[#0d121c] p-3.5 rounded-lg border border-surface-border flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-semibold">MAX DRAWDOWN (MDD)</span>
            <ShieldAlert className="w-4 h-4 text-loss" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-loss">{scorecard.max_drawdown_pct}%</span>
            <span className="text-xs text-slate-400">(-${scorecard.max_drawdown_amount})</span>
          </div>
          <span className="text-[9px] text-slate-500 mt-1">High watermark peak-to-trough</span>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">WIN RATE</span>
          <span className="text-base font-bold text-gain">{scorecard.win_rate}%</span>
        </div>
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">PROFIT FACTOR</span>
          <span className="text-base font-bold text-white">{scorecard.profit_factor}</span>
        </div>
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">TOTAL NET PNL</span>
          <span className="text-base font-bold text-gain">${scorecard.total_pnl.toLocaleString()}</span>
        </div>
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">AVG WIN / LOSS</span>
          <span className="text-xs font-bold text-slate-200">${scorecard.avg_win} / ${scorecard.avg_loss}</span>
        </div>
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">HALF-KELLY ALLOC</span>
          <span className="text-base font-bold text-accent">{scorecard.half_kelly_pct}%</span>
        </div>
        <div className="bg-[#111722] p-3 rounded border border-surface-border">
          <span className="text-[10px] text-slate-400 block">WIN / LOSS RATIO</span>
          <span className="text-base font-bold text-slate-200">
            {(scorecard.avg_win / (scorecard.avg_loss || 1)).toFixed(2)} : 1
          </span>
        </div>
      </div>

      <div className="bg-[#0d121c] rounded-lg border border-surface-border p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-bold text-white flex items-center space-x-2">
            <PieChart className="w-3.5 h-3.5 text-accent" />
            <span>DUCKDB COLUMNAR ASSET BREAKDOWN</span>
          </h3>
          <span className="text-[10px] text-slate-500">Aggregated OLAP Query</span>
        </div>
        <table className="w-full text-left text-xs">
          <thead className="text-[10px] text-slate-500 uppercase border-b border-surface-border">
            <tr>
              <th className="py-2">Asset Symbol</th>
              <th className="py-2">Trades Count</th>
              <th className="py-2">Win Rate</th>
              <th className="py-2">Avg PnL</th>
              <th className="py-2 text-right">Net PnL ($)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/40 text-[11px]">
            {symbols.map((s) => (
              <tr key={s.symbol} className="hover:bg-[#111722]">
                <td className="py-2.5 font-bold text-white">{s.symbol}</td>
                <td className="py-2.5 text-slate-300">{s.count}</td>
                <td className="py-2.5 text-gain font-semibold">{s.win_rate}%</td>
                <td className="py-2.5 text-slate-300">${s.avg_pnl}</td>
                <td className="py-2.5 text-right font-bold text-gain">+${s.total_pnl.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )}
</div>
  );
};