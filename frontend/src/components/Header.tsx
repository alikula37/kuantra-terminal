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
    <header className="h-14 border-b border-surface-border bg-surface flex items-center justify-between gap-3 px-4 select-none shrink-0 font-sans">
      {/* Left: Brand Identity */}
      <div className="flex items-center space-x-2 min-w-0">
        <div className="w-7 h-7 rounded k-primary flex items-center justify-center font-black text-sm shrink-0">
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
            className="k-btn k-nav-active transition shadow-sm active:scale-95"
            title={t("header.change_persona")}
          >
            <Zap className="w-4 h-4 text-accent animate-pulse" />
            <span className="uppercase tracking-wide">
              {isLiteMode ? "LITE" : activePersona.replace("kuantra_", "").toUpperCase()}
            </span>
          </button>
        )}

        {/* Language Selector */}
        <div className="flex items-center space-x-1 bg-elevated px-2 rounded border border-surface-border text-sm text-ink">
          <Globe className="w-4 h-4 text-accent" />
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            aria-label={t("header.language")}
            className="k-btn bg-transparent border-none text-ink !px-1 cursor-pointer"
          >
            {SUPPORTED_LOCALES.map((loc) => (
              <option key={loc.id} value={loc.id} className="bg-surface text-ink">
                {loc.id.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        {/* Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          className="k-btn k-control !px-3 transition"
          title={t(theme === "dark" ? "header.switch_to_light_theme" : "header.switch_to_dark_theme")}
          aria-label={t(theme === "dark" ? "header.switch_to_light_theme" : "header.switch_to_dark_theme")}
        >
          {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-accent" />}
        </button>

        {/* Exchange API Key Configuration Trigger */}
        {onOpenApiKeySettings && (
          <button
            onClick={onOpenApiKeySettings}
            className="k-btn k-control transition"
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
          className="k-btn k-primary transition shadow-md active:scale-95"
        >
          <PlusCircle className="w-4 h-4" />
          <span>{t("header.new_trade_btn")}</span>
        </button>
      </div>
    </header>
  );
};
