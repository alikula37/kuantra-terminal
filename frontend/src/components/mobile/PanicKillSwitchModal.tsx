import React, { useState, useEffect } from "react";
import { AlertOctagon, ShieldAlert, Lock, Unlock, Zap, X } from "lucide-react";
import { apiUrl } from "../../lib/backend";

interface PanicStatus {
  is_locked_down: boolean;
  lockdown_reason?: string;
  lockdown_timestamp?: number;
}

interface PanicKillSwitchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PanicKillSwitchModal: React.FC<PanicKillSwitchModalProps> = ({ isOpen, onClose }) => {
  const [panicStatus, setPanicStatus] = useState<PanicStatus>({ is_locked_down: false });
  const [disarmPin, setDisarmPin] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchStatus = () => {
    fetch(apiUrl("/api/v1/panic/status"))
      .then((res) => res.json())
      .then((data) => setPanicStatus(data))
      .catch(() => {});
  };

  useEffect(() => {
    if (isOpen) fetchStatus();
  }, [isOpen]);

  const triggerPanic = async () => {
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      const res = await fetch(apiUrl("/api/v1/panic/trigger"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source: "DESKTOP_PANIC_MODAL",
          reason: "Manual 1-Tap Emergency Position Flattening & Lockdown",
        }),
      });
      const data = await res.json();
      setPanicStatus({
        is_locked_down: true,
        lockdown_reason: data.reason,
        lockdown_timestamp: data.timestamp,
      });
    } catch (e) {
      setErrorMsg("Failed to trigger emergency kill-switch.");
    } finally {
      setIsProcessing(false);
    }
  };

  const disarmPanic = async () => {
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      const res = await fetch(apiUrl("/api/v1/panic/disarm"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin_or_passkey: disarmPin }),
      });
      if (res.ok) {
        setPanicStatus({ is_locked_down: false });
        setDisarmPin("");
      } else {
        setErrorMsg("Invalid Security PIN or Hardware Passkey challenge.");
      }
    } catch (e) {
      setErrorMsg("Error disarming terminal.");
    } finally {
      setIsProcessing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 font-mono select-none">
      <div className="bg-[#0d121c] border border-rose-500/50 rounded-xl w-full max-w-lg overflow-hidden shadow-2xl space-y-4 p-5">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-surface-border pb-3">
          <div className="flex items-center space-x-2 text-rose-500 font-bold text-sm">
            <AlertOctagon className="w-5 h-5 animate-pulse" />
            <span>EMERGENCY WEARABLE PANIC KILL-SWITCH</span>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {errorMsg && (
          <div className="bg-rose-500/10 border border-rose-500 text-rose-300 p-2 rounded text-xs">
            {errorMsg}
          </div>
        )}

        {/* Active Lockdown Status */}
        {panicStatus.is_locked_down ? (
          <div className="bg-rose-500/15 border border-rose-500 p-4 rounded-lg space-y-3">
            <div className="flex items-center space-x-2 text-rose-400 font-bold text-xs">
              <Lock className="w-4 h-4 text-rose-500" />
              <span>TERMINAL IN READ-ONLY LOCKDOWN</span>
            </div>
            <p className="text-xs text-slate-300">
              All broker trading tokens are revoked. All active positions have been flattened at market price.
            </p>

            <div className="space-y-2 pt-2">
              <span className="text-[10px] text-slate-400 block">ENTER DISARM PIN (Default: 1234):</span>
              <div className="flex items-center space-x-2">
                <input
                  type="password"
                  value={disarmPin}
                  onChange={(e) => setDisarmPin(e.target.value)}
                  placeholder="Master PIN..."
                  className="flex-1 bg-[#111722] border border-surface-border text-white px-3 py-1.5 rounded text-xs focus:outline-none focus:border-gain"
                />
                <button
                  onClick={disarmPanic}
                  disabled={isProcessing || !disarmPin}
                  className="bg-gain hover:bg-emerald-400 text-black font-bold px-4 py-1.5 rounded text-xs flex items-center space-x-1 transition"
                >
                  <Unlock className="w-3.5 h-3.5" />
                  <span>DISARM</span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-2 text-xs text-slate-300">
              <div className="flex items-center space-x-2 font-bold text-amber-400">
                <ShieldAlert className="w-4 h-4" />
                <span>INSTANT POSITION FLATTEN PROTOCOL</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Activating the Emergency Kill-Switch executes immediate market exit for all open trades across Binance Futures, OKX V5, and CME FIX DMA, cancels all pending limits, and locks trading.
              </p>
            </div>

            <button
              onClick={triggerPanic}
              disabled={isProcessing}
              className="w-full bg-rose-600 hover:bg-rose-500 text-white font-black py-4 rounded-lg shadow-lg hover:shadow-rose-600/30 flex items-center justify-center space-x-2 text-sm tracking-wider uppercase transition animate-pulse"
            >
              <Zap className="w-5 h-5 fill-white" />
              <span>{isProcessing ? "FLATTENING ALL POSITIONS..." : "TRIGGER 1-TAP EMERGENCY FLATTEN"}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};