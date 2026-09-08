import React, { useCallback, useEffect, useRef, useState } from "react";
import { QuantScorecard, SymbolBreakdown } from "../types";
import { Award, TrendingUp, ShieldAlert, Target, PieChart } from "lucide-react";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";

const SCORECARD_FIELDS: Array<keyof QuantScorecard> = [
  "total_trades", "win_rate", "loss_rate", "total_pnl", "avg_win", "avg_loss",
  "profit_factor", "expectancy", "sqn", "sharpe_ratio", "sortino_ratio",
  "max_drawdown_amount", "max_drawdown_pct", "half_kelly_pct",
];

function isQuantScorecard(value: unknown): value is QuantScorecard {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return SCORECARD_FIELDS.every((field) => typeof candidate[field] === "number" && Number.isFinite(candidate[field]));
}

function isSymbolBreakdown(value: unknown): value is SymbolBreakdown {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.symbol === "string"
    && typeof candidate.count === "number" && Number.isFinite(candidate.count)
    && typeof candidate.total_pnl === "number" && Number.isFinite(candidate.total_pnl)
    && typeof candidate.avg_pnl === "number" && Number.isFinite(candidate.avg_pnl)
    && typeof candidate.win_rate === "number" && Number.isFinite(candidate.win_rate);
}

async function readAnalyticsResponse(response: Response): Promise<unknown> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status as the bounded error when the body is not JSON.
    }
    throw new Error(detail || `Analytics request failed (HTTP ${response.status})`);
  }
  return response.json();
}

export const AnalyticsView: React.FC = () => {
  const { t } = useTranslation();
  const [scorecard, setScorecard] = useState<QuantScorecard | null>(null);
  const [symbols, setSymbols] = useState<SymbolBreakdown[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState<boolean>(false);
  const loadControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);

  const loadAnalytics = useCallback(async () => {
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    loadControllerRef.current = controller;
    setIsLoading(true);
    setError(null);
    setCancelled(false);

    try {
      const [quantData, symData] = await Promise.all([
        apiFetch(apiUrl("/api/v1/analytics/quant"), { signal: controller.signal }).then(readAnalyticsResponse),
        apiFetch(apiUrl("/api/v1/analytics/symbols"), { signal: controller.signal }).then(readAnalyticsResponse),
      ]);

      if (!isQuantScorecard(quantData)) {
        throw new Error("Analytics response did not contain a complete quant scorecard");
      }

      if (!Array.isArray(symData) || !symData.every(isSymbolBreakdown)) {
        throw new Error("Analytics response did not contain a valid symbol breakdown");
      }

      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setScorecard(quantData);
      setSymbols(symData);
    } catch (err) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      console.warn("[AnalyticsView] Failed to fetch quantitative analytics:", err);
      setError(err instanceof Error ? err.message : t("analytics.error"));
    } finally {
      if (requestId === requestIdRef.current) {
        setIsLoading(false);
        loadControllerRef.current = null;
      }
    }
  }, [t]);

  useEffect(() => {
    void loadAnalytics();
    return () => {
      requestIdRef.current += 1;
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
    };
  }, [loadAnalytics]);

  const cancelLoad = () => {
    const controller = loadControllerRef.current;
    if (!controller) return;
    requestIdRef.current += 1;
    controller.abort();
    loadControllerRef.current = null;
    setIsLoading(false);
    setCancelled(true);
    setError(t("analytics.cancelled"));
  };

  if (isLoading) {
    return (
      <div role="status" data-testid="analytics-loading" className="p-8 text-center text-slate-400 font-mono space-y-3">
        <span className="block">{t("analytics.loading")}</span>
        <button type="button" data-testid="analytics-cancel" onClick={cancelLoad} className="px-2 py-1 rounded border border-surface-border text-slate-300 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
          {t("analytics.cancel_load")}
        </button>
      </div>
    );
  }

  if (error || !scorecard) {
    return (
      <div role="alert" data-testid={cancelled ? "analytics-cancelled" : "analytics-error"} className="p-8 text-center text-loss font-mono space-y-3">
        <span className="block">{error || t("analytics.error")}</span>
        <button type="button" data-testid="analytics-retry" onClick={() => void loadAnalytics()} className="px-2 py-1 rounded border border-loss/50 text-loss font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">
          {t("analytics.retry")}
        </button>
      </div>
    );
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
