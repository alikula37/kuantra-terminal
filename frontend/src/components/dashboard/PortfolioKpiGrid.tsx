import React from "react";
import { 
  Wallet, 
  Target, 
  Scale, 
  ShieldAlert, 
  TrendingUp, 
  Zap, 
  ArrowUpRight, 
  ArrowDownRight,
  Edit2
} from "lucide-react";

import { useTranslation } from "../../context/I18nContext";
import { relativeAgeLabel } from "../../lib/tradeTime";

export interface PortfolioSummaryData {
  initial_balance: number;
  total_equity: number;
  net_pnl: number;
  net_pnl_pct: number;
  today_pnl: number;
  today_pnl_pct: number;
  today_trades_count: { wins: number; losses: number; total: number };
  open_risk_usd: number;
  open_risk_r: number;
  active_positions_count: number;
  total_closed_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_r_multiple: number;
  gross_profit?: number;
  gross_loss?: number;
  max_drawdown_usd: number;
  max_drawdown_pct: number;
  unknown_pnl_trades?: number;
  unverified_open_positions?: number;
  known_r_trades?: number;
  open_risk_basis?: "COMPLETE" | "PARTIAL" | "NOT_AVAILABLE";
  profit_factor_basis?: "READY" | "INFINITE_NO_LOSS";
  live_equity?: number | null;
  live_equity_basis?: "COMPLETE" | "PARTIAL" | "NOT_AVAILABLE";
  unrealized_pnl_usd?: number;
  unrealized_pnl_pct?: number;
  live_positions_covered?: number;
  live_positions_unpriced?: number;
  live_quotes_stale?: boolean;
  oldest_live_quote_age_seconds?: number | null;
}

interface PortfolioKpiGridProps {
  summary: PortfolioSummaryData | null;
  loading?: boolean;
  onOpenInitialBalanceModal?: () => void;
}

