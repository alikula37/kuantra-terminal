import React, { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import packageJson from "../../../package.json";
import { useTranslation } from "../../context/I18nContext";
import { expectsDesktop, getBridge } from "../../lib/bridge";

const RELEASE_URL = "https://github.com/alikula37/kuantra-terminal/releases";

export const UpdateNotifier: React.FC = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState<"idle" | "opening" | "error">("idle");
  const attempt = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => { attempt.current++; clearTimeout(timer.current); }, []);

  const openRelease = async () => {
    const id = ++attempt.current;
    setStatus("opening");
    const finish = (ok: boolean) => {
      if (attempt.current !== id) return;
      attempt.current++;
      clearTimeout(timer.current);
      setStatus(ok ? "idle" : "error");
    };
    timer.current = setTimeout(() => finish(false), 5000);
    try {
      const bridge = getBridge();
      if (!bridge) { finish(false); return; }
      const result = await bridge.open_external(RELEASE_URL);
      finish(result?.ok === true);
    } catch { finish(false); }
  };

  const actionClass = "inline-flex items-center gap-2 px-3 py-2 border border-surface-border rounded text-xs text-white hover:bg-slate-800 disabled:opacity-50";
  return (
    <section aria-label={t("updates.title")} className="bg-[#0d121c] p-4 rounded-lg border border-surface-border space-y-3">
      <h2 className="text-sm font-bold text-white">{t("updates.title")}</h2>
      <p className="text-xs text-slate-300">{t("updates.version", { version: packageJson.version })}</p>
      <p className="text-xs text-slate-400">{t("updates.description")}</p>
      {expectsDesktop() ? (
        <button type="button" className={actionClass} onClick={() => void openRelease()} disabled={status === "opening"}>
          <ExternalLink className="w-4 h-4" aria-hidden="true" />
          {t(status === "opening" ? "updates.opening" : status === "error" ? "updates.retry" : "updates.open")}
        </button>
      ) : (
        <a className={actionClass} href={RELEASE_URL} target="_blank" rel="noopener noreferrer">
          <ExternalLink className="w-4 h-4" aria-hidden="true" />{t("updates.open")}
        </a>
      )}
      {status === "error" && <p role="alert" className="text-xs text-loss">{t("updates.error")}</p>}
    </section>
  );
};
