import { useState, useEffect, useMemo } from "react";
import { Header } from "./components/Header";
import { Sidebar, NavTab } from "./components/Sidebar";
import { DashboardView } from "./components/DashboardView";
import { JournalView } from "./components/JournalView";
import { VirtualizedTradeJournal } from "./components/virtual/VirtualizedTradeJournal";
import { DockLayoutView } from "./components/layout/DockLayoutView";
import { WorkspacePresetSelector } from "./components/workspace/WorkspacePresetSelector";
import { TradeReplayCanvas } from "./components/TradeReplayCanvas";
import { PlaybookManager } from "./components/PlaybookManager";
import { ExecutionDriftVisualizer } from "./components/ExecutionDriftVisualizer";
import { PsychologyView } from "./components/PsychologyView";
import { WearableBiometricsHUD } from "./components/biometrics/WearableBiometricsHUD";
import { AiCoachPanel } from "./components/AiCoachPanel";
import { SwarmDebateVisualizer } from "./components/ai/SwarmDebateVisualizer";
import { AnalyticsView } from "./components/AnalyticsView";
import { MaeMfeVisualizer } from "./components/MaeMfeVisualizer";
import { PropFirmShield } from "./components/PropFirmShield";
import { PivotGrid } from "./components/PivotGrid";
import { SettingsView } from "./components/SettingsView";
import { NewTradeModal } from "./components/NewTradeModal";
import { ChartVisionUploader } from "./components/ChartVisionUploader";
import { FirstBootWizard } from "./components/onboarding/FirstBootWizard";
import { useWebSocket } from "./hooks/useWebSocket";
import { usePopoutWindow } from "./hooks/usePopoutWindow";

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [activePreset, setActivePreset] = useState<string>("day_trader");
  const [replayTradeId, setReplayTradeId] = useState<string>("TRD-DEFAULT");
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isVisionModalOpen, setIsVisionModalOpen] = useState<boolean>(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState<boolean>(false);

  useWebSocket();
  const { popout } = usePopoutWindow();

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/v1/onboarding/status")
      .then((res) => res.json())
      .then((data) => {
        if (!data.first_boot_completed) {
          setIsOnboardingOpen(true);
        }
      })
      .catch(() => {});
  }, []);

  // Check if current window instance is a popped-out sub-window
  const popoutParam = useMemo(() => {
    if (typeof window !== "undefined") {
      return new URLSearchParams(window.location.search).get("popout");
    }
    return null;
  }, []);

  const handleLaunchReplay = (tradeId: string) => {
    setReplayTradeId(tradeId);
    setActiveTab("replay");
  };

  // If detached pop-out window, render target subcomponent in full screen
  if (popoutParam) {
    return (
      <div className="h-screen w-screen bg-[#0b0e14] text-slate-100 flex flex-col font-mono select-none overflow-hidden">
        <div className="h-8 bg-[#0d121c] border-b border-surface-border px-3 flex items-center justify-between text-[11px]">
          <span className="text-accent font-bold">KUANTRA DETACHED MONITOR ({popoutParam.toUpperCase()})</span>
          <span className="text-slate-500 text-[10px]">Tauri Multi-Screen Sync Active</span>
        </div>
        <div className="flex-1 overflow-hidden">
          {popoutParam === "chart" && <DashboardView />}
          {popoutParam === "virtual_journal" && <VirtualizedTradeJournal onReplayTrade={handleLaunchReplay} />}
          {popoutParam === "ai_coach" && <AiCoachPanel />}
          {popoutParam === "swarm" && <SwarmDebateVisualizer />}
          {popoutParam === "psychology" && <PsychologyView />}
          {popoutParam === "biometrics" && <WearableBiometricsHUD />}
          {popoutParam === "analytics" && <AnalyticsView />}
        </div>
      </div>
    );
  }

  const handlePresetSelect = (presetId: string) => {
    setActivePreset(presetId);
    if (presetId === "day_trader") setActiveTab("dashboard");
    else if (presetId === "docking") setActiveTab("docking");
    else if (presetId === "ai_focus") setActiveTab("swarm");
    else if (presetId === "quant_lab") setActiveTab("analytics");
  };

  const handlePopoutAll = () => {
    popout("chart", "Live Chart Monitor", 1200, 800);
    popout("virtual_journal", "60 FPS Virtual Audit Log", 1000, 650);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0e14] text-slate-100 overflow-hidden select-none">
      <Header
        onOpenNewTrade={() => setIsModalOpen(true)}
        onOpenVisionUploader={() => setIsVisionModalOpen(true)}
      />

      <WorkspacePresetSelector
        currentPreset={activePreset}
        onSelectPreset={handlePresetSelect}
        onPopoutAll={handlePopoutAll}
        onResetLayout={() => handlePresetSelect("day_trader")}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === "dashboard" && <DashboardView />}
          {activeTab === "docking" && <DockLayoutView onPopoutWindow={popout} />}
          {activeTab === "virtual_journal" && (
            <VirtualizedTradeJournal
              onOpenNewTrade={() => setIsModalOpen(true)}
              onReplayTrade={handleLaunchReplay}
            />
          )}
          {activeTab === "journal" && (
            <JournalView
              onOpenNewTrade={() => setIsModalOpen(true)}
              onReplayTrade={handleLaunchReplay}
            />
          )}
          {activeTab === "replay" && <TradeReplayCanvas tradeId={replayTradeId} />}
          {activeTab === "playbook" && <PlaybookManager />}
          {activeTab === "drift" && <ExecutionDriftVisualizer />}
          {activeTab === "psychology" && <PsychologyView />}
          {activeTab === "biometrics" && <WearableBiometricsHUD />}
          {activeTab === "ai_coach" && <AiCoachPanel />}
          {activeTab === "swarm" && <SwarmDebateVisualizer />}
          {activeTab === "analytics" && <AnalyticsView />}
          {activeTab === "mae_mfe" && <MaeMfeVisualizer />}
          {activeTab === "prop_shield" && <PropFirmShield />}
          {activeTab === "pivot_grid" && <PivotGrid />}
          {activeTab === "settings" && <SettingsView />}
        </main>
      </div>

      <NewTradeModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      <ChartVisionUploader isOpen={isVisionModalOpen} onClose={() => setIsVisionModalOpen(false)} />
      <FirstBootWizard isOpen={isOnboardingOpen} onCompleted={() => setIsOnboardingOpen(false)} />
    </div>
  );
}