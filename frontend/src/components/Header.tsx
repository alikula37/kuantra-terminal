import React, { useState, useEffect } from "react";
import { 
  PlusCircle, 
  Zap, 
  Camera, 
  Sun, 
  Moon, 
  Globe, 
  Cpu, 
  Wallet, 
  ShieldAlert, 
  Calendar 
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useTranslation, SUPPORTED_LOCALES, Locale } from "../context/I18nContext";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { useMarketStore } from "../stores/marketStore";
import { ExtensionSlot } from "./plugins/ExtensionSlot";

interface PortfolioSummary {
  initial_balance: number;
  total_equity: number;
  net_pnl: number;
  net_pnl_pct: number;
  today_pnl: number;
  today_pnl_pct: number;
  today_trades_count: { wins: number; losses: number; total: number };
  open_risk_usd: number;
  open_risk_r: number;
  active_positions_count: number;
  win_rate: number;
  profit_factor: number;
}

interface HeaderProps {
  onOpenNewTrade: () => void;
  onOpenVisionUploader?: () => void;
  onOpenGPUTelemetry?: () => void;
  onOpenPersonaSelector?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ 
  onOpenNewTrade, 
  onOpenVisionUploader, 
  onOpenGPUTelemetry,
  onOpenPersonaSelector 
}) => {
  const { latencyMs } = useMarketStore();
  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, t } = useTranslation();
  const { activePersona, isLiteMode, isPluginActive } = usePluginRegistry();

  const [portfolio, setPortfolio] = useState<PortfolioSummary>({
    initial_balance: 100000.0,
    total_equity: 100000.0,
    net_pnl: 0.0,
    net_pnl_pct: 0.0,
    today_pnl: 0.0,
    today_pnl_pct: 0.0,
    today_trades_count: { wins: 0, losses: 0, total: 0 },
    open_risk_usd: 0.0,
    open_risk_r: 0.0,
    active_positions_count: 0,
    win_rate: 0.0,
    profit_factor: 0.0
  });

  const fetchPortfolioSummary = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/api/v1/portfolio/summary");
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch (err) {
      // Backend sidecar booting, keep existing state
    }
  };

  useEffect(() => {
    fetchPortfolioSummary();
    const interval = setInterval(fetchPortfolioSummary, 4000);
    return () => clearInterval(interval);
  }, []);

  const isNetPnlPositive = portfolio.net_pnl >= 0;
  const isTodayPnlPositive = portfolio.today_pnl >= 0;

  return (
    <header className="h-14 border-b border-surface-border bg-[#0d121c] flex items-center justify-between px-4 select-none shrink-0">
      {/* Left: Brand Identity */}
      <div className="flex items-center space-x-5">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm">
            K
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-sm tracking-wider text-slate-100 font-mono leading-none">
              {isLiteMode ? "KUANTRA LITE" : "KUANTRA"}
            </span>
            <span className="text-[9px] text-accent font-mono tracking-widest leading-none mt-0.5">
              {isLiteMode ? "DISCIPLINED CORE" : "QUANT TERMINAL"}
            </span>
          </div>
        </div>

        <div className="h-6 w-[1px] bg-surface-border" />

        {/* Portfolio-First Live Telemetry Strip */}
        <div className="flex items-center space-x-4 font-mono text-xs">
          {/* 1. Total Equity & Net PnL */}
          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1 rounded border border-surface-border">
            <Wallet className="w-3.5 h-3.5 text-accent" />
            <div className="flex flex-col">
              <span className="text-[9px] text-slate-500 font-semibold leading-tight">TOPLAM KASA</span>
              <div className="flex items-baseline space-x-1.5 leading-tight">
                <span className="text-white font-bold text-xs">
                  ${portfolio.total_equity.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className={`text-[10px] font-bold ${isNetPnlPositive ? "text-gain" : "text-loss"}`}>
                  {isNetPnlPositive ? "+" : ""}${portfolio.net_pnl.toFixed(2)} ({isNetPnlPositive ? "+" : ""}{portfolio.net_pnl_pct.toFixed(1)}%)
                </span>
              </div>
            </div>
          </div>

          {/* 2. Open Position Risk Exposure */}
          <div className="hidden sm:flex items-center space-x-2 bg-[#111722] px-3 py-1 rounded border border-surface-border">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            <div className="flex flex-col">
              <span className="text-[9px] text-slate-500 font-semibold leading-tight">AÇIK RİSK (EXPOSURE)</span>
              <div className="flex items-baseline space-x-1.5 leading-tight">
                <span className="text-amber-400 font-bold text-xs">
                  {portfolio.open_risk_r.toFixed(1)}R (${portfolio.open_risk_usd.toFixed(2)})
                </span>
                <span className="text-[10px] text-slate-400">
                  | {portfolio.active_positions_count} Pozisyon
                </span>
              </div>
            </div>
          </div>

          {/* 3. Today's Performance */}
          <div className="hidden md:flex items-center space-x-2 bg-[#111722] px-3 py-1 rounded border border-surface-border">
            <Calendar className="w-3.5 h-3.5 text-sky-400" />
            <div className="flex flex-col">
              <span className="text-[9px] text-slate-500 font-semibold leading-tight">BUGÜN (REALIZED)</span>
              <div className="flex items-baseline space-x-1.5 leading-tight">
                <span className={`font-bold text-xs ${isTodayPnlPositive ? "text-gain" : "text-loss"}`}>
                  {isTodayPnlPositive ? "+" : ""}${portfolio.today_pnl.toFixed(2)}
                </span>
                <span className="text-[10px] text-slate-400">
                  ({portfolio.today_trades_count.wins}W / {portfolio.today_trades_count.losses}L)
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Controls, Personas & Actions */}
      <div className="flex items-center space-x-3">
        {/* Dynamic Plugin Header Extension Slots */}
        <ExtensionSlot slot="header" />

        {/* Prominent Persona Preset Badge */}
        {onOpenPersonaSelector && (
          <button
            onClick={onOpenPersonaSelector}
            className="flex items-center space-x-1.5 bg-gradient-to-r from-accent/20 to-blue-600/20 hover:from-accent/30 hover:to-blue-600/30 border border-accent/40 text-accent px-3 py-1 rounded-md text-xs font-mono font-bold transition shadow-sm hover:shadow-accent/10 active:scale-95"
            title="Mimari Modu & Persona Değiştir (ModStore)"
          >
            <Zap className="w-3.5 h-3.5 text-accent animate-pulse" />
            <span className="uppercase text-[11px] font-extrabold tracking-wide">
              {isLiteMode ? "⚡ LITE MODE" : `⚡ ${activePersona.replace("kuantra_", "").toUpperCase()} MODE`}
            </span>
            <span className="text-[10px] text-slate-400 font-normal ml-0.5">| Değiştir</span>
          </button>
        )}

        {/* Language Selector */}
        <div className="flex items-center space-x-1 bg-[#111722] px-2 py-1 rounded border border-surface-border text-xs font-mono text-slate-300">
          <Globe className="w-3.5 h-3.5 text-accent" />
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            className="bg-transparent border-none text-white text-xs focus:outline-none cursor-pointer"
          >
            {SUPPORTED_LOCALES.map((loc) => (
              <option key={loc.id} value={loc.id} className="bg-[#0d121c] text-white">
                {loc.id.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="p-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 hover:text-white rounded transition"
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Theme`}
        >
          {theme === "dark" ? <Sun className="w-3.5 h-3.5 text-amber-400" /> : <Moon className="w-3.5 h-3.5 text-accent" />}
        </button>

        {/* GPU Acceleration Telemetry Trigger - Only visible if plugin_ai_swarm is active */}
        {!isLiteMode && isPluginActive("plugin_ai_swarm") && onOpenGPUTelemetry && (
          <button
            onClick={onOpenGPUTelemetry}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-purple-400 hover:text-purple-300 px-2.5 py-1 rounded text-xs font-mono transition"
            title="Open Local GPU Acceleration & Telemetry Studio"
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="font-bold">GPU</span>
          </button>
        )}

        {/* Latency & Connectivity */}
        <div className="flex items-center space-x-1.5 bg-[#111722] px-2.5 py-1 rounded border border-surface-border text-xs font-mono">
          <Zap className="w-3.5 h-3.5 text-accent" />
          <span className="text-slate-400">LAT:</span>
          <span className="text-accent font-bold">{latencyMs}ms</span>
        </div>

        {!isLiteMode && onOpenVisionUploader && (
          <button
            onClick={onOpenVisionUploader}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-xs px-3 py-1.5 rounded transition"
            title="Upload Chart Screenshot for Vision OCR"
          >
            <Camera className="w-3.5 h-3.5 text-accent" />
            <span>{t("dashboard.upload_chart_btn")}</span>
          </button>
        )}

        {/* Primary Trade Entry Action Button */}
        <button
          onClick={onOpenNewTrade}
          className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold text-xs px-3 py-1.5 rounded transition shadow-md hover:shadow-cyan-500/20 active:scale-95"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>+ Manuel İşlem Girişi</span>
        </button>
      </div>
    </header>
  );
};