import React, { useState } from "react";
import { TrendingUp, Plus } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";

export interface EquityCurvePoint {
  timestamp: number;
  date: string;
  equity: number;
  drawdown_pct: number;
  trade_pnl: number;
  cumulative_pnl: number;
  symbol?: string;
}

interface EquityCurveChartProps {
  series: EquityCurvePoint[];
  loading?: boolean;
  onOpenNewTrade?: () => void;
}

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  series,
  loading,
  onOpenNewTrade,
}) => {
  const { t } = useTranslation();
  const [hoveredPoint, setHoveredPoint] = useState<EquityCurvePoint | null>(null);

  if (loading) {
    return (
      <div className="bg-elevated p-4 rounded-lg border border-surface-border animate-pulse h-80 flex flex-col justify-center items-center text-slate-500 font-mono text-xs">
        <span>{t("equity_curve.loading")}</span>
      </div>
    );
  }

  const isRealHistory = series && series.length > 0 && !(series.length === 1 && series[0].symbol === "INITIAL");

  if (!isRealHistory) {
    return (
      <div className="bg-elevated p-6 rounded-lg border border-surface-border flex flex-col justify-center items-center h-80 text-center select-none font-mono">
        <div className="w-12 h-12 rounded-full bg-soft flex items-center justify-center mb-3 border border-surface-border">
          <TrendingUp className="w-6 h-6 text-accent" />
        </div>
        <h4 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
          {t("equity_curve.waiting_title")}
        </h4>
        <p className="text-xs text-slate-400 max-w-md mb-4 leading-relaxed">
          {t("equity_curve.waiting_desc")}
        </p>
        {onOpenNewTrade && (
          <button
            onClick={onOpenNewTrade}
            className="flex items-center space-x-1.5 px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition shadow-md cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>{t("equity_curve.new_trade_action")}</span>
          </button>
        )}
      </div>
    );
  }

  // Calculate SVG Dimensions & Scales
  const width = 600;
  const height = 240;
  const padding = { top: 20, right: 30, bottom: 45, left: 60 };

  const innerWidth = width - padding.left - padding.right;
  const equityHeight = 130;
  const ddHeight = 45;
  const gap = 15;

  const minEquity = Math.min(...series.map((p) => p.equity));
  const maxEquity = Math.max(...series.map((p) => p.equity));
  const equityRange = maxEquity === minEquity ? 1000 : maxEquity - minEquity;
  const yEquityMin = minEquity - equityRange * 0.05;
  const yEquityMax = maxEquity + equityRange * 0.05;

  const minDd = Math.min(...series.map((p) => p.drawdown_pct), -1.0);

  const getX = (index: number) => {
    if (series.length <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (series.length - 1)) * innerWidth;
  };

  const getEquityY = (val: number) => {
    const norm = (val - yEquityMin) / (yEquityMax - yEquityMin);
    return padding.top + equityHeight - norm * equityHeight;
  };

  const getDdY = (val: number) => {
    const norm = Math.abs(val) / Math.abs(minDd || 1.0);
    return padding.top + equityHeight + gap + norm * ddHeight;
  };

  const ddZeroY = padding.top + equityHeight + gap;

  // Build SVG Paths
  const equityPoints = series.map((p, idx) => `${getX(idx)},${getEquityY(p.equity)}`).join(" ");
  const equityAreaPath = `${getX(0)},${padding.top + equityHeight} ` + equityPoints + ` ${getX(series.length - 1)},${padding.top + equityHeight}`;

  const ddPoints = series.map((p, idx) => `${getX(idx)},${getDdY(p.drawdown_pct)}`).join(" ");
  const ddAreaPath = `${getX(0)},${ddZeroY} ` + ddPoints + ` ${getX(series.length - 1)},${ddZeroY}`;

  const currentPoint = hoveredPoint || series[series.length - 1];

  return (
    <div className="bg-elevated p-4 rounded-lg border border-surface-border flex flex-col h-full select-none font-mono">
      <div className="flex items-center justify-between pb-2 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <TrendingUp className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            {t("equity_curve.chart_title")}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="text-[10px] text-slate-500">{t("equity_curve.equity_growth").toUpperCase()}:</span>
            <span className="font-bold text-white">${currentPoint.equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="text-[10px] text-slate-500">{t("equity_curve.drawdown").toUpperCase()}:</span>
            <span className="font-bold text-loss">{currentPoint.drawdown_pct.toFixed(2)}%</span>
          </div>
        </div>
      </div>

      <div className="relative flex-1 mt-2 flex items-center justify-center">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full overflow-visible"
          onMouseLeave={() => setHoveredPoint(null)}
        >
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.35" />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-loss)" stopOpacity="0.0" />
              <stop offset="100%" stopColor="var(--color-loss)" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left + innerWidth}
            y2={padding.top}
            stroke="var(--border-color)"
            strokeDasharray="3 3"
          />
          <line
            x1={padding.left}
            y1={padding.top + equityHeight / 2}
            x2={padding.left + innerWidth}
            y2={padding.top + equityHeight / 2}
            stroke="var(--border-color)"
            strokeDasharray="3 3"
          />
          <line
            x1={padding.left}
            y1={padding.top + equityHeight}
            x2={padding.left + innerWidth}
            y2={padding.top + equityHeight}
            stroke="var(--border-color)"
          />

          {/* Equity Y-Labels */}
          <text x={padding.left - 8} y={padding.top + 4} fill="var(--text-muted)" fontSize="9" textAnchor="end">
            ${(yEquityMax / 1000).toFixed(1)}k
          </text>
          <text x={padding.left - 8} y={padding.top + equityHeight / 2 + 3} fill="var(--text-muted)" fontSize="9" textAnchor="end">
            ${((yEquityMax + yEquityMin) / 2000).toFixed(1)}k
          </text>
          <text x={padding.left - 8} y={padding.top + equityHeight} fill="var(--text-muted)" fontSize="9" textAnchor="end">
            ${(yEquityMin / 1000).toFixed(1)}k
          </text>

          {/* Equity Area & Line */}
          <polygon points={equityAreaPath} fill="url(#equityGradient)" />
          <polyline
            points={equityPoints}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Drawdown Sub-Pane */}
          <line
            x1={padding.left}
            y1={ddZeroY}
            x2={padding.left + innerWidth}
            y2={ddZeroY}
            stroke="var(--text-muted)"
            strokeWidth="1"
          />
          <polygon points={ddAreaPath} fill="url(#ddGradient)" />
          <polyline
            points={ddPoints}
            fill="none"
            stroke="var(--color-loss)"
            strokeWidth="1.5"
            strokeLinecap="round"
          />

          {/* Drawdown Y-Labels */}
          <text x={padding.left - 8} y={ddZeroY + 4} fill="var(--text-muted)" fontSize="9" textAnchor="end">
            0%
          </text>
          <text x={padding.left - 8} y={ddZeroY + ddHeight} fill="var(--color-loss)" fontSize="9" textAnchor="end">
            {minDd.toFixed(1)}%
          </text>

          {/* Interactive Hover Circles and Vertical Guide */}
          {series.map((p, i) => {
            const x = getX(i);
            const y = getEquityY(p.equity);
            return (
              <g key={i} className="cursor-pointer" onMouseEnter={() => setHoveredPoint(p)}>
                <rect
                  x={x - 8}
                  y={padding.top}
                  width="16"
                  height={height - padding.top}
                  fill="transparent"
                />
                {hoveredPoint === p && (
                  <>
                    <line
                      x1={x}
                      y1={padding.top}
                      x2={x}
                      y2={ddZeroY + ddHeight}
                      stroke="var(--color-accent)"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <circle cx={x} cy={y} r="4" fill="#00e5ff" stroke="#0d121c" strokeWidth="2" />
                    <circle cx={x} cy={getDdY(p.drawdown_pct)} r="3" fill="var(--color-loss)" />
                  </>
                )}
              </g>
            );
          })}

          {/* X-Axis Date Labels */}
          {series.length > 0 && (
            <>
              <text x={padding.left} y={height - 8} fill="var(--text-muted)" fontSize="9" textAnchor="start">
                {series[0].date}
              </text>
              {series.length > 2 && (
                <text x={padding.left + innerWidth / 2} y={height - 8} fill="var(--text-muted)" fontSize="9" textAnchor="middle">
                  {series[Math.floor(series.length / 2)].date}
                </text>
              )}
              <text x={padding.left + innerWidth} y={height - 8} fill="var(--text-muted)" fontSize="9" textAnchor="end">
                {series[series.length - 1].date}
              </text>
            </>
          )}
        </svg>
      </div>
    </div>
  );
};
