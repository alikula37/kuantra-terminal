import React, { useState } from "react";
import { X, Check, Cpu, Zap, Sparkles, Shield, Layers, Sliders, CheckCircle2 } from "lucide-react";
import { usePluginRegistry } from "../../context/PluginRegistryContext";

interface PersonaSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PERSONA_DETAILS: Record<
  string,
  {
    title: string;
    ram: string;
    boot: string;
    description: string;
    icon: React.ComponentType<any>;
    color: string;
    badge: string;
    included: string[];
  }
> = {
  kuantra_lite: {
    title: "Kuantra Lite",
    ram: "~20 MB RAM",
    boot: "<350ms boot",
    description: "Ultra-lean core for disciplined journal logging and essential trade analytics.",
    icon: Zap,
    color: "text-amber-400 border-amber-500/40 bg-amber-950/20",
    badge: "LIGHTWEIGHT",
    included: ["SQLite WAL Journal", "Base Charts", "MAE / MFE Visualizer", "Basic Analytics"]
  },
  kuantra_quant: {
    title: "Kuantra Quant",
    ram: "~140 MB RAM",
    boot: "~550ms boot",
    description: "High-frequency quant engine with order flow footprint and columnar DuckDB OLAP.",
    icon: Layers,
    color: "text-sky-400 border-sky-500/40 bg-sky-950/20",
    badge: "POPULAR",
    included: ["Lite Features", "Order Flow Footprint", "Prop Firm Drawdown Shield", "DuckDB Shadow Engine"]
  },
  kuantra_defai: {
    title: "Kuantra DeFAI",
    ram: "~480 MB RAM",
    boot: "~950ms boot",
    description: "Autonomous AI Swarm orchestrator, cross-DEX flash loan arbitrage, and financial MCP.",
    icon: Sparkles,
    color: "text-purple-400 border-purple-500/40 bg-purple-950/20",
    badge: "AI & DEFI",
    included: ["Lite Features", "Multi-Agent AI Swarm", "Cross-DEX Arbitrage & Flash Loans", "Financial MCP Gateway"]
  },
  kuantra_institutional: {
    title: "Kuantra Institutional",
    ram: "~320 MB RAM",
    boot: "~750ms boot",
    description: "Institutional execution suite with CME FIX 5.0 DMA, L2/L3 DOM Ladder, and BLE Biometrics.",
    icon: Shield,
    color: "text-emerald-400 border-emerald-500/40 bg-emerald-950/20",
    badge: "INSTITUTIONAL",
    included: ["Lite Features", "Order Flow Footprint", "CME FIX 5.0 DMA & DOM Ladder", "Wearable Biometrics & Lockout", "Reverse-Skill Transpiler"]
  },
  full: {
    title: "Kuantra Full Suite",
    ram: "~1.8 GB Max",
    boot: "~1200ms boot",
    description: "Complete professional workstation with all 8 modular plugin subsystems activated.",
    icon: Cpu,
    color: "text-accent border-cyan-500/40 bg-cyan-950/20",
    badge: "ALL MODULES",
    included: ["All 8 Modular Subsystems", "Full Hardware Acceleration", "Max Capability Matrix"]
  }
};

export const PersonaSelectorModal: React.FC<PersonaSelectorModalProps> = ({ isOpen, onClose }) => {
  const { activePersona, applyPersona } = usePluginRegistry();
  const [selectedPersona, setSelectedPersona] = useState<string>(activePersona || "full");
  const [applying, setApplying] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleApply = async () => {
    setApplying(true);
    await applyPersona(selectedPersona);
    setApplying(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm select-none p-4">
      <div className="bg-[#0e131f] border border-surface-border rounded-xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-surface-border bg-[#0b0f19]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">Select Architectural Persona</h2>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Tailor backend sidecar memory consumption, router footprint, and UI complexity.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Persona Selection Grid */}
        <div className="p-5 overflow-y-auto space-y-3 flex-1">
          {Object.entries(PERSONA_DETAILS).map(([key, details]) => {
            const Icon = details.icon;
            const isSelected = selectedPersona === key;
            return (
              <div
                key={key}
                onClick={() => setSelectedPersona(key)}
                className={`p-4 rounded-xl border transition cursor-pointer flex items-start justify-between ${
                  isSelected
                    ? "border-accent bg-accent/10 shadow-lg shadow-accent/5 ring-1 ring-accent"
                    : "border-surface-border bg-[#111724]/50 hover:bg-[#131b2c] hover:border-slate-600"
                }`}
              >
                <div className="flex items-start space-x-3.5">
                  <div className={`p-2.5 rounded-lg border ${details.color} mt-0.5`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-white font-mono">{details.title}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700">
                        {details.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">{details.description}</p>
                    <div className="flex flex-wrap gap-1.5 pt-1.5">
                      {details.included.map((inc, i) => (
                        <span
                          key={i}
                          className="text-[10px] font-mono text-slate-400 bg-black/40 px-2 py-0.5 rounded border border-slate-800"
                        >
                          ✓ {inc}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col items-end space-y-2 shrink-0 pl-3">
                  <div className="text-right">
                    <span className="text-xs font-mono font-bold text-accent block">{details.ram}</span>
                    <span className="text-[10px] font-mono text-slate-500 block">{details.boot}</span>
                  </div>
                  <div
                    className={`w-5 h-5 rounded-full border flex items-center justify-center transition ${
                      isSelected ? "bg-accent border-accent text-black" : "border-slate-600"
                    }`}
                  >
                    {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-border bg-[#0b0f19] flex items-center justify-between">
          <div className="text-xs text-slate-400 font-mono">
            Active: <span className="text-accent font-bold uppercase">{activePersona}</span>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              disabled={applying}
              className="flex items-center space-x-2 px-5 py-2 rounded-lg text-xs font-bold font-mono bg-accent hover:bg-sky-400 text-black transition shadow-md shadow-accent/20 active:scale-95 disabled:opacity-50"
            >
              {applying ? (
                <span>Re-configuring Sidecar...</span>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Apply Architectural Preset</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};