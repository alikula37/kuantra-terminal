import { useState, useEffect, useMemo, lazy, Suspense } from "react";
import { Header } from "./components/Header";
import { Sidebar, NavTab } from "./components/Sidebar";
import { DashboardView } from "./components/DashboardView";
import { JournalView } from "./components/JournalView";
import { ModuleLoadingSkeleton } from "./components/layout/ModuleLoadingSkeleton";
import { useWebSocket } from "./hooks/useWebSocket";
import { usePopoutWindow } from "./hooks/usePopoutWindow";
import { usePluginRegistry } from "./context/PluginRegistryContext";

// Lazy-loaded Studio & Advanced Analysis Modules for Lite Mode bundle isolation
const VirtualizedTradeJournal = lazy(() =>
  import("./components/virtual/VirtualizedTradeJournal").then((m) => ({ default: m.VirtualizedTradeJournal }))
);
const DockLayoutView = lazy(() =>
  import("./components/layout/DockLayoutView").then((m) => ({ default: m.DockLayoutView }))
);
const WorkspacePresetSelector = lazy(() =>
  import("./components/workspace/WorkspacePresetSelector").then((m) => ({ default: m.WorkspacePresetSelector }))
);
const BiometricHardwareStudio = lazy(() =>
  import("./components/biometrics/BiometricHardwareStudio").then((m) => ({ default: m.BiometricHardwareStudio }))
);
const FIXOrderBookStudio = lazy(() =>
  import("./components/fix/FIXOrderBookStudio").then((m) => ({ default: m.FIXOrderBookStudio }))
);
const DEXArbitrageStudio = lazy(() =>
  import("./components/dex/DEXArbitrageStudio").then((m) => ({ default: m.DEXArbitrageStudio }))
);
const MCPDataExplorer = lazy(() =>
  import("./components/mcp/MCPDataExplorer").then((m) => ({ default: m.MCPDataExplorer }))
);
const ReverseSkillStudio = lazy(() =>
  import("./components/studio/ReverseSkillStudio").then((m) => ({ default: m.ReverseSkillStudio }))
);
const MobileCompanionHUD = lazy(() =>
  import("./components/mobile/MobileCompanionHUD").then((m) => ({ default: m.MobileCompanionHUD }))
);
const MeshNetworkHUD = lazy(() =>
  import("./components/p2p/MeshNetworkHUD").then((m) => ({ default: m.MeshNetworkHUD }))
);
const CopyTradingMatrix = lazy(() =>
  import("./components/p2p/CopyTradingMatrix").then((m) => ({ default: m.CopyTradingMatrix }))
);
const FootprintChart = lazy(() =>
  import("./components/orderflow/FootprintChart").then((m) => ({ default: m.FootprintChart }))
);
const FixStatusWidget = lazy(() =>
  import("./components/orderflow/FixStatusWidget").then((m) => ({ default: m.FixStatusWidget }))
);
const TradeReplayCanvas = lazy(() =>
  import("./components/TradeReplayCanvas").then((m) => ({ default: m.TradeReplayCanvas }))
);
const PlaybookManager = lazy(() =>
  import("./components/PlaybookManager").then((m) => ({ default: m.PlaybookManager }))
);
const ExecutionDriftVisualizer = lazy(() =>
  import("./components/ExecutionDriftVisualizer").then((m) => ({ default: m.ExecutionDriftVisualizer }))
);
const PsychologyView = lazy(() =>
  import("./components/PsychologyView").then((m) => ({ default: m.PsychologyView }))
);
const WearableBiometricsHUD = lazy(() =>
  import("./components/biometrics/WearableBiometricsHUD").then((m) => ({ default: m.WearableBiometricsHUD }))
);
const AiCoachPanel = lazy(() =>
  import("./components/AiCoachPanel").then((m) => ({ default: m.AiCoachPanel }))
);
const SwarmDebateVisualizer = lazy(() =>
  import("./components/ai/SwarmDebateVisualizer").then((m) => ({ default: m.SwarmDebateVisualizer }))
);
const AnalyticsView = lazy(() =>
  import("./components/AnalyticsView").then((m) => ({ default: m.AnalyticsView }))
);
const MaeMfeVisualizer = lazy(() =>
  import("./components/MaeMfeVisualizer").then((m) => ({ default: m.MaeMfeVisualizer }))
);
const PropFirmShield = lazy(() =>
  import("./components/PropFirmShield").then((m) => ({ default: m.PropFirmShield }))
);
const PivotGrid = lazy(() =>
  import("./components/PivotGrid").then((m) => ({ default: m.PivotGrid }))
);
const SettingsView = lazy(() =>
  import("./components/SettingsView").then((m) => ({ default: m.SettingsView }))
);
const TradingViewChart = lazy(() =>
  import("./components/TradingViewChart").then((m) => ({ default: m.TradingViewChart }))
);
const ModStoreStudio = lazy(() =>
  import("./components/plugins/ModStoreStudio").then((m) => ({ default: m.ModStoreStudio }))
);

