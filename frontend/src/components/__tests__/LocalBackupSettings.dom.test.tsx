// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ create: vi.fn(), preview: vi.fn(), apiFetch: vi.fn() }));
vi.mock('../../lib/localBackup', () => ({ runLocalBackup: mocks.create, runBackupPreview: mocks.preview }));
vi.mock('../../lib/backend', () => ({ apiUrl: (p: string) => p, apiFetch: mocks.apiFetch }));
import { I18nProvider } from '../../context/I18nContext';
import { LocalBackupSettings } from '../settings/LocalBackupSettings';
let host: HTMLDivElement; let root: ReturnType<typeof createRoot>;
const result = { status: 'SAVED', name: 'test.zip', path: '/chosen/test.zip', sha256: 'a'.repeat(64),
  schema_version: 8, bundle_schema_version: 1, files_checked: 1, restore_applied: false,
  counts: { trades: 1, events: 3, tracking_plans: 1, weekly_reviews: 1 }, errors: [] };
const mount = async () => { await act(async () => root.render(<I18nProvider><LocalBackupSettings /></I18nProvider>)); };
const click = async (id: string) => { await act(async () => (host.querySelector(`[data-testid="${id}"]`) as HTMLElement).click()); };
beforeEach(() => {
  localStorage.clear(); (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  mocks.create.mockReset(); mocks.preview.mockReset();
  mocks.apiFetch.mockResolvedValue(new Response('{}', { headers: { 'Content-Type': 'application/json' } }));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it('has no automatic work and explains reports and preview-only restore', async () => {
  await mount(); expect(mocks.create).not.toHaveBeenCalled(); expect(mocks.preview).not.toHaveBeenCalled();
  expect(host.textContent).toContain('CSV/PDF'); expect(host.textContent).toContain('No data is restored');
  expect(host.querySelectorAll('button')).toHaveLength(2);
  expect(host.innerHTML).not.toMatch(/text-white|bg-\[#|text-\[10px\]/);
});
it('explicitly includes both actions and diagnostics in WKWebView keyboard navigation', async () => {
  mocks.preview.mockResolvedValue({ status: 'INVALID', errors: ['INVALID_ARCHIVE'], restore_applied: false });
  await mount();
  for (const button of host.querySelectorAll('button')) {
    expect(button.getAttribute('tabindex')).toBe('0');
  }
  await click('backup-preview');
  expect(host.querySelector('summary')?.getAttribute('tabindex')).toBe('0');
});
it('shows actual saved counts, destination and hash, not a restored claim', async () => {
  mocks.create.mockResolvedValue(result); await mount(); await click('backup-create');
  expect(host.textContent).toContain('/chosen/test.zip'); expect(host.textContent).toContain('Backup saved');
  expect(host.querySelector('[data-testid="backup-counts"]')?.textContent).toContain('Evidence events: 3');
  expect(host.textContent).toContain('a'.repeat(64));
});
it('cancelled dialog is not success and retry remains possible', async () => {
  mocks.create.mockResolvedValueOnce({ status: 'CANCELLED' }).mockResolvedValueOnce(result);
  await mount(); await click('backup-create'); expect(host.textContent).not.toContain('Backup saved');
  expect(host.textContent).toContain('Cancelled'); await click('backup-create'); expect(host.textContent).toContain('Backup saved');
});
it('verifier result does not apply anything and invalid errors stay folded', async () => {
  mocks.preview.mockResolvedValue({ status: 'INVALID', name: 'bad.zip', restore_applied: false, errors: ['RAW_UNTRUSTED'] });
  await mount(); await click('backup-preview');
  expect(host.textContent).toContain('Invalid backup');
  expect(host.querySelector('details')?.hasAttribute('open')).toBe(false);
  expect(host.querySelector('[role="status"]')?.textContent).not.toContain('RAW_UNTRUSTED');
  expect(mocks.create).not.toHaveBeenCalled();
});
it('disables duplicate requests until actual completion', async () => {
  let resolve!: (x: any) => void; mocks.create.mockReturnValue(new Promise(r => { resolve = r; }));
  await mount(); await click('backup-create');
  expect((host.querySelector('[data-testid="backup-preview"]') as HTMLButtonElement).disabled).toBe(true);
  expect(host.textContent).toContain('Please wait');
  await act(async () => resolve(result)); expect(host.textContent).toContain('Backup saved');
});
it('failure is generic and retry does not leave the old success visible', async () => {
  mocks.create.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error('private server path'));
  await mount(); await click('backup-create'); await click('backup-create');
  expect(host.textContent).not.toContain('Backup saved'); expect(host.textContent).not.toContain('private server path');
  expect(host.textContent).toContain('could not be completed');
});
it.each([['tr', 'Yerel yedek'], ['de', 'Lokale Sicherung']])('localizes the entry in %s', async (locale, title) => {
  localStorage.setItem('kuantra_locale', locale); await mount(); expect(host.textContent).toContain(title);
});
it('ignores a late response after unmount', async () => {
  let resolve!: (x: any) => void; mocks.preview.mockReturnValue(new Promise(r => { resolve = r; }));
  await mount(); await click('backup-preview'); await act(async () => root.render(<div>new view</div>));
  await act(async () => resolve({ ...result, status: 'VERIFIED' })); expect(host.textContent).toBe('new view');
});
