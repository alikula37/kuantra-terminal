import React from "react";
import {
  PlusCircle,
  Zap,
  Camera,
  Sun,
  Moon,
  Globe,
  Cpu,
  Key
} from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useTranslation, SUPPORTED_LOCALES, Locale } from "../context/I18nContext";
import { usePluginRegistry } from "../context/PluginRegistryContext";
import { ExtensionSlot } from "./plugins/ExtensionSlot";

interface HeaderProps {
  onOpenNewTrade: () => void;
  onOpenVisionUploader?: () => void;
  onOpenGPUTelemetry?: () => void;
  onOpenPersonaSelector?: () => void;
  onOpenInitialBalanceModal?: () => void;
  onOpenApiKeySettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onOpenNewTrade,
  onOpenVisionUploader,
  onOpenGPUTelemetry,
  onOpenPersonaSelector,
  onOpenApiKeySettings
}) => {
  const { theme, toggleTheme } = useTheme();
  const { locale, setLocale, t } = useTranslation();
  const { activePersona, isLiteMode, isPluginActive } = usePluginRegistry();

  return (
    <header className="h-14 border-b border-surface-border bg-[#0d121c] flex items-center justify-between gap-3 px-4 select-none shrink-0">
      {/* Left: Brand Identity */}
      <div className="flex items-center space-x-2 min-w-0">
        <div className="w-7 h-7 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm shrink-0">
          K
        </div>
        <div className="flex flex-col min-w-0">
          <span className="font-bold text-sm tracking-wide text-slate-100 leading-none truncate">
            {isLiteMode ? "KUANTRA LITE" : "KUANTRA"}
          </span>
          <span className="k-help leading-none mt-0.5 truncate">
            {isLiteMode ? t("header.disciplined_core") : t("header.quant_terminal")}
          </span>
        </div>
      </div>

      {/* Right: Controls, Personas & Actions */}
      <div className="flex items-center space-x-2 shrink-0">
        {/* Dynamic Plugin Header Extension Slots */}
        <ExtensionSlot slot="header" />

        {/* Prominent Persona Preset Badge */}
        {onOpenPersonaSelector && (
          <button
            onClick={onOpenPersonaSelector}
            className="flex items-center space-x-1.5 bg-gradient-to-r from-accent/20 to-blue-600/20 hover:from-accent/30 hover:to-blue-600/30 border border-accent/40 text-accent px-3 py-2 rounded-md text-sm font-bold transition shadow-sm hover:shadow-accent/10 active:scale-95 cursor-pointer"
            title={t("header.change_persona")}
          >
            <Zap className="w-4 h-4 text-accent animate-pulse" />
            <span className="uppercase tracking-wide">
              {isLiteMode ? "LITE" : activePersona.replace("kuantra_", "").toUpperCase()}
            </span>
          </button>
        )}

        {/* Language Selector */}
        <div className="flex items-center space-x-1 bg-[#111722] px-2 py-1.5 rounded border border-surface-border text-sm text-slate-300">
          <Globe className="w-4 h-4 text-accent" />
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            aria-label={t("header.language")}
            className="bg-transparent border-none text-white text-sm focus:outline-none cursor-pointer"
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
          className="p-2 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 hover:text-white rounded transition cursor-pointer"
          title={t(theme === "dark" ? "header.switch_to_light_theme" : "header.switch_to_dark_theme")}
          aria-label={t(theme === "dark" ? "header.switch_to_light_theme" : "header.switch_to_dark_theme")}
        >
          {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-accent" />}
        </button>

        {/* Exchange API Key Configuration Trigger */}
        {onOpenApiKeySettings && (
          <button
            onClick={onOpenApiKeySettings}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-slate-300 hover:text-white px-2.5 py-2 rounded text-sm transition cursor-pointer"
            title={t("exchange.header_btn")}
          >
            <Key className="w-4 h-4 text-accent" />
            <span className="font-bold">{t("exchange.header_btn")}</span>
          </button>
        )}

        {/* GPU Acceleration Telemetry Trigger - Only visible if plugin_ai_swarm is active */}
        {!isLiteMode && isPluginActive("plugin_ai_swarm") && onOpenGPUTelemetry && (
          <button
            onClick={onOpenGPUTelemetry}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-purple-400 hover:text-purple-300 px-2.5 py-2 rounded text-sm transition cursor-pointer"
            title={t("header.gpu_telemetry")}
          >
            <Cpu className="w-4 h-4 text-purple-400" />
            <span className="font-bold">GPU</span>
          </button>
        )}

        {isPluginActive("plugin_ai_swarm") && onOpenVisionUploader && (
          <button
            onClick={onOpenVisionUploader}
            className="flex items-center space-x-1.5 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white text-sm px-3 py-2 rounded transition cursor-pointer"
            title={t("dashboard.upload_chart_btn")}
          >
            <Camera className="w-4 h-4 text-accent" />
            <span>{t("dashboard.upload_chart_btn")}</span>
          </button>
        )}

        {/* Primary Trade Entry Action Button */}
        <button
          onClick={onOpenNewTrade}
          className="flex items-center space-x-1.5 bg-accent hover:bg-sky-400 text-black font-bold text-sm px-3 py-2 rounded transition shadow-md hover:shadow-cyan-500/20 active:scale-95 cursor-pointer"
        >
          <PlusCircle className="w-4 h-4" />
          <span>{t("header.new_trade_btn")}</span>
        </button>
      </div>
    </header>
  );
};
