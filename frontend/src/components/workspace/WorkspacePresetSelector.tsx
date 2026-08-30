import React from "react";
import { Layout, MonitorUp, RotateCcw, Check } from "lucide-react";

interface WorkspacePresetSelectorProps {
  currentPreset: string;
  onSelectPreset: (preset: string) => void;
  onPopoutAll?: () => void;
  onResetLayout?: () => void;
}

export const WorkspacePresetSelector: React.FC<WorkspacePresetSelectorProps> = ({
  currentPreset,
  onSelectPreset,
  onPopoutAll,
  onResetLayout,
}) => {
  const presets = [
    { id: "day_trader", label: "Day Trader", desc: "Chart, Order Flow & Live Positions" },
    { id: "docking", label: "Docking Grid", desc: "rc-dock Drag & Drop Multi-Split Grid" },
    { id: "ai_focus", label: "AI Auditor Focus", desc: "Cognitive Auditor & Tilt Guardian" },
    { id: "quant_lab", label: "Quant Analytics", desc: "Pivot Grid, MAE/MFE & Prop Shield" },
  ];

  return (
    <div className="bg-[#0d121c] border-b border-surface-border px-4 py-1.5 flex items-center justify-between font-mono text-xs select-none">
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-1.5 text-accent font-bold">
          <Layout className="w-3.5 h-3.5" />
          <span className="text-[10px] uppercase tracking-wider">WORKSPACE PRESETS:</span>
        </div>

        <div className="flex items-center space-x-1">
          {presets.map((p) => {
            const isActive = currentPreset === p.id;
            return (
              <button
                key={p.id}
                onClick={() => onSelectPreset(p.id)}
                className={`px-2.5 py-1 rounded text-[10px] font-semibold transition flex items-center space-x-1.5 ${
                  isActive
                    ? "bg-accent/20 text-accent border border-accent/40 shadow-xs font-bold"
                    : "bg-[#111722] text-slate-400 hover:text-slate-200 border border-surface-border"
                }`}
                title={p.desc}
              >
                {isActive && <Check className="w-2.5 h-2.5" />}
                <span>{p.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center space-x-2 text-[10px]">
        {onResetLayout && (
          <button
            onClick={onResetLayout}
            className="flex items-center space-x-1 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-400 hover:text-white px-2 py-0.5 rounded transition"
          >
            <RotateCcw className="w-2.5 h-2.5" />
            <span>RESET WORKSPACE</span>
          </button>
        )}

        {onPopoutAll && (
          <button
            onClick={onPopoutAll}
            className="flex items-center space-x-1 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent font-bold px-2.5 py-0.5 rounded transition"
          >
            <MonitorUp className="w-2.5 h-2.5" />
            <span>POP-OUT MONITORS</span>
          </button>
        )}
      </div>
    </div>
  );
};