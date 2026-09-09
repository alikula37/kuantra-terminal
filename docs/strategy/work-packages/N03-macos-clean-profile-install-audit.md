<!-- doc-role: current-work-package -->
# N03 — macOS Temiz Profil / İkinci Host Install-Lifecycle Audit

```yaml
work_package: N03
version: 1.0.0
status: InProgress
date: 2026-09-09
baseline_commit: e042790
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP27, N01, N02, H01, H02, H04, H06
release_gate: H05-commercial-distribution-deferred
```

## Amaç

Mac arm64 üzerinde P1-WP27 ile doğrulanan sentetik değer zincirinin, geliştirici
profiline veya mevcut checkout/cache durumuna bağlı olmadığını ikinci bir temiz
macOS profili ya da ikinci bir Mac host üzerinde kanıtlamak. Bu paket install →
launch → temiz local data oluşturma → sentetik import/review/export → close/reopen
akışının host/lifecycle kanıtıdır; imzalı dağıtım veya production readiness değildir.

## Mevcut blocker

`HOST_REQUIRED`: mevcut hostta aynı geliştirici profiliyle yapılan packaged smoke,
geçici `KUANTRA_DATA_DIR` kullanımı veya mevcut checkout'ın silinip yeniden açılması
temiz ikinci profil/host kanıtı sayılmaz. Gerçek kullanıcı hesabı oluşturma, admin
onayı, Gatekeeper/quarantine değişikliği veya başka host erişimi kullanıcı/host sahibi
tarafından sağlanmalıdır. Bu paket, host hazır olmadan sonucu PASS/COMPLETE olarak
işaretlemez.

## Kanıt ve kapsam sözleşmesi

1. Audit başlamadan önce host, macOS sürümü/architecture, kullanıcı profilinin temiz
   olduğu ve geliştirici cache/credential/migration data içermediği kaydedilir.
2. P1-WP27 ile üretilen aynı sentetik fixture ve açıkça seçilen artifact kullanılır;
   fixture hash'i, source commit, tracked tree, lock hash'leri, executable ve artifact
   hash'leri tek raporda bağlanır.
3. İlk launch yeni ve private data directory oluşturur. Windows data, migration ZIP,
   SQLite/DuckDB, log, plugin, model, `.env`, credential veya gerçek kullanıcı verisi
   taşınmaz. Gerçek credential Keychain'e yazılmaz.
4. Import → review → Evidence Pack → JSON/HTML/CSV export → close/reopen akışı
   sentetik veriyle çalışır; `PARTIAL`, `UNKNOWN` ve `NOT_AVAILABLE` complete/zero/pass
   yapılmaz. Weekly review kimliği ve snapshot lineage'ı korunur.
5. Quarantine/Gatekeeper davranışı yalnız gözlemlenir ve raporlanır. Signing,
   notarization, stapled ticket veya commercial distribution iddiası N03'ten çıkmaz;
   bunlar N05 ve owner/release kapılarıdır.
6. Test başarısı bu host/profile/lifecycle kanıtı ile sınırlıdır; Windows/Linux,
   Intel Mac, kullanıcı pilotu, update/uninstall policy veya production support limiti
   iddia edilmez.

## Acceptance criteria

- [ ] İkinci temiz macOS profil/host, OS version/architecture ve temiz başlangıç
  koşulları sahibi tarafından seçilip kanıtlanıyor; geliştirici cache/credential veya
  önceki Kuantra data'sı bulunmadığı kaydediliyor.
- [ ] Seçilen packaged artifact'in source commit, provenance status, executable SHA-256
  ve artifact SHA-256 değerleri raporlanıyor; artifact mismatch veya eksik provenance
  fail-closed kalıyor.
- [ ] App kopyalama/ilk açılış ve varsa quarantine/Gatekeeper davranışı gözlenip
  explicit sonuç olarak kaydediliyor; approval gerektiğinde kullanıcı/host sahibi
  onayı olmadan atlanmıyor.
- [ ] İlk launch temiz private data directory oluşturuyor; Windows/migration bundle,
  kullanıcı credential'ı veya mevcut checkout verisi okunmadan startup tamamlanıyor.
- [ ] Sentetik import preview → import → review/discrepancy → Evidence Pack →
  JSON/HTML/CSV export → close/reopen akışı geçiyor; export ve review snapshot
  deterministik, coverage sınırları görünür ve no-data false-success yok.
- [ ] Uygulama kapatılıp yeniden açıldığında sentetik local data ve review lineage'ı
  beklenen şekilde korunuyor; veri kaybı, sessiz reset veya yarım transaction yok.
- [ ] Audit raporu, focused regression, `python3.11 scripts/check_docs.py` ve uygun
  locked local CI sonuçlarını aynı source commit/platform ile bağlıyor; sınırlamalar,
  network/credential/live-execution durumu ve sonraki N04 bağımlılığı açıkça yazılıyor.

## Kesinlikle kapsam dışı

- Developer ID signing, notarization, stapled ticket ve final commercial DMG (N05).
- Update/uninstall/rollback veri koruma matrisi (N04); N03 yalnız mevcut packaged
  install-lifecycle ve close/reopen kanıtını sağlar.
- Windows/Linux veya başka architecture final artifact kanıtı (N06/host kapısı).
- Gerçek kullanıcı verisi, migration apply/restore, credential/Keychain yazımı,
  exchange credential, market stream zorlaması veya canlı broker emri.
- Yeni connector, funding/transfer schema, full-account PnL/tax, AI order authority,
  plugin promotion, production/release veya ticari support iddiası.

## Uygulama sırası

1. Host/profile sahibi ve temiz koşul onayını kaydet; mevcut `.codex/` ve kullanıcı
   dosyalarını silmeden izole test alanını doğrula.
2. P1-WP27 artifact/provenance hash'lerini doğrula ve quarantine davranışını gözle.
3. Temiz profile ilk launch ve synthetic import/review/export/reopen akışını çalıştır.
4. Close/reopen, data-preservation ve no-secret/no-network sınırlarını doğrula.
5. Red → green focused evidence, docs gate ve local CI sonuçlarını bu pakete yaz.
6. Kanıt eksikse paketi açık bırak; kanıt tamamlanırsa STATUS üzerinden N04'ü seç.

## Sonraki bağımlılık

N03 tamamlanmadan N04 update/uninstall data-preservation denetimi ve N05 signing/
notarization final-artifact doğrulaması production kanıtı sayılamaz. H05 ticari
license/notices ve default-branch Dependabot disposition gate'i deferred kalır;
P1-WP27'nin packaged audit kanıtı bu kapıları kapatmaz.
