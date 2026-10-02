import React, { useState } from "react";
import { ShieldCheck, ArrowRight, ArrowLeft, Check, Lock, Sun, Moon, Globe, Layers, Activity } from "lucide-react";
import { useTheme } from "../../context/ThemeContext";
import { useTranslation, SUPPORTED_LOCALES } from "../../context/I18nContext";
import { apiFetch, apiUrl } from "../../lib/backend";

interface FirstBootWizardProps {
  isOpen: boolean;
  onCompleted: () => void;
}

export const FirstBootWizard: React.FC<FirstBootWizardProps> = ({ isOpen, onCompleted }) => {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, t } = useTranslation();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [tradingMode, setTradingMode] = useState<"external" | "simulation">("external");
  const [paperBalance, setPaperBalance] = useState<number>(100000.0);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  const handleFinish = async () => {
    if (isSaving) return;
    setIsSaving(true);
    setSaveError(false);
    try {
      const payload = {
        trading_mode: tradingMode,
        paper_balance: paperBalance,
        active_theme: theme,
        active_locale: locale,
        // Local model inference is not enabled until a verified sidecar is
        // configured; onboarding must not request the retired mock downloader.
        ai_mode: "disabled",
      };

      const res = await apiFetch(apiUrl("/api/v1/onboarding/complete"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        onCompleted();
      } else setSaveError(true);
    } catch (e) {
      setSaveError(true);
    } finally { setIsSaving(false); }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 font-mono select-none">
      <div role="dialog" aria-modal="true" aria-label={t("onboarding.wizard_title")} className="bg-surface border border-surface-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col space-y-4 p-6 text-ink">
        {/* Header */}
        <div className="border-b border-surface-border pb-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded bg-gradient-to-tr from-accent to-blue-600 flex items-center justify-center font-black text-black text-sm">
              K
            </div>
            <div>
              <h2 className="text-sm font-bold text-ink uppercase tracking-wider">
                {t("onboarding.wizard_title")}
              </h2>
              <p className="text-sm text-muted">
                {t("onboarding.wizard_subtitle")}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-sm text-accent bg-elevated px-2.5 py-1 rounded border border-surface-border font-bold">
              {t("first_use.step", { step: currentStep, total: 4 })}
            </span>
          </div>
        </div>

        {/* Stepper Progress Bar */}
        <div className="grid grid-cols-4 gap-2">
          {[1, 2, 3, 4].map((step) => (
            <div
              key={step}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                step <= currentStep ? "bg-accent" : "bg-soft"
              }`}
            />
          ))}
        </div>

        {/* STEP 1: JOURNAL MODE */}
        {currentStep === 1 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-bold text-ink uppercase tracking-wider">
                {t("onboarding.step1_title")}
              </h3>
              <p className="text-sm text-muted">{t("first_use.manual")}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-base">
              {/* External journal */}
              <div
                role="button" tabIndex={0} aria-pressed={tradingMode === "external"}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTradingMode("external"); } }}
                onClick={() => setTradingMode("external")}
                className={`p-4 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-3 ${
                  tradingMode === "external"
                    ? "bg-accent/10 border-accent text-ink shadow-md"
                    : "bg-elevated border-surface-border text-ink hover:border-slate-600"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Activity className={`w-5 h-5 ${tradingMode === "external" ? "text-accent" : "text-muted"}`} />
                    {tradingMode === "external" && <Check className="w-4 h-4 text-accent" />}
                  </div>
                  <span className="font-bold text-base block">{t("onboarding.mode.external_title")}</span>
                  <p className="text-sm text-muted">{t("onboarding.mode.external_desc")}</p>
                </div>
                <span className="text-sm bg-deep px-2 py-0.5 rounded border border-surface-border text-gain font-bold inline-block">
                  {t("onboarding.mode.external_badge")}
                </span>
              </div>

              {/* Explicit simulation */}
              <div
                role="button" tabIndex={0} aria-pressed={tradingMode === "simulation"}
                onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTradingMode("simulation"); } }}
                onClick={() => setTradingMode("simulation")}
                className={`p-4 rounded-lg border cursor-pointer transition flex flex-col justify-between space-y-3 ${
                  tradingMode === "simulation"
                    ? "bg-amber-400/10 border-amber-400 text-ink shadow-md"
                    : "bg-elevated border-surface-border text-ink hover:border-slate-600"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Layers className={`w-5 h-5 ${tradingMode === "simulation" ? "text-amber-300" : "text-muted"}`} />
                    {tradingMode === "simulation" && <Check className="w-4 h-4 text-amber-300" />}
                  </div>
                  <span className="font-bold text-base block">{t("onboarding.mode.simulation_title")}</span>
                  <p className="text-sm text-muted">{t("onboarding.mode.simulation_desc")}</p>
                </div>
                <span className="text-sm bg-deep px-2 py-0.5 rounded border border-surface-border text-amber-300 font-bold inline-block">
                  {t("onboarding.mode.simulation_badge")}
                </span>
              </div>
            </div>

            {tradingMode === "simulation" && (
              <div className="bg-elevated p-3 rounded-lg border border-surface-border space-y-1.5">
                <span className="text-sm text-muted block">{t("onboarding.mode.balance_label")}</span>
                <input
                  aria-label={t("onboarding.mode.balance_label")}
                  type="number"
                  value={paperBalance}
                  onChange={(e) => setPaperBalance(parseFloat(e.target.value) || 0)}
                  className="w-full bg-deep border border-surface-border text-ink text-base px-3 py-1.5 rounded focus:outline-none focus:border-accent"
                />
              </div>
            )}
          </div>
        )}

        {/* STEP 2: OPTIONAL INTEGRATIONS */}
        {currentStep === 2 && (
          <div className="space-y-3">
            <div>
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-accent" />
                <h3 className="text-base font-bold text-ink uppercase tracking-wider">
                  {t("onboarding.step2_title")}
                </h3>
              </div>
              <p className="text-sm text-muted">{t("onboarding.step2_desc")}</p>
            </div>

            <div className="bg-elevated p-4 rounded flex items-start space-x-3 text-sm text-ink" data-testid="onboarding-no-credentials">
              <Lock className="w-3.5 h-3.5 text-accent" />
              <span>{t("onboarding.vault.disabled_notice")}</span>
            </div>
          </div>
        )}

        {/* STEP 3: UI THEME & LOCALIZATION */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <div>
              <h3 className="text-base font-bold text-ink uppercase tracking-wider">
                {t("onboarding.step3_title")}
              </h3>
              <p className="text-sm text-muted">{t("onboarding.step3_desc")}</p>
            </div>

            <div className="space-y-3">
              <span className="text-sm font-bold text-ink block">{t("onboarding.preferences.theme_label")}</span>
              <div className="grid grid-cols-2 gap-3 text-base">
                <div
                  role="button" tabIndex={0} aria-pressed={theme === "dark"}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTheme("dark"); } }}
                  onClick={() => setTheme("dark")}
                  className={`p-3 rounded-lg border cursor-pointer flex items-center space-x-3 ${
                    theme === "dark" ? "bg-accent/15 border-accent text-ink" : "bg-elevated border-surface-border text-muted"
                  }`}
                >
                  <Moon className="w-4 h-4 text-accent" />
                  <span className="font-bold">{t("onboarding.preferences.theme_dark")}</span>
                </div>

                <div
                  role="button" tabIndex={0} aria-pressed={theme === "light"}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setTheme("light"); } }}
                  onClick={() => setTheme("light")}
                  className={`p-3 rounded-lg border cursor-pointer flex items-center space-x-3 ${
                    theme === "light" ? "bg-accent/15 border-accent text-ink" : "bg-elevated border-surface-border text-muted"
                  }`}
                >
                  <Sun className="w-4 h-4 text-amber-400" />
                  <span className="font-bold">{t("onboarding.preferences.theme_light")}</span>
                </div>
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <span className="text-sm font-bold text-ink block">{t("onboarding.preferences.locale_label")}</span>
              <div className="grid grid-cols-3 gap-3 text-base">
                {SUPPORTED_LOCALES.map((loc) => (
                  <div
                    key={loc.id}
                    role="button" tabIndex={0} aria-pressed={locale === loc.id}
                    onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setLocale(loc.id); } }}
                    onClick={() => setLocale(loc.id)}
                    className={`p-3 rounded-lg border cursor-pointer flex items-center justify-between ${
                      locale === loc.id ? "bg-accent/15 border-accent text-ink" : "bg-elevated border-surface-border text-muted"
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <Globe className="w-3.5 h-3.5 text-accent" />
                      <span className="font-bold">{loc.label}</span>
                    </div>
                    <span className="text-sm text-muted font-mono">[{loc.flag}]</span>
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
              <h3 className="text-base font-bold text-ink uppercase tracking-wider">
                {t("first_use.setup_summary")}
              </h3>
              <p className="text-sm text-muted">{t("first_use.setup_boundary")}</p>
            </div>

            <p className="text-base">{tradingMode === "external" ? t("onboarding.mode.external_title") : t("onboarding.mode.simulation_title")} · {theme === "dark" ? t("onboarding.preferences.theme_dark") : t("onboarding.preferences.theme_light")} · {SUPPORTED_LOCALES.find(loc => loc.id === locale)?.label}</p>
            <p className="text-sm text-warn">{t("first_use.report_boundary")}</p>
            {saveError && <p role="alert" className="text-sm text-loss">{t("first_use.save_failed")}</p>}
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="border-t border-surface-border pt-4 flex items-center justify-between text-base">
          {currentStep > 1 ? (
            <button
              onClick={() => setCurrentStep((prev) => prev - 1)}
              className="flex items-center space-x-1.5 px-3 py-2 rounded bg-elevated hover:bg-[#1a2333] text-ink transition"
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
              className="k-btn k-primary"
            >
              <span>{t("onboarding.buttons.next")}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={isSaving}
              className="k-btn k-primary disabled:opacity-50"
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
