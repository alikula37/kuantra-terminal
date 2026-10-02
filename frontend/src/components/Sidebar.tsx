
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
import { useTranslation } from "../context/I18nContext";
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

export const CORE_NAV_ITEMS: { id: NavTab; icon: React.ComponentType<any> }[] = [
  { id: "dashboard", icon: LayoutDashboard },
  { id: "journal", icon: BookOpen },
  { id: "charts", icon: LineChart },
  { id: "mae_mfe", icon: Crosshair },
  { id: "modstore", icon: Puzzle },
  { id: "settings", icon: Sliders },
];

export const PLUGIN_NAV_ITEMS: { id: NavTab; icon: React.ComponentType<any>; pluginId: string }[] = [
  { id: "biometrics_studio", icon: HeartPulse, pluginId: "plugin_biometrics" },
  { id: "fix_studio", icon: AlignJustify, pluginId: "plugin_fix_dma" },
  { id: "dex_arbitrage", icon: ArrowRightLeft, pluginId: "plugin_dex_arbitrage" },
  { id: "mcp_explorer", icon: Database, pluginId: "plugin_mcp_gateway" },
  { id: "reverse_skill", icon: Code, pluginId: "plugin_reverse_skill" },
  { id: "orderflow", icon: Flame, pluginId: "plugin_orderflow" },
  { id: "fix_dma", icon: Terminal, pluginId: "plugin_fix_dma" },
  { id: "mobile_companion", icon: Smartphone, pluginId: "plugin_mobile_sync" },
  { id: "p2p_mesh", icon: Share2, pluginId: "plugin_p2p_mesh" },
  { id: "copy_trading", icon: Copy, pluginId: "plugin_p2p_copy" },
  { id: "docking", icon: Layout, pluginId: "plugin_docking" },
  { id: "virtual_journal", icon: Zap, pluginId: "plugin_virtual_journal" },
  { id: "replay", icon: PlayCircle, pluginId: "plugin_replay" },
  { id: "playbook", icon: BookmarkCheck, pluginId: "plugin_quant_shield" },
  { id: "drift", icon: GitCommit, pluginId: "plugin_quant_shield" },
  { id: "psychology", icon: Brain, pluginId: "plugin_biometrics" },
  { id: "biometrics", icon: Activity, pluginId: "plugin_biometrics" },
  { id: "ai_coach", icon: Bot, pluginId: "plugin_ai_swarm" },
  { id: "swarm", icon: Users, pluginId: "plugin_ai_swarm" },
  { id: "analytics", icon: BarChart3, pluginId: "plugin_quant_shield" },
  { id: "prop_shield", icon: ShieldCheck, pluginId: "plugin_quant_shield" },
  { id: "pivot_grid", icon: Layers, pluginId: "plugin_duckdb" },
];

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const { isPluginActive, activePlugins, isLiteMode } = usePluginRegistry();
  const { t } = useTranslation();

  const visibleNavItems = isLiteMode
    ? CORE_NAV_ITEMS
    : [
        ...CORE_NAV_ITEMS,
        ...PLUGIN_NAV_ITEMS.filter((item) => isPluginActive(item.pluginId))
      ];

  return (
    <aside className="w-56 bg-surface border-r border-surface-border flex flex-col justify-between select-none shrink-0 font-sans">
      <div className="p-3 space-y-1 overflow-y-auto">
        <div className="px-3 py-2 text-sm text-muted font-semibold flex items-center justify-between">
          <span>
            {isLiteMode
              ? t("sidebar.lite_core_badge")
              : t("sidebar.active_modules_badge", { count: activePlugins.length })}
          </span>
        </div>
        {visibleNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          const label = t(`nav.${item.id}`);
          return (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => onTabChange(item.id as NavTab)}
              className={`k-btn w-full !justify-start text-left transition ${
                isActive
                  ? "k-nav-active"
                  : "text-muted hover:text-ink hover:bg-elevated"
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="min-w-0 whitespace-normal leading-snug">{label}</span>
            </button>
          );
        })}

        {/* Dynamic Extension Slot for 3rd-party/ModStore plugins (only in non-lite modes) */}
        {!isLiteMode && <ExtensionSlot slot="sidebar" />}
      </div>

      <div className="p-3 border-t border-surface-border space-y-2 bg-deep">
        <div className="px-1 text-sm text-muted font-semibold">
          {t("sidebar.engine_diagnostics")}
        </div>
        <div className="space-y-1.5 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-1 text-muted">
            <span className="flex items-center space-x-1.5">
              <Database className="w-3 h-3 text-gain" />
              <span>SQLite (OLTP)</span>
            </span>
            <span className="text-gain font-semibold">{t("sidebar.wal_on")}</span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-1 text-muted">
            <span className="flex items-center space-x-1.5">
              <Layers className={`w-3 h-3 ${isLiteMode ? "text-muted" : "text-accent"}`} />
              <span>DuckDB (OLAP)</span>
            </span>
            <span className={`font-semibold ${isLiteMode ? "text-muted" : "text-accent"}`}>
              {isLiteMode ? t("sidebar.on_demand") : t("sidebar.columnar")}
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-1 text-muted">
            <span className="flex items-center space-x-1.5">
              <Cpu className="w-3 h-3 text-purple-400" />
              <span>{t("sidebar.desktop_core")}</span>
            </span>
            <span className="text-purple-400 text-[10px] font-semibold">ASYNCIO</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
