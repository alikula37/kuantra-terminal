# Windows-to-macOS migration runbook

Document ID: KMP-001
Version: 1.2.1
Status: Accepted
Last updated: 2026-09-10

## Initial Windows transition decision: no-user-data path

At the original Windows-to-Mac transition there were no external users or user-owned
journals to migrate. This is not permission to reset data now present on a pilot or
developer Mac. `backend/data/` contains local development artifacts and is
ignored by Git; it is not part of the code migration. For the current Windows
to Mac move, **do not create or restore a migration ZIP**. Clone the private
repository, checkout the product branch, install the toolchain, and let Kuantra
create a fresh local data directory on first run.

The bundle procedure below remains the required path for a future machine that
contains real journal/evidence data. It is intentionally separate from the
code-only Mac bootstrap so test fixtures, synthetic local trades, DuckDB files,
logs, and credentials are never copied accidentally.

### Code-only Mac bootstrap acceptance

1. Windows has no intended uncommitted code (`git status --short` reviewed) and
   the intended branch is pushed to the private GitHub repository.
2. On Mac, authenticate with `gh auth login --web`; never paste a GitHub token
   into Codex chat or commit it to a file.
3. Clone `main` with `gh repo clone` and confirm the
   remote branch contains the expected latest commit.
4. Run the local merge gate, frontend tests/build, macOS desktop smoke, and DMG
   packaging with a fresh data directory.
5. Verify that no `backend/data` contents, Windows Credential Manager entries,
   `.env` files, logs, or generated artifacts were copied from Windows.

After these checks, the Mac becomes the single active development workspace.

This runbook moves the local Kuantra journal to a Mac without copying API
secrets or treating DuckDB as a second source of truth. The migration bundle is
created on Windows, verified before transport, and restored only into a clean
macOS data directory.

## What is migrated

- A compact SQLite snapshot of the canonical journal/evidence ledger.
- SQLite integrity evidence and SHA-256 hashes.
- `cold_storage/**/*.parquet` historical market files.

## What is deliberately not migrated

- Exchange secrets, legacy encrypted credential rows, machine-local keychain
  reference rows, or keychain contents.
- DuckDB and its WAL sidecar; it is rebuilt from SQLite after restore.
- Logs, telemetry queues, plugins, experimental local models, and SQLite WAL/SHM sidecars.

Credentials must be entered again into macOS Keychain. Never copy Windows
Credential Manager material or raw `.env` secrets to the Mac.

## Legacy SQLite schema upgrade (future real-data path only)

This command is **not** part of the clean bootstrap. When an existing database predates the evidence ledger or
typed projection, stop Kuantra and obtain explicit owner approval before using:

```bash
python scripts/macos_migration.py upgrade-schema \
  --db-path "$HOME/Library/Application Support/Kuantra Terminal/kuantra_oltp.sqlite3" \
  --json
```

The command accepts only the supported baseline/evidence schema versions. It
performs integrity and schema preflight, creates a verifiable SQLite snapshot,
works in a temporary staging file, adds only bounded additive trade columns,
backfills legacy trades into the existing canonical evidence event types, rebuilds
the existing projection, and atomically promotes the validated file. The previous
SQLite/WAL set is retained as a `.pre-upgrade-*` backup. Unsupported/future schema,
corrupt backup, malformed legacy rows, or any failed validation stops the operation
without promoting staged data. It does not remove credentials; bundle creation has
the separate credential-sanitization policy below.

The current additive journal revision is `005_trade_position_type` (schema version 5).
Spot/long/short identity is retained through snapshots and export; historical rows
receive `UNKNOWN`, never an inferred spot classification. Supported stamped and
unstamped pre-quote/pre-position layouts are recognized only when the core trade,
ledger and projection columns remain intact. Missing core columns and future
schema versions still fail closed. Development checks use temporary synthetic
databases; they do not authorize upgrading an existing user's database.

Do not run `upgrade-schema` on the clean no-user-data Mac and do not treat it as a
general database reset or migration-apply shortcut. After a successful upgrade,
create and verify the migration bundle; only a bundle with `valid=true`,
`migration_ready=true`, and empty `errors` may enter the restore flow.

## 1. Create the bundle on Windows

Stop the desktop app first. Use the frozen data directory if the app was
installed, or `backend/data` for a development checkout:

```powershell
python scripts/macos_migration.py create `
  --source-data-dir "$env:LOCALAPPDATA\Kuantra Terminal" `
  --output "$env:USERPROFILE\Desktop\kuantra-macos-migration.zip"
```

