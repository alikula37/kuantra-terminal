import React from "react";
import { PieChart, Layers } from "lucide-react";

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
}

interface MultiAssetBreakdownProps {
  items: AssetBreakdownItem[];
  loading?: boolean;
}

export const MultiAssetBreakdown: React.FC<MultiAssetBreakdownProps> = ({ items, loading }) => {
  if (loading) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border animate-pulse h-80 flex flex-col justify-center items-center text-slate-500 font-mono text-xs">
        <span>Varlık Dağılımı Yükleniyor...</span>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col justify-center items-center h-80 text-slate-500 font-mono text-xs">
        <Layers className="w-8 h-8 text-slate-600 mb-2" />
        <span>Henüz kaydedilmiş çoklu varlık işlemi bulunmuyor.</span>
      </div>
    );
  }

  // Calculate max PnL magnitude for bar scaling
  const maxAbsPnl = Math.max(...items.map((i) => Math.abs(i.net_pnl)), 1.0);

  const getAssetClassBadge = (cls: string) => {
    switch (cls) {
      case "forex":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-bold">FX</span>;
      case "commodity":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">EMTİA</span>;
      case "equity":
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">HİSSE</span>;
      default:
        return <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-bold">KRİPTO</span>;
    }
  };

  return (
    <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col h-full select-none font-mono">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <PieChart className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">VARLIK PERFORMANS DAĞILIMI</span>
        </div>
        <span className="text-[10px] text-slate-400 font-semibold">{items.length} Farklı Enstrüman</span>
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
                    {item.trade_count} İşlem ({item.win_rate.toFixed(0)}% WR)
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
                <span>Hacim: ${item.total_volume.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
                {item.open_positions > 0 && (
                  <span className="text-amber-400 font-semibold">{item.open_positions} Açık Pozisyon</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
