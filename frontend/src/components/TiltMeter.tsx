import React, { useState, useEffect } from "react";
import { TiltStatusResponse } from "../types";
import { Brain, AlertCircle, CheckCircle2 } from "lucide-react";

export const TiltMeter: React.FC = () => {
  const [tilt, setTilt] = useState<TiltStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchTilt = () => {
    fetch("http://127.0.0.1:8000/api/v1/psychology/tilt-status")
      .then((res) => res.json())
      .then((data: TiltStatusResponse) => {
        setTilt(data);
        setIsLoading(false);
      })
      .catch(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchTilt();
    const interval = setInterval(fetchTilt, 4000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !tilt) {
    return <div className="p-4 text-center text-slate-500 font-mono text-xs">Calibrating Tilt Meter...</div>;
  }

  const score = tilt.tilt_score;
  const isHighRisk = score >= 60;
  const isCritical = score >= 80;

  const colorClass = isCritical
    ? "text-rose-500 border-rose-500/40 bg-rose-950/20"
    : isHighRisk
    ? "text-amber-400 border-amber-500/40 bg-amber-950/20"
    : score >= 30
    ? "text-yellow-300 border-yellow-500/40 bg-yellow-950/20"
    : "text-emerald-400 border-emerald-500/40 bg-emerald-950/20";

  return (
    <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border font-mono select-none space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Brain className={`w-4 h-4 ${isHighRisk ? "text-rose-400 animate-pulse" : "text-purple-400"}`} />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            ALGORITHMIC TILT & EMOTION SHIELD
          </span>
        </div>

        <div className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colorClass}`}>
          {tilt.status}
        </div>
      </div>

      {/* Main Score Bar & Gauge */}
      <div className="space-y-1.5">
        <div className="flex items-end justify-between">
          <span className="text-[11px] text-slate-400 font-semibold">SESSION TILT SCORE</span>
          <span className="text-2xl font-black text-white">
            {score} <span className="text-xs font-normal text-slate-500">/ 100</span>
          </span>
        </div>

        <div className="w-full bg-[#111722] rounded-full h-3 overflow-hidden border border-surface-border p-0.5">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isCritical
                ? "bg-gradient-to-r from-amber-500 to-rose-600 animate-pulse"
                : isHighRisk
                ? "bg-gradient-to-r from-yellow-500 to-amber-500"
                : score >= 30
                ? "bg-gradient-to-r from-emerald-500 to-yellow-400"
                : "bg-emerald-500"
            }`}
            style={{ width: `${Math.max(5, Math.min(100, score))}%` }}
          />
        </div>

        <div className="flex justify-between text-[9px] text-slate-500">
          <span>0 (CALM)</span>
          <span>30 (ELEVATED)</span>
          <span>60 (HIGH TILT)</span>
          <span>100 (BLOWUP RISK)</span>
        </div>
      </div>

      {/* Directive Coach Message */}
      <div className={`p-2.5 rounded border text-[11px] ${colorClass}`}>
        <div className="flex items-start space-x-2">
          {isHighRisk ? (
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400 mt-0.5" />
          ) : (
            <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-400 mt-0.5" />
          )}
          <span className="leading-tight text-slate-200">{tilt.risk_message}</span>
        </div>
      </div>

      {/* Behavioral Breakdown Indicators */}
      <div className="grid grid-cols-4 gap-2 text-center text-xs pt-1">
        <div className="bg-[#111722] p-2 rounded border border-surface-border">
          <span className="text-[9px] text-slate-500 block">LOSS STREAK</span>
          <span className={`font-bold ${tilt.consecutive_losses >= 2 ? "text-loss" : "text-slate-200"}`}>
            {tilt.consecutive_losses}
          </span>
        </div>

        <div className="bg-[#111722] p-2 rounded border border-surface-border">
          <span className="text-[9px] text-slate-500 block">REVENGE ENTRIES</span>
          <span className={`font-bold ${tilt.revenge_trades_count > 0 ? "text-loss" : "text-gain"}`}>
            {tilt.revenge_trades_count}
          </span>
        </div>

        <div className="bg-[#111722] p-2 rounded border border-surface-border">
          <span className="text-[9px] text-slate-500 block">FOMO CHASES</span>
          <span className={`font-bold ${tilt.fomo_trades_count > 0 ? "text-amber-400" : "text-slate-200"}`}>
            {tilt.fomo_trades_count}
          </span>
        </div>

        <div className="bg-[#111722] p-2 rounded border border-surface-border">
          <span className="text-[9px] text-slate-500 block">LOT ESCALATION</span>
          <span className={`font-bold ${tilt.lot_escalation_detected ? "text-loss" : "text-gain"}`}>
            {tilt.lot_escalation_detected ? "YES" : "NO"}
          </span>
        </div>
      </div>
    </div>
  );
};