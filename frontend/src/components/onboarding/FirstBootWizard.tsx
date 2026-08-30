import React, { useState, useEffect } from "react";
import { OnboardingStatusResponse } from "../../types";
import { Cpu, Cloud, HardDrive, ArrowRight, Zap, Key, Check } from "lucide-react";

interface FirstBootWizardProps {
  isOpen: boolean;
  onCompleted: () => void;
}

export const FirstBootWizard: React.FC<FirstBootWizardProps> = ({ isOpen, onCompleted }) => {
  const [statusData, setStatusData] = useState<OnboardingStatusResponse | null>(null);
  const [selectedMode, setSelectedMode] = useState<"cloud" | "local_gguf" | "skip">("local_gguf");
  const [apiKey, setApiKey] = useState<string>("");
  const [provider, setProvider] = useState<string>("openai");

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      fetch("http://127.0.0.1:8000/api/v1/onboarding/status")
        .then((res) => res.json())
        .then((data: OnboardingStatusResponse) => {
          setStatusData(data);
        })
        .catch(() => {});
    }
  }, [isOpen]);

  const handleComplete = async () => {
    setIsSubmitting(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/onboarding/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ai_mode: selectedMode,
          api_key: apiKey || undefined,
          provider: provider,
        }),
      });

      if (res.ok) {
        onCompleted();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  const hw = statusData?.hardware;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 font-mono select-none">
      <div className="bg-[#0d121c] border border-surface-border rounded-xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col space-y-4 p-6">
        {/* Header */}
        <div className="border-b border-surface-border pb-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm">
              K
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                KUANTRA TERMINAL v1.0 ONBOARDING WIZARD
              </h2>
              <p className="text-[11px] text-slate-400">
                System Hardware Calibration & AI Cognitive Engine Setup
              </p>
            </div>
          </div>

          <span className="text-[10px] text-accent bg-[#111722] px-2.5 py-1 rounded border border-surface-border font-bold">
            FIRST BOOT SETUP
          </span>
        </div>

        {/* Hardware Acceleration Profile Strip */}
        {hw && (
          <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-white font-bold">
                <Cpu className="w-4 h-4 text-accent" />
                <span>Detected Acceleration: {hw.device_name}</span>
              </div>
              <span className="text-[10px] font-bold text-gain bg-gain/10 border border-gain/30 px-2 py-0.5 rounded">
                {hw.detected_backend} ACTIVE
              </span>
            </div>
            <p className="text-[11px] text-slate-400">{hw.notes}</p>
            <div className="flex items-center space-x-4 text-[10px] text-slate-400 pt-1">
              <span>Cores: <strong className="text-white">{hw.cpu_cores}</strong></span>
              <span>Recommended Quant: <strong className="text-accent">{hw.recommended_quant}</strong></span>
              <span>Est. Speed: <strong className="text-gain">~{hw.estimated_tokens_per_sec} tok/s</strong></span>
            </div>
          </div>
        )}

        {/* 3 AI Mode Selection Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          {/* Option A: Local GGUF */}
          <div
            onClick={() => setSelectedMode("local_gguf")}
            className={`p-3.5 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-2 ${
              selectedMode === "local_gguf"
                ? "bg-accent/10 border-accent text-white shadow-md"
                : "bg-[#111722] border-surface-border text-slate-300 hover:border-slate-600"
            }`}
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <HardDrive className={`w-4 h-4 ${selectedMode === "local_gguf" ? "text-accent" : "text-slate-400"}`} />
                {selectedMode === "local_gguf" && <Check className="w-3.5 h-3.5 text-accent" />}
              </div>
              <span className="font-bold text-xs block">Local GGUF Engine</span>
              <p className="text-[10px] text-slate-400">
                Runs 100% offline with zero cloud latency. Downloads ~1.25GB quantized weights.
              </p>
            </div>
            <span className="text-[9px] bg-[#090d14] px-2 py-0.5 rounded border border-surface-border text-accent font-bold inline-block">
              RECOMMENDED (GPU/CPU)
            </span>
          </div>

          {/* Option B: Cloud LLM */}
          <div
            onClick={() => setSelectedMode("cloud")}
            className={`p-3.5 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-2 ${
              selectedMode === "cloud"
                ? "bg-accent/10 border-accent text-white shadow-md"
                : "bg-[#111722] border-surface-border text-slate-300 hover:border-slate-600"
            }`}
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Cloud className={`w-4 h-4 ${selectedMode === "cloud" ? "text-accent" : "text-slate-400"}`} />
                {selectedMode === "cloud" && <Check className="w-3.5 h-3.5 text-accent" />}
              </div>
              <span className="font-bold text-xs block">Cloud LLM API</span>
              <p className="text-[10px] text-slate-400">
                Connect OpenAI or Claude API keys. 0MB download, instant setup.
              </p>
            </div>
            <span className="text-[9px] bg-[#090d14] px-2 py-0.5 rounded border border-surface-border text-slate-400 font-bold inline-block">
              0 MB DOWNLOAD
            </span>
          </div>

          {/* Option C: Skip AI */}
          <div
            onClick={() => setSelectedMode("skip")}
            className={`p-3.5 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-2 ${
              selectedMode === "skip"
                ? "bg-accent/10 border-accent text-white shadow-md"
                : "bg-[#111722] border-surface-border text-slate-300 hover:border-slate-600"
            }`}
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Zap className={`w-4 h-4 ${selectedMode === "skip" ? "text-accent" : "text-slate-400"}`} />
                {selectedMode === "skip" && <Check className="w-3.5 h-3.5 text-accent" />}
              </div>
              <span className="font-bold text-xs block">Offline Quant Only</span>
              <p className="text-[10px] text-slate-400">
                Launch pure mathematical terminal without AI natural language features.
              </p>
            </div>
            <span className="text-[9px] bg-[#090d14] px-2 py-0.5 rounded border border-surface-border text-slate-400 font-bold inline-block">
              PURE TRADING
            </span>
          </div>
        </div>

        {/* API Key input if Cloud selected */}
        {selectedMode === "cloud" && (
          <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Key className="w-3.5 h-3.5 text-accent" />
              <span>Enter API Key (Encrypted in Stronghold Vault):</span>
            </span>
            <div className="flex items-center space-x-2">
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="bg-[#090d14] border border-surface-border text-white text-xs px-2 py-1.5 rounded focus:outline-none focus:border-accent"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Claude</option>
              </select>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="flex-1 bg-[#090d14] border border-surface-border text-white text-xs px-3 py-1.5 rounded focus:outline-none focus:border-accent"
              />
            </div>
          </div>
        )}

        {/* Action Button */}
        <button
          onClick={handleComplete}
          disabled={isSubmitting}
          className="w-full flex items-center justify-center space-x-2 bg-accent hover:bg-sky-400 text-black font-bold py-2.5 rounded text-xs transition shadow-md active:scale-98"
        >
          <span>{isSubmitting ? "CALIBRATING ENGINES..." : "COMPLETE SETUP & INITIALIZE KUANTRA TERMINAL"}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};