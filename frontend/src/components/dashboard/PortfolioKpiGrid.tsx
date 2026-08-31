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
  const isAvgRPositive = summary.avg_r_multiple >= 0;

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
              {t("portfolio.total_equity")}
            </span>
            {onOpenInitialBalanceModal && (
              <Edit2 className="w-2.5 h-2.5 text-slate-500 group-hover:text-accent transition opacity-60 group-hover:opacity-100" />
            )}
          </div>
          <Wallet className="w-3.5 h-3.5 text-accent" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-white group-hover:text-cyan-300 transition">
            ${summary.total_equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={`text-[11px] font-semibold flex items-center mt-0.5 ${isNetPnlPositive ? "text-gain" : "text-loss"}`}>
            {isNetPnlPositive ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            <span>{isNetPnlPositive ? "+" : ""}${summary.net_pnl.toFixed(2)} ({isNetPnlPositive ? "+" : ""}{summary.net_pnl_pct.toFixed(1)}%)</span>
          </div>
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
            {summary.profit_factor >= 999 ? "∞" : summary.profit_factor.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {t("portfolio.profit_loss_ratio")}
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
            -{summary.max_drawdown_pct.toFixed(2)}%
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
          <div className={`text-base font-bold ${isAvgRPositive ? "text-purple-300" : "text-loss"}`}>
            {isAvgRPositive ? "+" : ""}{summary.avg_r_multiple.toFixed(2)}R
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {t("portfolio.ev_per_trade")}
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
          <div className="text-base font-bold text-amber-400">
            {summary.open_risk_r.toFixed(1)}R
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            ${summary.open_risk_usd.toFixed(2)} ({summary.active_positions_count} {t("header.positions")})
          </div>
        </div>
      </div>
    </div>
  );
};
