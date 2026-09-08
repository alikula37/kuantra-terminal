import React, { useState, useEffect, useCallback } from "react";
import { PortfolioKpiGrid, PortfolioSummaryData } from "./dashboard/PortfolioKpiGrid";
import { MultiAssetBreakdown, AssetBreakdownItem } from "./dashboard/MultiAssetBreakdown";
import { EquityCurveChart, EquityCurvePoint } from "./dashboard/EquityCurveChart";
import { OpenPositionsTable } from "./dashboard/OpenPositionsTable";
import { PnlCalendarHeatmap, DailyHeatmapItem } from "./dashboard/PnlCalendarHeatmap";
import { useTradeStore } from "../stores/tradeStore";
import { useMarketStore } from "../stores/marketStore";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { RefreshCw, LayoutDashboard } from "lucide-react";
import { apiBase, apiFetch, apiUrl } from "../lib/backend";
import type { MarketDataStatus } from "../types";

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

export const DashboardView: React.FC<DashboardViewProps> = ({
  onOpenNewTrade,
  onOpenInitialBalanceModal
}) => {
  const { openPositions, updatePositionPnl } = useTradeStore();
  const { currentPrice, marketDataStatus } = useMarketStore();
  const { isLiteMode } = usePluginRegistry();

  const [summary, setSummary] = useState<PortfolioSummaryData | null>(null);
  const [breakdown, setBreakdown] = useState<AssetBreakdownItem[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([]);
  const [heatmap, setHeatmap] = useState<DailyHeatmapItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [closeError, setCloseError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    try {
      const [sumRes, breakRes, curveRes, heatRes] = await Promise.all([
        apiFetch(apiUrl("/api/v1/portfolio/summary")),
        apiFetch(apiUrl("/api/v1/portfolio/multi-asset-breakdown")),
        apiFetch(apiUrl("/api/v1/portfolio/equity-curve")),
        apiFetch(apiUrl("/api/v1/portfolio/heatmap"))
      ]);

      if (sumRes.ok) setSummary(await sumRes.json());
      if (breakRes.ok) setBreakdown(await breakRes.json());
      if (curveRes.ok) setEquityCurve(await curveRes.json());
      if (heatRes.ok) setHeatmap(await heatRes.json());
    } catch (err) {
      console.warn("[DashboardView] Failed to fetch portfolio telemetry:", err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 4000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    fetchDashboardData();
  };

  const handleClosePosition = async (tradeId: string) => {
    if (!canClosePositionAtMarketPrice(currentPrice, marketDataStatus)) {
      setCloseError("Canlı piyasa fiyatı olmadan pozisyon kapatılamaz.");
      return;
    }

    try {
      const result = await requestPositionClose(tradeId, currentPrice, (id, exitPrice) => apiFetch(`${apiBase()}/api/v1/trades/${id}/close`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exit_price: exitPrice,
          exit_time: new Date().toISOString(),
        }),
      }), marketDataStatus);
      if (!result.closed) {
        setCloseError(result.error);
        return;
      }
      updatePositionPnl(openPositions.filter((p) => p.id !== tradeId));
      setCloseError(null);
      fetchDashboardData();
    } catch {
      setCloseError("Pozisyon kapatma isteği gönderilemedi; pozisyon korunuyor.");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-[#0b0e14] p-4 space-y-4 font-mono select-none custom-scrollbar">
      {/* Top Header / Refresh Bar */}
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center space-x-2">
          <LayoutDashboard className="w-5 h-5 text-accent" />
          <h1 className="text-sm font-bold text-white uppercase tracking-wider">
            {isLiteMode ? "LITE PORTFÖY & RİSK DASHBOARD" : "BIG PICTURE QUANT DASHBOARD"}
          </h1>
        </div>
        <button
          onClick={handleManualRefresh}
          className="flex items-center space-x-1.5 px-3 py-1 rounded bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 hover:text-white text-xs font-semibold transition active:scale-95 cursor-pointer"
          title="Verileri Yenile"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-accent ${isRefreshing ? "animate-spin" : ""}`} />
          <span>Yenile</span>
        </button>
      </div>

      {closeError && (
        <div role="alert" className="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          {closeError}
        </div>
      )}

      {/* Section 1: Portfolio Key Performance Indicators (KPIs) */}
      <PortfolioKpiGrid 
        summary={summary} 
        loading={loading} 
        onOpenInitialBalanceModal={onOpenInitialBalanceModal} 
      />

      {/* Section 2: Two-Column Grid -> Equity Curve Chart & Multi-Asset Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-[320px]">
        <div className="lg:col-span-2 h-full">
          <EquityCurveChart 
            series={equityCurve} 
            loading={loading} 
            onOpenNewTrade={onOpenNewTrade}
          />
        </div>
        <div className="lg:col-span-1 h-full">
          <MultiAssetBreakdown items={breakdown} loading={loading} />
        </div>
      </div>

      {/* Section 3: Open Multi-Asset Positions Table */}
      <OpenPositionsTable
        positions={openPositions}
        onClosePosition={handleClosePosition}
        onOpenNewTrade={onOpenNewTrade}
        loading={loading}
      />

      {/* Section 4: 90-Day PnL Calendar Heatmap */}
      <PnlCalendarHeatmap data={heatmap} loading={loading} />
    </div>
  );
};
