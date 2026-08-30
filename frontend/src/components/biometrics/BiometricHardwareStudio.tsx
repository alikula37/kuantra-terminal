import React, { useState, useEffect } from "react";
import { Activity, Heart, ShieldAlert, Key, Zap, Bluetooth, Battery, RefreshCw, CheckCircle2 } from "lucide-react";

export const BiometricHardwareStudio: React.FC = () => {
  const [telemetry, setTelemetry] = useState<any>(null);
  const [devices, setDevices] = useState<any[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("POLAR-H10-8849");
  const [overrideMsg, setOverrideMsg] = useState<string | null>(null);

  // Manual test stress controls for demo/simulation
  const [simBpm, setSimBpm] = useState<number>(72);
  const [simEda, setSimEda] = useState<number>(2.5);

  const fetchTelemetry = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/v1/biometrics/live-telemetry?bpm=${simBpm}&eda=${simEda}`);
      const data = await res.json();
      setTelemetry(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchDevices = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/biometrics/devices");
      const data = await res.json();
      setDevices(data.devices || []);
      if (data.active_device_id) {
        setSelectedDeviceId(data.active_device_id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDevices();
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 2500);
    return () => clearInterval(interval);
  }, [simBpm, simEda]);

  const handleConnectDevice = async (devId: string, proto: string) => {
    try {
      await fetch("http://127.0.0.1:8000/api/v1/biometrics/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: devId, protocol: proto }),
      });
      setSelectedDeviceId(devId);
      fetchDevices();
      setOverrideMsg(`Connected to ${devId} via ${proto}`);
      setTimeout(() => setOverrideMsg(null), 3500);
    } catch (e) {
      console.error(e);
    }
  };

  const handleFIDO2Override = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/biometrics/override-lockout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge_signature: "FIDO2_WEBAUTHN_ENCLAVE_SIGNED_SIG99042",
          passkey_user_id: "INSTITUTIONAL_CHIEF_TRADER",
        }),
      });
      await res.json();
      setOverrideMsg(`Lockout Override Approved by FIDO2 Passkey! State reset to NOMINAL.`);
      // Reset sliders to calm
      setSimBpm(68);
      setSimEda(2.0);
      fetchTelemetry();
      setTimeout(() => setOverrideMsg(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const sBio = telemetry ? telemetry.s_bio : 40.0;
  const isLockout = telemetry?.lockout_state === "CRITICAL_TILT_LOCKOUT" || telemetry?.lockout_state === "PANIC_EMERGENCY";

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4 text-slate-100">
      {/* Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <Activity className="w-5 h-5 text-accent" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              HARDWARE BIOMETRICS & PHYSIOLOGICAL TILT INTERCEPTOR
            </h2>
          </div>
          <p className="text-xs text-slate-400">
            BLE GATT Polar H10 &bull; Empatica E4 EDA &bull; Real-Time HRV RMSSD &bull; FIDO2 Hardware Lockout
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {isLockout && (
            <button
              onClick={handleFIDO2Override}
              className="flex items-center space-x-1.5 bg-amber-500 hover:bg-amber-400 text-black font-bold px-3 py-1.5 rounded text-xs transition shadow"
            >
              <Key className="w-3.5 h-3.5" />
              <span>FIDO2 PASSKEY OVERRIDE</span>
            </button>
          )}

          <button
            onClick={() => {
              fetchDevices();
              fetchTelemetry();
            }}
            className="p-1.5 bg-[#0d121c] hover:bg-[#111722] border border-surface-border rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Override / Action Alert */}
      {overrideMsg && (
        <div className="bg-accent/10 border border-accent/30 p-3 rounded-lg flex items-center space-x-2 text-accent text-xs">
          <CheckCircle2 className="w-4 h-4 text-accent" />
          <span>{overrideMsg}</span>
        </div>
      )}

      {/* Critical Lockout Banner */}
      {isLockout && (
        <div className="bg-loss/20 border border-loss p-4 rounded-lg flex items-center justify-between text-white">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-loss/30 rounded-full animate-pulse">
              <ShieldAlert className="w-6 h-6 text-loss" />
            </div>
            <div>
              <span className="text-sm font-bold text-loss block">CRITICAL BIOMETRIC TILT LOCKOUT ACTIVE</span>
              <p className="text-xs text-slate-300">
                Stress Score (S_bio: {sBio}) breached safety threshold (75.0). All DMA/FIX/DEX order execution is locked.
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-xl font-bold text-loss font-mono">
              {Math.floor((telemetry?.lockout_remaining_seconds || 900) / 60)}:
              {String((telemetry?.lockout_remaining_seconds || 900) % 60).padStart(2, "0")}
            </span>
            <span className="text-[10px] text-slate-400 block">COOLDOWN REMAINING</span>
          </div>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1">
        {/* LEFT COLUMN: LIVE PULSE & S_BIO RADAR */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Heart className="w-4 h-4 text-rose-500 animate-pulse" />
              <span>LIVE BIOMETRIC RADAR</span>
            </span>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
              sBio < 60 ? "bg-gain/20 text-gain" : sBio < 75 ? "bg-amber-500/20 text-amber-400" : "bg-loss/20 text-loss"
            }`}>
              {telemetry?.lockout_state || "NOMINAL"}
            </span>
          </div>

          {/* S_bio Score Radial Widget */}
          <div className="flex flex-col items-center justify-center p-6 bg-[#090d14] rounded-lg border border-surface-border relative">
            <div className={`text-4xl font-bold font-mono ${
              sBio < 60 ? "text-gain" : sBio < 75 ? "text-amber-400" : "text-loss animate-pulse"
            }`}>
              {sBio}
            </div>
            <span className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">
              COMPOSITE STRESS (S_bio / 100)
            </span>

            <div className="w-full bg-[#111722] h-2 rounded-full mt-4 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  sBio < 60 ? "bg-gain" : sBio < 75 ? "bg-amber-400" : "bg-loss"
                }`}
                style={{ width: `${sBio}%` }}
              />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="bg-[#111722] p-3 rounded border border-surface-border">
              <span className="text-slate-400 text-[10px] block">HEART RATE</span>
              <span className="text-xl font-bold text-rose-400 font-mono">{telemetry?.bpm || 72} BPM</span>
            </div>
            <div className="bg-[#111722] p-3 rounded border border-surface-border">
              <span className="text-slate-400 text-[10px] block">HRV (RMSSD)</span>
              <span className="text-xl font-bold text-accent font-mono">{telemetry?.rmssd_ms || 45.2} ms</span>
            </div>
            <div className="bg-[#111722] p-3 rounded border border-surface-border">
              <span className="text-slate-400 text-[10px] block">EDA CONDUCTANCE</span>
              <span className="text-xl font-bold text-purple-400 font-mono">{telemetry?.eda_microsiemens || 2.4} μS</span>
            </div>
            <div className="bg-[#111722] p-3 rounded border border-surface-border">
              <span className="text-slate-400 text-[10px] block">SIGNAL QUALITY (SQI)</span>
              <span className="text-xl font-bold text-gain font-mono">{telemetry?.signal_quality_pct || 98.5}%</span>
            </div>
          </div>
        </div>

        {/* CENTER COLUMN: LIVE SIMULATOR & STRESS CONTROL */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
          <span className="text-xs font-bold text-white flex items-center space-x-1.5 border-b border-surface-border pb-2">
            <Zap className="w-4 h-4 text-accent" />
            <span>PHYSIOLOGICAL STRESS STIMULATOR & TEST BENCH</span>
          </span>

          <div className="space-y-4 text-xs">
            <div>
              <div className="flex justify-between text-slate-300 text-[11px] mb-1">
                <span>Simulated Heart Rate:</span>
                <span className="text-rose-400 font-bold font-mono">{simBpm} BPM</span>
              </div>
              <input
                type="range"
                min="50"
                max="140"
                value={simBpm}
                onChange={(e) => setSimBpm(Number(e.target.value))}
                className="w-full h-1.5 bg-[#111722] rounded-lg appearance-none cursor-pointer accent-rose-500"
              />
            </div>

            <div>
              <div className="flex justify-between text-slate-300 text-[11px] mb-1">
                <span>Simulated EDA Skin Conductance:</span>
                <span className="text-purple-400 font-bold font-mono">{simEda} μS</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="25.0"
                step="0.5"
                value={simEda}
                onChange={(e) => setSimEda(Number(e.target.value))}
                className="w-full h-1.5 bg-[#111722] rounded-lg appearance-none cursor-pointer accent-purple-400"
              />
            </div>

            <div className="bg-[#111722] p-3 rounded border border-surface-border space-y-2">
              <span className="font-bold text-white text-[11px] block">STRESS FACTOR BREAKDOWN</span>
              <div className="space-y-1.5 text-[10px] font-mono text-slate-400">
                <div className="flex justify-between">
                  <span>HRV Parasympathetic Index (40%):</span>
                  <span className="text-accent font-bold">{telemetry?.components?.hrv_stress_component || 0} / 100</span>
                </div>
                <div className="flex justify-between">
                  <span>Elevated BPM Factor (35%):</span>
                  <span className="text-rose-400 font-bold">{telemetry?.components?.bpm_stress_component || 0} / 100</span>
                </div>
                <div className="flex justify-between">
                  <span>EDA Sympathetic Surge (25%):</span>
                  <span className="text-purple-400 font-bold">{telemetry?.components?.eda_arousal_component || 0} / 100</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => {
                  setSimBpm(62);
                  setSimEda(1.8);
                }}
                className="bg-gain/20 hover:bg-gain text-gain hover:text-black font-bold py-2 rounded text-[10px] transition"
              >
                SET CALM BASELINE
              </button>
              <button
                onClick={() => {
                  setSimBpm(118);
                  setSimEda(19.2);
                }}
                className="bg-loss/20 hover:bg-loss text-loss hover:text-white font-bold py-2 rounded text-[10px] transition"
              >
                TRIGGER CRITICAL TILT
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: HARDWARE WEARABLES MANAGER */}
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3 flex flex-col">
          <div className="flex items-center justify-between border-b border-surface-border pb-2">
            <span className="text-xs font-bold text-white flex items-center space-x-1.5">
              <Bluetooth className="w-4 h-4 text-accent" />
              <span>DETECTED WEARABLE HARDWARE</span>
            </span>
            <span className="text-[10px] text-slate-400">{devices.length} Devices</span>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto text-xs">
            {devices.map((dev) => {
              const isSelected = selectedDeviceId === dev.device_id;
              return (
                <div
                  key={dev.device_id}
                  onClick={() => handleConnectDevice(dev.device_id, dev.protocol)}
                  className={`p-3 rounded-lg border cursor-pointer transition flex items-center justify-between ${
                    isSelected
                      ? "bg-accent/15 border-accent/40 text-white"
                      : "bg-[#111722] border-surface-border text-slate-300 hover:bg-[#151c2a]"
                  }`}
                >
                  <div className="space-y-0.5">
                    <div className="font-bold flex items-center space-x-1.5">
                      <span>{dev.name}</span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      <span>ID: {dev.device_id} &bull; {dev.protocol}</span>
                    </div>
                  </div>

                  <div className="text-right flex flex-col items-end space-y-1">
                    <span className="text-[10px] flex items-center space-x-1 text-gain">
                      <Battery className="w-3.5 h-3.5" />
                      <span>{dev.battery_pct}%</span>
                    </span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      isSelected ? "bg-accent text-black" : "bg-[#090d14] text-slate-400"
                    }`}>
                      {isSelected ? "PAIRED" : "CONNECT"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};