import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";

export interface PluginMetadata {
  plugin_id: string;
  name: string;
  version: string;
  category: string;
  description: string;
  author: string;
  heavy_dependencies: string[];
  router_prefix?: string;
  is_active: boolean;
  ram_footprint_mb: number;
  persona_tags: string[];
}

export type SlotType = "sidebar" | "header" | "dashboard_tile" | "settings_tab" | "studio_view";

export interface PluginContribution {
  id: string;
  pluginId: string;
  slot: SlotType;
  title: string;
  icon?: string;
  component: React.LazyExoticComponent<React.ComponentType<any>> | React.ComponentType<any>;
  order?: number;
  routePath?: string;
}

export const PERSONA_PLUGIN_MAP: Record<string, string[]> = {
  lite: [],
  kuantra_lite: [],
  quant: ["plugin_quant_shield", "plugin_orderflow", "plugin_duckdb", "plugin_backtester"],
  kuantra_quant: ["plugin_quant_shield", "plugin_orderflow", "plugin_duckdb", "plugin_backtester"],
  defai: ["plugin_dex_arbitrage", "plugin_ai_swarm", "plugin_mcp_gateway", "plugin_reverse_skill"],
  kuantra_defai: ["plugin_dex_arbitrage", "plugin_ai_swarm", "plugin_mcp_gateway", "plugin_reverse_skill"],
  institutional: ["plugin_fix_dma", "plugin_biometrics", "plugin_orderflow", "plugin_p2p_copy", "plugin_quant_shield", "plugin_ai_swarm", "plugin_reverse_skill"],
  kuantra_institutional: ["plugin_fix_dma", "plugin_biometrics", "plugin_orderflow", "plugin_p2p_copy", "plugin_quant_shield", "plugin_ai_swarm", "plugin_reverse_skill"],
  full: [
    "plugin_quant_shield",
    "plugin_orderflow",
    "plugin_ai_swarm",
    "plugin_mcp_gateway",
    "plugin_reverse_skill",
    "plugin_dex_arbitrage",
    "plugin_fix_dma",
    "plugin_biometrics"
  ],
  kuantra_full: [
    "plugin_quant_shield",
    "plugin_orderflow",
    "plugin_ai_swarm",
    "plugin_mcp_gateway",
    "plugin_reverse_skill",
    "plugin_dex_arbitrage",
    "plugin_fix_dma",
    "plugin_biometrics"
  ]
};

interface PluginRegistryContextType {
  plugins: PluginMetadata[];
  activePlugins: string[];
  activePersona: string;
  isLiteMode: boolean;
  loading: boolean;
  error: string | null;
  contributions: PluginContribution[];
  isPluginActive: (pluginId: string) => boolean;
  togglePlugin: (pluginId: string, enable: boolean) => Promise<boolean>;
  applyPersona: (persona: string) => Promise<boolean>;
  refreshPlugins: () => Promise<void>;
  registerContribution: (contribution: PluginContribution) => void;
  getSlotContributions: (slot: SlotType) => PluginContribution[];
}

const PluginRegistryContext = createContext<PluginRegistryContextType | undefined>(undefined);

const API_BASE = "http://127.0.0.1:8000/api/v1";

