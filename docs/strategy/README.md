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
| KPS-P0-STATUS | [Faz 0 durum panosu](./PHASE-0-STATUS.md) | Active | — | 2026-09-05 |
| ADR-0001 | [Ürün kimliği ve ilk pazar](./adr/ADR-0001-product-identity-and-entry-market.md) | Accepted | — | 2026-09-05 |
| ADR-0002 | [Evidence ledger ve veri katmanları](./adr/ADR-0002-evidence-ledger-and-storage.md) | Accepted | — | 2026-09-05 |
| ADR-0003 | [Execution ve AI yetki sınırı](./adr/ADR-0003-execution-authority-boundary.md) | Accepted | — | 2026-09-05 |
| P0-WP01 | [Tekil paper execution rotası ve risk/compliance sözleşmesi](./work-packages/P0-WP01-execution-risk-contract.md) | Verified | — | 2026-09-05 |
| P0-WP02 | [Market data truth contract ve fabricated fiyat/latency temizliği](./work-packages/P0-WP02-market-data-truth-contract.md) | Verified | — | 2026-09-05 |
| P0-WP03 | [Frontend dev-toolchain güvenlik güncellemesi](./work-packages/P0-WP03-frontend-toolchain-security.md) | Verified | — | 2026-09-05 |
| P0-WP04 | [CI truth ve release güvenlik kapıları](./work-packages/P0-WP04-ci-truth-and-release-gates.md) | Verified | — | 2026-09-05 |
| P0-WP05 | [Python universal dependency lock](./work-packages/P0-WP05-python-universal-lock.md) | Verified | — | 2026-09-05 |
| P0-WP06A | [Replay ve excursion veri doğruluğu](./work-packages/P0-WP06A-replay-excursion-truth.md) | Verified | `d517c34` | 2026-09-06 |
| P0-WP06B | [Order-flow/L2/FIX truth boundary](./work-packages/P0-WP06B-orderflow-fix-truth.md) | Verified | `1cfd778` | 2026-09-06 |
| P0-WP07 | [Credential ve OS keychain truth boundary](./work-packages/P0-WP07-credential-keychain-boundary.md) | Verified | `TBD` | 2026-09-06 |

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
