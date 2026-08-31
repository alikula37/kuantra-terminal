import React, { useState } from "react";
import { TrendingUp, Plus } from "lucide-react";

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
  const [hoveredPoint, setHoveredPoint] = useState<EquityCurvePoint | null>(null);

  if (loading) {
    return (
      <div className="bg-[#111722] p-4 rounded-lg border border-surface-border animate-pulse h-80 flex flex-col justify-center items-center text-slate-500 font-mono text-xs">
        <span>Kümülatif Kasa Eğrisi Yükleniyor...</span>
      </div>
    );
  }

  const isRealHistory = series && series.length > 0 && !(series.length === 1 && series[0].symbol === "INITIAL");

  if (!isRealHistory) {
    return (
      <div className="bg-[#111722] p-6 rounded-lg border border-surface-border flex flex-col justify-center items-center h-80 text-center select-none font-mono">
        <div className="w-12 h-12 rounded-full bg-[#162032] flex items-center justify-center mb-3 border border-surface-border">
          <TrendingUp className="w-6 h-6 text-accent" />
        </div>
        <h4 className="text-sm font-bold text-white mb-1.5 uppercase tracking-wide">
          Kümülatif Bakiye Eğrisi Bekleniyor
        </h4>
        <p className="text-xs text-slate-400 max-w-md mb-4 leading-relaxed">
          Henüz kapatılmış bir işlem bulunmuyor. İlk işleminizi kaydettiğinizde kümülatif büyüme ve drawdown eğrisi burada dinamik olarak çizilecektir.
        </p>
        {onOpenNewTrade && (
          <button
            onClick={onOpenNewTrade}
            className="flex items-center space-x-1.5 px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs transition shadow-md cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Yeni İşlem Girişi</span>
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

  const getYEquity = (val: number) => {
    return padding.top + equityHeight - ((val - yEquityMin) / (yEquityMax - yEquityMin)) * equityHeight;
  };

  const getYDd = (val: number) => {
    const top = padding.top + equityHeight + gap;
    return top + (Math.abs(val) / Math.abs(minDd || 1.0)) * ddHeight;
  };

  // Build SVG Paths
  const equityPoints = series.map((p, i) => `${getX(i)},${getYEquity(p.equity)}`).join(" ");
  const equityAreaPath = `${getX(0)},${getYEquity(yEquityMin)} ` + equityPoints + ` ${getX(series.length - 1)},${getYEquity(yEquityMin)}`;

  const ddZeroY = padding.top + equityHeight + gap;
  const ddPoints = series.map((p, i) => `${getX(i)},${getYDd(p.drawdown_pct)}`).join(" ");
  const ddAreaPath = `${getX(0)},${ddZeroY} ` + ddPoints + ` ${getX(series.length - 1)},${ddZeroY}`;

  const currentPoint = hoveredPoint || series[series.length - 1];

  return (
    <div className="bg-[#111722] p-4 rounded-lg border border-surface-border flex flex-col h-full select-none font-mono">
      <div className="flex items-center justify-between pb-2 border-b border-surface-border">
        <div className="flex items-center space-x-2">
          <TrendingUp className="w-4 h-4 text-accent" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">KÜMÜLATİF KASA & SU ALTI DRAWDOWN</span>
        </div>
        <div className="flex items-center space-x-3 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="text-[10px] text-slate-500">KASA:</span>
            <span className="font-bold text-white">${currentPoint.equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="text-[10px] text-slate-500">DD:</span>
            <span className="font-bold text-loss">{currentPoint.drawdown_pct.toFixed(2)}%</span>
          </div>
        </div>
      </div>

      <div className="relative flex-1 mt-2 flex items-center justify-center">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full max-h-64 overflow-visible"
          onMouseLeave={() => setHoveredPoint(null)}
        >
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#00e5ff" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.0" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left + innerWidth}
            y2={padding.top}
            stroke="#1e293b"
            strokeDasharray="3 3"
          />
          <line
            x1={padding.left}
            y1={padding.top + equityHeight / 2}
            x2={padding.left + innerWidth}
            y2={padding.top + equityHeight / 2}
            stroke="#1e293b"
            strokeDasharray="3 3"
          />
          <line
            x1={padding.left}
            y1={padding.top + equityHeight}
            x2={padding.left + innerWidth}
            y2={padding.top + equityHeight}
            stroke="#334155"
          />

          {/* Equity Y-Labels */}
          <text x={padding.left - 8} y={padding.top + 4} fill="#64748b" fontSize="9" textAnchor="end">
            ${(yEquityMax / 1000).toFixed(1)}k
          </text>
          <text x={padding.left - 8} y={padding.top + equityHeight / 2 + 3} fill="#64748b" fontSize="9" textAnchor="end">
            ${((yEquityMax + yEquityMin) / 2000).toFixed(1)}k
          </text>
          <text x={padding.left - 8} y={padding.top + equityHeight} fill="#64748b" fontSize="9" textAnchor="end">
            ${(yEquityMin / 1000).toFixed(1)}k
          </text>

          {/* Equity Area & Line */}
          <polygon points={equityAreaPath} fill="url(#equityGradient)" />
          <polyline
            points={equityPoints}
            fill="none"
            stroke="#00e5ff"
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
            stroke="#475569"
            strokeWidth="1"
          />
          <polygon points={ddAreaPath} fill="url(#ddGradient)" />
          <polyline
            points={ddPoints}
            fill="none"
            stroke="#ef4444"
            strokeWidth="1.5"
            strokeLinecap="round"
          />

          {/* Drawdown Y-Labels */}
          <text x={padding.left - 8} y={ddZeroY + 4} fill="#64748b" fontSize="9" textAnchor="end">
            0%
          </text>
          <text x={padding.left - 8} y={ddZeroY + ddHeight} fill="#ef4444" fontSize="9" textAnchor="end">
            {minDd.toFixed(1)}%
          </text>

          {/* Interactive Hover Circles and Vertical Guide */}
          {series.map((p, i) => {
            const x = getX(i);
            const y = getYEquity(p.equity);
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
                      stroke="#00e5ff"
                      strokeWidth="1"
                      strokeDasharray="2 2"
                    />
                    <circle cx={x} cy={y} r="4" fill="#00e5ff" stroke="#0d121c" strokeWidth="2" />
                    <circle cx={x} cy={getYDd(p.drawdown_pct)} r="3" fill="#ef4444" />
                  </>
                )}
              </g>
            );
          })}

          {/* X-Axis Date Labels */}
          {series.length > 0 && (
            <>
              <text x={padding.left} y={height - 8} fill="#64748b" fontSize="9" textAnchor="start">
                {series[0].date}
              </text>
              {series.length > 2 && (
                <text x={padding.left + innerWidth / 2} y={height - 8} fill="#64748b" fontSize="9" textAnchor="middle">
                  {series[Math.floor(series.length / 2)].date}
                </text>
              )}
              <text x={padding.left + innerWidth} y={height - 8} fill="#64748b" fontSize="9" textAnchor="end">
                {series[series.length - 1].date}
              </text>
            </>
          )}
        </svg>
      </div>
    </div>
  );
};