// Lazy-loaded Modals
const NewTradeModal = lazy(() =>
  import("./components/NewTradeModal").then((m) => ({ default: m.NewTradeModal }))
);
const InitialBalanceModal = lazy(() =>
  import("./components/modals/InitialBalanceModal").then((m) => ({ default: m.InitialBalanceModal }))
);
const CsvImportModal = lazy(() =>
  import("./components/modals/CsvImportModal").then((m) => ({ default: m.CsvImportModal }))
);
const ApiKeySettingsModal = lazy(() =>
  import("./components/modals/ApiKeySettingsModal").then((m) => ({ default: m.ApiKeySettingsModal }))
);
const ChartVisionUploader = lazy(() =>
  import("./components/ChartVisionUploader").then((m) => ({ default: m.ChartVisionUploader }))
);
const FirstBootWizard = lazy(() =>
  import("./components/onboarding/FirstBootWizard").then((m) => ({ default: m.FirstBootWizard }))
);
const GPUTelemetryModal = lazy(() =>
  import("./components/hardware/GPUTelemetryModal").then((m) => ({ default: m.GPUTelemetryModal }))
);
const PersonaSelectorModal = lazy(() =>
  import("./components/onboarding/PersonaSelectorModal").then((m) => ({ default: m.PersonaSelectorModal }))
);

