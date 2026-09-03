import React, { useState, useEffect } from "react";
import { Activity, Heart, ShieldAlert, CheckCircle2, Bluetooth, Sliders, Zap } from "lucide-react";
import { apiUrl } from "../../lib/backend";

interface BiometricStatus {
  device_name: string;
  is_connected: boolean;
  bpm: number;
  hrv_ms: number;
  biometric_tilt_score: number;
  stress_category: string;
  risk_level: string;
  is_stress_critical: boolean;
}

export const WearableBiometricsHUD: React.FC = () => {
  const [status, setStatus] = useState<BiometricStatus>({
    device_name: "Apple Watch Ultra / BLE Bridge",
    is_connected: true,
    bpm: 68,
    hrv_ms: 70,
    biometric_tilt_score: 55.0,
    stress_category: "ELEVATED_STRESS",
    risk_level: "WARNING",
    is_stress_critical: false,
  });

  const fetchStatus = () => {
    fetch(apiUrl("/api/v1/biometrics/status"))
      .then((res) => res.json())
      .then((data: BiometricStatus) => setStatus(data))
      .catch(() => {});
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);
    return () => clearInterval(interval);
  }, []);

  const sendSimulation = (bpmVal: number, hrvVal: number) => {
    fetch(apiUrl("/api/v1/biometrics/telemetry"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bpm: bpmVal, hrv: hrvVal, device_name: "Apple Watch Ultra / BLE" }),
    })
      .then((res) => res.json())
      .then((data: BiometricStatus) => setStatus(data))
      .catch(() => {});
  };

  const isCritical = status.is_stress_critical;
  const isWarning = status.stress_category === "ELEVATED_STRESS";

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-rose-500 animate-pulse" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              BIOMETRIC WEARABLE STRESS INTERCEPTOR
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            Real-time Autonomic Nervous System & Physiological Tilt Guardian (BLE Bridge)
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-[#0d121c] border border-surface-border px-3 py-1.5 rounded-lg text-xs">
          <Bluetooth className="w-4 h-4 text-accent animate-pulse" />
          <span className="text-white font-bold">{status.device_name}</span>
          <span className="text-[10px] bg-gain/20 text-gain px-1.5 py-0.2 rounded font-bold">
            CONNECTED
          </span>
        </div>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Heart Rate BPM */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-bold flex items-center space-x-1.5">
              <Heart className={`w-4 h-4 ${isCritical ? "text-rose-500 fill-rose-500 animate-ping" : "text-rose-400"}`} />
              <span>HEART RATE (BPM)</span>
            </span>
            <span className="text-[10px] text-slate-500">Opto-Plethysmography</span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className={`text-4xl font-black ${isCritical ? "text-rose-500" : isWarning ? "text-amber-400" : "text-white"}`}>
              {status.bpm}
            </span>
            <span className="text-xs text-slate-400 font-bold">BPM</span>
          </div>

          <div className="text-[10px] text-slate-400">
            Baseline Resting: <strong>60-75 BPM</strong>
          </div>
        </div>

        {/* HRV (Heart Rate Variability) */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-xs font-bold flex items-center space-x-1.5">
              <Zap className="w-4 h-4 text-purple-400" />
              <span>HRV (RMSSD)</span>
            </span>
            <span className="text-[10px] text-slate-500">Vagal Tone</span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className={`text-4xl font-black ${status.hrv_ms < 40 ? "text-rose-500" : status.hrv_ms < 60 ? "text-amber-400" : "text-purple-400"}`}>
              {status.hrv_ms}
            </span>
            <span className="text-xs text-slate-400 font-bold">ms</span>
          </div>

          <div className="text-[10px] text-slate-400">
            Higher HRV indicates autonomic resilience & calm focus.
          </div>
        </div>

        {/* Biometric Tilt Score */}
        <div className={`p-4 rounded-lg border flex flex-col justify-between space-y-3 ${
          isCritical
            ? "bg-rose-500/10 border-rose-500 text-rose-300"
            : isWarning
            ? "bg-amber-500/10 border-amber-500 text-amber-200"
            : "bg-[#0d121c] border-surface-border text-slate-300"
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold flex items-center space-x-1.5">
              <ShieldAlert className={`w-4 h-4 ${isCritical ? "text-rose-500 animate-bounce" : "text-accent"}`} />
              <span>BIOMETRIC TILT SCORE</span>
            </span>
            <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
              isCritical
                ? "bg-rose-500 text-white"
                : isWarning
                ? "bg-amber-500 text-black"
                : "bg-gain/20 text-gain border border-gain/30"
            }`}>
              {status.stress_category.replace(/_/g, " ")}
            </span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span className="text-4xl font-black">
              {status.biometric_tilt_score}
            </span>
            <span className="text-xs font-bold text-slate-400">/ 100</span>
          </div>

          <div className="text-[10px]">
            {isCritical ? (
              <strong className="text-rose-400">CRITICAL: Order dispatch automatically VETOED by Guardrail!</strong>
            ) : isWarning ? (
              <strong className="text-amber-400">Elevated autonomic stress. Sizing warning active.</strong>
            ) : (
              <span className="text-gain">Optimal parasympathetic state for trade execution.</span>
            )}
          </div>
        </div>
      </div>

      {/* Interactive Wearable BLE Simulator Strip */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center space-x-2 text-white font-bold text-xs">
          <Sliders className="w-4 h-4 text-accent" />
          <span>PHYSIOLOGICAL TELEMETRY CALIBRATION / TEST CONTROLS</span>
        </div>
        <p className="text-[11px] text-slate-400">
          Simulate biometric stress events to test automatic order execution blocking:
        </p>

        <div className="flex items-center space-x-3 pt-2">
          <button
            onClick={() => sendSimulation(55, 88)}
            className="flex items-center space-x-1.5 bg-gain/15 hover:bg-gain/30 border border-gain/40 text-gain px-3 py-1.5 rounded text-xs font-bold transition"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>CALM FLOW (BPM 55, HRV 88ms)</span>
          </button>

          <button
            onClick={() => sendSimulation(85, 52)}
            className="flex items-center space-x-1.5 bg-amber-500/15 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 px-3 py-1.5 rounded text-xs font-bold transition"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>MODERATE STRESS (BPM 85, HRV 52ms)</span>
          </button>

          <button
            onClick={() => sendSimulation(135, 20)}
            className="flex items-center space-x-1.5 bg-rose-500/20 hover:bg-rose-500/40 border border-rose-500 text-rose-300 px-3 py-1.5 rounded text-xs font-bold transition animate-pulse"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
            <span>TRIGGER PANIC VETO (BPM 135, HRV 20ms)</span>
          </button>
        </div>
      </div>
    </div>
  );
};