For a development checkout:

```powershell
python scripts/macos_migration.py create `
  --source-data-dir ".\backend\data" `
  --output "$env:USERPROFILE\Desktop\kuantra-macos-migration.zip"
```

The command never modifies the source database. It creates a sanitized SQLite
snapshot, removes legacy `exchange_credentials` rows, and reports the bundle
SHA-256. It also records whether the disposable trade projection has exact
coverage. Keep the bundle encrypted at rest while transporting it.

If `migration_ready` is `false`, run the explicit evidence migration on the
Windows source first, then recreate the bundle:

```powershell
python backend/app/cli.py evidence-ledger backfill --dry-run
python backend/app/cli.py evidence-ledger backfill --apply
python backend/app/cli.py evidence-ledger projection-rebuild --dry-run
python backend/app/cli.py evidence-ledger projection-rebuild --apply
```

Review each report before using `--apply`; these commands mutate the local
SQLite ledger/projection but never transmit credentials.

## 2. Verify before transport

```powershell
python scripts/macos_migration.py verify `
  --bundle "$env:USERPROFILE\Desktop\kuantra-macos-migration.zip" `
  --json
```

Continue only when `valid` is `true`, `migration_ready` is `true`, and `errors`
is empty. Record the printed `bundle_sha256` next to the backup. A changed hash
means the bundle must be recreated or transported again.

## 3. Prepare the Mac

Clone the private repository and use the same product branch. Install Python
3.11, Node.js 20, npm, `uv`, GitHub CLI and Xcode Command Line Tools. Run the
frontend/backend tests and the local merge gate with a fresh staging data
directory before restoring user data:

```bash
xcode-select --install
gh auth login --web --git-protocol https
gh repo clone alikula37/kuantra-terminal -- --branch main
cd kuantra-terminal
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
uv run --offline --no-project --with-requirements backend/requirements.lock \
  python scripts/run_local_ci.py
```

The first dependency installation may require network access if the local `uv`
cache is empty. Do not label that first run as offline evidence.

Build and smoke the native macOS bundle before restoring the real data:

```bash
python scripts/build_desktop.py --skip-frontend
python scripts/smoke_desktop.py
bash scripts/package_macos.sh
```

macOS uses Cocoa/WKWebView. Windows WebView2 diagnostics are a separate release
gate and are not proven by this Mac smoke.

## 4. Restore into a clean data directory

Copy the ZIP to the Mac and verify it again. Restore to the frozen app path only
after staging smoke is green:

```bash
python scripts/macos_migration.py verify \
  --bundle "$HOME/Desktop/kuantra-macos-migration.zip" --json

python scripts/macos_migration.py restore \
  --bundle "$HOME/Desktop/kuantra-macos-migration.zip" \
  --target-data-dir "$HOME/Library/Application Support/Kuantra Terminal"
```

Rebuild the analytical projection from the restored canonical ledger:

```bash
python scripts/macos_migration.py rebuild-projection \
  --data-dir "$HOME/Library/Application Support/Kuantra Terminal"
```

This command fails closed when the evidence projection is incomplete. Do not
copy an old DuckDB file to bypass that gate.

Restore refuses a non-empty target. If an explicit replacement is necessary,
use `--force`; the existing target is moved to a timestamped
`.pre-migration-*` sibling instead of being deleted. Extraction always happens in
a temporary sibling staging directory; a checksum, schema, chain, and projection
coverage failure leaves the target untouched and removes the failed staging tree.

After restore:

1. Re-enter exchange credentials into macOS Keychain.
2. Rebuild the DuckDB projection from the restored SQLite ledger.
3. Run SQLite integrity, evidence-chain verification, and the backup/restore drill.
4. Compare journal/evidence counts and Evidence Pack hashes with the Windows export.
5. Test a read-only broker import only. Do not submit live orders during migration.

## Migration acceptance

- Bundle verification is green on both machines, `migration_ready` is `true`, and the SHA-256 matches.
- SQLite integrity and evidence-chain verification are green.
- No `exchange_credentials` rows or sensitive settings remain in the bundle.
- DuckDB is rebuilt successfully; no old DuckDB file is copied as canonical data.
- macOS packaged smoke reports `ok=true` with Cocoa/WKWebView.
- Keychain credentials are recreated; no plaintext secret is in the repository or data bundle.
- Windows data remains read-only until all checks pass.
