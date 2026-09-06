import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { apiFetch, apiUrl } from "../lib/backend";

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
  // Quant is intentionally limited to the deterministic risk/journal extension.
  // Order flow and every execution/AI extension remain experimental until the
  // backend can prove data provenance and availability.
  quant: ["plugin_quant_shield"],
  kuantra_quant: ["plugin_quant_shield"]
};

export const SAFE_PERSONAS = new Set(["kuantra_lite", "kuantra_quant"]);
// Dynamic plugin activation remains closed until signed packages and process
// isolation exist. Quant analytics are served by core endpoints in this release.
const PRODUCTION_PLUGIN_IDS = new Set<string>();

const normalizePersona = (persona?: string | null): string =>
  SAFE_PERSONAS.has(persona || "") ? persona! : "kuantra_lite";

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

// Resolved lazily: apiUrl() is path-only inside the desktop bridge, absolute in browser dev.
const API_BASE = () => apiUrl("/api/v1");

export const PluginRegistryProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [plugins, setPlugins] = useState<PluginMetadata[]>([]);
  const [activePersona, setActivePersona] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return normalizePersona(localStorage.getItem("kuantra_selected_persona"));
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
      const res = await apiFetch(`${API_BASE()}/plugins/installed`);
      if (!res.ok) {
        throw new Error(`Plugin registry returned HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!data || !Array.isArray(data.plugins)) {
        throw new Error("Plugin registry did not return an installed-component list");
      }

      setPlugins(data.plugins);
      setActivePersona(normalizePersona(data.active_persona || localStorage.getItem("kuantra_selected_persona")));
      setError(null);
    } catch (err: any) {
      console.warn("[PluginRegistry] Backend unavailable; no plugin capability is asserted:", err.message);
      setPlugins([]);
      setError("Installed component registry is unavailable. No plugin capability is asserted.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  const isPluginActive = useCallback(
    (pluginId: string) => {
      if (isLiteMode || !PRODUCTION_PLUGIN_IDS.has(pluginId)) return false;
      const p = plugins.find((item) => item.plugin_id === pluginId);
      return p ? p.is_active : false;
    },
    [plugins, isLiteMode]
  );

  const togglePlugin = useCallback(
    async (pluginId: string, enable: boolean): Promise<boolean> => {
      if (!PRODUCTION_PLUGIN_IDS.has(pluginId)) {
        setError("Runtime extension changes are unavailable for experimental components.");
        return false;
      }
      try {
        const res = await apiFetch(`${API_BASE()}/plugins/toggle`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plugin_id: pluginId, enable })
        });
        if (!res.ok) throw new Error(`Plugin toggle returned HTTP ${res.status}`);
        await fetchPlugins();
        return true;
      } catch (err) {
        console.error(`Failed to toggle plugin ${pluginId}:`, err);
        setError("Plugin state could not be verified; no local state was changed.");
        return false;
      }
    },
    [fetchPlugins]
  );

  const applyPersona = useCallback(
    async (persona: string): Promise<boolean> => {
      if (!SAFE_PERSONAS.has(persona)) {
        setError("This persona is experimental and unavailable in the current release.");
        return false;
      }
      try {
        const res = await apiFetch(`${API_BASE()}/plugins/apply-persona`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ persona })
        });
        if (!res.ok) throw new Error(`Persona update returned HTTP ${res.status}`);
        localStorage.setItem("kuantra_selected_persona", persona);
        setActivePersona(persona);
        await fetchPlugins();
        return true;
      } catch (err) {
        console.error(`Failed to apply persona ${persona}:`, err);
        setError("Persona change could not be verified; the previous capability state was kept.");
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
