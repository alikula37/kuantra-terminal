import React, { useState } from "react";
import { 
  Puzzle, 
  Download, 
  CheckCircle, 
  Sliders, 
  Activity, 
  HardDrive, 
  Cpu, 
  Search, 
  ShieldCheck, 
  Power, 
  RefreshCw 
} from "lucide-react";
import { usePluginRegistry } from "../../context/PluginRegistryContext";

export const ModStoreStudio: React.FC<{ onOpenPersonaSelector?: () => void }> = ({ onOpenPersonaSelector }) => {
  const { plugins, activePersona, loading, togglePlugin, refreshPlugins } = usePluginRegistry();
  const [activeTab, setActiveTab] = useState<"installed" | "marketplace" | "telemetry">("installed");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // Compute live memory stats
  const baseCoreRamMb = 22.0;
  const activePluginsRamMb = plugins
    .filter((p) => p.is_active)
    .reduce((acc, curr) => acc + curr.ram_footprint_mb, 0);
  const totalEstimatedRamMb = Math.round((baseCoreRamMb + activePluginsRamMb) * 10) / 10;

  const handleToggle = async (pluginId: string, currentStatus: boolean) => {
    setTogglingId(pluginId);
    await togglePlugin(pluginId, !currentStatus);
    setTogglingId(null);
  };

  const filteredPlugins = plugins.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const marketplaceModules = [
    {
      id: "mod_options_greeks",
      name: "Options Analytics & Live Black-Scholes Greeks",
      category: "Derivatives",
      version: "1.0.4",
      author: "Kuantra Institutional",
      description: "Real-time volatility smile, Delta/Gamma/Vega/Theta surface visualizer with CME options DMA.",
      rating: 4.9,
      downloads: "12.4k",
      verified: true,
      ram: 24.5
    },
    {
      id: "mod_macro_nowcasting",
      name: "Global Macro Nowcasting & Central Bank Sentiment",
      category: "Macro & NLP",
      version: "2.1.0",
      author: "Kuantra Research",
      description: "Scrapes FOMC, ECB, and BOJ minutes using fine-tuned transformer models for macro bias scoring.",
      rating: 4.8,
      downloads: "8.9k",
      verified: true,
      ram: 32.0
    },
    {
      id: "mod_binance_liquidation_radar",
      name: "High-Density Liquidation Heatmap & Cascade Hunter",
      category: "Order Flow",
      version: "1.3.2",
      author: "Community Verified",
      description: "Live visual liquidation levels and high-conviction cascading squeeze entry alerts.",
      rating: 4.95,
      downloads: "24.1k",
      verified: true,
      ram: 18.0
    },
    {
      id: "mod_hft_tick_compressor",
      name: "ZSTD High-Frequency Tick Database Compressor",
      category: "Storage",
      version: "1.0.1",
      author: "Kuantra Infrastructure",
      description: "Lossless column-oriented tick archival achieving 85%+ storage footprint reduction.",
      rating: 4.75,
      downloads: "6.2k",
      verified: true,
      ram: 15.0
    }
  ];

  return (
    <div className="flex-1 bg-[#0b0e14] text-slate-100 flex flex-col overflow-hidden select-none font-sans">
      {/* Top Banner */}
      <div className="p-6 bg-[#0e131f] border-b border-surface-border flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
            <Puzzle className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <h1 className="text-xl font-bold text-white tracking-wide font-mono">ModStore & Extension Hub</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent/20 text-accent font-bold border border-accent/30">
                MICRO-KERNEL v1.1.0
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Hot-mount, unmount, and configure modular quantitative algorithms and sidecar subsystems.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {onOpenPersonaSelector && (
            <button
              onClick={onOpenPersonaSelector}
              className="flex items-center space-x-2 px-3.5 py-2 rounded-lg bg-[#151c2c] hover:bg-[#1a2337] border border-surface-border text-xs font-mono text-slate-200 transition"
            >
              <Sliders className="w-3.5 h-3.5 text-accent" />
              <span>Persona:</span>
              <span className="text-accent font-bold uppercase">{activePersona}</span>
            </button>
          )}

          <button
            onClick={() => refreshPlugins()}
            className="p-2 rounded-lg bg-[#151c2c] hover:bg-[#1a2337] border border-surface-border text-slate-300 hover:text-white transition"
            title="Reload Plugin Registry"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-accent" : ""}`} />
          </button>
        </div>
      </div>

      {/* Navigation Tabs & Search */}
      <div className="px-6 py-3 border-b border-surface-border bg-[#090d15] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab("installed")}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium font-mono transition flex items-center space-x-2 ${
              activeTab === "installed"
                ? "bg-accent text-black font-bold"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Installed Subsystems ({plugins.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("marketplace")}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium font-mono transition flex items-center space-x-2 ${
              activeTab === "marketplace"
                ? "bg-accent text-black font-bold"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Download className="w-3.5 h-3.5" />
            <span>ModStore Catalog ({marketplaceModules.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("telemetry")}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium font-mono transition flex items-center space-x-2 ${
              activeTab === "telemetry"
                ? "bg-accent text-black font-bold"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Resource Telemetry</span>
          </button>
        </div>

        {activeTab !== "telemetry" && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search plugins or tags..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-[#121824] border border-surface-border rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-accent w-56 font-mono"
            />
          </div>
        )}
      </div>

      {/* Main Content Body */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Tab 1: Installed Plugins */}
        {activeTab === "installed" && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredPlugins.map((plugin) => {
              const isToggling = togglingId === plugin.plugin_id;
              return (
                <div
                  key={plugin.plugin_id}
                  className={`p-4 rounded-xl border flex flex-col justify-between transition ${
                    plugin.is_active
                      ? "border-surface-border bg-[#111724]/80 shadow-md"
                      : "border-slate-800/60 bg-[#0d121c]/40 opacity-70"
                  }`}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="font-bold text-sm text-white font-mono">{plugin.name}</h3>
                        </div>
                        <span className="text-[10px] font-mono text-accent font-semibold">{plugin.category}</span>
                      </div>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        v{plugin.version}
                      </span>
                    </div>

                    <p className="text-xs text-slate-300 line-clamp-2">{plugin.description}</p>

                    <div className="flex flex-wrap gap-1 pt-1">
                      {plugin.persona_tags.map((tag, i) => (
                        <span
                          key={i}
                          className="text-[9px] font-mono uppercase bg-slate-800/80 text-slate-400 px-1.5 py-0.5 rounded"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="pt-4 mt-4 border-t border-surface-border/50 flex items-center justify-between">
                    <div className="flex items-center space-x-2 text-[11px] font-mono text-slate-400">
                      <HardDrive className="w-3 h-3 text-slate-500" />
                      <span>~{plugin.ram_footprint_mb} MB RAM</span>
                    </div>

                    <button
                      onClick={() => handleToggle(plugin.plugin_id, plugin.is_active)}
                      disabled={isToggling}
                      className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-mono font-bold transition ${
                        plugin.is_active
                          ? "bg-gain/20 text-gain border border-gain/40 hover:bg-gain/30"
                          : "bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700 hover:text-white"
                      }`}
                    >
                      <Power className={`w-3 h-3 ${plugin.is_active ? "text-gain" : "text-slate-500"}`} />
                      <span>{isToggling ? "Switching..." : plugin.is_active ? "ACTIVE" : "MOUNT"}</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Tab 2: ModStore Marketplace Catalog */}
        {activeTab === "marketplace" && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {marketplaceModules.map((mod) => (
              <div
                key={mod.id}
                className="p-4 rounded-xl border border-surface-border bg-[#111724]/80 flex flex-col justify-between space-y-3"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-1.5">
                        <h3 className="font-bold text-sm text-white font-mono">{mod.name}</h3>
                        {mod.verified && <ShieldCheck className="w-3.5 h-3.5 text-accent shrink-0" />}
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">{mod.author}</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      v{mod.version}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">{mod.description}</p>
                </div>

                <div className="pt-3 border-t border-surface-border/50 flex items-center justify-between">
                  <div className="text-[11px] font-mono text-slate-400 space-x-2">
                    <span>★ {mod.rating}</span>
                    <span>• {mod.downloads} DLs</span>
                  </div>

                  <button className="flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-mono font-bold bg-accent hover:bg-sky-400 text-black transition shadow-sm">
                    <Download className="w-3 h-3" />
                    <span>INSTALL</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab 3: Resource Telemetry & Footprint Gauge */}
        {activeTab === "telemetry" && (
          <div className="space-y-6 max-w-4xl">
            <div className="p-5 rounded-xl border border-surface-border bg-[#111724] space-y-4">
              <h2 className="text-sm font-bold font-mono text-white flex items-center space-x-2">
                <Cpu className="w-4 h-4 text-accent" />
                <span>Sidecar Dynamic Memory Footprint</span>
              </h2>

              {/* Progress / Gauge Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Total Allocated Dynamic RAM</span>
                  <span className="text-accent font-bold">{totalEstimatedRamMb} MB / 2048 MB Limit</span>
                </div>
                <div className="w-full bg-[#0a0d14] h-4 rounded-full overflow-hidden border border-surface-border flex">
                  <div
                    style={{ width: `${(baseCoreRamMb / 2048) * 100}%` }}
                    className="bg-purple-500 h-full"
                    title={`Base Core: ${baseCoreRamMb} MB`}
                  />
                  <div
                    style={{ width: `${(activePluginsRamMb / 2048) * 100}%` }}
                    className="bg-accent h-full"
                    title={`Active Plugins: ${activePluginsRamMb} MB`}
                  />
                </div>
                <div className="flex items-center space-x-4 text-[10px] font-mono text-slate-400 pt-1">
                  <div className="flex items-center space-x-1.5">
                    <div className="w-2.5 h-2.5 rounded bg-purple-500" />
                    <span>Base Micro-Kernel ({baseCoreRamMb} MB)</span>
                  </div>
                  <div className="flex items-center space-x-1.5">
                    <div className="w-2.5 h-2.5 rounded bg-accent" />
                    <span>Active Subsystems (+{activePluginsRamMb} MB)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Plugin Memory Breakdown Table */}
            <div className="rounded-xl border border-surface-border overflow-hidden bg-[#111724]">
              <div className="p-4 border-b border-surface-border font-mono text-xs font-bold text-white">
                Subsystem Allocation Breakdown
              </div>
              <div className="divide-y divide-surface-border">
                {plugins.map((p) => (
                  <div key={p.plugin_id} className="p-3 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center space-x-2.5">
                      <div className={`w-2 h-2 rounded-full ${p.is_active ? "bg-gain" : "bg-slate-600"}`} />
                      <span className={p.is_active ? "text-white font-semibold" : "text-slate-400"}>
                        {p.name}
                      </span>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span className="text-slate-400">~{p.ram_footprint_mb} MB</span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          p.is_active ? "bg-gain/20 text-gain" : "bg-slate-800 text-slate-500"
                        }`}
                      >
                        {p.is_active ? "LOADED" : "UNLOADED"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};