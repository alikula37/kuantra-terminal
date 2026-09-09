<!-- doc-role: current-work-package -->
# P1-WP27 — G0–G2 Supported Matrix ve Packaged Value-Chain Audit

```yaml
work_package: P1-WP27
version: 1.0.0
status: InProgress
date: 2026-09-09
baseline_commit: 3e8ecab
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP16, P1-WP17, P1-WP18, P1-WP19, P1-WP20, P1-WP21, P1-WP22, P1-WP23, P1-WP24, P1-WP25, P1-WP26, H01, H02, H04, H06, H07
release_gate: H05-commercial-distribution-deferred
```

## Amaç

G0–G2 kapılarının mevcut bounded davranışla gerçekten eşleştiğini tek bir güncel
destek matrisi, bağımsız golden-oracle denetimi ve gerçek packaged executable üzerinde
sentetik import → review → Evidence Pack → export → reopen kanıtıyla doğrulamak.
Bu paket yeni ürün capability'si açmaz; mevcut P1-WP22–26 akışının kabul kanıtını
birleştirir ve kullanıcıya yanlış market, accounting veya production desteği sözü
verilmesini engeller.

## Ürün ve kanıt sınırı

Kuantra local-first Execution Intelligence & Trade Forensics Workstation'dır. Bu
paketin başarılı olması profitability, full-account PnL/tax doğruluğu, broker
reconciliation completeness, live execution, AI order authority, network isolation,
pilot veya production readiness kanıtı değildir. Gerçek kullanıcı verisi, credential,
migration bundle ve live broker kullanılmaz. Diagnostic çalışması yalnız temiz geçici
data directory ve sentetik CSV ile yapılır; network ve market-data stream disabled
kalır.

## G0–G2 destek matrisi — bu paketin current source'u

| Yüzey / kapsam | Durum | Bu pakette doğrulanacak gerçek sınır |
|---|---|---|
| Generic Kuantra CSV → local journal | `CANDIDATE_VALIDATED` | UTF-8 bounded CSV; preview read-only; explicit accounting fields; clean row import |
| CSV preview'da malformed/partial/unknown row | `SUPPORTED_FAIL_CLOSED` | DB değişmez; `PARTIAL`/`UNKNOWN` ve user-review/blocked kararı korunur; zero/PASS üretilmez |
| Local journal → canonical evidence/projection | `SUPPORTED_BOUNDED` | Source row/file hash, immutable event ve deterministic projection/evidence lineage korunur |
| Reconciliation inbox / correction decision | `SUPPORTED_BOUNDED` | Discrepancy source event'e bağlıdır; ACK/REJECT/CORRECT append-only'dir; correction eski kanıtı silmez |
| Trade Evidence Pack JSON/HTML/CSV export | `SUPPORTED_BOUNDED` | Coverage/rule/source hashes görünür; replay aynı payload/artifact hash'ini üretir; redaction korunur |
| Weekly review → COMPLETE → REOPEN | `SUPPORTED_BOUNDED` | Period/timezone/as-of deterministik; incomplete coverage `LIMITED`; `is_pass` false; reopen aynı snapshot lineage'ını korur |
| Binance USD-M / OKX SWAP venue claim'i | `NOT_YET_CLAIMED` | Ayrı venue/market/settlement/position-mode fixture ve owner kapsam kararı olmadan production desteği iddia edilmez |
| Spot, hedge/inverse, full account PnL/tax, transfer/funding ledger | `SCOPE_BOUNDARY` | Funding/transfer schema eklenmez; unavailable/unknown açık kalır; accounting kapsamı genişletilmez |
| Mac arm64 packaged app | `TESTED_NON_RELEASE` | Bu hostta sentetik packaged audit; signing/notarization/Gatekeeper/second-host kanıtı değildir |
| Windows/Linux artifact | `HOST_REQUIRED` | Bu Mac çalışması başka OS kanıtı yerine geçmez |
| AI, live order, connector promotion, plugin download | `DISABLED_OR_OUT_OF_SCOPE` | Audit yolunda görünür başarı veya order authority oluşmaz |

`CANDIDATE_VALIDATED` ve `SUPPORTED_BOUNDED` bu geliştirme/release-candidate kanıt
etiketleridir; ticari support, maksimum history veya production claim değildir.
Venue claim'leri matriste özellikle `NOT_YET_CLAIMED` bırakılır.

## B2 kapsam kararı

