import React from "react";
import { PieChart, Layers } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";

export interface AssetBreakdownItem {
  symbol: string;
  asset_class: "crypto" | "forex" | "commodity" | "equity";
  net_pnl: number;
  pnl_percentage: number;
  trade_count: number;
  closed_count: number;
  open_positions: number;
  win_rate: number;
  total_volume: number;
  unknown_pnl_trades?: number;
  unverified_unit_trades?: number;
  volume_basis?: "READY" | "PARTIAL";
}

interface MultiAssetBreakdownProps {
  items: AssetBreakdownItem[];
  loading?: boolean;
}

export const MultiAssetBreakdown: React.FC<MultiAssetBreakdownProps> = ({ items, loading }) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border animate-pulse h-80 flex flex-col justify-center items-center text-slate-500 font-mono text-xs">
        <span>{t("breakdown.loading")}</span>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="bg-[#111722] p-6 rounded-lg border border-surface-border flex flex-col justify-center items-center h-80 text-center select-none font-mono">
        <div className="w-12 h-12 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
          <Layers className="w-6 h-6 text-slate-500" />
        </div>
        <h4 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
          {t("breakdown.empty_title")}
        </h4>
        <p className="text-xs text-slate-400 max-w-xs leading-relaxed">
          {t("breakdown.empty_desc")}
        </p>
      </div>
    );
  }

  // Calculate max PnL magnitude for bar scaling
  const maxAbsPnl = Math.max(...items.map((i) => Math.abs(i.net_pnl)), 1.0);

  const getAssetClassBadge = (cls: string) => {
    switch (cls) {
      case "forex":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">{t("breakdown.fx")}</span>;
      case "commodity":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">{t("breakdown.commodity")}</span>;
      case "equity":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">{t("breakdown.equity")}</span>;
      default:
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">{t("breakdown.crypto")}</span>;
    }
  };

  return (
    <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col h-full select-none font-mono">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <PieChart className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">{t("breakdown.title")}</span>
        </div>
        <span className="text-[10px] text-slate-400 font-semibold">{t("breakdown.instruments_count", { count: items.length })}</span>
      </div>

      <div className="mt-3 space-y-3 overflow-y-auto flex-1 pr-1 custom-scrollbar">
        {items.map((item) => {
          const isProfitable = item.net_pnl >= 0;
          const barWidth = Math.min(100, Math.max(8, (Math.abs(item.net_pnl) / maxAbsPnl) * 100));

          return (
            <div key={item.symbol} className="bg-[#0d121c] p-2.5 rounded border border-surface-border hover:border-slate-700 transition">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-white">{item.symbol}</span>
                  {getAssetClassBadge(item.asset_class)}
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] text-slate-400">
                    {t("breakdown.trades_count", { count: item.trade_count })} ({item.win_rate.toFixed(0)}% WR)
                  </span>
                  <span className={`font-bold ${isProfitable ? "text-gain" : "text-loss"}`}>
                    {isProfitable ? "+" : ""}${item.net_pnl.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Performance Progress Bar */}
              <div className="w-full bg-[#161f2e] h-1.5 rounded-full overflow-hidden flex">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${isProfitable ? "bg-gradient-to-r from-emerald-500 to-gain" : "bg-gradient-to-r from-rose-500 to-loss"}`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[9px] text-slate-500 mt-1">
                <span>
                  {t("breakdown.volume", { vol: item.total_volume.toLocaleString("en-US", { maximumFractionDigits: 0 }) })}
                  {item.volume_basis === "PARTIAL" && (
                    <span className="ml-1 text-amber-300">· {t("breakdown.partial_volume")}</span>
                  )}
                </span>
                {item.open_positions > 0 && (
                  <span className="text-amber-400 font-semibold">{item.open_positions} {t("header.positions")}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
