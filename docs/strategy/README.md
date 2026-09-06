# Kuantra Strateji ve Mimari Kayıtları

Bu dizin Kuantra'nın ürün stratejisi, hedef mimarisi, yol haritası ve kabul edilmiş
mimari kararları için kalıcı kayıt sistemidir. Buradaki belgeler pazarlama metni değil;
uygulama kapsamını, kalite kapılarını ve durdurma kriterlerini belirleyen sözleşmelerdir.

## Belge kataloğu

| Kimlik | Belge | Durum | Sürüm | Son güncelleme |
|---|---|---:|---:|---:|
| KPS-001 | [Ürün ve Mimari Stratejisi](./KUANTRA-STRATEGY-001.md) | Accepted | 1.0.0 | 2026-09-05 |
| KDG-001 | [Geliştirme Yönetişimi](./DEVELOPMENT-GOVERNANCE.md) | Accepted | 1.0.0 | 2026-09-05 |
| KWT-001 | [İş Paketi / Agent Prompt Şablonu](./WORK-PACKAGE-TEMPLATE.md) | Active | 1.0.0 | 2026-09-05 |
| KPS-P0-STATUS | [Faz 0 durum panosu](./PHASE-0-STATUS.md) | Verified | — | 2026-09-06 |
| ADR-0001 | [Ürün kimliği ve ilk pazar](./adr/ADR-0001-product-identity-and-entry-market.md) | Accepted | — | 2026-09-05 |
| ADR-0002 | [Evidence ledger ve veri katmanları](./adr/ADR-0002-evidence-ledger-and-storage.md) | Accepted | — | 2026-09-05 |
| ADR-0003 | [Execution ve AI yetki sınırı](./adr/ADR-0003-execution-authority-boundary.md) | Accepted | — | 2026-09-05 |
| KTR-001 | [Release truth matrix](../release/README.md) | Accepted | 1.0.0 | 2026-09-06 |
| P0-WP01 | [Tekil paper execution rotası ve risk/compliance sözleşmesi](./work-packages/P0-WP01-execution-risk-contract.md) | Verified | — | 2026-09-05 |
| P0-WP02 | [Market data truth contract ve fabricated fiyat/latency temizliği](./work-packages/P0-WP02-market-data-truth-contract.md) | Verified | — | 2026-09-05 |
| P0-WP03 | [Frontend dev-toolchain güvenlik güncellemesi](./work-packages/P0-WP03-frontend-toolchain-security.md) | Verified | — | 2026-09-05 |
| P0-WP04 | [CI truth ve release güvenlik kapıları](./work-packages/P0-WP04-ci-truth-and-release-gates.md) | Verified | — | 2026-09-05 |
| P0-WP05 | [Python universal dependency lock](./work-packages/P0-WP05-python-universal-lock.md) | Verified | — | 2026-09-05 |
| P0-WP06A | [Replay ve excursion veri doğruluğu](./work-packages/P0-WP06A-replay-excursion-truth.md) | Verified | `d517c34` | 2026-09-06 |
| P0-WP06B | [Order-flow/L2/FIX truth boundary](./work-packages/P0-WP06B-orderflow-fix-truth.md) | Verified | `1cfd778` + `564beed` | 2026-09-06 |
| P0-WP07 | [Credential ve OS keychain truth boundary](./work-packages/P0-WP07-credential-keychain-boundary.md) | Verified | `a09ad80` | 2026-09-06 |
| P0-WP08 | [Experimental capability containment](./work-packages/P0-WP08-experimental-containment.md) | Verified | 1.0.0 | 2026-09-06 |
| P0-WP09 | [Release truth matrix ve current claims](./work-packages/P0-WP09-release-truth-matrix.md) | Verified | 1.0.0 | 2026-09-06 |
| P0-WP10 | [Üç OS final artifact smoke ve Faz 0 exit audit](./work-packages/P0-WP10-phase0-exit-audit.md) | Verified | 1.0.0 | 2026-09-06 |
| P1-WP01 | [Canonical Evidence Ledger Foundation](./work-packages/P1-WP01-canonical-evidence-ledger.md) | Active | 1.1.0 | 2026-09-06 |
| P1-WP02 | [Atomic Journal Evidence Write Adapter](./work-packages/P1-WP02-atomic-journal-evidence-write.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP03 | [Rebuildable Trade Projection ve Tombstone](./work-packages/P1-WP03-rebuildable-trade-projection.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP04 | [Projection Read Adapter ve Coverage Gate](./work-packages/P1-WP04-projection-read-adapter.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP05 | [Evidence-Gated DuckDB OLAP Hydration](./work-packages/P1-WP05-evidence-gated-olap-hydration.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP06 | [Bulk OLAP Sync Evidence Gate](./work-packages/P1-WP06-bulk-olap-sync-gate.md) | Active | 1.0.0 | 2026-09-06 |

## Sürümleme kuralları

1. Dosya adı kalıcı kimlik taşır; sürüm numarası dosya adına eklenmez. Böylece iç ve dış
   bağlantılar kırılmaz.
2. Yaşayan belgeler SemVer kullanır:
   - `PATCH`: anlamı değiştirmeyen açıklama, kaynak veya yazım düzeltmesi.
   - `MINOR`: mevcut karar sınırları içinde yeni ayrıntı, metrik veya faz teslimatı.
   - `MAJOR`: hedef pazar, ürün kimliği, yetki sınırı veya temel veri mimarisi değişikliği.
3. Her sürüm değişikliği belgenin `Değişiklik geçmişi` bölümüne ve bu kataloğa işlenir.
4. Kabul edilmiş ADR metni geriye dönük değiştirilmez. Karar değişirse yeni ADR yazılır;
   eski ADR `Superseded by ADR-XXXX` olarak işaretlenir.
5. Her strateji sürümü bir Git commit SHA'sına ve incelenen ürün tag/commit'ine bağlanır.
6. Bir faz başlamadan önce ilgili ADR'ler `Accepted`, iş paketi ise `Ready` olmalıdır.

## Durum sözlüğü

- `Draft`: tartışmaya açık, uygulama yetkisi vermez.
- `Proposed`: karar için hazır, henüz onaylanmamış.
- `Accepted`: uygulama için bağlayıcı.
- `Active`: kullanılan şablon veya süreç.
- `Superseded`: daha yeni belge tarafından değiştirilmiş.
- `Retired`: artık geçerli değil; tarihsel kayıt olarak tutulur.

## Değişiklik geçmişi

### 2026-09-05

- KPS-001 v1.0.0: v1.4.0 kod incelemesi, rekabet araştırması, hedef mimari,
  fazlandırma, ticari model ve talep doğrulama tabanı oluşturuldu.
- ADR-0001–0003 kabul edildi.
- KDG-001 ve KWT-001 ile agent destekli geliştirme süreci tanımlandı.
- P0-WP05 remote lock kanıtı `97774b2`, P0-WP06A replay/excursion truth implementation
  `d517c34` ile doğrulandı.

### 2026-09-06

- P0-WP06B ile seed order-flow/L2 verisi ve simulated FIX/DMA success yolları kaldırıldı;
  no-data/experimental-disabled sözleşmesi ve UI regression kanıtı eklendi.
- P0-WP07 ile exchange/generic secret'lar OS keychain'e taşındı; SQLite yalnızca referans
  ve metadata tutuyor, keychain yoksa credential yazma fail-closed oluyor.
- P0-WP06B follow-up `564beed` ile transport'suz FIX çağrıları risk state'inden önce
  disabled oluyor ve router testleri kalıcı compliance verisinden ayrıştırılıyor.
- P0-WP08 ile unsigned plugin download/runtime mount kapatıldı; AI/DEX/biometric/MCP,
  adapter ve reverse deploy yüzeyleri 503/fail-closed sözleşmesine taşındı.
- P0-WP08 `d0eda56` + `f8653e2` ile doğrulandı; packaged smoke, API/UI truth gates
  ve üç-OS push/PR CI yeşil (`34025225053`, `34025227211`).
- P0-WP09 ile current release claim'leri `KTR-001` truth matrix'e bağlandı; tarihsel release
  notları GitHub Release body'sinden ayrıldı ve exact tag/version ile forbidden-claim checker CI
  ve release workflow'a alındı. `7217610`, push CI `34027220927` ve PR CI `34027222829`
  ile üç OS'ta doğrulandı.
- P0-WP10 ile smoke raporları schema v2 provenance/hash bilgisi taşıyacak ve release workflow
  final NSIS/DMG/AppImage artefaktlarını kendi içinden doğrulayacak şekilde hazırlandı. Aday
  workflow `34035766242` ile üç OS final smoke ve publish audit geçti; backend suite ephemeral
  test data ile 350 passed/1 skipped. Teknik Phase 0 çıkışı Verified; gerçek release/tag
  yayınlama `publish=true` ve ayrı ürün sahibi onayına bırakıldı.
- P1-WP01, teknik Phase 0 çıkışı ve mevcut ürün sahibi faz-geçiş direktifinden sonra uygulanacak
  ilk Phase 1 paketi olarak hazırlandı. Append-only SQLite evidence ledger, idempotency ve
  hash-chain verifier kapsamı tanımlandı; gerçek release/tag yayınlama ise ayrı `publish=true`
  onay kapısı olarak kaldı.
- P1-WP01 implementation `43641e1` + CLI düzeltmesi `25e4640` + verifier hardening `db80a77` ile canonical SQLite `evidence_events` ledger, ortak
  runtime/Alembic schema, hash-chain verifier, duplicate/conflict kapısı, explicit legacy
  backfill/export CLI ve focused test suite eklendi. Full backend regression `359 passed,
  1 skipped`; `a103a06` için three-OS push CI `34038244922` green. `db80a77` sonrası CI
  denemesi GitHub billing/spending-limit koruması nedeniyle job başlatamadı; broker, DuckDB,
  UI ve AI akışlarına dokunulmadı.
- GitHub Actions maliyet koruması: tam üç-OS CI matrisi yalnızca `main` push'u ve PR→`main`
  için otomatik; feature branch push'u duplicate çalıştırma üretmiyor, manuel
  `workflow_dispatch` korunuyor. Release workflow'u değişmedi.
- GitHub Actions dahil dakika kotası %100 dolduğu için `Kuantra Terminal CI` ve
  `Kuantra Terminal Release` workflow'ları geçici olarak GitHub tarafında manuel disabled edildi;
  local doğrulama zorunlu kalır, kota resetinden sonra yeniden enable edilecektir.
- P1-WP01 `2f0e7d7` ile legacy journal upsert'i `ON CONFLICT DO UPDATE` kullanacak şekilde
  harden edildi; duplicate trade yazımı artık `trade_tags` ilişkilerini silmiyor.
- P1-WP02 `4dc7c22` ile production journal, CSV ve TradingView yazıları canonical evidence
  event'iyle aynı SQLite transaction'ına alındı; rollback/idempotency suite'i `14 passed`,
  full backend regression `364 passed, 1 skipped`.
- P1-WP03 `ad45281` ile typed `evidence_trade_projections`, Alembic `003_trade_projection`,
  deterministic rebuild/dry-run CLI ve physical delete yerine `CANCELED` tombstone teslim edildi;
  projection suite'i `5 passed`, full backend regression `369 passed, 1 skipped`.
- P1-WP04 `3fbc5c0` ile canlı journal yazıları typed projection'ı aynı transaction'da
  güncelliyor; exact coverage gate kullanan `TradeReadAdapter` seçili API, portfolio ve
  quant read path'lerine bağlandı. Eksik backfill durumunda projection/legacy veri
  karıştırılmadan bütün istek compatibility fallback'e gider. Focused suite `18 passed`,
  full backend regression `372 passed, 1 skipped`.
- P1-WP05 `7a5b596` ile DuckDB hydrator kanıtsız compatibility satırlarını OLAP'a
  taşımayı reddediyor; eksik coverage durumunda destructive rebuild yapmadan `BLOCKED`
  dönüyor. Legacy migration venue'ları için duplicate-safe exact coverage eklendi.
  Focused hydration/projection suite `15 passed`, full backend regression `374 passed,
  1 skipped`.
- P1-WP06 `99d6ad2` ile `SyncPipeline.full_sync()` de aynı evidence coverage gate'ine
  bağlandı; unverified bulk sync `0` ile fail-closed oluyor. Full backend regression
  `376 passed, 1 skipped`.
