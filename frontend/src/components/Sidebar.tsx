import React from "react";
import { LayoutDashboard, BookOpen, BarChart3, Crosshair, ShieldCheck, Layers, PlayCircle, BookmarkCheck, GitCommit, Brain, Bot, Sliders, Database, Cpu } from "lucide-react";

export type NavTab = "dashboard" | "journal" | "replay" | "playbook" | "drift" | "psychology" | "ai_coach" | "analytics" | "mae_mfe" | "prop_shield" | "pivot_grid" | "settings";

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "journal", label: "Journal", icon: BookOpen },
    { id: "replay", label: "Trade Replay", icon: PlayCircle },
    { id: "playbook", label: "Strategy Playbook", icon: BookmarkCheck },
    { id: "drift", label: "Execution Drift", icon: GitCommit },
    { id: "psychology", label: "Psychology & Tilt", icon: Brain },
    { id: "ai_coach", label: "AI Trade Auditor", icon: Bot },
    { id: "analytics", label: "Quant Scorecard", icon: BarChart3 },
    { id: "mae_mfe", label: "MAE / MFE Visualizer", icon: Crosshair },
    { id: "prop_shield", label: "Prop Firm Shield", icon: ShieldCheck },
    { id: "pivot_grid", label: "Dynamic Pivot Grid", icon: Layers },
    { id: "settings", label: "Settings", icon: Sliders },
  ];

  return (
    <aside className="w-56 bg-[#0d121c] border-r border-surface-border flex flex-col justify-between select-none">
      <div className="p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
          Terminal Modules
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id as NavTab)}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded text-xs font-medium transition ${
                isActive
                  ? "bg-accent/15 text-accent border border-accent/30 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-[#111722]"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-accent" : "text-slate-400"}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div className="p-3 border-t border-surface-border space-y-2 bg-[#090d14]/60">
        <div className="px-1 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
          Engine Diagnostics
        </div>
        <div className="space-y-1.5 text-[11px] font-mono">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center space-x-1.5">
              <Database className="w-3 h-3 text-gain" />
              <span>SQLite (OLTP)</span>
            </span>
            <span className="text-gain text-[10px] font-semibold">WAL ON</span>
          </div>

          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center space-x-1.5">
              <Layers className="w-3 h-3 text-accent" />
              <span>DuckDB (OLAP)</span>
            </span>
            <span className="text-accent text-[10px] font-semibold">COLUMNAR</span>
          </div>

          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center space-x-1.5">
              <Cpu className="w-3 h-3 text-purple-400" />
              <span>FastAPI Sidecar</span>
            </span>
            <span className="text-purple-400 text-[10px] font-semibold">ASYNCIO</span>
          </div>
        </div>
      </div>
    </aside>
  );
};