
import React from "react";
import { 
  LayoutDashboard, 
  BookOpen, 
  BarChart3, 
  Crosshair, 
  ShieldCheck, 
  Layers, 
  PlayCircle, 
  BookmarkCheck, 
  GitCommit, 
  Brain, 
  Bot, 
  Sliders, 
  Database, 
  Cpu, 
  Layout, 
  Zap, 
  Activity, 
  Users, 
  Flame, 
  Terminal, 
  Share2, 
  Copy, 
  Smartphone, 
  Code, 
  ArrowRightLeft, 
  AlignJustify, 
  HeartPulse, 
  Puzzle,
  LineChart
} from "lucide-react";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { ExtensionSlot } from "./plugins/ExtensionSlot";

export type NavTab = 
  | "dashboard" 
  | "biometrics_studio" 
  | "fix_studio" 
  | "dex_arbitrage" 
  | "mcp_explorer" 
  | "reverse_skill" 
  | "docking" 
  | "virtual_journal" 
  | "journal" 
  | "charts"
  | "orderflow" 
  | "fix_dma" 
  | "p2p_mesh" 
  | "copy_trading" 
  | "mobile_companion" 
  | "replay" 
  | "playbook" 
  | "drift" 
  | "psychology" 
  | "biometrics" 
  | "ai_coach" 
  | "swarm" 
  | "analytics" 
  | "mae_mfe" 
  | "prop_shield" 
  | "pivot_grid" 
  | "modstore" 
  | "settings";

interface SidebarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const CORE_NAV_ITEMS: { id: NavTab; label: string; icon: React.ComponentType<any> }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "journal", label: "İşlem Günlüğü (Journal)", icon: BookOpen },
  { id: "charts", label: "Temel Grafik (Charts)", icon: LineChart },
  { id: "mae_mfe", label: "MAE / MFE Risk Analizi", icon: Crosshair },
  { id: "modstore", label: "ModStore & Eklenti Merkezi 🧩", icon: Puzzle },
  { id: "settings", label: "Ayarlar", icon: Sliders },
];

export const PLUGIN_NAV_ITEMS: { id: NavTab; label: string; icon: React.ComponentType<any>; pluginId: string }[] = [
  { id: "biometrics_studio", label: "Hardware Biometrics Studio", icon: HeartPulse, pluginId: "plugin_biometrics" },
  { id: "fix_studio", label: "L2/L3 DOM & FIX Studio", icon: AlignJustify, pluginId: "plugin_fix_dma" },
  { id: "dex_arbitrage", label: "DEX Arbitrage & Flash Loans", icon: ArrowRightLeft, pluginId: "plugin_dex_arbitrage" },
  { id: "mcp_explorer", label: "Financial MCP Gateway", icon: Database, pluginId: "plugin_mcp_gateway" },
  { id: "reverse_skill", label: "Reverse-Skill Studio", icon: Code, pluginId: "plugin_reverse_skill" },
  { id: "orderflow", label: "Order Flow Footprint", icon: Flame, pluginId: "plugin_orderflow" },
  { id: "fix_dma", label: "CME QuickFIX DMA", icon: Terminal, pluginId: "plugin_fix_dma" },
  { id: "mobile_companion", label: "Mobile Companion & Passkey", icon: Smartphone, pluginId: "plugin_mobile_sync" },
  { id: "p2p_mesh", label: "Encrypted P2P Mesh", icon: Share2, pluginId: "plugin_p2p_mesh" },
  { id: "copy_trading", label: "Multi-Account Copy", icon: Copy, pluginId: "plugin_p2p_copy" },
  { id: "docking", label: "Docking Workspace", icon: Layout, pluginId: "plugin_docking" },
  { id: "virtual_journal", label: "60 FPS Virtual Journal", icon: Zap, pluginId: "plugin_virtual_journal" },
  { id: "replay", label: "Trade Replay", icon: PlayCircle, pluginId: "plugin_replay" },
  { id: "playbook", label: "Strategy Playbook", icon: BookmarkCheck, pluginId: "plugin_quant_shield" },
  { id: "drift", label: "Execution Drift", icon: GitCommit, pluginId: "plugin_quant_shield" },
  { id: "psychology", label: "Psychology & Tilt", icon: Brain, pluginId: "plugin_biometrics" },
  { id: "biometrics", label: "Biometric Wearable", icon: Activity, pluginId: "plugin_biometrics" },
  { id: "ai_coach", label: "AI Trade Auditor", icon: Bot, pluginId: "plugin_ai_swarm" },
  { id: "swarm", label: "Multi-Agent Swarm", icon: Users, pluginId: "plugin_ai_swarm" },
  { id: "analytics", label: "Quant Scorecard", icon: BarChart3, pluginId: "plugin_quant_shield" },
  { id: "prop_shield", label: "Prop Firm Shield", icon: ShieldCheck, pluginId: "plugin_quant_shield" },
  { id: "pivot_grid", label: "Dynamic Pivot Grid", icon: Layers, pluginId: "plugin_duckdb" },
];

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const { isPluginActive, activePlugins, isLiteMode } = usePluginRegistry();

  const visibleNavItems = [
    ...CORE_NAV_ITEMS,
    ...PLUGIN_NAV_ITEMS.filter((item) => isPluginActive(item.pluginId))
  ];

  return (
    <aside className="w-56 bg-[#0d121c] border-r border-surface-border flex flex-col justify-between select-none shrink-0">
      <div className="p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold flex items-center justify-between">
          <span>{isLiteMode ? "LITE ÇEKİRDEK" : "AKTİF MODÜLLER"}</span>
          <span className="text-accent font-bold">
            {isLiteMode ? "0 Eklenti" : `${activePlugins.length} Eklenti`}
          </span>
        </div>
        {visibleNavItems.map((item) => {
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
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}

        {/* Dynamic Extension Slot for 3rd-party/ModStore plugins */}
        <ExtensionSlot slot="sidebar" />
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
              <Layers className={`w-3 h-3 ${isLiteMode ? "text-slate-500" : "text-accent"}`} />
              <span>DuckDB (OLAP)</span>
            </span>
            <span className={`text-[10px] font-semibold ${isLiteMode ? "text-slate-500" : "text-accent"}`}>
              {isLiteMode ? "ON DEMAND" : "COLUMNAR"}
            </span>
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