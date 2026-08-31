import React from "react";
import { 
  Wallet, 
  Target, 
  Scale, 
  ShieldAlert, 
  TrendingUp, 
  Zap, 
  ArrowUpRight, 
  ArrowDownRight 
} from "lucide-react";

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
}

export const PortfolioKpiGrid: React.FC<PortfolioKpiGridProps> = ({ summary, loading }) => {
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
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">TOPLAM KASA</span>
          <Wallet className="w-3.5 h-3.5 text-accent" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-white">
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
          <span className="text-[10px] uppercase font-semibold tracking-wider">KAZANMA ORANI</span>
          <Target className="w-3.5 h-3.5 text-sky-400" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-white">
            {summary.win_rate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {summary.total_closed_trades} Toplam İşlem
          </div>
        </div>
      </div>

      {/* 3. Kâr Faktörü (Profit Factor) */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">KÂR FAKTÖRÜ</span>
          <Scale className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-emerald-400">
            {summary.profit_factor >= 999 ? "∞" : summary.profit_factor.toFixed(2)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Brüt Kâr / Zarar
          </div>
        </div>
      </div>

      {/* 4. Maksimum Drawdown */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">MAX DRAWDOWN</span>
          <ShieldAlert className="w-3.5 h-3.5 text-loss" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-loss">
            -{summary.max_drawdown_pct.toFixed(2)}%
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            -${summary.max_drawdown_usd.toFixed(2)} (Peak-to-Trough)
          </div>
        </div>
      </div>

      {/* 5. Ortalama R-Multiple */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">ORTALAMA R</span>
          <TrendingUp className="w-3.5 h-3.5 text-purple-400" />
        </div>
        <div className="mt-1">
          <div className={`text-base font-bold ${isAvgRPositive ? "text-purple-300" : "text-loss"}`}>
            {isAvgRPositive ? "+" : ""}{summary.avg_r_multiple.toFixed(2)}R
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            İşlem Başına R-Getiri
          </div>
        </div>
      </div>

      {/* 6. Açık Pozisyon Riski */}
      <div className="bg-[#111722] p-3 rounded-lg border border-surface-border flex flex-col justify-between hover:border-slate-700 transition">
        <div className="flex items-center justify-between text-slate-400">
          <span className="text-[10px] uppercase font-semibold tracking-wider">AÇIK RİSK (EXPOSURE)</span>
          <Zap className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="mt-1">
          <div className="text-base font-bold text-amber-400">
            {summary.open_risk_r.toFixed(1)}R
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            ${summary.open_risk_usd.toFixed(2)} ({summary.active_positions_count} Pozisyon)
          </div>
        </div>
      </div>
    </div>
  );
};
