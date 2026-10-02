import { useTranslation } from "../../context/I18nContext";

/** Contextual help only: no preference writes, backup creation or restore action. */
export function FirstUseGuide({ onNewTrade, onExport, onOpenJournal }: {
  onNewTrade?: () => void; onExport?: () => void; onOpenJournal?: () => void;
}) {
  const { t } = useTranslation();
  return <details className="k-card bg-surface border border-surface-border text-ink text-base" data-testid="first-use-guide">
    <summary className="cursor-pointer rounded p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t("first_use.title")}</summary>
    <div className="p-3 pt-0 space-y-3 max-h-[35vh] overflow-y-auto">
      <p>{t("first_use.manual")}</p>
      <p className="text-sm text-muted">{t("first_use.simulation")}</p>
      <div className="flex flex-wrap gap-2">
        {onNewTrade && <button type="button" className="k-btn k-primary" onClick={onNewTrade}>{t("first_use.new_trade")}</button>}
        {onExport && <button type="button" className="k-btn border border-surface-border" onClick={onExport}>{t("first_use.reports")}</button>}
        {onOpenJournal && <button type="button" data-testid="guidance-journal" className="k-btn border border-surface-border" onClick={onOpenJournal}>{t("first_use.open_journal")}</button>}
      </div>
      <p className="text-sm text-warn">{t("first_use.report_boundary")}</p>
      <p className="text-sm">{t("first_use.backup_boundary")}</p>
      <p className="text-sm text-muted">{t("first_use.privacy")}</p>
    </div>
  </details>;
}
