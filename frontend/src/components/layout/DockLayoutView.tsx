import React, { useRef, useState } from "react";
import DockLayout, { LayoutData } from "rc-dock";
import "rc-dock/dist/rc-dock-dark.css";
import { TradingViewChart } from "../TradingViewChart";
import { PsychologyView } from "../PsychologyView";
import { AiCoachPanel } from "../AiCoachPanel";
import { MaeMfeVisualizer } from "../MaeMfeVisualizer";
import { PropFirmShield } from "../PropFirmShield";
import { PivotGrid } from "../PivotGrid";
import { Layout, Save, RotateCcw, MonitorUp } from "lucide-react";

interface DockLayoutViewProps {
  onPopoutWindow?: (panelId: string) => void;
}

export const DockLayoutView: React.FC<DockLayoutViewProps> = ({ onPopoutWindow }) => {
  const dockRef = useRef<DockLayout>(null);
  const [activePreset, setActivePreset] = useState<string>("default");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const defaultLayout: LayoutData = {
    dockbox: {
      mode: "horizontal",
      children: [
        {
          mode: "vertical",
          size: 650,
          children: [
            {
              tabs: [
                {
                  id: "chart_tab",
                  title: "Live Terminal Chart",
                  closable: false,
                  content: (
                    <div className="h-full w-full bg-[#0b0e14]">
                      <TradingViewChart />
                    </div>
                  ),
                },
                {
                  id: "pivot_tab",
                  title: "Dynamic Pivot Grid",
                  content: <PivotGrid />,
                },
              ],
            },
            {
              size: 280,
              tabs: [
                {
                  id: "prop_shield_tab",
                  title: "Prop Firm Shield",
                  content: <PropFirmShield />,
                },
                {
                  id: "mae_mfe_tab",
                  title: "MAE / MFE Excursion",
                  content: <MaeMfeVisualizer />,
                },
              ],
            },
          ],
        },
        {
          mode: "vertical",
          size: 450,
          children: [
            {
              tabs: [
                {
                  id: "psychology_tab",
                  title: "Psychology & Tilt Shield",
                  content: <PsychologyView />,
                },
                {
                  id: "ai_coach_tab",
                  title: "AI Trade Auditor",
                  content: <AiCoachPanel />,
                },
              ],
            },
          ],
        },
      ],
    },
  };



  const loadPresetLayout = (presetName: string) => {
    setActivePreset(presetName);
    fetch(`http://127.0.0.1:8000/api/v1/workspace/layout/${encodeURIComponent(presetName)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.layout_data && dockRef.current) {
          dockRef.current.loadLayout(data.layout_data);
          setSaveStatus(`Loaded ${presetName}`);
        } else {
          resetToDefault();
        }
      })
      .catch(() => {
        resetToDefault();
      });
  };

  const handleSaveLayout = () => {
    if (!dockRef.current) return;
    const saved = dockRef.current.saveLayout();
    fetch("http://127.0.0.1:8000/api/v1/workspace/layout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preset_name: activePreset,
        layout_data: saved,
      }),
    })
      .then(() => {
        setSaveStatus("Workspace layout saved!");
        setTimeout(() => setSaveStatus(null), 2500);
      })
      .catch(() => {
        setSaveStatus("Error saving layout");
      });
  };

  const resetToDefault = () => {
    if (dockRef.current) {
      dockRef.current.loadLayout(defaultLayout);
      setSaveStatus("Reset to default layout");
      setTimeout(() => setSaveStatus(null), 2000);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-hidden select-none font-mono">
      {/* Workspace Control Strip */}
      <div className="h-10 border-b border-surface-border bg-[#0d121c] px-4 flex items-center justify-between text-xs">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 text-accent font-bold">
            <Layout className="w-3.5 h-3.5" />
            <span className="text-[11px] uppercase tracking-wider">DOCKING WORKSPACE MANAGER</span>
          </div>

          <div className="h-4 w-[1px] bg-surface-border" />

          {/* Preset Selector */}
          <div className="flex items-center space-x-1.5 text-[11px]">
            <span className="text-slate-400">Preset:</span>
            {["default", "Day Trader", "AI Auditor Focus", "Multi-Chart Grid"].map((p) => (
              <button
                key={p}
                onClick={() => loadPresetLayout(p)}
                className={`px-2.5 py-0.5 rounded text-[10px] font-semibold transition ${
                  activePreset === p
                    ? "bg-accent/20 text-accent border border-accent/40"
                    : "bg-[#111722] text-slate-400 hover:text-slate-200 border border-surface-border"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {saveStatus && (
            <span className="text-[10px] text-gain bg-gain/10 border border-gain/30 px-2 py-0.5 rounded animate-pulse">
              {saveStatus}
            </span>
          )}

          <button
            onClick={handleSaveLayout}
            className="flex items-center space-x-1 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-[10px] font-bold px-2.5 py-1 rounded transition"
          >
            <Save className="w-3 h-3 text-gain" />
            <span>SAVE LAYOUT</span>
          </button>

          <button
            onClick={resetToDefault}
            className="flex items-center space-x-1 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-400 hover:text-slate-200 text-[10px] font-bold px-2.5 py-1 rounded transition"
          >
            <RotateCcw className="w-3 h-3" />
            <span>RESET</span>
          </button>

          {onPopoutWindow && (
            <button
              onClick={() => onPopoutWindow("chart")}
              className="flex items-center space-x-1 bg-accent/15 hover:bg-accent/30 border border-accent/40 text-accent text-[10px] font-bold px-2.5 py-1 rounded transition"
            >
              <MonitorUp className="w-3 h-3" />
              <span>POP-OUT MONITORS</span>
            </button>
          )}
        </div>
      </div>

      {/* Docking Grid Canvas */}
      <div className="flex-1 relative overflow-hidden bg-[#090d14]">
        <DockLayout
          ref={dockRef}
          defaultLayout={defaultLayout}
          style={{ position: "absolute", left: 0, top: 0, right: 0, bottom: 0 }}
        />
      </div>
    </div>
  );
};