export const PortfolioKpiGrid: React.FC<PortfolioKpiGridProps> = ({
  summary,
  loading,
  onOpenInitialBalanceModal,
}) => {
  const { t } = useTranslation();

  if (loading || !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 select-none font-mono">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="bg-[#111722] p-3 rounded-lg border border-surface-border animate-pulse h-20" />
        ))}
      </div>
    );
  }

  const isNetPnlPositive = summary.net_pnl >= 0;
  const knownRTrades = summary.known_r_trades ?? 0;
  const avgR = knownRTrades > 0 && summary.avg_r_multiple != null ? summary.avg_r_multiple : null;
  const isAvgRPositive = avgR != null && avgR >= 0;
  const openRiskBasis = summary.open_risk_basis ?? "COMPLETE";
  const liveBasis = summary.live_equity_basis ?? "COMPLETE";
  const liveEquity = summary.live_equity ?? null;
  const showLiveEquity = liveEquity != null && liveBasis !== "NOT_AVAILABLE";
  const unrealized = summary.unrealized_pnl_usd ?? 0;
  const unpricedLive = summary.live_positions_unpriced ?? 0;
  const liveQuoteAge = summary.oldest_live_quote_age_seconds ?? null;
  const money = (value: number) =>
    `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const signedMoney = (value: number) => `${value >= 0 ? "+" : "-"}${money(Math.abs(value))}`;
  const drawdownPct = Math.abs(summary.max_drawdown_pct) < 0.005 ? 0 : summary.max_drawdown_pct;
  const infiniteProfitFactor = (summary.profit_factor_basis ?? (summary.profit_factor >= 999 ? "INFINITE_NO_LOSS" : "READY")) === "INFINITE_NO_LOSS";

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 select-none font-mono">
      {/* 1. Toplam Kasa & Net PnL */}
      <div
        onClick={onOpenInitialBalanceModal}
        className={`bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-accent/60 transition group ${
          onOpenInitialBalanceModal ? "cursor-pointer" : ""
        }`}
        title={t("portfolio.set_balance_tooltip")}
      >
        <div className="flex items-center justify-between text-slate-400">
          <div className="flex items-center space-x-1">
            <span className="text-[10px] uppercase font-semibold tracking-wider">
              {showLiveEquity ? t("portfolio.total_equity_live") : t("portfolio.total_equity")}
            </span>
            {onOpenInitialBalanceModal && (
              <Edit2 className="w-2.5 h-2.5 text-slate-500 group-hover:text-accent transition opacity-60 group-hover:opacity-100" />
            )}
          </div>
          <Wallet className="w-3.5 h-3.5 text-accent" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-white group-hover:text-cyan-300 transition">
            {money(showLiveEquity ? (liveEquity as number) : summary.total_equity)}
          </div>
          <div className={`text-[11px] font-semibold flex items-center mt-0.5 ${isNetPnlPositive ? "text-gain" : "text-loss"}`}>
            {isNetPnlPositive ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            <span>{isNetPnlPositive ? "+" : ""}${summary.net_pnl.toFixed(2)} ({isNetPnlPositive ? "+" : ""}{summary.net_pnl_pct.toFixed(1)}%)</span>
          </div>
          {summary.active_positions_count > 0 && (
            <div className="text-[10px] text-slate-400 mt-0.5 leading-tight" data-testid="live-equity-detail">
              {showLiveEquity ? (
                <>
                  <span>
                    {t("portfolio.live_equity_breakdown", {
                      realized: money(summary.total_equity),
                      open: signedMoney(unrealized),
                    })}
                  </span>
                  <span className="block">
                    {summary.live_quotes_stale
                      ? t("portfolio.live_equity_stale")
                      : liveQuoteAge != null
                        ? t("portfolio.live_equity_age", { age: relativeAgeLabel(liveQuoteAge) })
                        : ""}
                    {liveBasis === "PARTIAL" && unpricedLive > 0
                      ? ` · ${t("portfolio.live_equity_partial", { count: unpricedLive })}`
                      : ""}
                  </span>
                </>
              ) : (
                <span>{t("portfolio.live_equity_unavailable")}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 2. Kazanma Oranı (Win Rate) */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">
            {t("portfolio.win_rate")}
          </span>
          <Target className="w-3.5 h-3.5 text-sky-400" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-white">
            {summary.win_rate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {t("portfolio.trades_count", { count: summary.total_closed_trades })}
          </div>
        </div>
      </div>

      {/* 3. Kâr Faktörü (Profit Factor) */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">
            {t("portfolio.profit_factor")}
          </span>
          <Scale className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-emerald-400">
            {infiniteProfitFactor ? "∞" : summary.profit_factor.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {infiniteProfitFactor ? t("portfolio.no_losses") : t("portfolio.profit_loss_ratio")}
          </div>
        </div>
      </div>

      {/* 4. Maksimum Drawdown */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">
            {t("portfolio.max_drawdown")}
          </span>
          <ShieldAlert className="w-3.5 h-3.5 text-loss" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-loss">
            {drawdownPct === 0 ? "0.00%" : `-${Math.abs(drawdownPct).toFixed(2)}%`}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {t("portfolio.peak_to_trough", { amount: summary.max_drawdown_usd.toFixed(2) })}
          </div>
        </div>
      </div>

      {/* 5. Ortalama R-Multiple */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">
            {t("portfolio.avg_r_multiple")}
          </span>
          <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
        </div>
        <div className="mt-1">
          <div className={`text-base font-bold ${avgR == null ? "text-slate-400" : isAvgRPositive ? "text-purple-300" : "text-loss"}`}>
            {avgR == null ? "—" : `${isAvgRPositive ? "+" : ""}${avgR.toFixed(2)}R`}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {avgR == null ? t("portfolio.no_r_data") : t("portfolio.r_over_trades", { count: knownRTrades })}
          </div>
        </div>
      </div>

      {/* 6. Açık Pozisyon Riski */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">
            {t("portfolio.open_risk")}
          </span>
          <Zap className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="mt-1">
          <div className={`text-base font-bold ${openRiskBasis === "COMPLETE" ? "text-amber-400" : "text-slate-400"}`}>
            {openRiskBasis === "COMPLETE" ? `${summary.open_risk_r.toFixed(1)}R` : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {openRiskBasis === "COMPLETE"
              ? `$${summary.open_risk_usd.toFixed(2)} (${summary.active_positions_count} ${t("header.positions")})`
              : t("portfolio.open_risk_unverified", { count: summary.unverified_open_positions ?? summary.active_positions_count })}
          </div>
        </div>
      </div>
    </div>
  );
};
