import React, { useState, useEffect, useCallback, useRef } from "react";
import { PortfolioKpiGrid, PortfolioSummaryData } from "./dashboard/PortfolioKpiGrid";
import { MultiAssetBreakdown, AssetBreakdownItem } from "./dashboard/MultiAssetBreakdown";
import { EquityCurveChart, EquityCurvePoint } from "./dashboard/EquityCurveChart";
import { OpenPositionsTable } from "./dashboard/OpenPositionsTable";
import { PnlCalendarHeatmap, DailyHeatmapItem } from "./dashboard/PnlCalendarHeatmap";
import { useTradeStore } from "../stores/tradeStore";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { RefreshCw, LayoutDashboard } from "lucide-react";
import { apiFetch, apiUrl } from "../lib/backend";
import type { MarketDataStatus } from "../types";
import { useTranslation } from "../context/I18nContext";
import { LocalTrackingPanel } from "./LocalTrackingPanel";
import type { Trade } from "../types";

interface DashboardViewProps {
  onOpenNewTrade?: () => void;
  onOpenInitialBalanceModal?: () => void;
}

export function canClosePositionAtMarketPrice(currentPrice: number | null, marketDataStatus: MarketDataStatus = "LIVE"): currentPrice is number {
  return marketDataStatus === "LIVE" && currentPrice !== null && Number.isFinite(currentPrice) && currentPrice > 0;
}

