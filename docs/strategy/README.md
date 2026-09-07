# Kuantra Strateji ve Mimari Kayıtları

Bu dizin Kuantra'nın ürün stratejisi, hedef mimarisi, yol haritası ve kabul edilmiş
mimari kararları için kalıcı kayıt sistemidir. Buradaki belgeler pazarlama metni değil;
uygulama kapsamını, kalite kapılarını ve durdurma kriterlerini belirleyen sözleşmelerdir.

## Belge kataloğu

| Kimlik | Belge | Durum | Sürüm | Son güncelleme |
|---|---|---:|---:|---:|
| KPS-001 | [Ürün ve Mimari Stratejisi](./KUANTRA-STRATEGY-001.md) | Accepted | 1.0.0 | 2026-09-05 |
| KDG-001 | [Geliştirme Yönetişimi](./DEVELOPMENT-GOVERNANCE.md) | Accepted | 1.0.0 | 2026-09-05 |
| KDG-002 | [Yerel CI ve merge gate politikası](./LOCAL-CI-POLICY.md) | Accepted | 1.1.0 | 2026-09-07 |
| KWT-001 | [İş Paketi / Agent Prompt Şablonu](./WORK-PACKAGE-TEMPLATE.md) | Active | 1.0.0 | 2026-09-05 |
| KPS-P0-STATUS | [Faz 0 durum panosu](./PHASE-0-STATUS.md) | Verified | — | 2026-09-06 |
| ADR-0001 | [Ürün kimliği ve ilk pazar](./adr/ADR-0001-product-identity-and-entry-market.md) | Accepted | — | 2026-09-05 |
| ADR-0002 | [Evidence ledger ve veri katmanları](./adr/ADR-0002-evidence-ledger-and-storage.md) | Accepted | — | 2026-09-05 |
| ADR-0003 | [Execution ve AI yetki sınırı](./adr/ADR-0003-execution-authority-boundary.md) | Accepted | — | 2026-09-05 |
| ADR-0004 | [Windows WebView2 renderer sınırı](./adr/ADR-0004-windows-webview2-renderer.md) | Accepted | — | 2026-09-07 |
| KTR-001 | [Release truth matrix](../release/README.md) | Accepted | 1.0.1 | 2026-09-07 |
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
| P0-WP11 | [WebView2 host diagnostics](./work-packages/P0-WP11-webview2-host-diagnostics.md) | Active | 1.0.0 | 2026-09-07 |
| P1-WP01 | [Canonical Evidence Ledger Foundation](./work-packages/P1-WP01-canonical-evidence-ledger.md) | Active | 1.1.0 | 2026-09-06 |
| P1-WP02 | [Atomic Journal Evidence Write Adapter](./work-packages/P1-WP02-atomic-journal-evidence-write.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP03 | [Rebuildable Trade Projection ve Tombstone](./work-packages/P1-WP03-rebuildable-trade-projection.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP04 | [Projection Read Adapter ve Coverage Gate](./work-packages/P1-WP04-projection-read-adapter.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP05 | [Evidence-Gated DuckDB OLAP Hydration](./work-packages/P1-WP05-evidence-gated-olap-hydration.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP06 | [Bulk OLAP Sync Evidence Gate](./work-packages/P1-WP06-bulk-olap-sync-gate.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP07 | [Trade Evidence Pack API](./work-packages/P1-WP07-trade-evidence-pack-api.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP08 | [Deterministic Replay ve Market-Context Attachment](./work-packages/P1-WP08-deterministic-replay-market-context.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP09 | [Market-Data Provenance Schema](./work-packages/P1-WP09-market-data-provenance.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP10 | [CSV Import Evidence Provenance ve Fail-Closed Validation](./work-packages/P1-WP10-csv-import-evidence-provenance.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP11 | [Read-Only Broker Lifecycle Import ve Reconciliation](./work-packages/P1-WP11-broker-lifecycle-import-reconciliation.md) | Active | 1.0.1 | 2026-09-06 |
| P1-WP12 | [Read-Only API Snapshot Adapter ve Credential Scope](./work-packages/P1-WP12-read-only-api-snapshot-adapter.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP13 | [Evidence Pack Export ve Backup/Restore Drill](./work-packages/P1-WP13-evidence-pack-export-restore-drill.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP14 | [Versioned Playbook ve Risk Policy Events](./work-packages/P1-WP14-versioned-playbook-risk-policy-events.md) | Active | 1.0.0 | 2026-09-06 |
| P1-WP15 | [Trade Evidence Pack UI ve Provenance Review](./work-packages/P1-WP15-trade-evidence-pack-ui.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP01 | [Sequence Gap-Aware Market Context](./work-packages/P2-WP01-sequence-gap-aware-market-context.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP02 | [Binance Snapshot + Delta Sequence Validator](./work-packages/P2-WP02-binance-depth-sequence-validator.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP03 | [Binance Depth Snapshot/Event Recovery Coordinator](./work-packages/P2-WP03-binance-depth-recovery-coordinator.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP04 | [Binance Depth Payload Normalization ve Venue Projection](./work-packages/P2-WP04-binance-depth-payload-projection.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP05 | [Canonical Market Event Envelope ve Hash Chain](./work-packages/P2-WP05-market-event-envelope.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP06 | [Durable Market Event Segment Writer](./work-packages/P2-WP06-market-event-segment-writer.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP07 | [Rotated Market Event Segments ve Manifest Recovery](./work-packages/P2-WP07-market-event-segment-manifest.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP08 | [Columnar Market Event Batch Contract](./work-packages/P2-WP08-market-event-batch-contract.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP09 | [Injected Binance Depth Ingestor Boundary](./work-packages/P2-WP09-binance-depth-ingestor.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP10 | [Injected Async Binance Depth Transport Boundary](./work-packages/P2-WP10-binance-depth-transport-boundary.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP11 | [Public Binance Depth Network Adapter](./work-packages/P2-WP11-binance-depth-network-adapter.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP12 | [Bounded Binance Depth Reconnect Session](./work-packages/P2-WP12-binance-depth-reconnect-session.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP13 | [Deterministic Binance Depth Soak Harness](./work-packages/P2-WP13-binance-depth-soak-harness.md) | Active | 1.0.0 | 2026-09-06 |
| P2-WP14 | [Opt-in Binance Depth Testnet Soak Gate](./work-packages/P2-WP14-binance-depth-testnet-soak-gate.md) | Active | 1.0.1 | 2026-09-07 |
| P2-WP15 | [Binance Depth Soak Report Verification Gate](./work-packages/P2-WP15-binance-depth-report-verification.md) | Active | 1.0.1 | 2026-09-07 |
| P2-WP16 | [Binance Depth Soak Report Hash Archive](./work-packages/P2-WP16-binance-depth-report-hash-archive.md) | Active | 1.0.0 | 2026-09-07 |
| P2-WP17 | [Binance Depth Soak Operator Attestation](./work-packages/P2-WP17-binance-depth-operator-attestation.md) | Active | 1.0.0 | 2026-09-07 |
| P2-WP18 | [Binance Depth Attestation Key Registry](./work-packages/P2-WP18-binance-depth-key-registry.md) | Active | 1.0.0 | 2026-09-07 |
| P2-WP19 | [Binance Depth Attestation Review Gate](./work-packages/P2-WP19-binance-depth-attestation-review-gate.md) | Active | 1.0.0 | 2026-09-07 |
| P2-WP20 | [Binance Depth Operator Review ve Key Policy](./work-packages/P2-WP20-binance-depth-review-record-key-policy.md) | Active | 1.0.0 | 2026-09-07 |
| P2-WP21 | [Binance Depth Evidence Bundle ve Restore Drill](./work-packages/P2-WP21-binance-depth-evidence-bundle.md) | Active | 1.0.0 | 2026-09-07 |

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
- P1-WP07 `65e4b71` ile `GET /trades/{trade_id}/evidence` kaynak-linked snapshot,
  ledger integrity, hash/provenance ve coverage bilgisini raw payload sızdırmadan tek
  read-only pakette sunuyor. Full backend regression `377 passed, 1 skipped`.
- P1-WP08 `de93a48` ile replay projection-aware oldu; bounded market-context attachment,
  deterministic `replay_fingerprint`, UTC boundaries ve `source_verified=false`
  provenance'ı API/Evidence Pack'e eklendi. Focused replay/candle/evidence suite `68
  passed`, full backend regression `379 passed, 1 skipped`.
- P1-WP09 `811cb6c` ile `market_candles` venue/feed/source-event/sequence/ingestion
  provenance alanlarına taşındı; dokuz kolonlu legacy DuckDB dosyaları additive migration
  ile `UNVERIFIED` olarak açılıyor. Binance kline kimliği saklanıyor ancak sequence/gap
  doğrulaması gelene kadar `source_verified=false` kalıyor. Focused suite `46 passed`,
  full backend regression `382 passed, 1 skipped`.
- P1-WP10 `d62db79` ile CSV importer eksik timestamp/identity/numeric alanlarda fail-closed
  oldu; current-time, BTCUSDT, BUY veya qty=1 gibi sentetik varsayılanlar kaldırıldı.
  File SHA-256, row SHA-256, row number ve format canonical `LegacyTradeImported`
  provenance'ına bağlandı. Focused import suite `25 passed`, full backend regression
  `386 passed, 1 skipped`.
- P1-WP11 `4b23405` ile Binance/OKX fixture/export envelope'ı normalized order/fill
  lifecycle event'lerine ve explicit quantity/price/fee/orphan reconciliation raporuna
  bağlandı. Aynı export idempotent; eksik/çelişkili satırlar `UNRECONCILED`. Local JSON
  endpoint 10 MB ile bounded, live connector veya order write yok. Focused suite `6
  passed`, full backend regression `392 passed, 1 skipped`.
- P1-WP12 ile gerçek exchange çağrısı execution engine'den ayrıldı: Binance/OKX için
  keychain `READ_ONLY` scope, CCXT fetch-only proxy, bounded pagination/retry ve
  tamper-detectable snapshot manifest eklendi. Incomplete snapshot başarı gibi
  raporlanmıyor; focused suite `6 passed`, full backend regression `398 passed,
  1 skipped`.
- P1-WP13 ile Trade Evidence Pack deterministic JSON/HTML artifact ve payload/artifact
  SHA-256 header'larıyla export edilebilir oldu. SQLite backup artık hash, integrity,
  evidence chain ve geçici DuckDB restore drill'i geçmeden başarılı sayılmıyor;
  focused suite `4 passed`, full backend regression `402 passed, 1 skipped`.
- P1-WP14 ile playbook tanımları/sürüm snapshot'ları ve playbook audit review'ları
  append-only `JournalReviewAdded` olaylarıyla, risk policy snapshot'ları ve
  pre-execution kararları ise `RiskEvaluated` olaylarıyla aynı SQLite transaction
  sınırına alındı. RiskGuard metadata'sı policy id/version/hash ve risk event id
  taşıyor; eski playbook/risk davranışı korunuyor. Focused suite `3 passed`, full
  backend regression `405 passed, 1 skipped`.
- P1-WP15 ile Journal içinden source-linked Trade Evidence Pack paneli açılabilir
  hale geldi. Ledger bütünlüğü, typed projection/legacy read kaynağı, policy/playbook
  snapshot referansı, market-context provenance ve JSON/HTML export durumu tek
  read-only ekranda gösteriliyor. Frontend suite `51 passed`, production build
  ve tri-locale parity doğrulandı.
- P2-WP01 ile candle provenance içindeki `source_sequence` sürekliliği görünür hale
  geldi: `COMPLETE`, `PARTIAL` ve `GAPPED` ayrımı, bounded gap listesi ve
  `sequence_gap_count` eklendi. Gap veya eksik sequence hiçbir zaman
  `source_verified=true` olarak yükseltilmiyor; mevcut bar-approximation replay
  akışı fail-closed açıklama ile korunuyor. Focused suite `49 passed`.
- P2-WP02 ile Binance snapshot + diff-depth sequence state machine'i eklendi.
  `U/u` snapshot bridge, stale event, gap/recovery ve futures `pu` previous-ID
  kuralları saf ve network'süz bir validator olarak test ediliyor. Hatalı veya
  yanlış sembollü event'ler local book'a uygulanmadan `GAP` durumuna geçiyor;
  sentetik recovery yapılmıyor. Focused suite `7 passed`.
- P2-WP03 ile websocket event buffer'ı ve REST snapshot yarışının transport-free
  recovery coordinator sözleşmesi eklendi. Bounded buffer overflow, snapshot-behind
  retry, stale replay filtering ve açık `start_buffering()` recovery cycle'ı
  test ediliyor; network/order-book mutation hâlâ kapsam dışı. Focused suite
  `6 passed`.
- P2-WP04 ile Binance depth payload'ı Decimal tabanlı normalize eden ve yalnızca
  sequence `APPLIED` ise venue L2 projection'a yazan ayrı adapter eklendi.
  Mevcut local matching engine'e bağlanılmadı; duplicate/non-finite level,
  zero-quantity silme ve atomic rejection regression'ları eklendi. Focused suite
  `6 passed`.
- P2-WP05 ile normalize snapshot/APPLIED update payload'ları için deterministic
  source identity, payload SHA-256 ve prev/event hash chain envelope'ı eklendi.
  Duplicate identity idempotent, farklı içerik conflict; gap/rejected/stale
  kararları canonical applied chain'e giremiyor. Durable market storage ve real
  feed hâlâ kapsam dışı. Focused suite `6 passed`.
- P2-WP06 ile canonical envelope'ların tek-yazarlı fsync-backed JSONL segment'e
  append edilmesi ve restart recovery drill'i eklendi. Bozuk hash veya yarım
  final line otomatik onarılmıyor; strict mod açılışı fail-closed yapıyor.
  Parquet/Arrow/DuckDB ve multi-process writer kapsam dışı. Focused suite
  `5 passed`.
- P2-WP07 ile global chain'i segmentler arasında koruyan rotation ve canonical
  manifest eklendi. Missing segment, manifest tamper ve cross-segment duplicate
  identity recovery testleri fail-closed; Parquet/Arrow/DuckDB compaction hâlâ
  kapsam dışı. Focused suite `5 passed`.
- P2-WP08 ile Arrow/Parquet öncesi bounded event/level row batch sözleşmesi
  eklendi. Decimal değerler canonical string, chain slice contiguous, bounds
  aşımı truncation'sız fail-closed; mevcut runtime'da pyarrow/DuckDB yokluğu
  nedeniyle gerçek sink yazılmadı. Focused suite `5 passed`.
- P2-WP09 ile coordinator → Decimal venue book → canonical chain → optional
  durable segment akışı injected bir ingestor sınırında birleştirildi. Snapshot
  replay event hand-off, live gap, malformed payload, restart ve sink failure
  testleri eklendi; gerçek Binance transport hâlâ kapsam dışı. Focused suite
  `5 passed`.
- P2-WP10 ile bounded async event source/snapshot fetcher transport sözleşmesi
  eklendi. Snapshot/source failure, stop event, queue backpressure ve güvenli
  Binance URL üretimi test ediliyor; gerçek websocket/HTTP client hâlâ kapsam
  dışı. Focused suite `5 passed`.
- P2-WP11 ile testnet varsayılanlı, TLS-only public REST snapshot + websocket
  depth adapter'ı transport boundary'ye bağlandı; credential, execution,
  reconnect ve source verification terfisi kapsam dışı tutuldu. Focused suite
  `5 passed`.
- P2-WP12 ile source/snapshot failure sonrası reconnect budget, exponential
  backoff ve stop-event kapanışı bounded session sonucuna bağlandı; persistence,
  recovery ve snapshot rejection hataları retry edilmedi. Focused suite
  `5 passed`.
- P2-WP13 ile disconnect fixture'ı aynı ingestor + rotated durable segment sink
  üzerinden yeniden oynatılıyor; chain continuity, gap terminality ve reopen
  recovery kanıtı deterministik harness'e bağlandı. Focused suite `3 passed`.
- P2-WP14 ile fixture-default soak CLI ve explicit `--allow-network` testnet
  kapısı eklendi. Rapor schema'sı chain/sink/session ölçümlerini taşır;
  `source_verified` ve execution authority false kalır. Focused suite
  `5 passed`.
- P2-WP15 ile soak JSON raporları schema, session decision, chain/sink
  bütünlüğü ve truth flag tamper'ına karşı fail-closed doğrulanıyor. Geçerli
  testnet raporu bile production verification'a terfi etmiyor. Focused suite
  `5 passed`.
- P2-WP16 ile doğrulanmış soak raporları hash-adresli JSON + fsync manifest
  arşivine append-only/idempotent olarak alınıyor; dosya veya manifest tamper'ı
  strict recovery'de reddediliyor. Focused suite `5 passed`.
- P2-WP17 ile arşivlenmiş rapor hash/metadata'sı için opsiyonel Ed25519
  operator attestation ve strict sidecar store eklendi. İmza source verification
  veya execution authority yükseltmiyor. Focused suite `5 passed`.
- P2-WP18 ile Ed25519 public key registry/revocation append-only event log'u
  eklendi. Revoked key tarihsel imzayı geçersiz kılmıyor; audit status'u
  `REVOKED_KEY` oluyor. Focused suite `5 passed`, full backend regression
  `497 passed, 1 skipped`.
- P2-WP19 ile archived depth attestation için aktif kayıtlı anahtar, geçerli
  imza, testnet verdict'i ve freshness'i birlikte kontrol eden fail-closed
  `ELIGIBLE_FOR_REVIEW` gate'i eklendi. Gate `source_verified` veya
  `execution_authority` yükseltmiyor; fixture, revoked, stale/future ve
  ambiguous multi-attestation durumlarını reddediyor. Focused suite `5 passed`,
  full backend regression `502 passed, 1 skipped`.
- P2-WP20 ile gate çıktısını ve key-policy snapshot'ını hash'leriyle birlikte
  imzalayan append-only operator review kaydı eklendi. Tek aktif key, yaş ve
  revoke-retention politikası fail-closed değerlendiriliyor; review kaydı
  `retention_until` taşıyor ve hiçbir truth/execution yetkisi üretmiyor.
  Focused suite `5 passed`, full backend regression `507 passed, 1 skipped`.
- P2-WP21 ile archive, attestation, registry ve review kayıtlarını private key
  içermeden deterministic ZIP evidence bundle'a alan, manifest/hash doğrulayan
  ve strict restore recovery yapan akış eklendi. Focused suite `5 passed`, full
  backend regression `512 passed, 1 skipped`.

### 2026-09-07

- KDG-002 v1.0.0 ile GitHub Actions kotası kullanılamazken yerel CI merge gate'i canonical
  süreç olarak kabul edildi; packaged smoke'un Qt fallback'i yeşil UI kontrollerine rağmen
  merge'i bloklayan fail-closed kanıt kapısına bağlandı.
- ADR-0004 ile Windows production renderer'ı Evergreen WebView2 olarak sabitlendi; PyQt6/Qt
  WebEngine payload'dan çıkarıldı ve Windows smoke görünür WebView2 controller'ı ile doğrulanır.
- P0-WP11 ile WebView2 controller `E_ABORT` blocker'ını farklı Windows makinesi
  gerektirmeden runtime/profile/native-host katmanlarına ayıran bağımsız, bounded
  probe tanımlandı. Aynı host'ta runtime ve interop mevcut olmasına rağmen bağımsız
  probe ve gerçek paket smoke'u `CreateCoreWebView2ControllerAsync` / `E_ABORT` ile
  BLOCKED kaldı; probe başarısı ürün smoke veya release approval sayılmıyor.
- P2-WP14/P2-WP15 operasyon kanıtında offline fixture raporu
  `VALID_OFFLINE_FIXTURE` olarak doğrulandı; public Binance testnet denemesi
  snapshot fetch aşamasında `FAILED_OBSERVATION` ile fail-closed kaldı. 0 event'li
  bu negatif sonuç gerçek feed gözlemi veya source verification sayılmıyor;
  ağ koşulları değişmeden yeni soak tekrarı planlanmıyor.
