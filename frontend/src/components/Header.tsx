import React, { useState, useEffect } from "react";
import { Radio, PlusCircle, Zap, Camera, Sun, Moon, Globe, Cpu } from "lucide-react";
import { useMarketStore } from "../stores/marketStore";
import { useTheme } from "../context/ThemeContext";
import { useTranslation, SUPPORTED_LOCALES, Locale } from "../context/I18nContext";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { ExtensionSlot } from "./plugins/ExtensionSlot";

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
  const { symbol, currentPrice, prevPrice, latencyMs, isConnected } = useMarketStore();
  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, t } = useTranslation();
  const { activePersona } = usePluginRegistry();
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (currentPrice > prevPrice) {
      setPriceFlash("up");
    } else if (currentPrice < prevPrice) {
      setPriceFlash("down");
    }
    const timer = setTimeout(() => setPriceFlash(null), 300);
    return () => clearTimeout(timer);
  }, [currentPrice, prevPrice]);

  return (
    <header className="h-14 border-b border-surface-border bg-[#0d121c] flex items-center justify-between px-4 select-none">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <div className="w-7 h-7 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm">
            K
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-sm tracking-wider text-slate-100 font-mono leading-none">
              KUANTRA
            </span>
            <span className="text-[9px] text-accent font-mono tracking-widest leading-none mt-0.5">
              TERMINAL v2.0
            </span>
          </div>
        </div>

        <div className="h-6 w-[1px] bg-surface-border" />

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-[#111722] px-3 py-1 rounded border border-surface-border">
            <span className="font-bold text-xs text-white font-mono">{symbol}</span>
            <span className="text-[10px] text-slate-500 font-mono">SPOT</span>
          </div>

          <div className="flex items-baseline space-x-2">
            <span
              className={`text-lg font-bold font-mono transition-colors duration-150 ${
                priceFlash === "up"
                  ? "text-gain"
                  : priceFlash === "down"
                  ? "text-loss"
                  : "text-white"
              }`}
            >
              ${currentPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className="text-xs font-mono text-gain font-semibold">+2.45%</span>
          </div>
        </div>
      </div>

      <div className="hidden lg:flex items-center space-x-6 text-xs font-mono text-slate-400">
        <div>
          <span className="text-[10px] text-slate-500 block">24H HIGH</span>
          <span className="text-slate-200">{(currentPrice * 1.03).toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 block">24H LOW</span>
          <span className="text-slate-200">{(currentPrice * 0.96).toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 block">24H VOL (USDT)</span>
          <span className="text-slate-200">1.48B</span>
        </div>
      </div>

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
              {activePersona === "kuantra_lite" ? "⚡ LITE MODE" : `⚡ ${activePersona.replace("kuantra_", "").toUpperCase()} MODE`}
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

        {/* GPU Acceleration Telemetry Trigger */}
        {onOpenGPUTelemetry && (
          <button
            onClick={onOpenGPUTelemetry}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-purple-400 hover:text-purple-300 px-2.5 py-1 rounded text-xs font-mono transition"
            title="Open Local GPU Acceleration & Telemetry Studio"
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span className="font-bold">GPU</span>
          </button>
        )}

        <div className="flex items-center space-x-1.5 bg-[#111722] px-2.5 py-1 rounded border border-surface-border text-xs font-mono">
          <Zap className="w-3.5 h-3.5 text-accent" />
          <span className="text-slate-400">LAT:</span>
          <span className="text-accent font-bold">{latencyMs}ms</span>
        </div>

        <div
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono border ${
            isConnected
              ? "bg-gain/10 border-gain/30 text-gain"
              : "bg-amber-500/10 border-amber-500/30 text-amber-400"
          }`}
        >
          <Radio className={`w-3.5 h-3.5 ${isConnected ? "animate-pulse text-gain" : "text-amber-400"}`} />
          <span className="text-[11px] font-semibold">{isConnected ? "LIVE FEED" : "SIMULATED"}</span>
        </div>

        {onOpenVisionUploader && (
          <button
            onClick={onOpenVisionUploader}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-xs px-3 py-1.5 rounded transition"
            title="Upload Chart Screenshot for Vision OCR"
          >
            <Camera className="w-3.5 h-3.5 text-accent" />
            <span>{t("dashboard.upload_chart_btn")}</span>
          </button>
        )}

        <button
          onClick={onOpenNewTrade}
          className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold text-xs px-3 py-1.5 rounded transition shadow-md hover:shadow-cyan-500/20 active:scale-95"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>{t("dashboard.new_trade_btn")}</span>
        </button>
      </div>
    </header>
  );
};