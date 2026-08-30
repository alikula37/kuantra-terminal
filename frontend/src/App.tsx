import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar, NavTab } from "./components/Sidebar";
import { DashboardView } from "./components/DashboardView";
import { JournalView } from "./components/JournalView";
import { AnalyticsView } from "./components/AnalyticsView";
import { MaeMfeVisualizer } from "./components/MaeMfeVisualizer";
import { PropFirmShield } from "./components/PropFirmShield";
import { PivotGrid } from "./components/PivotGrid";
import { SettingsView } from "./components/SettingsView";
import { NewTradeModal } from "./components/NewTradeModal";
import { useWebSocket } from "./hooks/useWebSocket";

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  useWebSocket();

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0e14] text-slate-100 overflow-hidden select-none">
      <Header onOpenNewTrade={() => setIsModalOpen(true)} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === "dashboard" && <DashboardView />}
          {activeTab === "journal" && <JournalView onOpenNewTrade={() => setIsModalOpen(true)} />}
          {activeTab === "analytics" && <AnalyticsView />}
          {activeTab === "mae_mfe" && <MaeMfeVisualizer />}
          {activeTab === "prop_shield" && <PropFirmShield />}
          {activeTab === "pivot_grid" && <PivotGrid />}
          {activeTab === "settings" && <SettingsView />}
        </main>
      </div>

      <NewTradeModal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </div>
  );
}