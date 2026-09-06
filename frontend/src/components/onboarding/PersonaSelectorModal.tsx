import React, { useState } from "react";
import { X, Check, Zap, Layers, Sliders, CheckCircle2 } from "lucide-react";
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
    ram: "On-demand profile",
    boot: "Capability-verified",
    description: "Journal analytics and deterministic risk workflow beyond Lite. It does not enable order-flow, execution, or AI features.",
    icon: Layers,
    color: "text-sky-400 border-sky-500/40 bg-sky-950/20",
    badge: "VERIFIED SURFACE",
    included: ["Lite Features", "MAE / MFE Analytics", "Deterministic Risk Workflow", "DuckDB Analytics Projection"]
  }
};

export const PersonaSelectorModal: React.FC<PersonaSelectorModalProps> = ({ isOpen, onClose }) => {
  const { activePersona, applyPersona } = usePluginRegistry();
  const [selectedPersona, setSelectedPersona] = useState<string>(
    activePersona === "kuantra_quant" ? "kuantra_quant" : "kuantra_lite"
  );
  const [applying, setApplying] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleApply = async () => {
    setApplying(true);
    const applied = await applyPersona(selectedPersona);
    setApplying(false);
    if (applied) onClose();
  };

  const handleCancelOrClose = () => {
    if (!localStorage.getItem("kuantra_selected_persona")) {
      localStorage.setItem("kuantra_selected_persona", "kuantra_lite");
    }
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
                Tailor desktop core memory consumption, router footprint, and UI complexity.
              </p>
            </div>
          </div>
          <button
            onClick={handleCancelOrClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Persona Cards Grid */}
        <div className="p-5 overflow-y-auto space-y-3 flex-1">
          {Object.entries(PERSONA_DETAILS).map(([id, details]) => {
            const isSelected = selectedPersona === id;
            const Icon = details.icon;
            return (
              <div
                key={id}
                onClick={() => setSelectedPersona(id)}
                className={`p-4 rounded-xl border transition cursor-pointer flex flex-col md:flex-row items-start md:items-center justify-between gap-4 ${
                  isSelected
                    ? "border-accent bg-accent/10 shadow-lg shadow-accent/5 ring-1 ring-accent"
                    : "border-surface-border bg-[#111724]/60 hover:bg-[#111724] hover:border-slate-700"
                }`}
              >
                <div className="flex items-start space-x-3.5 flex-1">
                  <div className={`p-2.5 rounded-lg border shrink-0 ${details.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <h3 className="font-bold text-sm text-white font-mono">{details.title}</h3>
                      <span
                        className={`text-[9px] font-mono font-extrabold px-2 py-0.5 rounded border uppercase ${details.color}`}
                      >
                        {details.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300">{details.description}</p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {details.included.map((feat, i) => (
                        <span
                          key={i}
                          className="text-[10px] font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded"
                        >
                          ✓ {feat}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-4 shrink-0 self-end md:self-center">
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
              onClick={handleCancelOrClose}
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
                <span>Re-configuring Desktop Core...</span>
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
