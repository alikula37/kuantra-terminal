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

  const actionClass = "k-btn k-control disabled:opacity-50";
  return (
    <section aria-label={t("updates.title")} className="bg-surface text-ink p-4 rounded-lg border border-surface-border space-y-3">
      <h2 className="text-base font-bold">{t("updates.title")}</h2>
      <p className="text-base">{t("updates.version", { version: packageJson.version })}</p>
      <p className="text-sm text-muted">{t("updates.build_boundary")}</p>
      <p className="text-sm text-muted">{t("updates.description")}</p>
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
      {status === "error" && <p role="alert" className="text-sm text-loss">{t("updates.error")}</p>}
      <details data-testid="update-guide" className="border border-surface-border rounded p-3">
        <summary className="text-base cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("updates.guide_title")}</summary>
        <ol className="list-decimal pl-6 space-y-3 mt-3 text-sm">
          <li>{t("updates.choose_package")}</li>
          <li>{t("updates.check_package")}</li>
          <li>{t("updates.preserve_data")}</li>
        </ol>
        <p className="text-sm text-warn mt-3">{t("updates.security_boundary")}</p>
      </details>
    </section>
  );
};
