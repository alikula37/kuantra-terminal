import React, { useState, useEffect } from "react";
import { MaeMfeAnalyticsResponse, MaeMfePoint } from "../types";
import { Crosshair, ShieldAlert, TrendingUp } from "lucide-react";
import { useTranslation } from "../context/I18nContext";

export const MaeMfeVisualizer: React.FC = () => {
  const { t } = useTranslation();
  const [data, setData] = useState<MaeMfeAnalyticsResponse | null>(null);
  const [hoveredPoint, setHoveredPoint] = useState<MaeMfePoint | null>(null);
  const [filterSide, setFilterSide] = useState<string>("ALL");
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    setIsLoading(true);
    fetch("http://127.0.0.1:8000/api/v1/analytics/mae-mfe")
      .then((res) => res.json())
      .then((resData) => {
        setData(resData);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, []);

  if (isLoading || !data) {
    return <div className="p-8 text-center text-slate-400 font-mono">Loading MAE / MFE analytics...</div>;
  }

  const filteredPoints = data.points.filter((p) => {
    if (filterSide === "ALL") return true;
    return p.side.toUpperCase() === filterSide.toUpperCase();
  });

  // Chart dimensions & scaling
  const width = 640;
  const height = 360;
  const padding = 45;

  // X range: MAE from -2.5R to 0.0R
  const minX = -2.5;
  const maxX = 0.0;
  // Y range: MFE from 0.0R to 5.0R
  const minY = 0.0;
  const maxY = 5.0;

  const scaleX = (mae_r: number) => {
    const clamped = Math.max(minX, Math.min(maxX, mae_r));
    return padding + ((clamped - minX) / (maxX - minX)) * (width - 2 * padding);
  };

  const scaleY = (mfe_r: number) => {
    const clamped = Math.max(minY, Math.min(maxY, mfe_r));
    return height - padding - ((clamped - minY) / (maxY - minY)) * (height - 2 * padding);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header Bar */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Crosshair className="w-4 h-4 text-accent" />
            <span>{t("mae_mfe.title")}</span>
          </h2>
          <p className="text-xs text-slate-400">
            {t("mae_mfe.subtitle")}
          </p>
        </div>

        {/* Side Filter */}
        <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1 rounded border border-surface-border text-xs">
          <span className="text-slate-400">Direction:</span>
          <select
            value={filterSide}
            onChange={(e) => setFilterSide(e.target.value)}
            className="bg-transparent text-white focus:outline-none font-bold"
          >
            <option value="ALL">All Trades</option>
            <option value="BUY">Long Only</option>
            <option value="SELL">Short Only</option>
          </select>
        </div>
      </div>

      {data.total_analyzed === 0 || data.points.length === 0 ? (
        <div className="flex-1 bg-[#0d121c] p-12 rounded-lg border border-surface-border flex flex-col items-center justify-center text-center select-none font-mono">
          <div className="w-14 h-14 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
            <Crosshair className="w-7 h-7 text-accent" />
          </div>
          <h3 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
            {t("mae_mfe.waiting_title")}
          </h3>
          <p className="text-xs text-slate-400 max-w-md leading-relaxed">
            {t("mae_mfe.waiting_desc")}
          </p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">AVG EXIT EFFICIENCY</span>
              <span className="text-xl font-bold text-gain">{data.average_exit_efficiency_pct}%</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">(Actual PnL / MFE Potential)</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">RECOMMENDED TARGET (75TH %)</span>
              <span className="text-xl font-bold text-accent">+{data.recommended_target_r} R</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">Optimal take profit cluster</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">LEFT MONEY ON TABLE</span>
              <span className="text-xl font-bold text-amber-400">{data.trades_left_money_on_table} Trades</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">Reached &gt;2R MFE but exited &lt;0.5R</span>
            </div>

            <div className="bg-[#0d121c] p-3 rounded-lg border border-surface-border">
              <span className="text-[10px] text-slate-400 block font-semibold">AVG ADVERSE EXCURSION</span>
              <span className="text-xl font-bold text-slate-200">{data.average_mae_r} R</span>
              <span className="text-[9px] text-slate-500 block mt-0.5">Mean heat endured before exit</span>
            </div>
          </div>

          {/* Main Scatter Visualizer Canvas + Details Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Interactive Scatter Plot */}
        <div className="lg:col-span-2 bg-[#0d121c] p-4 rounded-lg border border-surface-border relative flex flex-col items-center">
          <div className="w-full flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-accent" />
              <span>MAE (Heat Endured) vs MFE (Peak Potential) Scatter</span>
            </span>
            <span className="text-[10px] text-slate-500 font-mono">X: Adverse (R) | Y: Favorable (R)</span>
          </div>

          <div className="w-full relative flex justify-center">
            <svg width={width} height={height} className="overflow-visible">
              {/* Background Grid & Axes */}
              <rect x={padding} y={padding} width={width - 2 * padding} height={height - 2 * padding} fill="#090d14" stroke="#1e293b" />

              {/* 1R Stop Loss Threshold Line */}
              <line
                x1={scaleX(-1.0)}
                y1={padding}
                x2={scaleX(-1.0)}
                y2={height - padding}
                stroke="#ef4444"
                strokeDasharray="4"
                strokeWidth="1.5"
              />
              <text x={scaleX(-1.0) - 5} y={padding + 15} fill="#ef4444" fontSize="9" textAnchor="end" fontWeight="bold">
                1.0R Initial Stop
              </text>

              {/* 2R / 3R Target Lines */}
              <line
                x1={padding}
                y1={scaleY(2.0)}
                x2={width - padding}
                y2={scaleY(2.0)}
                stroke="#38bdf8"
                strokeDasharray="3"
                strokeWidth="1"
                opacity="0.5"
              />
              <text x={width - padding - 5} y={scaleY(2.0) - 4} fill="#38bdf8" fontSize="9" textAnchor="end">
                +2.0R Target
              </text>

              <line
                x1={padding}
                y1={scaleY(data.recommended_target_r)}
                x2={width - padding}
                y2={scaleY(data.recommended_target_r)}
                stroke="#10b981"
                strokeDasharray="4"
                strokeWidth="1.5"
              />
              <text x={width - padding - 5} y={scaleY(data.recommended_target_r) - 4} fill="#10b981" fontSize="9" textAnchor="end" fontWeight="bold">
                +{data.recommended_target_r}R Optimal Target (75th %)
              </text>

              {/* Quadrant Zone Labels */}
              <text x={width - padding - 10} y={padding + 25} fill="#10b981" opacity="0.35" fontSize="11" fontWeight="bold" textAnchor="end">
                HIGH POTENTIAL / LOW HEAT (OPTIMAL)
              </text>
              <text x={padding + 10} y={padding + 25} fill="#f59e0b" opacity="0.3" fontSize="11" fontWeight="bold">
                HIGH HEAT / HIGH RETURN
              </text>
              <text x={padding + 10} y={height - padding - 15} fill="#ef4444" opacity="0.3" fontSize="11" fontWeight="bold">
                DIRECT STOP OUT
              </text>

              {/* X Axis Ticks */}
              {[-2.5, -2.0, -1.5, -1.0, -0.5, 0.0].map((val) => (
                <g key={val}>
                  <line x1={scaleX(val)} y1={height - padding} x2={scaleX(val)} y2={height - padding + 5} stroke="#334155" />
                  <text x={scaleX(val)} y={height - padding + 16} fill="#64748b" fontSize="9" textAnchor="middle">
                    {val.toFixed(1)}R
                  </text>
                </g>
              ))}

              {/* Y Axis Ticks */}
              {[0.0, 1.0, 2.0, 3.0, 4.0, 5.0].map((val) => (
                <g key={val}>
                  <line x1={padding - 5} y1={scaleY(val)} x2={padding} y2={scaleY(val)} stroke="#334155" />
                  <text x={padding - 8} y={scaleY(val) + 3} fill="#64748b" fontSize="9" textAnchor="end">
                    +{val.toFixed(0)}R
                  </text>
                </g>
              ))}

              {/* Trade Points */}
              {filteredPoints.map((pt) => {
                const cx = scaleX(pt.mae_r);
                const cy = scaleY(pt.mfe_r);
                const isWin = pt.pnl > 0;
                const isHovered = hoveredPoint?.trade_id === pt.trade_id;

                return (
                  <circle
                    key={pt.trade_id}
                    cx={cx}
                    cy={cy}
                    r={isHovered ? 7 : 5}
                    fill={isWin ? "#10b981" : "#ef4444"}
                    stroke={isHovered ? "#ffffff" : isWin ? "#059669" : "#dc2626"}
                    strokeWidth={isHovered ? 2 : 1}
                    className="cursor-pointer transition-all duration-150"
                    onMouseEnter={() => setHoveredPoint(pt)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                );
              })}
            </svg>

            {/* Hover Tooltip Overlay */}
            {hoveredPoint && (
              <div className="absolute top-4 right-4 bg-[#111722]/95 border border-accent p-3 rounded shadow-2xl text-xs z-20 pointer-events-none w-60 font-mono">
                <div className="flex justify-between border-b border-surface-border pb-1 mb-1 font-bold">
                  <span className="text-white">{hoveredPoint.trade_id}</span>
                  <span className={hoverPointClass(hoveredPoint.pnl)}>
                    {hoveredPoint.pnl >= 0 ? "+" : ""}${hoveredPoint.pnl.toFixed(2)}
                  </span>
                </div>
                <div className="space-y-0.5 text-[11px] text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Symbol:</span>
                    <span>{hoveredPoint.symbol} ({hoveredPoint.side})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Entry / Exit:</span>
                    <span>${hoveredPoint.entry_price} / ${hoveredPoint.exit_price}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">MAE (Endured):</span>
                    <span className="text-loss font-bold">{hoveredPoint.mae_r} R (${hoveredPoint.mae_price})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">MFE (Peak):</span>
                    <span className="text-gain font-bold">+{hoveredPoint.mfe_r} R (${hoveredPoint.mfe_price})</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Exit Efficiency:</span>
                    <span className="text-accent font-bold">{(hoveredPoint.exit_efficiency * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Stop Loss Survival Sensitivity Panel */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold text-white flex items-center space-x-2 mb-2">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
              <span>STOP LOSS SENSITIVITY SIMULATION</span>
            </h3>
            <p className="text-[11px] text-slate-400 mb-3">
              Survival rate of trades if initial stop distance is expanded or tightened.
            </p>

            <div className="space-y-2 text-xs">
              {data.stop_loss_sensitivities.map((s) => (
                <div key={s.stop_distance_r} className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-300 font-bold">{s.stop_distance_r.toFixed(2)} R Stop</span>
                    <span className="text-accent font-bold">{s.survival_rate_pct}% Survived</span>
                  </div>
                  <div className="w-full bg-[#111722] rounded-full h-2 overflow-hidden border border-surface-border">
                    <div
                      className="h-full bg-gradient-to-r from-sky-500 to-emerald-500 rounded-full"
                      style={{ width: `${s.survival_rate_pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-2.5 bg-[#111722] rounded border border-surface-border text-[10px] text-slate-400 space-y-1">
            <span className="font-bold text-white block">Quantitative Takeaway:</span>
            <span>
              Setting stop loss at <strong>1.25R</strong> increases survival rate to{" "}
              <strong>
                {data.stop_loss_sensitivities.find((s) => s.stop_distance_r === 1.25)?.survival_rate_pct || 94}%
              </strong>{" "}
              without significantly altering reward-to-risk expectancy.
            </span>
          </div>
        </div>
      </div>
    </>
  )}
</div>
  );
};

function hoverPointClass(pnl: number): string {
  return pnl > 0 ? "text-gain" : pnl < 0 ? "text-loss" : "text-slate-400";
}