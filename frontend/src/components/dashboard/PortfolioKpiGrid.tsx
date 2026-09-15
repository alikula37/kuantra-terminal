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
  Edit2,
  Layers,
  Activity,
  Gauge,
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
  open_notional_usd?: number;
  open_margin_usd?: number;
  open_margin_positions?: number;
  open_exposure_basis?: "COMPLETE" | "PARTIAL" | "NOT_AVAILABLE";
  open_exposure_unpriced?: number;
  timestamp?: string;
}

interface PortfolioKpiGridProps {
  summary: PortfolioSummaryData | null;
  loading?: boolean;
  onOpenInitialBalanceModal?: () => void;
  sparkline?: number[];
}

const money = (value: number) =>
  `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const signedMoney = (value: number) => `${value >= 0 ? "+" : "-"}${money(Math.abs(value))}`;
const compactMoney = (value: number) => {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${money(abs)}`;
};

const EquitySparkline: React.FC<{ points: number[] }> = ({ points }) => {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = 100 / (points.length - 1);
  const polyline = points
    .map((value, index) => `${(index * step).toFixed(2)},${(28 - ((value - min) / span) * 26 - 1).toFixed(2)}`)
    .join(" ");
  const rising = points[points.length - 1] >= points[0];
  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="w-24 h-8" aria-hidden="true" data-testid="equity-sparkline">
      <polyline
        points={polyline}
        fill="none"
        stroke={rising ? "#10b981" : "#ef4444"}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
};

