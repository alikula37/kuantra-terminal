import React from "react";
import { TiltMeter } from "./TiltMeter";
import { FomoDetectorCard } from "./FomoDetectorCard";
import { FatigueHeatmap } from "./FatigueHeatmap";
import { Brain } from "lucide-react";

export const PsychologyView: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4">
      {/* View Header */}
      <div className="pb-3 border-b border-surface-border flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <span>ALGORITHMIC TRADING PSYCHOLOGY & TILT ENGINE</span>
          </h2>
          <p className="text-xs text-slate-400">
            Real-time Cognitive Biases, FOMO Detection, Revenge Trading Guardian & Fatigue Heatmap
          </p>
        </div>
      </div>

      {/* Primary Grid: Tilt Meter + FOMO Detector */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TiltMeter />
        <FomoDetectorCard />
      </div>

      {/* Secondary Grid: Mental Fatigue & Overtrading Sequence Heatmap */}
      <div className="w-full">
        <FatigueHeatmap />
      </div>
    </div>
  );
};