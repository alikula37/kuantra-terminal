import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar, NavTab } from "./components/Sidebar";
import { DashboardView } from "./components/DashboardView";
import { JournalView } from "./components/JournalView";
import { TradeReplayCanvas } from "./components/TradeReplayCanvas";
import { PlaybookManager } from "./components/PlaybookManager";
import { ExecutionDriftVisualizer } from "./components/ExecutionDriftVisualizer";
import { PsychologyView } from "./components/PsychologyView";
import { AiCoachPanel } from "./components/AiCoachPanel";
import { AnalyticsView } from "./components/AnalyticsView";
import { MaeMfeVisualizer } from "./components/MaeMfeVisualizer";
import { PropFirmShield } from "./components/PropFirmShield";
import { PivotGrid } from "./components/PivotGrid";
import { SettingsView } from "./components/SettingsView";
import { NewTradeModal } from "./components/NewTradeModal";
import { ChartVisionUploader } from "./components/ChartVisionUploader";
import { useWebSocket } from "./hooks/useWebSocket";

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [replayTradeId, setReplayTradeId] = useState<string>("TRD-DEFAULT");
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isVisionModalOpen, setIsVisionModalOpen] = useState<boolean>(false);

  useWebSocket();

  const handleLaunchReplay = (tradeId: string) => {
    setReplayTradeId(tradeId);
    setActiveTab("replay");
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0e14] text-slate-100 overflow-hidden select-none">
      <Header
        onOpenNewTrade={() => setIsModalOpen(true)}
        onOpenVisionUploader={() => setIsVisionModalOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === "dashboard" && <DashboardView />}
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
          {activeTab === "ai_coach" && <AiCoachPanel />}
          {activeTab === "analytics" && <AnalyticsView />}
          {activeTab === "mae_mfe" && <MaeMfeVisualizer />}
          {activeTab === "prop_shield" && <PropFirmShield />}
          {activeTab === "pivot_grid" && <PivotGrid />}
          {activeTab === "settings" && <SettingsView />}
        </main>
      </div>

      <NewTradeModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
      <ChartVisionUploader isOpen={isVisionModalOpen} onClose={() => setIsVisionModalOpen(false)} />
    </div>
  );
}