export async function requestPositionClose(
  tradeId: string,
  currentPrice: number | null,
  request: (tradeId: string, exitPrice: number) => Promise<{ ok: boolean }>,
  marketDataStatus: MarketDataStatus = "LIVE",
): Promise<{ closed: boolean; error: string | null }> {
  if (!canClosePositionAtMarketPrice(currentPrice, marketDataStatus)) {
    return { closed: false, error: "Canlı piyasa fiyatı olmadan pozisyon kapatılamaz." };
  }
  const response = await request(tradeId, currentPrice);
  return response.ok
    ? { closed: true, error: null }
    : { closed: false, error: "Pozisyon kapatma isteği reddedildi; pozisyon korunuyor." };
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isPortfolioSummaryData(value: unknown): value is PortfolioSummaryData {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  const counts = candidate.today_trades_count;
  const numericFields = [
    "initial_balance", "total_equity", "net_pnl", "net_pnl_pct", "today_pnl", "today_pnl_pct",
    "open_risk_usd", "open_risk_r", "active_positions_count", "total_closed_trades", "win_rate",
    "profit_factor", "max_drawdown_usd", "max_drawdown_pct",
  ];
  const avgRKnown = candidate["avg_r_multiple"] === null || isFiniteNumber(candidate["avg_r_multiple"]);
  const liveEquityKnown = candidate["live_equity"] === undefined
    || candidate["live_equity"] === null
    || isFiniteNumber(candidate["live_equity"]);
  return avgRKnown && liveEquityKnown && numericFields.every((field) => isFiniteNumber(candidate[field]))
    && !!counts && typeof counts === "object"
    && ["wins", "losses", "total"].every((field) => isFiniteNumber((counts as Record<string, unknown>)[field]));
}

function isAssetBreakdown(value: unknown): value is AssetBreakdownItem {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.symbol === "string"
    && typeof candidate.asset_class === "string"
    && ["net_pnl", "pnl_percentage", "trade_count", "closed_count", "open_positions", "win_rate", "total_volume"]
      .every((field) => isFiniteNumber(candidate[field]));
}

function isEquityCurvePoint(value: unknown): value is EquityCurvePoint {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return isFiniteNumber(candidate.timestamp)
    && typeof candidate.date === "string"
    && ["equity", "drawdown_pct", "trade_pnl", "cumulative_pnl"].every((field) => isFiniteNumber(candidate[field]))
    && (candidate.symbol === undefined || typeof candidate.symbol === "string");
}

function isHeatmapItem(value: unknown): value is DailyHeatmapItem {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.date === "string"
    && ["pnl", "trades_count", "wins", "losses", "win_rate", "intensity"]
      .every((field) => isFiniteNumber(candidate[field]));
}

async function readDashboardResponse<T>(response: Response, validate: (value: unknown) => value is T, label: string): Promise<T> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status as the bounded error when the body is not JSON.
    }
    throw new Error(detail || `Dashboard request failed (HTTP ${response.status})`);
  }
  const payload = await response.json();
  if (!validate(payload)) throw new Error(`${label} response was incomplete or malformed`);
  return payload;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onOpenNewTrade,
  onOpenInitialBalanceModal
}) => {
  const { t } = useTranslation();
  const { openPositions } = useTradeStore();
  const { isLiteMode } = usePluginRegistry();

  const [summary, setSummary] = useState<PortfolioSummaryData | null>(null);
  const [breakdown, setBreakdown] = useState<AssetBreakdownItem[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([]);
  const [heatmap, setHeatmap] = useState<DailyHeatmapItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [quoteRefreshNonce, setQuoteRefreshNonce] = useState<number>(0);
  const [editTrade, setEditTrade] = useState<Trade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelled, setCancelled] = useState<boolean>(false);
  const loadControllerRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef(0);
  const hasSnapshotRef = useRef(false);

  const fetchDashboardData = useCallback(async (background = false) => {
    // A slow read must be allowed to finish instead of being aborted each poll.
    if (background && loadControllerRef.current) return;
    loadControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = ++requestIdRef.current;
    loadControllerRef.current = controller;
    setLoading(!hasSnapshotRef.current);
    if (!background) setIsRefreshing(true);
    setCancelled(false);

    try {
      const [summary, nextBreakdown, nextEquityCurve, nextHeatmap] = await Promise.all([
        apiFetch(apiUrl("/api/v1/portfolio/summary"), { signal: controller.signal }).then((response) => readDashboardResponse(response, isPortfolioSummaryData, "Portfolio summary")),
        apiFetch(apiUrl("/api/v1/portfolio/multi-asset-breakdown"), { signal: controller.signal }).then((response) => readDashboardResponse(response, (value): value is AssetBreakdownItem[] => Array.isArray(value) && value.every(isAssetBreakdown), "Portfolio breakdown")),
        apiFetch(apiUrl("/api/v1/portfolio/equity-curve"), { signal: controller.signal }).then((response) => readDashboardResponse(response, (value): value is EquityCurvePoint[] => Array.isArray(value) && value.every(isEquityCurvePoint), "Equity curve")),
        apiFetch(apiUrl("/api/v1/portfolio/heatmap"), { signal: controller.signal }).then((response) => readDashboardResponse(response, (value): value is DailyHeatmapItem[] => Array.isArray(value) && value.every(isHeatmapItem), "Portfolio heatmap"))
      ]);

      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      hasSnapshotRef.current = true;
      setSummary(summary);
      setBreakdown(nextBreakdown);
      setEquityCurve(nextEquityCurve);
      setHeatmap(nextHeatmap);
      setError(null);
    } catch (err) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      console.warn("[DashboardView] Failed to fetch portfolio telemetry:", err);
      setError(err instanceof Error ? err.message : t("dashboard.error"));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setIsRefreshing(false);
        loadControllerRef.current = null;
      }
    }
  }, [t]);

  useEffect(() => {
    void fetchDashboardData();
    const interval = setInterval(() => { void fetchDashboardData(true); }, 4000);
    return () => {
      clearInterval(interval);
      requestIdRef.current += 1;
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
    };
  }, [fetchDashboardData]);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    setQuoteRefreshNonce((current) => current + 1);
    void fetchDashboardData();
  };

  const cancelLoad = () => {
    const controller = loadControllerRef.current;
    if (!controller) return;
    requestIdRef.current += 1;
    controller.abort();
    loadControllerRef.current = null;
    setLoading(false);
    setIsRefreshing(false);
    setCancelled(true);
    setError(t("dashboard.cancelled"));
  };

  const handleClosePosition = (tradeId: string) => {
    const position = openPositions.find(p => p.id === tradeId);
    if (position) setEditTrade(position);
  };

  return (
    <div className="flex-1 h-full overflow-y-auto bg-background p-3 space-y-3 font-sans select-none custom-scrollbar">
      {/* Top Header / Refresh Bar */}
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center space-x-2">
          <LayoutDashboard className="w-5 h-5 text-accent" />
          <h1 className="text-base font-bold text-white uppercase tracking-wide">
            {isLiteMode ? t("dashboard.title_lite") : t("dashboard.title")}
          </h1>
          {summary?.timestamp && (
            <span className="text-[10px] text-slate-500" data-testid="dashboard-as-of">
              {t("dashboard.as_of", { time: new Date(summary.timestamp).toLocaleTimeString() })}
            </span>
          )}
        </div>
        <button
          onClick={handleManualRefresh}
          className="k-btn border border-surface-border bg-[#111722] hover:bg-[#1a2234] text-slate-300 hover:text-white"
          title={t("dashboard.refresh_title")}
        >
          <RefreshCw className={`w-4 h-4 text-accent ${isRefreshing ? "animate-spin" : ""}`} />
          <span>{t("dashboard.refresh")}</span>
        </button>
      </div>

      {loading && (
        <div role="status" data-testid="dashboard-loading" className="rounded border border-surface-border bg-[#111722] px-3 py-2 text-xs text-slate-300 flex items-center justify-between gap-3">
          <span>{t("dashboard.loading")}</span>
          <button type="button" data-testid="dashboard-cancel" onClick={cancelLoad} className="px-2 py-1 rounded border border-surface-border text-slate-300 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent">
            {t("dashboard.cancel_load")}
          </button>
        </div>
      )}

      {!loading && error && (
        <div role="alert" data-testid={cancelled ? "dashboard-cancelled" : "dashboard-error"} className="rounded border border-loss/50 bg-loss/10 px-3 py-2 text-xs text-loss flex items-center justify-between gap-3">
          <span className="break-words">{summary && <span>{t("dashboard.stale_snapshot")} </span>}{error}</span>
          <button type="button" data-testid="dashboard-retry" onClick={() => void fetchDashboardData()} className="shrink-0 px-2 py-1 rounded border border-loss/50 text-loss font-bold hover:bg-loss/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-loss">
            {t("dashboard.retry")}
          </button>
        </div>
      )}

      {(!error || summary !== null) && (
        <>
      {/* Section 1: Portfolio Key Performance Indicators (KPIs) */}
      <PortfolioKpiGrid 
        summary={summary} 
        loading={loading} 
        onOpenInitialBalanceModal={onOpenInitialBalanceModal}
        sparkline={equityCurve.map((point) => point.equity)} 
      />
      {!loading && summary && (summary.unknown_pnl_trades ?? 0) > 0 && (
        <p role="status" data-testid="dashboard-unknown-pnl-note" className="text-sm text-amber-300">
          {t("dashboard.unknown_pnl_note", { count: summary.unknown_pnl_trades ?? 0 })}
        </p>
      )}

      {/* Section 2: Equity curve with the distribution and activity column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 min-h-[320px]">
        <div className="lg:col-span-2 h-full">
          <EquityCurveChart 
            series={equityCurve} 
            loading={loading} 
            onOpenNewTrade={onOpenNewTrade}
          />
        </div>
        <div className="lg:col-span-1 flex flex-col gap-3">
          <MultiAssetBreakdown items={breakdown} loading={loading} />
          <PnlCalendarHeatmap data={heatmap} loading={loading} />
        </div>
      </div>

      {/* Section 3: Open Multi-Asset Positions Table */}
      <OpenPositionsTable
        positions={openPositions}
        onClosePosition={handleClosePosition}
        onEditPosition={setEditTrade}
        onOpenNewTrade={onOpenNewTrade}
        loading={loading}
        refreshNonce={quoteRefreshNonce}
      />
      <LocalTrackingPanel editTrade={editTrade} onEditorClose={() => setEditTrade(null)} />
        </>
      )}
    </div>
  );
};
