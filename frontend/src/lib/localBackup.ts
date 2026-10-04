import { bridgeReady } from './bridge';

export type BackupStatus = 'SAVED' | 'VERIFIED' | 'LIMITED' | 'INVALID' | 'CANCELLED' | 'FAILED' | 'UNAVAILABLE' | 'BUSY' | 'REJECTED';
export interface BackupResult {
  status: BackupStatus;
  name?: string; path?: string; sha256?: string;
  schema_version?: number | null; bundle_schema_version?: number | null;
  files_checked?: number;
  counts?: { trades: number | null; events: number | null; tracking_plans: number | null; weekly_reviews: number | null } | null;
  restore_applied?: false;
  errors?: string[];
}
const states = new Set<BackupStatus>(['SAVED', 'VERIFIED', 'LIMITED', 'INVALID', 'CANCELLED', 'FAILED', 'UNAVAILABLE', 'BUSY', 'REJECTED']);
const count = (x: unknown) => x === null || (typeof x === 'number' && Number.isSafeInteger(x) && x >= 0);

/** Validate before showing success; no browser path/upload/download fallback. */
export function validateBackupResult(value: unknown): BackupResult {
  if (!value || typeof value !== 'object') return { status: 'FAILED' };
  const r = value as BackupResult;
  if (!states.has(r.status) || (r.restore_applied !== undefined && r.restore_applied !== false)) return { status: 'FAILED' };
  for (const k of ['name', 'path', 'sha256'] as const) {
    if (r[k] !== undefined && (typeof r[k] !== 'string' || r[k]!.length > 4096)) return { status: 'FAILED' };
  }
  if (r.counts !== undefined && r.counts !== null && (!r.counts || typeof r.counts !== 'object' ||
      !['trades', 'events', 'tracking_plans', 'weekly_reviews'].every(k => count(r.counts?.[k as keyof typeof r.counts])))) return { status: 'FAILED' };
  if (r.status === 'SAVED' || r.status === 'VERIFIED' || r.status === 'LIMITED') {
    if (typeof r.name !== 'string' || !r.name || r.name.length > 2048 ||
        typeof r.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(r.sha256) ||
        r.restore_applied !== false || !count(r.schema_version) || !count(r.bundle_schema_version) ||
        !count(r.files_checked) || r.files_checked === null || !r.counts ||
        !['trades', 'events', 'tracking_plans', 'weekly_reviews'].every(k => count(r.counts?.[k as keyof typeof r.counts]))) return { status: 'FAILED' };
    if (r.status === 'SAVED' && (typeof r.path !== 'string' || !r.path || r.path.length > 4096)) return { status: 'FAILED' };
  }
  return { ...r, errors: Array.isArray(r.errors) ? r.errors.filter((e): e is string => typeof e === 'string').slice(0, 20).map(e => e.slice(0, 500)) : [] };
}

async function run(method: 'create_local_backup' | 'preview_local_backup'): Promise<BackupResult> {
  try {
    const api = await bridgeReady();
    if (!api || typeof api[method] !== 'function') return { status: 'UNAVAILABLE' };
    return validateBackupResult(await api[method]({}));
  } catch { return { status: 'FAILED' }; }
}
export const runLocalBackup = () => run('create_local_backup');
export const runBackupPreview = () => run('preview_local_backup');
