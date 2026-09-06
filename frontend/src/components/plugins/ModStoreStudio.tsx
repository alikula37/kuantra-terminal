import React, { useState } from "react";
import { 
  Puzzle, 
  CheckCircle, 
  Sliders, 
  Activity, 
  HardDrive, 
  Search, 
  RefreshCw 
} from "lucide-react";
import { usePluginRegistry } from "../../context/PluginRegistryContext";

export const ModStoreStudio: React.FC<{ onOpenPersonaSelector?: () => void }> = ({ onOpenPersonaSelector }) => {
  const { plugins, activePersona, loading, error, refreshPlugins } = usePluginRegistry();
  const [activeTab, setActiveTab] = useState<"installed" | "telemetry">("installed");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredPlugins = plugins.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
              <h1 className="text-xl font-bold text-white tracking-wide font-mono">Component Registry</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent/20 text-accent font-bold border border-accent/30">
                MICRO-KERNEL v1.1.0
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Installed components are reported by the local backend. Remote extension installation is unavailable in this release.
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
            onClick={() => setActiveTab("telemetry")}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium font-mono transition flex items-center space-x-2 ${
              activeTab === "telemetry"
                ? "bg-accent text-black font-bold"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Component Availability</span>
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
        {error && (
          <div role="alert" className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-100">
            {error}
          </div>
        )}

        <div className="mb-4 rounded-lg border border-slate-700 bg-slate-900/50 p-3 text-xs text-slate-300">
          Extension downloads, remote registries, and runtime mounting are disabled pending signed-package and capability-isolation controls.
        </div>

        {/* Backend-reported installed components */}
        {activeTab === "installed" && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {!loading && filteredPlugins.length === 0 && (
              <div className="col-span-full rounded-lg border border-slate-800 bg-[#0d121c] p-5 text-center text-xs text-slate-400">
                No installed component capability is available to display.
              </div>
            )}
            {filteredPlugins.map((plugin) => {
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
                      <span>Installed metadata</span>
                    </div>

                    <span className={`px-3 py-1 rounded text-xs font-mono font-bold border ${
                      plugin.is_active
                        ? "bg-gain/20 text-gain border-gain/40"
                        : "bg-slate-800 text-slate-400 border-slate-700"
                    }`}>
                      {plugin.is_active ? "BACKEND-REPORTED ACTIVE" : "NOT ACTIVE"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Reported metadata, not a measured runtime telemetry source. */}
        {activeTab === "telemetry" && (
          <div className="max-w-4xl">
            <div className="p-5 rounded-xl border border-surface-border bg-[#111724] space-y-3">
              <h2 className="text-sm font-bold font-mono text-white flex items-center space-x-2">
                <Activity className="w-4 h-4 text-accent" />
                <span>Component Availability</span>
              </h2>
              <p className="text-xs text-slate-400">
                Status below is supplied by the local backend. Memory footprints are not measured telemetry and are intentionally not displayed.
              </p>
              <div className="divide-y divide-surface-border rounded border border-surface-border overflow-hidden">
                {plugins.map((p) => (
                  <div key={p.plugin_id} className="p-3 flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center space-x-2.5">
                      <div className={`w-2 h-2 rounded-full ${p.is_active ? "bg-gain" : "bg-slate-600"}`} />
                      <span className={p.is_active ? "text-white font-semibold" : "text-slate-400"}>
                        {p.name}
                      </span>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          p.is_active ? "bg-gain/20 text-gain" : "bg-slate-800 text-slate-500"
                        }`}
                      >
                        {p.is_active ? "BACKEND-REPORTED ACTIVE" : "NOT ACTIVE"}
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
