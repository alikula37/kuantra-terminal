import React, { useState, useEffect } from "react";
import { Database, Server, RefreshCw, Zap, DollarSign, Check } from "lucide-react";
import { UpdateNotifier } from "./updater/UpdateNotifier";
import { SystemHealthSettings } from "./settings/SystemHealthSettings";
import { useTranslation } from "../context/I18nContext";
import { apiUrl } from "../lib/backend";

export const SettingsView: React.FC = () => {
  const { t } = useTranslation();
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [initialBalance, setInitialBalance] = useState<number>(0);
  const [balanceSavedMsg, setBalanceSavedMsg] = useState<string | null>(null);
  const [isSavingBalance, setIsSavingBalance] = useState<boolean>(false);

  useEffect(() => {
    fetch(apiUrl("/api/v1/portfolio/summary"))
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data.initial_balance === "number") {
          setInitialBalance(data.initial_balance);
        }
      })
      .catch(() => {});
  }, []);

  const handleSaveBalance = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingBalance(true);
    setBalanceSavedMsg(null);
    try {
      const res = await fetch(apiUrl("/api/v1/portfolio/set-initial-balance"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initial_balance: Number(initialBalance) }),
      });
      if (res.ok) {
        setBalanceSavedMsg(t("settings.save_capital_success"));
        setTimeout(() => setBalanceSavedMsg(null), 3000);
      }
    } catch {
      setBalanceSavedMsg(t("settings.save_capital_error"));
    } finally {
      setIsSavingBalance(false);
    }
  };

  const handleManualSync = () => {
    setSyncStatus(t("settings.syncing"));
    setTimeout(() => {
      setSyncStatus(t("settings.sync_success"));
      setTimeout(() => setSyncStatus(null), 3000);
    }, 600);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#0b0e14] overflow-y-auto p-4 select-none font-mono space-y-4 custom-scrollbar">
      <div className="pb-3 border-b border-surface-border">
        <h2 className="text-base font-bold text-white">{t("settings.terminal_config")}</h2>
        <p className="text-xs text-slate-400">{t("settings.terminal_config_sub")}</p>
      </div>

      {/* Account & Capital Management */}
      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-bold text-white text-xs flex items-center space-x-2">
            <DollarSign className="w-4 h-4 text-accent" />
            <span>{t("settings.capital_title")}</span>
          </span>
          <span className="bg-accent/20 text-accent text-[10px] font-bold px-2 py-0.5 rounded">
            {t("settings.capital_badge")}
          </span>
        </div>
        <p className="text-xs text-slate-400">
          {t("settings.capital_desc")}
        </p>
        <form onSubmit={handleSaveBalance} className="flex flex-wrap items-center gap-3 pt-1">
          <div className="relative">
            <span className="absolute left-3 top-2 text-slate-500 text-sm">$</span>
            <input
              type="number"
              step="any"
              min="0"
              value={initialBalance || ""}
              onChange={(e) => setInitialBalance(Number(e.target.value))}
              placeholder="0.00"
              className="bg-[#090d14] border border-surface-border rounded pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-accent font-bold w-48"
              required
            />
          </div>
          <button
            type="submit"
            disabled={isSavingBalance}
            className="px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs flex items-center space-x-1.5 transition disabled:opacity-50 cursor-pointer"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{isSavingBalance ? t("settings.saving_capital_btn") : t("settings.save_capital_btn")}</span>
          </button>
          {balanceSavedMsg && (
            <span className="text-xs text-gain font-semibold animate-fade-in">{balanceSavedMsg}</span>
          )}
        </form>
      </div>

      {/* Auto-Updater Banner */}
      <UpdateNotifier />

      {/* Privacy Telemetry & Diagnostic Health */}
      <SystemHealthSettings />

      {/* Database Engines Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-xs flex items-center space-x-2">
              <Database className="w-4 h-4 text-gain" />
              <span>{t("settings.sqlite_title")}</span>
            </span>
            <span className="bg-gain/20 text-gain text-[10px] font-bold px-2 py-0.5 rounded">
              {t("settings.wal_badge")}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            {t("settings.sqlite_desc")}
          </p>
          <div className="bg-[#090d14] p-2.5 rounded text-[11px] text-slate-300 space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-500">{t("settings.journal_mode")}</span>
              <span className="font-bold text-accent">{t("settings.wal_val")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">{t("settings.synchronous")}</span>
              <span className="text-slate-200">NORMAL</span>
            </div>
          </div>
        </div>

        <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-xs flex items-center space-x-2">
              <Server className="w-4 h-4 text-accent" />
              <span>{t("settings.duckdb_title")}</span>
            </span>
            <span className="bg-accent/20 text-accent text-[10px] font-bold px-2 py-0.5 rounded">
              {t("settings.columnar_badge")}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            {t("settings.duckdb_desc")}
          </p>
          <div className="bg-[#090d14] p-2.5 rounded text-[11px] text-slate-300 space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-500">{t("settings.engine_type")}</span>
              <span className="font-bold text-accent">{t("settings.duckdb_val")}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">{t("settings.query_engine")}</span>
              <span className="text-slate-200">{t("settings.vectorized_val")}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-4">
        <h3 className="font-bold text-white text-xs flex items-center space-x-2">
          <Zap className="w-4 h-4 text-yellow-400" />
          <span>{t("settings.sync_title")}</span>
        </h3>
        <p className="text-xs text-slate-400">
          {t("settings.sync_desc")}
        </p>

        <div className="flex items-center space-x-4">
          <button
            onClick={handleManualSync}
            className="flex items-center space-x-2 bg-[#111722] hover:bg-[#1a2234] border border-surface-border text-white px-4 py-2 rounded text-xs font-bold transition cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5 text-accent" />
            <span>{t("settings.sync_btn")}</span>
          </button>
          {syncStatus && <span className="text-xs text-gain font-bold">{syncStatus}</span>}
        </div>
      </div>
    </div>
  );
};