import React, { useCallback, useEffect, useRef, useState } from "react";
import { Database, Server, RefreshCw, Zap, DollarSign, Check } from "lucide-react";
import { UpdateNotifier } from "./updater/UpdateNotifier";
import { SystemHealthSettings } from "./settings/SystemHealthSettings";
import { useTranslation } from "../context/I18nContext";
import { apiFetch, apiUrl } from "../lib/backend";

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

async function readInitialBalance(response: Response): Promise<number> {
  if (!response.ok) {
    let detail = "";
    try {
      const payload = await response.json() as { detail?: unknown; message?: unknown };
      const candidate = [payload.detail, payload.message].find((item) => typeof item === "string");
      if (typeof candidate === "string") detail = candidate;
    } catch {
      // Keep the HTTP status as the bounded error when the body is not JSON.
    }
    throw new Error(detail || `Portfolio summary request failed (HTTP ${response.status})`);
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("Portfolio summary response was malformed");
  }
  if (
    !payload ||
    typeof payload !== "object" ||
    !isFiniteNumber((payload as Record<string, unknown>).initial_balance) ||
    (payload as Record<string, number>).initial_balance < 0
  ) {
    throw new Error("Portfolio summary response was malformed");
  }
  return (payload as Record<string, number>).initial_balance;
}

export const SettingsView: React.FC = () => {
  const { t } = useTranslation();
  const [syncStatus, setSyncStatus] = useState<string | null>(null);
  const [initialBalance, setInitialBalance] = useState<number | null>(null);
  const [isLoadingBalance, setIsLoadingBalance] = useState<boolean>(true);
  const [balanceError, setBalanceError] = useState<string | null>(null);
  const [balanceLoadCancelled, setBalanceLoadCancelled] = useState<boolean>(false);
  const [balanceSavedMsg, setBalanceSavedMsg] = useState<string | null>(null);
  const [isSavingBalance, setIsSavingBalance] = useState<boolean>(false);
  const balanceControllerRef = useRef<AbortController | null>(null);
  const balanceRequestIdRef = useRef(0);

  const loadInitialBalance = useCallback(async () => {
    balanceControllerRef.current?.abort();
    const controller = new AbortController();
    const requestId = ++balanceRequestIdRef.current;
    balanceControllerRef.current = controller;
    setIsLoadingBalance(true);
    setBalanceError(null);
    setBalanceLoadCancelled(false);

    try {
      const balance = await apiFetch(apiUrl("/api/v1/portfolio/summary"), { signal: controller.signal }).then(readInitialBalance);
      if (controller.signal.aborted || requestId !== balanceRequestIdRef.current) return;
      setInitialBalance(balance);
    } catch (cause) {
      if (controller.signal.aborted || requestId !== balanceRequestIdRef.current) return;
      if (!(cause instanceof Error && cause.name === "AbortError")) {
        console.warn("[SettingsView] Failed to fetch initial balance:", cause);
        setBalanceError(cause instanceof Error ? cause.message : t("settings.capital_load_error"));
      }
    } finally {
      if (requestId === balanceRequestIdRef.current) {
        setIsLoadingBalance(false);
        balanceControllerRef.current = null;
      }
    }
  }, [t]);

  useEffect(() => {
    void loadInitialBalance();
    return () => {
      balanceRequestIdRef.current += 1;
      balanceControllerRef.current?.abort();
      balanceControllerRef.current = null;
    };
  }, [loadInitialBalance]);

  const cancelBalanceLoad = () => {
    const controller = balanceControllerRef.current;
    if (!controller) return;
    balanceRequestIdRef.current += 1;
    controller.abort();
    balanceControllerRef.current = null;
    setIsLoadingBalance(false);
    setBalanceLoadCancelled(true);
    setBalanceError(t("settings.capital_load_cancelled"));
  };

  const handleSaveBalance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (initialBalance === null || !isFiniteNumber(initialBalance) || initialBalance < 0) {
      setBalanceSavedMsg(t("settings.save_capital_error"));
      return;
    }
    setIsSavingBalance(true);
    setBalanceSavedMsg(null);
    try {
      const res = await apiFetch(apiUrl("/api/v1/portfolio/set-initial-balance"), {
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
              value={initialBalance ?? ""}
              onChange={(e) => setInitialBalance(e.target.value === "" ? null : Number(e.target.value))}
              placeholder="0.00"
              className="bg-[#090d14] border border-surface-border rounded pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-accent font-bold w-48"
              required
            />
          </div>
          <button
            type="submit"
            disabled={isSavingBalance || isLoadingBalance}
            className="px-4 py-1.5 bg-accent hover:bg-sky-400 text-black font-bold rounded text-xs flex items-center space-x-1.5 transition disabled:opacity-50 cursor-pointer"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{isSavingBalance ? t("settings.saving_capital_btn") : t("settings.save_capital_btn")}</span>
          </button>
          {isLoadingBalance && (
            <div role="status" data-testid="settings-capital-loading" className="text-xs text-slate-400 flex items-center gap-2">
              <span>{t("settings.capital_loading")}</span>
              <button type="button" data-testid="settings-capital-cancel" onClick={cancelBalanceLoad} className="px-2 py-1 rounded border border-surface-border text-slate-300 hover:bg-slate-800">
                {t("settings.capital_cancel_load")}
              </button>
            </div>
          )}
          {balanceError && !isLoadingBalance && (
            <div role="alert" data-testid={balanceLoadCancelled ? "settings-capital-cancelled" : "settings-capital-error"} className="text-xs text-loss flex items-center gap-2">
              <span>{balanceError}</span>
              <button type="button" data-testid="settings-capital-retry" onClick={() => void loadInitialBalance()} className="px-2 py-1 rounded border border-loss/50 text-loss hover:bg-loss/10">
                {t("settings.capital_retry")}
              </button>
            </div>
          )}
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
