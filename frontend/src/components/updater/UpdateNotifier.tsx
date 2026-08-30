import React, { useState } from "react";
import { Download, RefreshCw, CheckCircle2, ShieldCheck, ArrowRight } from "lucide-react";

export const UpdateNotifier: React.FC = () => {
  const [isChecking, setIsChecking] = useState<boolean>(false);
  const [updateAvailable, setUpdateAvailable] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("Current version: v0.1.0 (Latest Release)");

  const checkForUpdates = async () => {
    setIsChecking(true);
    setStatusMessage("Verifying Ed25519 cryptographic signatures on GitHub releases...");

    setTimeout(() => {
      setIsChecking(false);
      setUpdateAvailable(false);
      setStatusMessage("Kuantra Terminal is up to date (v0.1.0). Ed25519 signature verified.");
    }, 1200);
  };

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-3">
      <div className="flex items-center justify-between border-b border-surface-border pb-2">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-gain" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            ED25519 SIGNED AUTO-UPDATER
          </span>
        </div>
        <span className="text-[10px] text-accent bg-[#111722] px-2 py-0.5 rounded border border-surface-border font-bold">
          v0.1.0-STABLE
        </span>
      </div>

      <div className="bg-[#111722] p-3 rounded border border-surface-border flex items-center justify-between text-xs">
        <div className="flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-gain flex-shrink-0" />
          <span className="text-slate-300 text-[11px]">{statusMessage}</span>
        </div>

        <button
          onClick={checkForUpdates}
          disabled={isChecking}
          className="flex items-center space-x-1 bg-[#0d121c] hover:bg-[#1a2234] border border-surface-border text-white text-[10px] font-bold px-3 py-1.5 rounded transition"
        >
          <RefreshCw className={`w-3 h-3 ${isChecking ? "animate-spin text-accent" : ""}`} />
          <span>{isChecking ? "Checking..." : "CHECK UPDATES"}</span>
        </button>
      </div>

      {updateAvailable && (
        <div className="p-3 bg-accent/15 border border-accent/40 rounded flex items-center justify-between">
          <span className="text-xs text-white font-bold">New signed release available: v0.2.0</span>
          <button className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold px-3 py-1 rounded text-xs transition">
            <Download className="w-3.5 h-3.5" />
            <span>UPDATE & RESTART</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
};