export const PortfolioKpiGrid: React.FC<PortfolioKpiGridProps> = ({
  summary,
  loading,
  onOpenInitialBalanceModal,
  sparkline,
}) => {
  const { t } = useTranslation();

  if (loading || !summary) {
    return (
      <div className="space-y-2 select-none font-mono">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-[#111722] p-3 rounded border border-surface-border animate-pulse h-20" />
          ))}
        </div>
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-[#111722] px-3 py-2 rounded border border-surface-border animate-pulse h-12" />
          ))}
        </div>
      </div>
    );
  }

  const isNetPnlPositive = summary.net_pnl >= 0;
  const knownRTrades = summary.known_r_trades ?? 0;
  const avgR = knownRTrades > 0 && summary.avg_r_multiple != null ? summary.avg_r_multiple : null;
  const isAvgRPositive = avgR != null && avgR >= 0;
  const openRiskBasis = summary.open_risk_basis ?? "COMPLETE";
  const drawdownPct = Math.abs(summary.max_drawdown_pct) < 0.005 ? 0 : summary.max_drawdown_pct;
  const infiniteProfitFactor = (summary.profit_factor_basis ?? (summary.profit_factor >= 999 ? "INFINITE_NO_LOSS" : "READY")) === "INFINITE_NO_LOSS";

  const liveBasis = summary.live_equity_basis ?? "COMPLETE";
  const liveEquity = summary.live_equity ?? null;
  const showLiveEquity = liveEquity != null && liveBasis !== "NOT_AVAILABLE";
  const unrealized = summary.unrealized_pnl_usd ?? 0;
  const unrealizedPct = summary.unrealized_pnl_pct ?? 0;
  const unpricedLive = summary.live_positions_unpriced ?? 0;
  const liveQuoteAge = summary.oldest_live_quote_age_seconds ?? null;

  const exposureBasis = summary.open_exposure_basis ?? "COMPLETE";
  const notional = summary.open_notional_usd ?? 0;
  const margin = summary.open_margin_usd ?? 0;
  const marginPositions = summary.open_margin_positions ?? 0;
  const exposureUnpriced = summary.open_exposure_unpriced ?? 0;

  const hasOpenRisk = openRiskBasis === "COMPLETE";
  const today = summary.today_trades_count ?? { wins: 0, losses: 0, total: 0 };
  const isTodayPositive = summary.today_pnl >= 0;

  return (
    <div className="space-y-2 select-none font-mono">
      {/* Hero row: what the owner must understand in one glance */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-2" data-testid="dashboard-hero">
        <div
          onClick={onOpenInitialBalanceModal}
          className={`col-span-2 lg:col-span-1 bg-[#0e141f] px-3 py-2 rounded border border-surface-border border-l-2 border-l-accent flex flex-col justify-between hover:border-accent/60 transition group ${
            onOpenInitialBalanceModal ? "cursor-pointer" : ""
          }`}
          title={t("portfolio.set_balance_tooltip")}
        >
          <div className="flex items-center justify-between text-slate-500">
            <div className="flex items-center space-x-1">
              <span className="text-[10px] uppercase font-semibold tracking-wider">
                {showLiveEquity ? t("portfolio.total_equity_live") : t("portfolio.total_equity")}
              </span>
              {onOpenInitialBalanceModal && (
                <Edit2 className="w-2.5 h-2.5 text-slate-600 group-hover:text-accent transition opacity-60 group-hover:opacity-100" />
              )}
            </div>
            <Wallet className="w-3.5 h-3.5 text-accent" />
          </div>
          <div className="flex items-end justify-between gap-2">
            <div className="text-lg font-bold leading-tight text-white group-hover:text-cyan-300 transition">
              {money(showLiveEquity ? (liveEquity as number) : summary.total_equity)}
            </div>
            {sparkline && <EquitySparkline points={sparkline} />}
          </div>
          <div className={`text-[11px] font-semibold flex items-center ${isNetPnlPositive ? "text-gain" : "text-loss"}`}>
            {isNetPnlPositive ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            <span>{isNetPnlPositive ? "+" : ""}${summary.net_pnl.toFixed(2)} ({isNetPnlPositive ? "+" : ""}{summary.net_pnl_pct.toFixed(1)}%)</span>
          </div>
          {summary.active_positions_count > 0 && (
            <div className="text-[10px] text-slate-400 leading-tight" data-testid="live-equity-detail">
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

        <div className="bg-[#0e141f] px-3 py-2 rounded border border-surface-border border-l-2 border-l-gain/70 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] uppercase font-semibold tracking-wider">{t("portfolio.open_unrealized")}</span>
            <TrendingUp className="w-3.5 h-3.5 text-gain" />
          </div>
          <div
            className={`text-lg font-bold leading-tight ${
              summary.active_positions_count === 0 || (!showLiveEquity && unpricedLive > 0)
                ? "text-slate-400"
                : unrealized >= 0
                  ? "text-gain"
                  : "text-loss"
            }`}
            title={t("portfolio.tooltip_unrealized")}
          >
            {summary.active_positions_count === 0 ? "—" : signedMoney(unrealized)}
          </div>
          <div className="text-[10px] text-slate-400">
            {summary.active_positions_count === 0
              ? t("portfolio.no_open_positions")
              : `${unrealized >= 0 ? "+" : ""}${unrealizedPct.toFixed(2)}% · ${showLiveEquity ? t("portfolio.live_priced") : t("portfolio.live_unpriced", { count: unpricedLive })}`}
          </div>
        </div>

        <div className="bg-[#0e141f] px-3 py-2 rounded border border-surface-border border-l-2 border-l-purple-400/70 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] uppercase font-semibold tracking-wider">{t("portfolio.open_risk")}</span>
            <ShieldAlert className="w-3.5 h-3.5 text-purple-300" />
          </div>
          <div className="text-lg font-bold leading-tight text-purple-200" title={t("portfolio.tooltip_risk")}>
            {hasOpenRisk ? `${summary.open_risk_r.toFixed(1)}R` : "—"}
          </div>
          <div className="text-[10px] text-slate-400">
            {hasOpenRisk
              ? `$${summary.open_risk_usd.toFixed(2)} (${summary.active_positions_count} ${t("header.positions")})`
              : t("portfolio.open_risk_unverified", { count: summary.unverified_open_positions ?? summary.active_positions_count })}
          </div>
        </div>

        <div className="bg-[#0e141f] px-3 py-2 rounded border border-surface-border border-l-2 border-l-sky-400/70 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] uppercase font-semibold tracking-wider">{t("portfolio.exposure")}</span>
            <Layers className="w-3.5 h-3.5 text-sky-400" />
          </div>
          <div className="text-lg font-bold leading-tight text-sky-100" title={t("portfolio.tooltip_exposure")}>
            {exposureBasis === "NOT_AVAILABLE" ? "—" : compactMoney(notional)}
          </div>
          <div className="text-[10px] text-slate-400" title={t("portfolio.tooltip_margin")}>
            {exposureBasis === "NOT_AVAILABLE"
              ? t("portfolio.exposure_unavailable")
              : `${t("portfolio.margin_line", {
                  margin: marginPositions > 0 ? compactMoney(margin) : "—",
                  count: marginPositions,
                })}${exposureBasis === "PARTIAL" && exposureUnpriced > 0 ? ` · ${t("portfolio.exposure_partial", { count: exposureUnpriced })}` : ""}`}
          </div>
        </div>

        <div className="bg-[#0e141f] px-3 py-2 rounded border border-surface-border border-l-2 border-l-amber-400/70 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-[10px] uppercase font-semibold tracking-wider">{t("portfolio.today_pnl")}</span>
            <Activity className="w-3.5 h-3.5 text-amber-300" />
          </div>
          <div className={`text-lg font-bold leading-tight ${isTodayPositive ? "text-gain" : "text-loss"}`}>
            {isTodayPositive ? "+" : ""}${summary.today_pnl.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-400">
            {t("portfolio.today_wl", { wins: today.wins, losses: today.losses })}
            {today.total - today.wins - today.losses > 0
              ? ` · ${t("portfolio.today_unknown", { count: today.total - today.wins - today.losses })}`
              : ""}
          </div>
        </div>
      </div>

      {/* Compact rail: secondary truth, always visible */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2" data-testid="dashboard-rail">
        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.win_rate")}</div>
            <div className="text-sm font-bold text-white">{summary.win_rate.toFixed(1)}%</div>
          </div>
          <div className="text-right">
            <Target className="w-3.5 h-3.5 text-sky-400" />
            <div className="text-[9px] text-slate-500">{t("portfolio.trades_count", { count: summary.total_closed_trades })}</div>
          </div>
        </div>

        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between" title={t("portfolio.tooltip_pf")}>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.profit_factor")}</div>
            <div className="text-sm font-bold text-emerald-400">
              {infiniteProfitFactor ? "∞" : summary.profit_factor.toFixed(2)}
            </div>
          </div>
          <div className="text-right">
            <Scale className="w-3.5 h-3.5 text-emerald-400" />
            <div className="text-[9px] text-slate-500">{infiniteProfitFactor ? t("portfolio.no_losses") : `${money(summary.gross_profit ?? 0)} / ${money(summary.gross_loss ?? 0)}`}</div>
          </div>
        </div>

        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between" title={t("portfolio.tooltip_avg_r")}>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.avg_r_multiple")}</div>
            <div className={`text-sm font-bold ${avgR == null ? "text-slate-400" : isAvgRPositive ? "text-gain" : "text-loss"}`}>
              {avgR == null ? "—" : `${isAvgRPositive ? "+" : ""}${avgR.toFixed(2)}R`}
            </div>
          </div>
          <div className="text-right">
            <Zap className="w-3.5 h-3.5 text-yellow-400" />
            <div className="text-[9px] text-slate-500">
              {avgR == null ? t("portfolio.no_r_data") : t("portfolio.r_over_trades", { count: knownRTrades })}
            </div>
          </div>
        </div>

        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between" title={t("portfolio.tooltip_dd")}>
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.max_drawdown")}</div>
            <div className="text-sm font-bold text-white">{drawdownPct.toFixed(2)}%</div>
          </div>
          <div className="text-right">
            <Gauge className="w-3.5 h-3.5 text-loss" />
            <div className="text-[9px] text-slate-500">{t("portfolio.peak_to_trough", { amount: `${summary.max_drawdown_usd.toFixed(2)}` })}</div>
          </div>
        </div>

        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.active_positions")}</div>
            <div className="text-sm font-bold text-white">{summary.active_positions_count}</div>
          </div>
          <div className="text-right">
            <Layers className="w-3.5 h-3.5 text-accent" />
            <div className="text-[9px] text-slate-500">
              {(summary.unverified_open_positions ?? 0) > 0
                ? t("portfolio.unverified_count", { count: summary.unverified_open_positions ?? 0 })
                : t("portfolio.all_verified")}
            </div>
          </div>
        </div>

        <div className="bg-[#111722] px-3 py-1.5 rounded border border-surface-border flex items-center justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-slate-500">{t("portfolio.unknown_results")}</div>
            <div className={`text-sm font-bold ${(summary.unknown_pnl_trades ?? 0) > 0 ? "text-amber-300" : "text-slate-400"}`}>
              {summary.unknown_pnl_trades ?? 0}
            </div>
          </div>
          <div className="text-right">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-300" />
            <div className="text-[9px] text-slate-500">{t("portfolio.of_closed", { count: summary.total_closed_trades })}</div>
          </div>
        </div>
      </div>
    </div>
  );
};
