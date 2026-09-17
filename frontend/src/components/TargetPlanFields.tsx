import { useTranslation } from "../context/I18nContext";
import type { TargetDraft } from "../lib/localTracking";

export function TargetPlanFields({ targets, onChange, locked = [], disabled = false }: {
  targets: TargetDraft[]; onChange: (targets: TargetDraft[]) => void; locked?: string[]; disabled?: boolean;
}) {
  const { t } = useTranslation();
  return <fieldset className="space-y-2" aria-label={t("tracking.targets")}>
    <legend className="text-sm font-semibold">{t("tracking.targets")}</legend>
    {targets.map((target, index) => <div className="flex flex-wrap gap-2 items-end" key={index}>
      <label className="flex-1 min-w-24 text-xs">{t("tracking.price", { n: index + 1 })}
        <input type="number" step="any" min="0" aria-label={t("tracking.price", { n: index + 1 })}
          value={target.price} disabled={disabled || locked.includes(`TP${index + 1}`)}
          onChange={e => onChange(targets.map((row, i) => i === index ? { ...row, price: e.target.value } : row))}
          className="w-full bg-[#0b0e14] border border-surface-border rounded p-2 text-gain" />
      </label>
      <label className="flex-1 min-w-24 text-xs">{t("tracking.percent", { n: index + 1 })}
        <input type="number" step="any" min="0" max="100" aria-label={t("tracking.percent", { n: index + 1 })}
          value={target.percent} disabled={disabled || locked.includes(`TP${index + 1}`)}
          onChange={e => onChange(targets.map((row, i) => i === index ? { ...row, percent: e.target.value } : row))}
          className="w-full bg-[#0b0e14] border border-surface-border rounded p-2 text-white" />
      </label>
      {index === targets.length - 1 && !locked.includes(`TP${index + 1}`) && !disabled && <button type="button"
        className="border border-surface-border rounded p-2 text-xs" onClick={() => onChange(targets.slice(0, -1))}>
        {t("tracking.remove")}</button>}
    </div>)}
    {targets.length < 3 && !disabled && <button type="button" className="text-accent text-xs border border-surface-border rounded p-2"
      onClick={() => onChange([...targets, { price: "", percent: "" }])}>{t("tracking.add")}</button>}
    <p className="text-xs text-slate-400">{t("tracking.allocation_help")}</p>
  </fieldset>;
}
