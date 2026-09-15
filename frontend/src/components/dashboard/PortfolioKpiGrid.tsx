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

const money = (value: number) => {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
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
    .map((value, index) => `${(index * step).toFixed(2)},${(26 - ((value - min) / span) * 24 - 1).toFixed(2)}`)
    .join(" ");
  const rising = points[points.length - 1] >= points[0];
  return (
    <svg
      viewBox="0 0 100 26"
      preserveAspectRatio="none"
      className="w-24 h-8 shrink-0"
      aria-hidden="true"
      data-testid="equity-sparkline"
    >
      <polyline
        points={polyline}
        fill="none"
        stroke={rising ? "rgb(var(--gain-rgb))" : "rgb(var(--loss-rgb))"}
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
        <div className="grid grid-cols-2 xl:grid-cols-6 gap-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="k-kpi h-[120px] animate-pulse" />
          ))}
        </div>
        <div className="k-kpi-strip">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="k-kpi-strip-item h-[64px] animate-pulse" />
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
  const hasOpenPositions = summary.active_positions_count > 0;
  const unverified = summary.unverified_open_positions ?? 0;
  const unknownClosed = summary.unknown_pnl_trades ?? 0;

  return (
    <div className="space-y-2 select-none font-mono" data-testid="dashboard-hero">
      {/* Tier 1: the five-second read — live cash, open P&L, risk, exposure, today */}
      <div className="grid grid-cols-2 xl:grid-cols-6 gap-2">
        <div
          onClick={onOpenInitialBalanceModal}
          className={`k-kpi col-span-2 justify-between ${
            onOpenInitialBalanceModal ? "cursor-pointer hover:border-accent/60" : ""
          }`}
          title={t("portfolio.set_balance_tooltip")}
        >
          <div className="k-kpi-label">
            <span className="flex items-center gap-1">
              {showLiveEquity ? t("portfolio.total_equity_live") : t("portfolio.total_equity")}
              {onOpenInitialBalanceModal && (
                <Edit2 className="w-3 h-3 text-muted opacity-60" />
              )}
            </span>
            <Wallet className="w-4 h-4 text-accent" />
          </div>
          <div className="flex items-end justify-between gap-3">
            <span className="k-kpi-value">
              {money(showLiveEquity ? (liveEquity as number) : summary.total_equity)}
            </span>
            {sparkline && <EquitySparkline points={sparkline} />}
          </div>
          <div className={`k-kpi-delta flex items-center ${isNetPnlPositive ? "text-gain" : "text-loss"}`}>
            {isNetPnlPositive ? <ArrowUpRight className="w-4 h-4 mr-0.5" /> : <ArrowDownRight className="w-4 h-4 mr-0.5" />}
            <span>{isNetPnlPositive ? "+" : ""}${summary.net_pnl.toFixed(2)} ({isNetPnlPositive ? "+" : ""}{summary.net_pnl_pct.toFixed(1)}%)</span>
          </div>
          {hasOpenPositions && (
            <div className="k-kpi-sub" data-testid="live-equity-detail">
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

        <div className="k-kpi justify-between">
          <div className="k-kpi-label">
            <span>{t("portfolio.open_unrealized")}</span>
            <TrendingUp className="w-4 h-4 text-accent" />
          </div>
          <span
            className={`k-kpi-value-md font-bold ${
              !hasOpenPositions || (!showLiveEquity && unpricedLive > 0)
                ? "text-muted"
                : unrealized >= 0
                  ? "text-gain"
                  : "text-loss"
            }`}
            title={t("portfolio.tooltip_unrealized")}
          >
            {hasOpenPositions ? signedMoney(unrealized) : "—"}
          </span>
          <span className="k-kpi-sub">
            {!hasOpenPositions
              ? t("portfolio.no_open_positions")
              : `${unrealized >= 0 ? "+" : ""}${unrealizedPct.toFixed(2)}% · ${showLiveEquity ? t("portfolio.live_priced") : t("portfolio.live_unpriced", { count: unpricedLive })}`}
          </span>
        </div>

        <div className="k-kpi justify-between">
          <div className="k-kpi-label">
            <span>{t("portfolio.open_risk")}</span>
            <ShieldAlert className="w-4 h-4 text-muted" />
          </div>
          <span className="k-kpi-value-md font-bold text-ink" title={t("portfolio.tooltip_risk")}>
            {hasOpenRisk ? `${summary.open_risk_r.toFixed(1)}R` : "—"}
          </span>
          <span className="k-kpi-sub">
            {hasOpenRisk
              ? `$${summary.open_risk_usd.toFixed(2)} (${summary.active_positions_count} ${t("header.positions")})`
              : t("portfolio.open_risk_unverified", { count: summary.unverified_open_positions ?? summary.active_positions_count })}
          </span>
        </div>

        <div className="k-kpi justify-between">
          <div className="k-kpi-label">
            <span>{t("portfolio.exposure")}</span>
            <Layers className="w-4 h-4 text-accent" />
          </div>
          <span className="k-kpi-value-md font-bold text-ink" title={t("portfolio.tooltip_exposure")}>
            {exposureBasis === "NOT_AVAILABLE" ? "—" : compactMoney(notional)}
          </span>
          <span className="k-kpi-sub" title={t("portfolio.tooltip_margin")}>
            {exposureBasis === "NOT_AVAILABLE"
              ? t("portfolio.exposure_unavailable")
              : `${t("portfolio.margin_line", {
                  margin: marginPositions > 0 ? compactMoney(margin) : "—",
                  count: marginPositions,
                })}${exposureBasis === "PARTIAL" && exposureUnpriced > 0 ? ` · ${t("portfolio.exposure_partial", { count: exposureUnpriced })}` : ""}`}
          </span>
        </div>

        <div className="k-kpi justify-between">
          <div className="k-kpi-label">
            <span>{t("portfolio.today_pnl")}</span>
            <Activity className="w-4 h-4 text-accent" />
          </div>
          <span className={`k-kpi-value-md font-bold ${isTodayPositive ? "text-gain" : "text-loss"}`}>
            {isTodayPositive ? "+" : ""}${summary.today_pnl.toFixed(2)}
          </span>
          <span className="k-kpi-sub">
            {t("portfolio.today_wl", { wins: today.wins, losses: today.losses })}
            {today.total - today.wins - today.losses > 0
              ? ` · ${t("portfolio.today_unknown", { count: today.total - today.wins - today.losses })}`
              : ""}
          </span>
        </div>
      </div>

      {/* Tier 2: one strip, every diagnostic with the same anatomy */}
      <div className="k-kpi-strip" data-testid="dashboard-rail">
        <div className="k-kpi-strip-item">
          <span className="k-kpi-label">
            <span>{t("portfolio.win_rate")}</span>
            <Target className="w-4 h-4 text-muted" />
          </span>
          <span className="text-lg font-bold text-ink">{summary.win_rate.toFixed(1)}%</span>
          <span className="k-kpi-sub">{t("portfolio.trades_count", { count: summary.total_closed_trades })}</span>
        </div>

        <div className="k-kpi-strip-item" title={t("portfolio.tooltip_pf")}>
          <span className="k-kpi-label">
            <span>{t("portfolio.profit_factor")}</span>
            <Scale className="w-4 h-4 text-muted" />
          </span>
          <span className="text-lg font-bold text-ink">
            {infiniteProfitFactor ? "∞" : summary.profit_factor.toFixed(2)}
          </span>
          <span className="k-kpi-sub">
            {infiniteProfitFactor ? t("portfolio.no_losses") : `${money(summary.gross_profit ?? 0)} / ${money(summary.gross_loss ?? 0)}`}
          </span>
        </div>

        <div className="k-kpi-strip-item" title={t("portfolio.tooltip_avg_r")}>
          <span className="k-kpi-label">
            <span>{t("portfolio.avg_r_multiple")}</span>
            <Zap className="w-4 h-4 text-muted" />
          </span>
          <span className={`text-lg font-bold ${avgR == null ? "text-muted" : isAvgRPositive ? "text-gain" : "text-loss"}`}>
            {avgR == null ? "—" : `${isAvgRPositive ? "+" : ""}${avgR.toFixed(2)}R`}
          </span>
          <span className="k-kpi-sub">{avgR == null ? t("portfolio.no_r_data") : t("portfolio.r_over_trades", { count: knownRTrades })}</span>
        </div>

        <div className="k-kpi-strip-item" title={t("portfolio.tooltip_dd")}>
          <span className="k-kpi-label">
            <span>{t("portfolio.max_drawdown")}</span>
            <Gauge className="w-4 h-4 text-muted" />
          </span>
          <span className="text-lg font-bold text-ink">{drawdownPct.toFixed(2)}%</span>
          <span className="k-kpi-sub">{t("portfolio.peak_to_trough", { amount: `${summary.max_drawdown_usd.toFixed(2)}` })}</span>
        </div>

        <div className="k-kpi-strip-item">
          <span className="k-kpi-label">
            <span>{t("portfolio.active_positions")}</span>
            <Layers className="w-4 h-4 text-muted" />
          </span>
          <span className="text-lg font-bold text-ink">{summary.active_positions_count}</span>
          <span className="k-kpi-sub">
            {unverified > 0
              ? t("portfolio.unverified_count", { count: unverified })
              : t("portfolio.all_verified")}
          </span>
        </div>

        <div className="k-kpi-strip-item">
          <span className="k-kpi-label">
            <span>{t("portfolio.unknown_results")}</span>
            <ShieldAlert className="w-4 h-4 text-muted" />
          </span>
          <span className={`text-lg font-bold ${unknownClosed > 0 ? "text-warn" : "text-muted"}`}>{unknownClosed}</span>
          <span className="k-kpi-sub">{t("portfolio.of_closed", { count: summary.total_closed_trades })}</span>
        </div>

      </div>
    </div>
  );
};
