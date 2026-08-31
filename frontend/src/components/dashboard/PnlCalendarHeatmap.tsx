import React, { useState } from "react";
import { Calendar } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";

export interface DailyHeatmapItem {
  date: string;
  pnl: number;
  trades_count: number;
  wins: number;
  losses: number;
  win_rate: number;
  intensity: number; // -1.0 to 1.0
}

interface PnlCalendarHeatmapProps {
  data: DailyHeatmapItem[];
  loading?: boolean;
}

export const PnlCalendarHeatmap: React.FC<PnlCalendarHeatmapProps> = ({ data, loading }) => {
  const { t } = useTranslation();
  const [hoveredDay, setHoveredDay] = useState<DailyHeatmapItem | null>(null);

  if (loading) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border animate-pulse h-48 flex items-center justify-center text-slate-500 font-mono text-xs">
        <span>{t("heatmap.loading")}</span>
      </div>
    );
  }

  // Create a 90-day grid map
  const today = new Date();
  const days: { dateStr: string; item?: DailyHeatmapItem }[] = [];
  const dataMap = new Map<string, DailyHeatmapItem>();

  (data || []).forEach((d) => {
    dataMap.set(d.date, d);
  });

  for (let i = 89; i >= 0; i--) {
    const d = new Date();
    d.setDate(today.getDate() - i);
    const dateStr = d.toISOString().split("T")[0];
    days.push({
      dateStr,
      item: dataMap.get(dateStr),
    });
  }

  const getHeatmapColor = (item?: DailyHeatmapItem) => {
    if (!item || item.trades_count === 0) {
      return "bg-[#161f2e] border-[#1e293b] hover:border-slate-500";
    }
    const pnl = item.pnl;
    if (pnl > 0) {
      if (item.intensity >= 0.7) return "bg-emerald-500 border-emerald-400 text-black";
      if (item.intensity >= 0.3) return "bg-emerald-600 border-emerald-500 text-white";
      return "bg-emerald-800/80 border-emerald-700 text-white";
    } else if (pnl < 0) {
      if (item.intensity <= -0.7) return "bg-rose-600 border-rose-500 text-white";
      if (item.intensity <= -0.3) return "bg-rose-700 border-rose-600 text-white";
      return "bg-rose-900/80 border-rose-800 text-white";
    }
    return "bg-slate-700 border-slate-600 text-white";
  };

  const totalPnL = (data || []).reduce((acc, d) => acc + d.pnl, 0);
  const activeDays = (data || []).filter((d) => d.trades_count > 0).length;

  return (
    <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col select-none font-mono">
      <div className="flex items-center justify-between pb-3 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <Calendar className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            {t("heatmap.title")}
          </span>
        </div>
        <div className="flex items-center space-x-4 text-xs">
          <span className="text-[10px] text-slate-400">
            {t("heatmap.active_days", { count: activeDays })}
          </span>
          <span className={`font-bold ${totalPnL >= 0 ? "text-gain" : "text-loss"}`}>
            {t("heatmap.net_pnl_val", { pnl: `${totalPnL >= 0 ? "+" : ""}$${totalPnL.toFixed(2)}` })}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-col">
        {/* Heatmap Grid (7 rows x ~13 cols) */}
        <div className="grid grid-flow-col grid-rows-7 gap-1.5 overflow-x-auto py-2">
          {days.map(({ dateStr, item }) => (
            <div
              key={dateStr}
              onMouseEnter={() => setHoveredDay(item || { date: dateStr, pnl: 0, trades_count: 0, wins: 0, losses: 0, win_rate: 0, intensity: 0 })}
              onMouseLeave={() => setHoveredDay(null)}
              className={`w-3.5 h-3.5 rounded-xs border transition cursor-pointer ${getHeatmapColor(item)}`}
            />
          ))}
        </div>

        {/* Hover Tooltip & Legend */}
        <div className="flex items-center justify-between pt-2 border-t border-surface-border/50 text-[10px] text-slate-400">
          <div>
            {hoveredDay ? (
              hoveredDay.trades_count > 0 ? (
                <span className="font-semibold text-slate-200">
                  📅 {hoveredDay.date}:{" "}
                  <span className={hoveredDay.pnl >= 0 ? "text-gain font-bold" : "text-loss font-bold"}>
                    {hoveredDay.pnl >= 0 ? "+" : ""}${hoveredDay.pnl.toFixed(2)}
                  </span>{" "}
                  ({t("heatmap.trades_summary", {
                    count: hoveredDay.trades_count,
                    rate: hoveredDay.win_rate.toFixed(0)
                  })})
                </span>
              ) : (
                <span className="font-semibold text-slate-400">
                  📅 {hoveredDay.date}: <span className="text-slate-500">{t("heatmap.no_trades")}</span>
                </span>
              )
            ) : (
              <span className="text-slate-500">
                {activeDays === 0
                  ? t("heatmap.empty_90_days")
                  : t("heatmap.hover_guide")}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-1.5">
            <span>{t("heatmap.loss")}</span>
            <div className="w-2.5 h-2.5 rounded-xs bg-rose-600 border border-rose-500" />
            <div className="w-2.5 h-2.5 rounded-xs bg-rose-800 border border-rose-700" />
            <div className="w-2.5 h-2.5 rounded-xs bg-[#161f2e] border border-[#1e293b]" />
            <div className="w-2.5 h-2.5 rounded-xs bg-emerald-800 border border-emerald-700" />
            <div className="w-2.5 h-2.5 rounded-xs bg-emerald-500 border border-emerald-400" />
            <span>{t("heatmap.profit")}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