export default function App() {
  const { isLiteMode } = usePluginRegistry();
  const [activeTab, setActiveTab] = useState<NavTab>("dashboard");
  const [activePreset, setActivePreset] = useState<string>("day_trader");
  const [replayTradeId, setReplayTradeId] = useState<string>("TRD-DEFAULT");
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isCsvModalOpen, setIsCsvModalOpen] = useState<boolean>(false);
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState<boolean>(false);
  const [isVisionModalOpen, setIsVisionModalOpen] = useState<boolean>(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState<boolean>(false);
  const [isGPUModalOpen, setIsGPUModalOpen] = useState<boolean>(false);
  const [isPersonaModalOpen, setIsPersonaModalOpen] = useState<boolean>(false);
  const [isInitialBalanceModalOpen, setIsInitialBalanceModalOpen] = useState<boolean>(false);

  useWebSocket();
  const { popout } = usePopoutWindow();

  useEffect(() => {
    // 1. Check if user has selected an architectural persona on first boot
    const savedPersona = localStorage.getItem("kuantra_selected_persona");
    if (!savedPersona) {
      setIsPersonaModalOpen(true);
    }

    // 2. Check general onboarding wizard status
    fetch("http://127.0.0.1:8000/api/v1/onboarding/status")
      .then((res) => res.json())
      .then((data) => {
        if (!data.first_boot_completed && savedPersona) {
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
          <Suspense fallback={<ModuleLoadingSkeleton moduleName={popoutParam} />}>
            {popoutParam === "chart" && <DashboardView />}
            {popoutParam === "modstore" && <ModStoreStudio onOpenPersonaSelector={() => setIsPersonaModalOpen(true)} />}
            {popoutParam === "biometrics_studio" && <BiometricHardwareStudio />}
            {popoutParam === "fix_studio" && <FIXOrderBookStudio />}
            {popoutParam === "dex_arbitrage" && <DEXArbitrageStudio />}
            {popoutParam === "mcp_explorer" && <MCPDataExplorer />}
            {popoutParam === "reverse_skill" && <ReverseSkillStudio />}
            {popoutParam === "mobile_companion" && <MobileCompanionHUD />}
            {popoutParam === "p2p_mesh" && <MeshNetworkHUD />}
            {popoutParam === "copy_trading" && <CopyTradingMatrix />}
            {popoutParam === "orderflow" && <FootprintChart />}
            {popoutParam === "fix_dma" && <FixStatusWidget />}
            {popoutParam === "virtual_journal" && <VirtualizedTradeJournal onReplayTrade={handleLaunchReplay} />}
            {popoutParam === "ai_coach" && <AiCoachPanel />}
            {popoutParam === "swarm" && <SwarmDebateVisualizer />}
            {popoutParam === "psychology" && <PsychologyView />}
            {popoutParam === "biometrics" && <WearableBiometricsHUD />}
            {popoutParam === "analytics" && <AnalyticsView />}
          </Suspense>
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
    popout("biometrics_studio", "Biometric Hardware Studio", 1200, 800);
    popout("fix_studio", "L2/L3 DOM & FIX Studio", 1200, 800);
    popout("dex_arbitrage", "DEX Arbitrage Studio", 1200, 800);
    popout("mcp_explorer", "Financial MCP Explorer", 1200, 800);
    popout("reverse_skill", "Reverse-Skill Studio", 1200, 800);
    popout("virtual_journal", "60 FPS Virtual Audit Log", 1000, 650);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#0b0e14] text-slate-100 overflow-hidden select-none">
      <Header
        onOpenNewTrade={() => setIsModalOpen(true)}
        onOpenVisionUploader={() => setIsVisionModalOpen(true)}
        onOpenGPUTelemetry={() => setIsGPUModalOpen(true)}
        onOpenPersonaSelector={() => setIsPersonaModalOpen(true)}
        onOpenInitialBalanceModal={() => setIsInitialBalanceModalOpen(true)}
        onOpenApiKeySettings={() => setIsApiKeyModalOpen(true)}
      />

      {!isLiteMode && (
        <Suspense fallback={<div className="h-9 bg-[#0d121c] border-b border-surface-border animate-pulse" />}>
          <WorkspacePresetSelector
            currentPreset={activePreset}
            onSelectPreset={handlePresetSelect}
            onPopoutAll={handlePopoutAll}
            onResetLayout={() => handlePresetSelect("day_trader")}
          />
        </Suspense>
      )}

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

        <main className="flex-1 flex flex-col overflow-hidden">
          {activeTab === "dashboard" && (
            <DashboardView
              onOpenNewTrade={() => setIsModalOpen(true)}
              onOpenInitialBalanceModal={() => setIsInitialBalanceModalOpen(true)}
            />
          )}
          {activeTab === "journal" && (
            <JournalView
              onOpenNewTrade={() => setIsModalOpen(true)}
              onOpenCsvImport={() => setIsCsvModalOpen(true)}
              onReplayTrade={handleLaunchReplay}
            />
          )}

          <Suspense fallback={<ModuleLoadingSkeleton moduleName={activeTab} />}>
            {activeTab === "charts" && (
              <div className="flex-1 flex flex-col overflow-hidden bg-[#0b0e14]">
                <TradingViewChart />
              </div>
            )}
            {activeTab === "modstore" && <ModStoreStudio onOpenPersonaSelector={() => setIsPersonaModalOpen(true)} />}
            {activeTab === "biometrics_studio" && <BiometricHardwareStudio />}
            {activeTab === "fix_studio" && <FIXOrderBookStudio />}
            {activeTab === "dex_arbitrage" && <DEXArbitrageStudio />}
            {activeTab === "mcp_explorer" && <MCPDataExplorer />}
            {activeTab === "reverse_skill" && <ReverseSkillStudio />}
            {activeTab === "mobile_companion" && <MobileCompanionHUD />}
            {activeTab === "p2p_mesh" && <MeshNetworkHUD />}
            {activeTab === "copy_trading" && <CopyTradingMatrix />}
            {activeTab === "orderflow" && <FootprintChart />}
            {activeTab === "fix_dma" && <FixStatusWidget />}
            {activeTab === "docking" && <DockLayoutView onPopoutWindow={popout} />}
            {activeTab === "virtual_journal" && (
              <VirtualizedTradeJournal
                onOpenNewTrade={() => setIsModalOpen(true)}
                onOpenCsvImport={() => setIsCsvModalOpen(true)}
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
          </Suspense>
        </main>
      </div>

      <Suspense fallback={null}>
        {isModalOpen && (
          <NewTradeModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onOpenApiKeySettings={() => setIsApiKeyModalOpen(true)}
          />
        )}
        {isCsvModalOpen && <CsvImportModal isOpen={isCsvModalOpen} onClose={() => setIsCsvModalOpen(false)} />}
        {isApiKeyModalOpen && (
          <ApiKeySettingsModal isOpen={isApiKeyModalOpen} onClose={() => setIsApiKeyModalOpen(false)} />
        )}
        {isInitialBalanceModalOpen && (
          <InitialBalanceModal isOpen={isInitialBalanceModalOpen} onClose={() => setIsInitialBalanceModalOpen(false)} />
        )}
        {isVisionModalOpen && <ChartVisionUploader isOpen={isVisionModalOpen} onClose={() => setIsVisionModalOpen(false)} />}
        {isOnboardingOpen && <FirstBootWizard isOpen={isOnboardingOpen} onCompleted={() => setIsOnboardingOpen(false)} />}
        {isGPUModalOpen && <GPUTelemetryModal isOpen={isGPUModalOpen} onClose={() => setIsGPUModalOpen(false)} />}
        {isPersonaModalOpen && <PersonaSelectorModal isOpen={isPersonaModalOpen} onClose={() => setIsPersonaModalOpen(false)} />}
      </Suspense>
    </div>
  );
}