export const PluginRegistryProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [plugins, setPlugins] = useState<PluginMetadata[]>([]);
  const [activePersona, setActivePersona] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("kuantra_selected_persona") || "kuantra_lite";
    }
    return "kuantra_lite";
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [contributions, setContributions] = useState<PluginContribution[]>([]);

  const isLiteMode = activePersona === "lite" || activePersona === "kuantra_lite";
  const activePlugins = plugins.filter((p) => p.is_active).map((p) => p.plugin_id);

  const fetchPlugins = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/plugins/installed`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.plugins) {
          setPlugins(data.plugins);
          const persona = data.active_persona || localStorage.getItem("kuantra_selected_persona") || "kuantra_lite";
          setActivePersona(persona);
        }
      }
      setError(null);
    } catch (err: any) {
      console.warn("[PluginRegistry] Backend unavailable, initializing fallback local plugins:", err.message);
      const currentPersona = localStorage.getItem("kuantra_selected_persona") || "kuantra_lite";
      const targetActiveSet = new Set(PERSONA_PLUGIN_MAP[currentPersona] || []);

      // Fallback local plugins if backend sidecar is still booting
      setPlugins([
        {
          plugin_id: "plugin_quant_shield",
          name: "Quantitative Risk & Prop Firm Drawdown Shield",
          version: "1.1.0",
          category: "Quant & Risk",
          description: "MAE/MFE analytics, SQN, Sharpe/Sortino, and Prop Firm drawdowns.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["duckdb", "numpy"],
          router_prefix: "/api/v1/plugins/quant-shield",
          is_active: targetActiveSet.has("plugin_quant_shield"),
          ram_footprint_mb: 18.5,
          persona_tags: ["quant", "institutional", "full"]
        },
        {
          plugin_id: "plugin_orderflow",
          name: "Order Flow Footprint & Cumulative Volume Delta",
          version: "1.1.0",
          category: "Order Flow",
          description: "Real-time Order Flow Footprint with bid/ask imbalance detection.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["numpy"],
          router_prefix: "/api/v1/plugins/orderflow",
          is_active: targetActiveSet.has("plugin_orderflow"),
          ram_footprint_mb: 14.2,
          persona_tags: ["quant", "institutional", "full"]
        },
        {
          plugin_id: "plugin_ai_swarm",
          name: "Multi-Agent AI Swarm & Local GPU Inference",
          version: "1.1.0",
          category: "AI & Swarm",
          description: "Sub-50ms Multi-Agent Quant Swarm consensus with GPU acceleration.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["torch", "llama_cpp"],
          router_prefix: "/api/v1/plugins/ai-swarm",
          is_active: true,
          ram_footprint_mb: 45.0,
          persona_tags: ["defai", "institutional", "full"]
        },
        {
          plugin_id: "plugin_mcp_gateway",
          name: "Financial Model Context Protocol (MCP) Gateway",
          version: "1.1.0",
          category: "Financial MCP",
          description: "SEC 10-K filings, CryptoPanic sentiment NLP, and Treasury macro feeds.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["httpx"],
          router_prefix: "/api/v1/plugins/mcp",
          is_active: true,
          ram_footprint_mb: 12.0,
          persona_tags: ["defai", "full"]
        },
        {
          plugin_id: "plugin_reverse_skill",
          name: "Reverse-Skill Strategy & Pine Script AST Transpiler",
          version: "1.1.0",
          category: "Transpiler & Strategy",
          description: "Transpiles Pine Script v4/v5 into Python Swarm Agents.",
          author: "Kuantra Core Team",
          heavy_dependencies: [],
          router_prefix: "/api/v1/plugins/reverse-skill",
          is_active: true,
          ram_footprint_mb: 8.5,
          persona_tags: ["institutional", "full"]
        },
        {
          plugin_id: "plugin_dex_arbitrage",
          name: "Cross-DEX Flash Loan Arbitrage & MEV Protection",
          version: "1.1.0",
          category: "DeFi & MEV",
          description: "Multi-chain RPC gateway, Bellman-Ford negative cycle pathfinding.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["web3"],
          router_prefix: "/api/v1/plugins/dex-arbitrage",
          is_active: true,
          ram_footprint_mb: 22.0,
          persona_tags: ["defai", "full"]
        },
        {
          plugin_id: "plugin_fix_dma",
          name: "Institutional FIX 4.4 / 5.0 SP2 & Limit Order Book",
          version: "1.1.0",
          category: "Institutional FIX & DMA",
          description: "Sub-10µs Limit Order Book with CME FIX gateway.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["quickfix"],
          router_prefix: "/api/v1/plugins/fix-dma",
          is_active: true,
          ram_footprint_mb: 28.0,
          persona_tags: ["institutional", "full"]
        },
        {
          plugin_id: "plugin_biometrics",
          name: "Hardware Wearable Biometrics & Stress Interceptor",
          version: "1.1.0",
          category: "Hardware Biometrics",
          description: "Polar H10, Garmin, and Empatica E4 BLE telemetry with S_bio lockout.",
          author: "Kuantra Core Team",
          heavy_dependencies: ["bleak"],
          router_prefix: "/api/v1/plugins/biometrics",
          is_active: true,
          ram_footprint_mb: 16.0,
          persona_tags: ["institutional", "full"]
        }
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const isPluginActive = useCallback(
    (pluginId: string) => {
      const p = plugins.find((item) => item.plugin_id === pluginId);
      return p ? p.is_active : false;
    },
    [plugins]
  );

  const togglePlugin = useCallback(
    async (pluginId: string, enable: boolean): Promise<boolean> => {
      try {
        await fetch(`${API_BASE}/plugins/toggle`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plugin_id: pluginId, enable })
        });
        setPlugins((prev) =>
          prev.map((p) => (p.plugin_id === pluginId ? { ...p, is_active: enable } : p))
        );
        return true;
      } catch (err) {
        console.error(`Failed to toggle plugin ${pluginId}:`, err);
        // Optimistic toggle fallback
        setPlugins((prev) =>
          prev.map((p) => (p.plugin_id === pluginId ? { ...p, is_active: enable } : p))
        );
        return true;
      }
    },
    []
  );

  const applyPersona = useCallback(
    async (persona: string): Promise<boolean> => {
      try {
        localStorage.setItem("kuantra_selected_persona", persona);
        setActivePersona(persona);

        // Immediate optimistic synchronization of all plugin states
        const targetActiveSet = new Set(PERSONA_PLUGIN_MAP[persona] || []);
        setPlugins((prev) =>
          prev.map((p) => ({
            ...p,
            is_active: targetActiveSet.has(p.plugin_id)
          }))
        );

        await fetch(`${API_BASE}/plugins/apply-persona`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ persona })
        });
        
        await fetchPlugins();
        return true;
      } catch (err) {
        console.error(`Failed to apply persona ${persona}:`, err);
        return false;
      }
    },
    [fetchPlugins]
  );

  const registerContribution = useCallback((contribution: PluginContribution) => {
    setContributions((prev) => {
      if (prev.some((c) => c.id === contribution.id)) {
        return prev.map((c) => (c.id === contribution.id ? contribution : c));
      }
      return [...prev, contribution];
    });
  }, []);

  const getSlotContributions = useCallback(
    (slot: SlotType): PluginContribution[] => {
      return contributions
        .filter((c) => c.slot === slot && isPluginActive(c.pluginId))
        .sort((a, b) => (a.order || 0) - (b.order || 0));
    },
    [contributions, isPluginActive]
  );

  return (
    <PluginRegistryContext.Provider
      value={{
        plugins,
        activePlugins,
        activePersona,
        isLiteMode,
        loading,
        error,
        contributions,
        isPluginActive,
        togglePlugin,
        applyPersona,
        refreshPlugins: fetchPlugins,
        registerContribution,
        getSlotContributions
      }}
    >
      {children}
    </PluginRegistryContext.Provider>
  );
};

export const usePluginRegistry = () => {
  const context = useContext(PluginRegistryContext);
  if (!context) {
    throw new Error("usePluginRegistry must be used within a PluginRegistryProvider");
  }
  return context;
};