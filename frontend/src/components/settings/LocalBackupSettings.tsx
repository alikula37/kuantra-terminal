import { useEffect, useRef, useState } from 'react';
import { useTranslation } from '../../context/I18nContext';
import { BackupResult, runBackupPreview, runLocalBackup } from '../../lib/localBackup';

export function LocalBackupSettings() {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BackupResult | null>(null);
  const running = useRef(false); const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, []);
  async function run(preview: boolean) {
    if (running.current) return;
    running.current = true; setBusy(true); setResult(null);
    const id = ++generation.current;
    try {
      const value = await (preview ? runBackupPreview() : runLocalBackup());
      if (id === generation.current) setResult(value);
    } catch {
      if (id === generation.current) setResult({ status: 'FAILED' });
    } finally {
      if (id === generation.current) { running.current = false; setBusy(false); }
    }
  }
  const status = result?.status;
  const message = status === 'SAVED' ? t('backup.saved') : status === 'VERIFIED' ? t('backup.verified') :
    status === 'LIMITED' ? t('backup.limited') : status === 'INVALID' ? t('backup.invalid') :
    status === 'CANCELLED' ? t('backup.cancelled') : status === 'UNAVAILABLE' ? t('backup.unavailable') :
    status === 'BUSY' ? t('backup.busy') : t('backup.failed');
  return <section className="k-card bg-surface border border-surface-border p-4 space-y-3 text-ink text-base" aria-labelledby="backup-title" data-testid="local-backup-settings">
    <h3 id="backup-title" className="font-bold">{t('backup.title')}</h3>
    <p>{t('backup.description')}</p>
    <p className="text-sm text-muted">{t('backup.exclusions')}</p>
    <p className="text-sm text-warn">{t('backup.privacy')}</p>
    <p className="text-sm">{t('backup.boundary')}</p>
    <div className="flex flex-wrap gap-3">
      <button type="button" tabIndex={0} className="k-btn k-primary" data-testid="backup-create" disabled={busy} onClick={() => void run(false)}>{t('backup.create')}</button>
      <button type="button" tabIndex={0} className="k-btn border border-surface-border" data-testid="backup-preview" disabled={busy} onClick={() => void run(true)}>{t('backup.preview')}</button>
    </div>
    {busy && <p role="status">{t('backup.working')}</p>}
    {result && <div className="space-y-2 break-words" data-testid="backup-result">
      <p role="status" className={status === 'INVALID' || status === 'FAILED' || status === 'REJECTED' ? 'text-loss' : 'text-ink'}>{message}</p>
      {result.name && <p>{t('backup.file')}: {result.name}</p>}
      {result.path && <p className="select-text">{t('backup.destination')}: {result.path}</p>}
      {result.sha256 && <p className="text-sm select-text break-all">{t('backup.hash')}: {result.sha256}</p>}
      {result.counts && <div data-testid="backup-counts" className="text-sm grid grid-cols-1 sm:grid-cols-2 gap-2">
        <p>{t('backup.trades')}: {result.counts.trades ?? t('backup.unknown')}</p>
        <p>{t('backup.events')}: {result.counts.events ?? t('backup.unknown')}</p>
        <p>{t('backup.tracking')}: {result.counts.tracking_plans ?? t('backup.unknown')}</p>
        <p>{t('backup.reviews')}: {result.counts.weekly_reviews ?? t('backup.unknown')}</p>
        <p>{t('backup.schema')}: {result.schema_version ?? t('backup.unknown')}</p>
        <p>{t('backup.files')}: {result.files_checked ?? t('backup.unknown')}</p>
      </div>}
      {!!result.errors?.length && <details className="text-sm">
        <summary tabIndex={0} className="cursor-pointer k-btn focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">{t('backup.diagnostics')}</summary>
        <ul className="space-y-2 select-text">{result.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
      </details>}
    </div>}
  </section>;
}
