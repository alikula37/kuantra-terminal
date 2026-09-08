<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# H02 — Schema Upgrade & Restore Boundary

```yaml
work_package: H02
version: 1.1.0
status: Complete
date: 2026-09-08
baseline_commit: 006e86e
completed_commit: 169c446
evidence_commit: ed689a0
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H01
```

## Amaç

Supported eski SQLite şeması, interrupted migration, corrupt backup, missing segment
ve incompatible future schema durumlarında verinin fail-closed korunmasını kanıtlamak.
H02 yalnız mevcut migration/bundle/restore sözleşmesinin bounded hardening paketidir;
canonical ledger ile mutable projection'ın doğrulanmış restore sonrası eşdeğerliğini
ölçer.

## Davranış sözleşmesi

- Upgrade başlamadan önce preflight schema/version/integrity kontrolü ve doğrulanabilir
  geçici backup alınır; backup veya preflight başarısızsa upgrade ACK verilmez.
- Supported eski schema upgrade'i idempotenttir; process kill veya migration exception
  sonrası yeniden açma ya eski geçerli DB'yi ya da doğrulanmış yeni DB'yi gösterir.
- Corrupt backup, bozuk archive entry, missing segment, path traversal veya checksum
  uyuşmazlığı fail-closed reddedilir; kısmi restore kullanıcı verisi olarak açılmaz.
- Incompatible future schema sürümü downgrade/ignore edilmez; açık unsupported sonucu
  verilir ve mevcut data directory sessizce silinmez/resetlenmez.
- Restore sonrası `verify_chain`, projection rebuild ve Trade Evidence Pack source
  event hash, correction lineage, coverage ve snapshot determinism'i korur.
- Restore/apply yalnız sentetik temporary fixture üzerinde test edilir. Gerçek kullanıcı
  verisi, credential, migration ZIP'i veya destructive apply bu pakette kullanılmaz.

## Red test kapsamı

- Current schema ile supported older fixture: version detection, preflight ve upgrade
  sonrası tablo/index/trigger bütünlüğü.
- Migration adımlarının her kritik noktasında process kill/failure injection; retry,
  rollback ve no-half-upgrade kontrolü.
- Valid backup round-trip: canonical event chain, mutable projection ve Evidence Pack
  snapshot'ının restore öncesi/sonrası eşdeğerliği.
- Corrupt backup checksum/JSON/SQLite integrity, missing required entry/segment,
  archive path traversal/symlink ve unsupported future schema negative testleri.
- Interrupted restore cleanup: temporary staging/artifact yalnız bounded scope içinde
  kalır; hedef data directory yanlışlıkla silinmez veya kısmi içerikle açılmaz.

## Uygulama sınırı

İlk adım mevcut `SQLiteDriver.run_migrations`, Alembic revisions, evidence/projection
schema primitives ve `docs/MACOS_MIGRATION.md` bundle akışını okuyup kırmızı test
matrisini yazmaktır. Test kanıtı eksikse yalnız ilgili migration/restore boundary'si
uygulanır. Yeni funding/transfer event type, connector, live execution, AI authority,
genel backup ürünü veya kullanıcı verisi taşıma akışı eklenmez.

## Acceptance criteria

- [x] Supported old schema preflight/upgrade idempotent; canonical data korunuyor.
- [x] Interrupted migration/restore sonrası no-half-upgrade ve tekrar açılış sonucu
  fail-closed, deterministik ve tekrar çalıştırılabilir.
- [x] Corrupt backup, missing segment/entry, traversal/symlink ve incompatible future
  schema açık hata ile reddediliyor; hedef data directory değişmeden kalıyor.
- [x] Restore sonrası `verify_chain` PASS; projection rebuild ve Evidence Pack snapshot
  canonical lineage/correction/coverage bilgilerini koruyor.
- [x] Red→green focused tests, full backend/frontend suite ve Mac local CI aynı source
  commit üzerinde PASS; yalnız synthetic temporary data kullanılıyor.
