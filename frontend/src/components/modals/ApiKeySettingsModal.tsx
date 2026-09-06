import React, { useState, useEffect } from "react";
import { Key, Shield, CheckCircle2, AlertTriangle, Trash2, RefreshCw, X, Eye, EyeOff } from "lucide-react";
import { useTranslation } from "../../context/I18nContext";
import { apiBase, apiFetch, apiUrl } from "../../lib/backend";

interface ApiKeySettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ExchangeConfig {
  exchange_id: string;
  name: string;
  is_configured: boolean;
  api_key_masked: string;
  requires_passphrase: boolean;
  has_passphrase: boolean;
  is_testnet: boolean;
  is_active: boolean;
  legacy_detected?: boolean;
  credentials_available?: boolean;
  storage_backend?: string;
  updated_at: string | null;
}

interface CredentialStoreStatus {
  backend: string;
  available: boolean;
  persistent: boolean;
  reason?: string | null;
}

export const ApiKeySettingsModal: React.FC<ApiKeySettingsModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();

  const [configs, setConfigs] = useState<ExchangeConfig[]>([]);
  const [credentialStoreStatus, setCredentialStoreStatus] = useState<CredentialStoreStatus | null>(null);
  const [activeTab, setActiveTab] = useState<string>("binance_futures");
  const [apiKey, setApiKey] = useState<string>("");
  const [apiSecret, setApiSecret] = useState<string>("");
  const [passphrase, setPassphrase] = useState<string>("");
  const [isTestnet, setIsTestnet] = useState<boolean>(false);
  const [showSecret, setShowSecret] = useState<boolean>(false);

  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
    free_quote_balance?: number;
    total_quote_balance?: number;
  } | null>(null);

  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const fetchConfigs = async () => {
    try {
      const res = await apiFetch(apiUrl("/api/v1/exchange/credentials"));
      if (res.ok) {
        const data = await res.json();
        setConfigs(data);
      }
    } catch {
      // Ignored
    }
  };

  const fetchCredentialStoreStatus = async () => {
    try {
      const res = await apiFetch(apiUrl("/api/v1/exchange/credentials/status"));
      if (res.ok) {
        setCredentialStoreStatus(await res.json());
      } else {
        setCredentialStoreStatus(null);
      }
    } catch {
      setCredentialStoreStatus(null);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchConfigs();
      fetchCredentialStoreStatus();
      setStatusMessage(null);
      setTestResult(null);
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const currentConfig = configs.find((c) => c.exchange_id === activeTab);
  const requiresPassphrase = activeTab === "okx";
  const canPersistCredentials = credentialStoreStatus?.available === true;

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    setStatusMessage(null);

    try {
      const payload: any = { exchange_id: activeTab };
      if (apiKey && apiSecret) {
        payload.api_key = apiKey.trim();
        payload.api_secret = apiSecret.trim();
        if (passphrase) payload.passphrase = passphrase.trim();
        payload.is_testnet = isTestnet;
      }

      const res = await apiFetch(apiUrl("/api/v1/exchange/test-connection"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setTestResult({
          success: true,
          message: data.message || t("exchange.test_success"),
          free_quote_balance: data.free_quote_balance,
          total_quote_balance: data.total_quote_balance,
        });
      } else {
        setTestResult({
          success: false,
          message: data.detail?.message || data.message || t("exchange.test_failed"),
        });
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || t("exchange.test_failed"),
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey || !apiSecret) {
      setStatusMessage({ type: "error", text: t("exchange.err_missing_fields") });
      return;
    }

    setIsSaving(true);
    setStatusMessage(null);

    try {
      const res = await apiFetch(apiUrl("/api/v1/exchange/credentials"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          exchange_id: activeTab,
          api_key: apiKey.trim(),
          api_secret: apiSecret.trim(),
          passphrase: passphrase.trim() || null,
          is_testnet: isTestnet,
        }),
      });

      if (res.ok) {
        setStatusMessage({ type: "success", text: t("exchange.save_success") });
        setApiKey("");
        setApiSecret("");
        setPassphrase("");
        fetchConfigs();
      } else {
        const err = await res.json();
        setStatusMessage({ type: "error", text: err.detail || t("exchange.save_failed") });
      }
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || t("exchange.save_failed") });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCredentials = async () => {
    if (!window.confirm(t("exchange.confirm_delete"))) return;

    setIsDeleting(true);
    setStatusMessage(null);

    try {
      const res = await apiFetch(`${apiBase()}/api/v1/exchange/credentials/${activeTab}`, {
        method: "DELETE",
      });

      if (res.ok) {
        setStatusMessage({ type: "success", text: t("exchange.delete_success") });
        setTestResult(null);
        fetchConfigs();
      }
    } catch {
      setStatusMessage({ type: "error", text: t("exchange.delete_failed") });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none animate-fadeIn">
      <div className="relative w-full max-w-xl bg-[#0b0e14] border border-surface-border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border bg-[#0d121c]">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent">
              <Key className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                {t("exchange.modal_title")}
              </h3>
              <p className="text-[11px] text-slate-400">
                {t("exchange.modal_subtitle")}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#162032] transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Exchange Venue Tabs */}
        <div className="flex border-b border-surface-border bg-[#090d14] px-6 text-xs">
          {[
            { id: "binance_futures", name: "Binance Futures" },
            { id: "binance_spot", name: "Binance Spot" },
            { id: "okx", name: "OKX V5" },
          ].map((tab) => {
            const isCfg = configs.find((c) => c.exchange_id === tab.id)?.is_configured;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  setTestResult(null);
                  setStatusMessage(null);
                }}
                className={`py-3 px-4 font-bold border-b-2 transition flex items-center space-x-2 cursor-pointer ${
                  activeTab === tab.id
                    ? "border-accent text-accent bg-[#111722]"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                <span>{tab.name}</span>
                <span
                  className={`w-2 h-2 rounded-full ${
                    isCfg ? "bg-gain shadow-sm shadow-emerald-500/50" : "bg-slate-600"
                  }`}
                  title={isCfg ? "Configured" : "Not Configured"}
                />
              </button>
            );
          })}
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-4 flex-1 text-xs">
          {/* Status Message */}
          {statusMessage && (
            <div
              className={`p-3 rounded-lg flex items-center space-x-2 border ${
                statusMessage.type === "success"
                  ? "bg-gain/15 border-gain/30 text-gain"
                  : "bg-loss/15 border-loss/30 text-loss"
              }`}
            >
              {statusMessage.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0" />
              )}
              <span>{statusMessage.text}</span>
            </div>
          )}

          {credentialStoreStatus && !credentialStoreStatus.available && (
            <div className="p-3 rounded-lg flex items-start space-x-2 border bg-loss/15 border-loss/30 text-loss">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{t("exchange.keychain_unavailable")}</span>
            </div>
          )}

          {/* Current Config State Card */}
          <div className="p-4 bg-[#0d121c] rounded-lg border border-surface-border space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">{t("exchange.status_label")}:</span>
              {currentConfig?.is_configured ? (
                <span className="px-2 py-0.5 rounded bg-gain/15 border border-gain/30 text-gain font-bold text-[10px]">
                  {t("exchange.configured_badge")} ({currentConfig.api_key_masked})
                </span>
              ) : currentConfig?.legacy_detected ? (
                <span className="px-2 py-0.5 rounded bg-loss/15 border border-loss/30 text-loss font-bold text-[10px]">
                  {t("exchange.legacy_badge")}
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-400 font-bold text-[10px]">
                  {t("exchange.unconfigured_badge")}
                </span>
              )}
            </div>

            {(currentConfig?.is_configured || currentConfig?.legacy_detected) && (
              <div className="flex items-center justify-between pt-2 border-t border-surface-border/50">
                <span className="text-[10px] text-slate-500">
                  {t("exchange.last_updated")}: {currentConfig.updated_at ? new Date(currentConfig.updated_at).toLocaleString() : "-"}
                </span>
                <button
                  onClick={handleDeleteCredentials}
                  disabled={isDeleting || (!!currentConfig?.is_configured && !canPersistCredentials)}
                  className="text-loss hover:text-rose-400 font-bold flex items-center space-x-1 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{t("exchange.delete_btn")}</span>
                </button>
              </div>
            )}
          </div>

          {/* Test Connection Results */}
          {testResult && (
            <div
              className={`p-3.5 rounded-lg border ${
                testResult.success
                  ? "bg-[#0a1612] border-gain/40 text-emerald-300"
                  : "bg-[#180e12] border-loss/40 text-rose-300"
              }`}
            >
              <div className="flex items-center space-x-2 font-bold mb-1">
                {testResult.success ? (
                  <CheckCircle2 className="w-4 h-4 text-gain" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-loss" />
                )}
                <span>{testResult.message}</span>
              </div>
              {testResult.success && testResult.free_quote_balance !== undefined && (
                <div className="text-[11px] text-slate-300 mt-1 pl-6">
                  {t("exchange.free_balance")}:{" "}
                  <span className="font-bold text-white">
                    ${testResult.free_quote_balance.toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Input Form */}
          <form onSubmit={handleSaveCredentials} className="space-y-3 pt-2">
            <div>
              <label className="text-slate-400 block mb-1 font-semibold">
                {t("exchange.api_key_label")}
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Paste exchange API key..."
                className="w-full bg-[#090d14] border border-surface-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-accent"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-slate-400 font-semibold">
                  {t("exchange.api_secret_label")}
                </label>
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="text-slate-500 hover:text-slate-300 flex items-center space-x-1 cursor-pointer text-[10px]"
                >
                  {showSecret ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  <span>{showSecret ? "Hide" : "Show"}</span>
                </button>
              </div>
              <input
                type={showSecret ? "text" : "password"}
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Paste exchange API secret..."
                className="w-full bg-[#090d14] border border-surface-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-accent"
              />
            </div>

            {requiresPassphrase && (
              <div>
                <label className="text-slate-400 block mb-1 font-semibold">
                  {t("exchange.passphrase_label")}
                </label>
                <input
                  type="password"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  placeholder="OKX API Passphrase..."
                  className="w-full bg-[#090d14] border border-surface-border rounded-lg px-3 py-2 text-white focus:outline-none focus:border-accent"
                />
              </div>
            )}

            <div className="flex items-center space-x-2 pt-1">
              <input
                type="checkbox"
                id="testnet-chk"
                checked={isTestnet}
                onChange={(e) => setIsTestnet(e.target.checked)}
                className="rounded bg-[#090d14] border-surface-border text-accent focus:ring-0"
              />
              <label htmlFor="testnet-chk" className="text-slate-300 text-[11px] cursor-pointer">
                {t("exchange.testnet_checkbox")}
              </label>
            </div>

            {/* Security Guarantee Note */}
            <div className="flex items-start space-x-2 p-3 bg-[#090d14] rounded-lg border border-surface-border text-[10px] text-slate-400">
              <Shield className="w-4 h-4 text-accent shrink-0 mt-0.5" />
              <p>{t("exchange.security_notice")}</p>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-3 border-t border-surface-border">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={isTesting || (!apiKey && !currentConfig?.is_configured)}
                className="flex items-center space-x-1.5 px-4 py-2 bg-[#162032] hover:bg-[#1f2d47] text-accent font-bold rounded-lg border border-surface-border transition disabled:opacity-40 cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? "animate-spin" : ""}`} />
                <span>{isTesting ? t("exchange.testing_btn") : t("exchange.test_btn")}</span>
              </button>

              <button
                type="submit"
                disabled={isSaving || !canPersistCredentials || !apiKey || !apiSecret}
                className="px-5 py-2 bg-accent hover:bg-sky-400 text-black font-bold rounded-lg transition shadow-md disabled:opacity-40 cursor-pointer"
              >
                {isSaving ? t("exchange.saving_btn") : t("exchange.save_btn")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
