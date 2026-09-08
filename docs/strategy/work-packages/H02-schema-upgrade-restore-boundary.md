<!-- doc-role: current-work-package -->
# H02 — Schema Upgrade & Restore Boundary

```yaml
work_package: H02
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 006e86e
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

- [ ] Supported old schema preflight/upgrade idempotent; canonical data korunuyor.
- [ ] Interrupted migration/restore sonrası no-half-upgrade ve tekrar açılış sonucu
  fail-closed, deterministik ve tekrar çalıştırılabilir.
- [ ] Corrupt backup, missing segment/entry, traversal/symlink ve incompatible future
  schema açık hata ile reddediliyor; hedef data directory değişmeden kalıyor.
- [ ] Restore sonrası `verify_chain` PASS; projection rebuild ve Evidence Pack snapshot
  canonical lineage/correction/coverage bilgilerini koruyor.
- [ ] Red→green focused tests, full backend/frontend suite ve Mac local CI aynı source
  commit üzerinde PASS; yalnız synthetic temporary data kullanılıyor.
- [ ] Yeni schema/event capability, funding/transfer modeli, live order, credential,
  destructive migration apply veya release/pilot claim'i eklenmiyor.

## Kesinlikle kapsam dışı

H04 threat model/archive extraction hardening, H05 dependency/SBOM, H06 privacy/keychain,
H07 performance, N03–N06 platform/distribution proof, signing/notarization, Windows/Linux
host kanıtı, pilot/release ve full-account PnL/tax accounting.

## Başlangıç kararı

H01 `006e86e` ile canonical persistence/recovery boundary'sini kapattı. H02 tamamlanmadan
restore/upgrade production claim'i veya gerçek kullanıcı migration'ı açılmaz.