- [x] Yeni schema/event capability, funding/transfer modeli, live order, credential,
  destructive migration apply veya release/pilot claim'i eklenmiyor.

## Uygulama ve kanıt

- `upgrade_sqlite_schema` yalnız desteklenen baseline/evidence şemalarını read-only
  preflight, doğrulanabilir snapshot, temporary staged upgrade, legacy evidence
  backfill, projection rebuild ve atomic file promotion sırasıyla işler. Eski hedef
  SQLite/WAL seti `.pre-upgrade-*` backup olarak korunur; failure injection öncesinde
  target'a yazılmaz.
- `SQLiteDriver` yalnız additive legacy trade sütunlarını (`commission`,
  `updated_at` ve mevcut nullable snapshot alanları) tamamlar; identity alanları
  eksikse şema unsupported kalır. Evidence/projection doğrulaması bootstrap ile
  sessizce onarılmaz.
- Bundle verify current schema, integrity, chain hash, projection coverage, manifest
  hash/size, missing entry, traversal ve symlink kontrollerini yapar. Restore önce
  staging directory'ye çıkarır, checksum/schema/coverage doğrular ve ancak sonra
  atomic directory promotion yapar.
- CLI'de gelecekteki gerçek kullanıcı verisi için açık opt-in
  `python scripts/macos_migration.py upgrade-schema --db-path ...` sınırı vardır;
  mevcut temiz Mac bootstrap'ında bu komut çalıştırılmadı.
- Red→green H02/migration/package focused suite: **19 passed**. Full backend suite:
  **651 passed, 2 warnings**. Testler yalnız synthetic temporary SQLite/archive
  fixture kullandı; gerçek kullanıcı verisi, credential, migration ZIP'i veya live
  broker işlemi yoktu.
- Mac local CI on `ed689a0ba7fd571d176cb3dfc09ae9397dace298`: **MERGE READY**;
  report SHA-256 `4ad98b4fd3d6eb6f0cc2afb2b554402c8f8bb1ede35643a8d0065f30ec935580`,
  tracked tree SHA-256
  `cf382072bb678f95286170fe3cfe0c2e8f886b546a707fa890c298c58e966c73`, local `.app`
  SHA-256 `51d44e29faa675acfcd10878d5ef0dd11ddb66cf2da8553d52d28c18cba3b4df`.
  Exact read-only DMG/WKWebView smoke PASS; DMG report SHA-256
  `da82507eda312bb6effc14acc2dbd2febf14109ab45175411593bad30105e1f2`, DMG SHA-256
  `0f53140163ba6526b611fbe7dff8b70425155ac1173e8c9801e140e4fd5c4fc8`, mounted
  executable SHA-256 `c75201db4fe54ace8b06eb85d6315ed5695e5ae7219c6d7b60434cc955980173`.
  `uv --offline` preparation is dependency evidence only; runtime smoke used the
  configured public stream and does not prove offline runtime.

Sonraki bounded paket: **H04 — Threat Model & Trust Boundaries**. H04 tamamlanana
kadar archive/import/WebView/gateway trust-boundary iddiaları production gate sayılmaz.

## Kesinlikle kapsam dışı

H04 threat model/archive extraction hardening, H05 dependency/SBOM, H06 privacy/keychain,
H07 performance, N03–N06 platform/distribution proof, signing/notarization, Windows/Linux
host kanıtı, pilot/release ve full-account PnL/tax accounting.

## Başlangıç kararı

H01 `006e86e` ile canonical persistence/recovery boundary'sini kapattı. H02
`169c446` ile yalnız sentetik fixture üzerinde schema/restore boundary'sini kapattı.
Gerçek kullanıcı migration'ı hâlâ `docs/MACOS_MIGRATION.md` içindeki açık onaylı akışa
bağlıdır; H04 ve sonraki production hardening kapıları geçilmeden production claim'i
açılmaz.
