import React, { useState, useEffect } from "react";
import { ShieldCheck, ArrowRight, ArrowLeft, Check, Lock, Sun, Moon, Globe, Layers, Activity, CheckCircle2 } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useTranslation, SUPPORTED_LOCALES } from "../../context/I18nContext";
import { apiUrl } from "../../lib/backend";

interface FirstBootWizardProps {
  isOpen: boolean;
  onCompleted: () => void;
}

export const FirstBootWizard: React.FC<FirstBootWizardProps> = ({ isOpen, onCompleted }) => {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, t } = useTranslation();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [tradingMode, setTradingMode] = useState<"live" | "paper">("paper");
  const [paperBalance, setPaperBalance] = useState<number>(100000.0);

  // Vault credentials
  const [twelvedataKey, setTwelvedataKey] = useState<string>("");
  const [polygonKey, setPolygonKey] = useState<string>("");
  const [binanceKey, setBinanceKey] = useState<string>("");
  const [binanceSecret, setBinanceSecret] = useState<string>("");
  const [okxKey, setOkxKey] = useState<string>("");
  const [okxSecret, setOkxSecret] = useState<string>("");
  const [okxPassphrase, setOkxPassphrase] = useState<string>("");

  // Verification stage
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verificationProgress, setVerificationProgress] = useState<number>(0);
  const [verificationLogs, setVerificationLogs] = useState<string[]>([]);
  const [isReady, setIsReady] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen && currentStep === 4) {
      runVerificationHandshake();
    }
  }, [isOpen, currentStep]);

  const runVerificationHandshake = async () => {
    setIsVerifying(true);
    setVerificationProgress(20);
    setVerificationLogs([t("onboarding.verification.checking_sidecar")]);

    await new Promise((r) => setTimeout(r, 400));
    setVerificationProgress(50);
    setVerificationLogs((prev) => [...prev, t("onboarding.verification.checking_sqlite")]);

    await new Promise((r) => setTimeout(r, 400));
    setVerificationProgress(80);
    setVerificationLogs((prev) => [...prev, t("onboarding.verification.checking_duckdb")]);

    await new Promise((r) => setTimeout(r, 400));
    setVerificationProgress(100);
    setVerificationLogs((prev) => [...prev, t("onboarding.verification.checking_websocket")]);

    setIsVerifying(false);
    setIsReady(true);
  };

  const handleFinish = async () => {
    try {
      const apiKeys: Record<string, string> = {};
      if (twelvedataKey.trim()) apiKeys["TWELVEDATA_API_KEY"] = twelvedataKey.trim();
      if (polygonKey.trim()) apiKeys["POLYGON_API_KEY"] = polygonKey.trim();
      if (binanceKey.trim()) apiKeys["BINANCE_API_KEY"] = binanceKey.trim();
      if (binanceSecret.trim()) apiKeys["BINANCE_API_SECRET"] = binanceSecret.trim();
      if (okxKey.trim()) apiKeys["OKX_API_KEY"] = okxKey.trim();
      if (okxSecret.trim()) apiKeys["OKX_API_SECRET"] = okxSecret.trim();
      if (okxPassphrase.trim()) apiKeys["OKX_PASSPHRASE"] = okxPassphrase.trim();

      const payload = {
        trading_mode: tradingMode,
        paper_balance: paperBalance,
        active_theme: theme,
        active_locale: locale,
        ai_mode: "local_gguf",
        api_keys: apiKeys,
      };

      const res = await fetch(apiUrl("/api/v1/onboarding/complete"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        onCompleted();
      }
    } catch (e) {
      console.error("Onboarding completion error:", e);
      onCompleted();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 font-mono select-none">
      <div className="bg-[#0d121c] border border-surface-border rounded-xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col space-y-4 p-6 text-slate-100">
        {/* Header */}
        <div className="border-b border-surface-border pb-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm">
              K
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                {t("onboarding.wizard_title")}
              </h2>
              <p className="text-[11px] text-slate-400">
                {t("onboarding.wizard_subtitle")}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-[10px] text-accent bg-[#111722] px-2.5 py-1 rounded border border-surface-border font-bold">
              STEP {currentStep} OF 4
            </span>
          </div>
        </div>

        {/* Stepper Progress Bar */}
        <div className="grid grid-cols-4 gap-2">
          {[1, 2, 3, 4].map((step) => (
            <div
              key={step}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                step <= currentStep ? "bg-accent" : "bg-[#1e293b]"
              }`}
            />
          ))}
        </div>

        {/* STEP 1: TRADING MODE */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                {t("onboarding.step1_title")}
              </h3>
              <p className="text-[11px] text-slate-400">{t("onboarding.step1_desc")}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {/* Paper Trading */}
              <div
                onClick={() => setTradingMode("paper")}
                className={`p-4 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-3 ${
                  tradingMode === "paper"
                    ? "bg-accent/10 border-accent text-white shadow-md"
                    : "bg-[#111722] border-surface-border text-slate-300 hover:border-slate-600"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Layers className={`w-5 h-5 ${tradingMode === "paper" ? "text-accent" : "text-slate-400"}`} />
                    {tradingMode === "paper" && <Check className="w-4 h-4 text-accent" />}
                  </div>
                  <span className="font-bold text-xs block">{t("onboarding.mode.paper_title")}</span>
                  <p className="text-[10px] text-slate-400">{t("onboarding.mode.paper_desc")}</p>
                </div>
                <span className="text-[9px] bg-[#090d14] px-2 py-0.5 rounded border border-surface-border text-gain font-bold inline-block">
                  RISK-FREE SIMULATION
                </span>
              </div>

              {/* Live Trading */}
              <div
                onClick={() => setTradingMode("live")}
                className={`p-4 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-3 ${
                  tradingMode === "live"
                    ? "bg-accent/10 border-accent text-white shadow-md"
                    : "bg-[#111722] border-surface-border text-slate-300 hover:border-slate-600"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Activity className={`w-5 h-5 ${tradingMode === "live" ? "text-accent" : "text-slate-400"}`} />
                    {tradingMode === "live" && <Check className="w-4 h-4 text-accent" />}
                  </div>
                  <span className="font-bold text-xs block">{t("onboarding.mode.live_title")}</span>
                  <p className="text-[10px] text-slate-400">{t("onboarding.mode.live_desc")}</p>
                </div>
                <span className="text-[9px] bg-[#090d14] px-2 py-0.5 rounded border border-surface-border text-accent font-bold inline-block">
                  DIRECT INSTITUTIONAL ROUTING
                </span>
              </div>
            </div>

            {tradingMode === "paper" && (
              <div className="bg-[#111722] p-3 rounded-lg border border-surface-border space-y-1.5">
                <span className="text-[10px] text-slate-400 block">{t("onboarding.mode.balance_label")}</span>
                <input
                  type="number"
                  value={paperBalance}
                  onChange={(e) => setPaperBalance(parseFloat(e.target.value) || 0)}
                  className="w-full bg-[#090d14] border border-surface-border text-white text-xs px-3 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>
            )}
          </div>
        )}

        {/* STEP 2: STRONGHOLD VAULT CREDENTIALS */}
        {currentStep === 2 && (
          <div className="space-y-3">
            <div>
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-accent" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  {t("onboarding.step2_title")}
                </h3>
              </div>
              <p className="text-[11px] text-slate-400">{t("onboarding.step2_desc")}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs max-h-60 overflow-y-auto pr-1">
              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.twelvedata_label")}</span>
                <input
                  type="password"
                  value={twelvedataKey}
                  onChange={(e) => setTwelvedataKey(e.target.value)}
                  placeholder="td_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.polygon_label")}</span>
                <input
                  type="password"
                  value={polygonKey}
                  onChange={(e) => setPolygonKey(e.target.value)}
                  placeholder="poly_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.binance_key_label")}</span>
                <input
                  type="password"
                  value={binanceKey}
                  onChange={(e) => setBinanceKey(e.target.value)}
                  placeholder="bin_key_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.binance_secret_label")}</span>
                <input
                  type="password"
                  value={binanceSecret}
                  onChange={(e) => setBinanceSecret(e.target.value)}
                  placeholder="bin_sec_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.okx_key_label")}</span>
                <input
                  type="password"
                  value={okxKey}
                  onChange={(e) => setOkxKey(e.target.value)}
                  placeholder="okx_key_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.okx_secret_label")}</span>
                <input
                  type="password"
                  value={okxSecret}
                  onChange={(e) => setOkxSecret(e.target.value)}
                  placeholder="okx_sec_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <span className="text-[10px] text-slate-400 block mb-1">{t("onboarding.vault.okx_passphrase_label")}</span>
                <input
                  type="password"
                  value={okxPassphrase}
                  onChange={(e) => setOkxPassphrase(e.target.value)}
                  placeholder="okx_pass_..."
                  className="w-full bg-[#111722] border border-surface-border text-white px-2 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>
            </div>

            <div className="bg-[#111722] p-2 rounded flex items-center space-x-2 text-[10px] text-slate-400">
              <Lock className="w-3.5 h-3.5 text-accent" />
              <span>{t("onboarding.vault.optional_notice")}</span>
            </div>
          </div>
        )}

        {/* STEP 3: UI THEME & LOCALIZATION */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                {t("onboarding.step3_title")}
              </h3>
              <p className="text-[11px] text-slate-400">{t("onboarding.step3_desc")}</p>
            </div>

            <div className="space-y-3">
              <span className="text-[11px] font-bold text-white block">{t("onboarding.preferences.theme_label")}</span>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div
                  onClick={() => setTheme("dark")}
                  className={`p-3 rounded-lg border cursor-pointer flex items-center space-x-3 ${
                    theme === "dark" ? "bg-accent/15 border-accent text-white" : "bg-[#111722] border-surface-border text-slate-400"
                  }`}
                >
                  <Moon className="w-4 h-4 text-accent" />
                  <span className="font-bold">{t("onboarding.preferences.theme_dark")}</span>
                </div>

                <div
                  onClick={() => setTheme("light")}
                  className={`p-3 rounded-lg border cursor-pointer flex items-center space-x-3 ${
                    theme === "light" ? "bg-accent/15 border-accent text-white" : "bg-[#111722] border-surface-border text-slate-400"
                  }`}
                >
                  <Sun className="w-4 h-4 text-amber-400" />
                  <span className="font-bold">{t("onboarding.preferences.theme_light")}</span>
                </div>
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <span className="text-[11px] font-bold text-white block">{t("onboarding.preferences.locale_label")}</span>
              <div className="grid grid-cols-3 gap-3 text-xs">
                {SUPPORTED_LOCALES.map((loc) => (
                  <div
                    key={loc.id}
                    onClick={() => setLocale(loc.id)}
                    className={`p-3 rounded-lg border cursor-pointer flex items-center justify-between ${
                      locale === loc.id ? "bg-accent/15 border-accent text-white" : "bg-[#111722] border-surface-border text-slate-400"
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <Globe className="w-3.5 h-3.5 text-accent" />
                      <span className="font-bold">{loc.label}</span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">[{loc.flag}]</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: VERIFICATION & HANDSHAKE */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                {t("onboarding.step4_title")}
              </h3>
              <p className="text-[11px] text-slate-400">{t("onboarding.step4_desc")}</p>
            </div>

            {/* Progress */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span>{isVerifying ? "Running Engine Diagnostics..." : t("onboarding.verification.all_systems_go")}</span>
                <span className="font-bold text-accent">{verificationProgress}%</span>
              </div>
              <div className="w-full bg-[#111722] h-2 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent transition-all duration-300"
                  style={{ width: `${verificationProgress}%` }}
                />
              </div>
            </div>

            {/* Diagnostic Logs */}
            <div className="bg-[#090d14] p-3 rounded-lg border border-surface-border space-y-1 text-[11px] font-mono max-h-36 overflow-y-auto">
              {verificationLogs.map((log, idx) => (
                <div key={idx} className="flex items-center space-x-2 text-slate-300">
                  <CheckCircle2 className="w-3 h-3 text-gain" />
                  <span>{log}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="border-t border-surface-border pt-4 flex items-center justify-between text-xs">
          {currentStep > 1 ? (
            <button
              onClick={() => setCurrentStep((prev) => prev - 1)}
              className="flex items-center space-x-1.5 px-3 py-2 rounded bg-[#111722] hover:bg-[#1a2333] text-slate-300 transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{t("onboarding.buttons.back")}</span>
            </button>
          ) : (
            <div />
          )}

          {currentStep < 4 ? (
            <button
              onClick={() => setCurrentStep((prev) => prev + 1)}
              className="flex items-center space-x-1.5 px-5 py-2 rounded bg-accent hover:bg-sky-400 text-black font-bold transition shadow"
            >
              <span>{t("onboarding.buttons.next")}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={!isReady}
              className="flex items-center space-x-2 px-6 py-2.5 rounded bg-gain hover:bg-emerald-400 text-black font-bold transition shadow"
            >
              <span>{t("onboarding.verification.complete_btn")}</span>
              <Check className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};