Bu audit, P1-WP17–21 ile taşınan bounded accounting truth'u yeniden doğrular:
bilinen fixture satırında verilen `pnl` ve `commission` korunur; account scope,
funding/transfer ve market context fixture'da mevcut değilse `NOT_AVAILABLE` kalır.
Tam hesap bakiyesi, vergi, funding/transfer muhasebesi veya venue-complete PnL
üretilmez. Bir değerin bilinmemesi sıfıra çevrilmez ve haftalık review `is_pass=true`
sonucu üretmez.

## Bounded uygulama

1. Önce bağımsız oracle ve packaged worker red testleri yazılır. Oracle, uygulamanın
   fingerprint/PnL/canonicalization fonksiyonlarını çağırmaz; beklenen değerleri
   küçük, elle okunabilir sentetik fixture'dan alır.
2. Diagnostic dispatch normal data/log/backend/WebView startup'tan önce çalışır;
   yalnız explicit executable, yeni geçici SQLite ve fixture kullanır.
3. Clean fixture için preview'nin read-only olduğu, import'un source hash'i taşıdığı,
   Evidence Pack'in coverage/lineage bilgisi verdiği ve JSON/HTML/CSV export'un
   tekrar üretilebilir olduğu kanıtlanır.
4. Malformed/partial preview DB'yi değiştirmeden `USER_REVIEW_REQUIRED` veya
   `IMPORT_BLOCKED` olarak kalır. No-data, unavailable coverage ve disabled market
   context başarı gibi gösterilmez.
5. Haftalık review sabit period/timezone/as-of ile oluşturulur; bounded `LIMITED`
   review explicit kullanıcı kararıyla tamamlanır, sonra `REOPEN` edilir. Her iki
   olay mevcut `JournalReviewAdded` sınırında kalır; yeni schema/event type eklenmez.
6. Launcher executable/artifact/fixture hash'lerini pre/post bağlar; packaged
   provenance release attestation'a yükseltilmez. Çıktı yalnız yeni evidence
   directory'ye yazılır ve mevcut kullanıcı data directory'sine dokunulmaz.

## Acceptance criteria

- [ ] Current supported matrix bu dosyada tek kaynak olarak yazılı; her satırda
  durum, fixture/scope sınırı, bilinmeyen ve platform iddiası ayrılmış.
- [ ] Bağımsız oracle; sembol, yön, miktar, PnL, commission, trade/event sayısı,
  coverage ve no-false-success durumlarını uygulama formülünü tekrar kullanmadan
  doğruluyor.
- [ ] Gerçek packaged arm64 executable üzerinde temiz temporary directory ile
  preview → import → canonical read → Evidence Pack → JSON/HTML/CSV export akışı
  geçiyor; export replay payload/artifact hash'leri eşit.
- [ ] Malformed/partial/unknown preview DB'yi değiştirmiyor; `UNKNOWN`, `PARTIAL`
  ve `NOT_AVAILABLE` downstream'de complete/zero/pass'e dönüşmüyor.
- [ ] Weekly review fixed period/timezone/as-of ile `LIMITED` üretiyor; explicit
  COMPLETE ardından REOPEN aynı review identity/snapshot'ı koruyor ve `is_pass`
  false kalıyor.
- [ ] Canonical event türleri, funding/transfer schema, authority ve connector
  kapsamı değişmiyor; no-network/no-credential/live-execution guard kanıtlı.
- [ ] Focused backend/launcher tests, frontend regression, docs/link gate ve
  locked local CI sonucu aynı source commit ile kaydediliyor. Bu sonuç release,
  signing, notarization veya Windows/Linux platform kanıtı olarak yazılmıyor.

## Kesinlikle kapsam dışı

- Yeni broker/venue connector, order endpoint'i, AI capability veya plugin promotion.
- Funding/transfer event type, ledger schema, migration veya full-account accounting.
- Gerçek kullanıcı verisi, credential/Keychain, Windows migration, network market
  stream veya canlı broker.
- Production SLO, ticari support limit, signing/notarization, Dependabot merge,
  LICENSE/third-party notices veya main merge.

## Sonraki bağımlılık

Paket tamamlanırsa bir sonraki teknik sıra N03 temiz Mac profil/ikinci host ve N04
sentetik update/uninstall data-preservation kanıtıdır. Açık venue, Windows/Linux,
commercial distribution, pilot ve release kararları kendi owner/host kapıları olarak
kalır.
