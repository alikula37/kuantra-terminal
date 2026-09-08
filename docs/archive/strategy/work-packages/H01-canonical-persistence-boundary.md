<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# H01 — Canonical Persistence & Recovery Boundary

```yaml
work_package: H01
version: 1.1.0
status: Complete
date: 2026-09-08
baseline_commit: 5257e63
implementation_commit: 006e86e
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, P1-WP25, P1-WP26
next_work_package: H02
```

## Sonuç

H01 canonical evidence ledger, compatibility journal ve typed projection yazılarının
transaction/crash/recovery sınırını bounded olarak kanıtladı. Append acknowledgement
yalnız aynı transaction commit edildikten sonra veriliyor; canonical append veya
projection update sonrasında process kill rollback ile yarım kayıt bırakmıyor. Commit
sonrası ACK kaybında tekrar import aynı immutable event/projection durumuna dönüyor.

Bu paket yeni schema, ledger event type, funding/transfer modeli, connector, migration
veya kullanıcı verisi işlemi eklemedi. `SQLiteDriver.transaction_hook` yalnız test
amaçlı failure/crash injection sınırıdır; production çağrıları hook sağlamaz.

## Acceptance evidence

- [x] Process kill/failure injection: canonical append ve projection update öncesi
  crash sonrası trade, event ve projection sayısı sıfır; retry tek immutable event
  ve valid chain oluşturdu.
- [x] Commit sonrası ACK öncesi process kill sonrası event/projection korundu; replay
  aynı event ve projection sayısını korudu, duplicate semantic event oluşmadı.
- [x] Read-only database (`PRAGMA query_only`) ve read-only directory fixture'ı
  fail-closed kaldı; önceki kayıt korunurken yeni kayıt oluşmadı.
- [x] Bounded `database or disk is full` / `database is locked` injection rollback
  yaptı ve aynı import yeniden çalıştırılabildi.
- [x] Gerçek SQLite WAL busy writer yarışı 5 saniyelik mevcut busy timeout içinde
  `OperationalError` ile fail-closed kaldı; yarım trade/event/projection oluşmadı.
- [x] Concurrent duplicate import tek canonical event ve tek projection üretti;
  distinct concurrent imports deterministic chain içinde korundu.
- [x] Restart + `verify_chain` + projection dry-run/rebuild sonrası Evidence Pack
  snapshot'ı birebir eşdeğer kaldı; immutable lineage korunmuş oldu.
- [x] H01 + P1-WP01/P1-WP02/P1-WP21–25 backend regression focused suite:
  **60 passed, 2 warnings**; WP26 frontend coverage is included in the full
  frontend suite below.
- [x] Full backend suite: **643 passed, 2 warnings**.
- [x] Frontend suite: **67 passed**; production build, i18n **560/560** PASS.
- [x] Canonical Mac local CI: **MERGE READY**; compileall, release truth,
  packaging integrity, backend/frontend suite, arm64 desktop build ve native
  `wkwebview` smoke PASS.

## Red → green implementation

İlk H01 test koşusu iki process-crash testinde `SQLiteDriver` seviyesinde
deterministic injection sınırının bulunmadığını gösterdi. Bounded implementation ile
`SQLiteDriver`'a production'da boş kalan, test-only `transaction_hook` eklendi. Hook
şu gözlem noktalarını sağlar: `after_canonical_event`, `after_projection_update`,
`before_commit` ve `after_commit_before_ack`. Transaction sahipliği, SQLite schema
ve event contract değiştirilmedi. Son focused sonuç:

```text
test_h01_canonical_persistence.py: 9 passed in 5.86s
```

## Mac evidence

Evidence source commit:
`006e86e6b6fae022fc27a1169f55f0c1e82c7120`.

- Platform: macOS 26.3 arm64; Python 3.11.16; Node v20.20.2; npm 10.8.2;
  uv 0.12.10; PyInstaller 6.22.2.
- Tracked source tree SHA-256:
  `1ecee1a18702ca26bbf76ee6825e60bbf4de9d9285a09da0b1921de650862b86`.
- Backend lock SHA-256:
  `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`.
- Frontend lock SHA-256:
  `b392a59d09ade73564ce082b1a5bc1236618ebeee11703a992980cfd1812882c`.
- Local CI report SHA-256:
  `dd80ec3a8b6ad5e57ef6a3586f45ebacafa823e0111c6a677926e5391bf06154`.
- Local CI smoke report SHA-256:
  `1049c1384929f41217e4609a7034984bd3b4c6a58a83d3a1cb99e5d46ae51f1c`.
- `.app` executable SHA-256:
  `90f3b06f9cde166eacb7310927b600fb3b6f0c1195435c99cca0d7f721a9ce60`.
- Exact DMG: `dist/Kuantra-Terminal-1.4.0-aarch64.dmg`.
- DMG SHA-256:
  `80764167ba924db4d918dfccb893936b1ac95d72931524351a0c4bd8a37530ad`.
- Exact mounted-DMG smoke report SHA-256:
  `0fa3e94c0bb54cfea34f832f762ede25e50af96bc05dc59cc045721735cd145f`.
- DMG smoke selected the executable explicitly from a read-only mount, verified
  artifact/executable identity, `wkwebview` controller readiness and safe detach.
- Provenance: `COMPLETE`; source SHA came from checkout because `GITHUB_SHA` was
  absent. The default runtime smoke attempted the configured public Binance stream;
  this is network-using startup evidence, not offline runtime proof.

## Scope boundaries that remain open

H01 does not prove schema upgrade/restore (H02), signing/notarization/Gatekeeper,
second-host installation, Windows/Linux artifacts, dependency/license hardening,
privacy/keychain lifecycle, performance budgets, pilot or production readiness.
No real user data, credential, migration restore/apply, live broker or order action
was used. Default-branch Dependabot alerts remain a repository-owner/merge gate.

## Next dependency

H02 — Schema/upgrade/restore is the next current bounded package. It must use only
synthetic temporary data and preserve the same canonical/projection/Evidence Pack
equivalence boundary.
