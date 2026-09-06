# P0-WP07 — Credential and OS Keychain Truth Boundary

```yaml
document_id: KPS-P0-WP07
status: Verified
version: 1.0.0
date: 2026-09-06
strategy: KPS-001@1.0.0
adr:
  - ADR-0003
```

## Problem

The previous credential path derived a deterministic machine passphrase and persisted
encrypted API material in SQLite. That made a copied database a credential target,
coupled recovery to hostname/OS details, and shipped a known fallback key for the
process-local vault. The TradingView gateway also accepted a shared built-in secret when
no environment secret was configured.

## Decision

Production secrets are stored only through the operating system credential manager:
Windows Credential Manager, macOS Keychain or Linux Secret Service via `keyring`. SQLite
stores non-secret exchange metadata and stable keychain account references in
`exchange_credential_refs`; it never stores the API key, secret or passphrase. If no
persistent OS backend is available, save/delete of active credentials fails closed with
`CREDENTIAL_STORE_UNAVAILABLE` (HTTP 503). An explicit `memory-test` provider is allowed
only under `KUANTRA_TEST_MODE=1` and is never an application fallback.

## In scope

- Add a keychain provider and structured availability status.
- Move exchange credentials to keychain account references and remove legacy encrypted
  rows when a credential is replaced.
- Ignore legacy SQLite credential rows for execution; expose them as requiring re-entry
  and allow explicit purge without decrypting them.
- Route generic onboarding/vault secrets to the keychain; keep only a transient in-memory
  compatibility copy for the current process.
- Remove the deterministic `StrongholdVault` default key.
- Replace the shared webhook default with a process-random secret and require
  `KUANTRA_WEBHOOK_SECRET` for a stable production integration.
- Surface keychain-unavailable state in the credentials UI and add regression coverage.

## Out of scope

- Live execution enablement, broker certification, or exchange permission management.
- Automatic decryption/migration of legacy SQLite credentials.
- Cloud secret managers, team secret sharing or remote KMS.
- Removal of all experimental connector UI; that is P0-WP08.

## Acceptance criteria

1. A production process without an OS keychain cannot persist credentials and returns a
   structured 503; it never falls back to plaintext, deterministic encryption or the
   test provider.
2. A successful save writes only keychain account references and metadata to SQLite;
   API key, secret and passphrase are absent from all SQLite rows.
3. Execution reads only keychain-backed references. Legacy encrypted rows are not
   decrypted or used and are visibly marked for re-entry.
4. Generic onboarding secrets do not enter `user_settings`; the process-local copy is
   ephemeral and the old shared webhook default is impossible.
5. Credentials UI disables persistence when keychain status is unavailable and all
   three locales retain i18n parity.
6. Isolated backend, frontend, build, audit and three-OS CI gates remain green.

## Migration and rollback

Existing `exchange_credentials` rows remain encrypted but are treated as legacy and are
never read for execution. The UI directs the user to re-enter credentials; explicit
delete purges the legacy row without attempting decryption. Rollback restores the old
code path but must be treated as a security rollback and requires an explicit release
decision; no automatic rollback is permitted.

## Verification record

- Backend isolated-data suite: `338 passed, 1 skipped`.
- Frontend: `45 passed` / 10 test files; i18n `479/479`; production build successful.
- Dependency audit: `npm audit --audit-level=moderate` found 0 vulnerabilities.
- `uv pip compile --universal --python-version 3.11 --generate-hashes` regenerated the
  lock with `keyring==25.7.0` and its platform-specific backends.
- Remote three-OS CI evidence is added after the implementation commit and must remain
  green before merge.

## Validation

- No-keychain fail-closed API test and explicit memory-test provider tests.
- SQLite inspection proving only references/metadata are persisted.
- Webhook default-secret regression test.
- Full locked backend suite, frontend unit/DOM suite, production build and npm audit.
- Three-OS GitHub CI including desktop smoke.
