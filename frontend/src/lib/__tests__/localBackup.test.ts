import { beforeEach, expect, it, vi } from 'vitest';
const mock = vi.hoisted(() => ({ ready: vi.fn(), create: vi.fn(), preview: vi.fn() }));
vi.mock('../bridge', () => ({ bridgeReady: mock.ready }));
import { runLocalBackup, runBackupPreview, validateBackupResult } from '../localBackup';
const good = { status: 'SAVED', name: 'backup.zip', path: '/selected/backup.zip', sha256: 'a'.repeat(64),
  restore_applied: false, schema_version: 8, bundle_schema_version: 1, files_checked: 1,
  counts: { trades: 1, events: 3, tracking_plans: 1, weekly_reviews: 1 } };
beforeEach(() => { vi.resetAllMocks(); mock.ready.mockResolvedValue({ create_local_backup: mock.create, preview_local_backup: mock.preview }); });
it('sends empty specs only and has no browser fallback', async () => {
  mock.create.mockResolvedValue(good); mock.preview.mockResolvedValue({ ...good, status: 'VERIFIED' });
  expect((await runLocalBackup()).status).toBe('SAVED'); expect(mock.create).toHaveBeenCalledWith({});
  expect((await runBackupPreview()).status).toBe('VERIFIED'); expect(mock.preview).toHaveBeenCalledWith({});
  mock.ready.mockResolvedValue(null); expect((await runLocalBackup()).status).toBe('UNAVAILABLE');
});
it.each([null, {}, { ...good, status: 'NEW_STATE' }, { ...good, restore_applied: true },
  { ...good, sha256: 'bad' }, { ...good, path: '' }, { ...good, counts: null },
  { ...good, counts: { ...good.counts, events: -1 } }, { ...good, schema_version: undefined }])('rejects malformed success %#', value => {
  expect(validateBackupResult(value).status).toBe('FAILED');
});
it('retains genuine zero and unknown counts, without inventing values', () => {
  const r = validateBackupResult({ ...good, counts: { trades: 0, events: 0, tracking_plans: null, weekly_reviews: 0 } });
  expect(r.counts?.tracking_plans).toBeNull(); expect(r.counts?.trades).toBe(0);
});
it('old bridges and bridge errors fail honestly', async () => {
  mock.ready.mockResolvedValue({}); expect((await runBackupPreview()).status).toBe('UNAVAILABLE');
  mock.ready.mockRejectedValue(new Error('private')); expect((await runLocalBackup()).status).toBe('FAILED');
});
it.each([{ status: 'INVALID', name: {} }, { status: 'INVALID', path: {} },
  { status: 'INVALID', sha256: {} }, { status: 'INVALID', counts: {} }])('rejects malformed diagnostic metadata %#', value => {
  expect(validateBackupResult(value).status).toBe('FAILED');
});
