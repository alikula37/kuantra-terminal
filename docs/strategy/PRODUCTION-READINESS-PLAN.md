<!-- doc-role: current-roadmap -->
# KPR-001 — İlk production sürümüne kadar geliştirme ve doğrulama planı

```yaml
document_id: KPR-001
version: 1.0.22
status: Proposed
date: 2026-09-08
reviewed_commit: 3863288
branch: codex/p1-wp01-evidence-ledger
strategy: KPS-001@1.1.0
audit: KRR-001@1.0.0
```

## 1. Karar özeti ve yetki

İlk production hedefi: **desteklendiği açıkça ilan edilen crypto/perps verisini yerelde
eksiksizlik kontrolünden geçirip, açıklanabilir reconciliation, kaynak bağlantılı Trade
Evidence Pack ve tekrarlanabilir haftalık review sunan read-only desktop workstation.**
Amaç kâr veya kusursuzluk garantisi değil; kullanıcıyı yanlış finansal sonuca ve kayıp
veriye karşı koruyan, sınırları ölçülmüş üründür. Bilinmeyen veri dürüstçe bilinmeyen
kalır. Bir kayıt hash'inin geçmesi, kaydın borsadaki bütün geçmişi içerdiğini kanıtlamaz.

Bu belge önceki [KRR-001 denetimini](../archive/strategy/ROADMAP-REVIEW-2026-09-08.md) ayrıntılandıran
**plan teklifidir**. Yeni eşikler, teslimat tahminleri ve destek kapsamı henüz achieved
veya kullanıcı tarafından ticari olarak onaylanmış değildir. Accepted ADR'ler ve
mevcut güvenlik kapıları geçerlidir. P1-WP16, P1-WP17, P1-WP18, P1-WP19 ve P1-WP20 bounded doğruluk paketleri
kanıtla kapatılmıştır; P1-WP21, N01, N02, H03 ve P1-WP22 bounded paketleri de kendi
kanıtlarıyla kapatılmıştır. P1-WP23 / U02 de bounded kanıtla kapatılmış; P1-WP24 /
U03, P1-WP25 / U04 ve P1-WP26 / U05 de bounded kanıtla kapatılmıştır. H01 canonical
persistence/recovery bounded kanıtla kapatılmıştır. H02 schema upgrade/restore da
`169c446` ile bounded kanıtla kapatılmıştır. H04 de `1cf486e` ile bounded kanıtla
kapalıdır; H05 machine-checkable kanıtla `c089cd2` üzerinde uygulanmıştır. H06
privacy/data-lifecycle ve credential availability boundary `4270d33` ile uygulanıp
`a7b99b7` üzerinde bounded kanıtla kapatılmıştır. Ürün lisansı/notices ve
default-branch alert disposition, ticari dağıtım öncesine kadar bilinçli olarak
ertelenmiştir; bu release gate'i kapalı tutar. H07 bounded performance/resource-limit
paketi yalnız sentetik non-release ölçüm olarak sıradaki aktif pakettir. Aşağıdaki diğer iş
kimlikleri plan satırıdır, topluca coding yetkisi veya tamamlanmış WP değildir.

Plan hazırlamak; gerçek hesap, API anahtarı, kullanıcı verisi, telemetri gönderimi,
sertifika satın alma, imzalama servislerine yükleme, pilot daveti, main merge, release
ve tag işlemlerini başlatmaz. Bunlar ilgili aşamada kapsam ve ürün sahibi onayı gerektirir.

## 2. İlk sürümün sınırı

| İlk production kapsamında | Koşullu / kapsam dışında |
|---|---|
| Local journal, canonical evidence, export ve doğrulanmış restore | AI auditor, cloud AI, model indirme |
| İlan edilmiş venue/market/export sürümleri için CSV ve doğrulanmış read-only snapshot | Her borsa, bütün derivatives, hedge/inverse ürünleri otomatik destekleme |
| Partial/unknown durumlarını gösteren order/fill ve kapsamı belirli accounting reconciliation | Tam hesap doğrulaması yokken net account PnL onayı |
| Trade ↔ kaynak lineage, coverage gösterimi, weekly review, versioned playbook | AI order, sinyal satışı, copy/bot, FIX/DMA |
| Elde bulunan uygun market context ile sınırlı replay/analytics | Kesintisiz L2/depth, tick-exact MAE/MFE veya venue-grade latency vaadi |
| Mac native pilot; release için mevcut üç-OS final artifact politikası | Mac başarısını Windows/Linux veya Intel başarısı sayma |

### Destek matrisi, geliştirmeden önce sözleşme olmalı

KPS-001'in Binance/OKX ilk pazar kararı korunur. R2 başlamadan ürün sahibiyle şu
öneri netleştirilir: ilk dikey fixture/UX doğrulaması **Binance USD-M linear,
USDT-settled, one-way** altkümesinde; ardından aynı doğruluk kapısından geçen açık
bir OKX SWAP altkümesi. Bu öneri mevcut connector desteği iddiası veya bugün kapsam
daraltma kararı değildir. Her iki venue ilan edilecekse ikisi de ayrı geçmelidir.
Bir venue hazır değilse yalnız o venue'nun claim'i çıkarılabilir; bu ticari kapsam
değişikliği ayrı ürün sahibi kararıdır, sessiz test muafiyeti değildir.

Her destek satırı: venue, market type, instrument/settlement, position mode, account
scope, CSV format/version veya endpoint/history sınırı, desteklenen event türleri,
bilinmeyenler, fixture sürümü ve son doğrulama tarihi içerir. Unsupported modlar UI'da
import öncesi reddedilir veya açık partial review olarak sunulur; valid sonucu üretmez.
Market context venue/instrument/time ile eşleşmelidir; Spot feed perps context diye
yeniden etiketlenmez. Candle içi fiyat yolu bilinmiyorsa tick replay/precise excursion
iddiası yoktur. Güncel venue kuralları implementasyonda resmi kaynaktan doğrulanır.

## 3. Fazlar ve kapıların mevcut stratejiye eşlemesi

G0–G7 yeni ürün fazı değil, **ilk production için teslimat kapılarıdır**. KPS-001 Faz
0–5 numaraları değiştirilmez. Aşağıdaki kapıların hiçbiri bu belgeyle geçmiş sayılmaz.

| Kapı | KPS/KRR karşılığı | Sonuç | Geçiş kararı |
|---|---|---|---|
| G0 — Kapsam ve kanıt baseline'ı | Faz 0 bakım; KRR bulguları | Capability/support matrisi, açık riskler, fixture ve claim eşlemesi | Lead review + kapsam seçiminde ürün sahibi |
| G1 — Veri/finansal doğruluk | Faz 1; R1–R3 | Kaynak → normalize → reconcile → trade zinciri güvenilir | Golden oracle, negative ve property testleri |
| G2 — Kullanılabilir review ürünü | Faz 1; R4–R5 | Import'tan haftalık karar değerlendirmesine çalışan UX | Uçtan uca test ve moderatörlü sentetik kullanım |
| G3 — Dayanıklılık ve güvenlik | Faz 0/1; R6 | Veriyi koruyan offline/degraded çalışma ve güvenlik sınırı | Failure drill, threat review, dependency/secret raporu |
| G4 — Pilot dağıtım adayı | Faz 0/1; R6 | Exact-commit native artifact, kurulum/güncelleme/restore kanıtı | Mac pilot kabulü; platform sınırlamaları açık |
| G5 — Kullanıcı doğrulaması | Faz 1; R7 | Formative cohort + 8 haftalık pilot, measured review değeri | KPS Faz 1 exit + önceden tanımlı pilot go/no-go |
| G6 — Production release candidate | Faz 0/1 release kapıları | Feature freeze, aynı aday için üç-OS artifact/security/recovery kanıtı | Tüm blocker'lar kapalı + ürün sahibi go/no-go |
| G7 — Kontrollü production ve bakım | Faz 1 operasyonu | Sınırlı rollout, destek, incident ve güvenli update döngüsü | Rollout kanıtı; sorun varsa dağıtımı durdur |

Kritik yol: **G0 → G1 → G2 → G3/G4 → G5 → G6 → G7**.
G3 güvenlik ve veri-koruma testleri G1'den itibaren her pakete uygulanır; sonradan
eklenecek bir “güvenlik sprinti” değildir. Windows host çalışması, doküman/fixture
hazırlığı ve dağıtım erişimleri bağımsız dosya/sorumlu alanlarında paralel ilerleyebilir.
G5 gerçek kullanıcıya ulaşmadan G3/G4 veri güvenliği tabanı geçmelidir. M1 mevcut
recovery bakımı uzun testnet koşusundan önce gelir; ilk ürünün kritik yolunu ele geçirmez.

## 4. G0–G1: Doğruluk paketleri

Kimlikler bu belgede kalıcı plan satırlarıdır. `D01 / P1-WP16`, `D02 / P1-WP17`,
`D03 / P1-WP18`, `D04 / P1-WP19`, `D05 / P1-WP20` ve `D06 / P1-WP21` kanıtla kapatılmıştır. P1-WP22, G2/R4 değer zinciri geçidini bounded olarak kapatmış; P1-WP23, U02 reconciliation inbox ve correction/user-decision boundary'sini bounded olarak; P1-WP24 ise U03 canonical Evidence Pack/export boundary'sini bounded olarak kapatmıştır. Sonraki işler hazır
olmadan ayrı WP açılıp dosya/test sınırı yazılır. Tek pakette birden çok bağımsız hata
varsa test edilebilir parçalara bölünür.

| İş | Çıktı ve dosya alanı | Asgari acceptance / negative test | Bağımlılık |
|---|---|---|---|
| D01 / P1-WP16 | Read-only sync completeness; `read_only_broker_sync.py`, importer/API tests | Same timestamp > page size; full/short/repeated/unsorted page; until boundary; missing cursor; no false complete | Mevcut P1-WP11/12; verified `ef909d1` |
| D02 / P1-WP17 | Read-only source identity/support contract; manifest/import provenance | Canonical venue ile source exchange id ve market type ayrımı; conflicting identity reject; same-venue idempotency separation; no new support | D01; verified `930d25a` |
| D03 / P1-WP18 | Decimal/precision ve fee unit contract; reconciliation | Missing ≠ zero; multi-currency fees ayrı; rebates; rounding/tick/step; string→numeric canonical roundtrip; known zero | D02; verified `0c7d11f` |
| D04 / P1-WP19 | Funding/corrections/account reconciliation kapsamı | Opening position/balance; realized/unrealized ayrımı; funding time; transfer ≠ PnL; liquidation/ADL varsa explicit event veya unsupported | D03; P1-WP18; verified `f67e732` |
| D05 / P1-WP20 | Economic dedup ve lifecycle trade grouping | Overlapping CSV/API imports; same fill/new source; late correction; partial fill; scale-in/out; flip; cancellation; orphan; multi-account ID collision | D04; P1-WP19; verified `5d691b9` |
| D06 / P1-WP21 | Journal/projection/evidence propagation | Same input same projection; correction eski kanıtı silmez; incomplete downstream'de görünür; transactional rollback; replay as-of version | D05; P1-WP01–15 |

**G1 release-blocking invariants:** curated supported fixture corpus'unda açıklanamayan
fill/quantity/unit/PnL farkı sıfır; silently dropped veya double-counted economic fill
sıfır; missing data'nın complete'e dönüşmesi sıfır. Genel import success ≥%90 hedefi,
başarılı diye işaretlenen import'ta %10 sessiz hata toleransı değildir. KPS normalized
fill ≥%99.5 popülasyon hedefi de bilinen bir accounting hatasını kabul etmez.

Oracle, test edilen fonksiyonla aynı formülü çağırarak üretilmez. Küçük elle doğrulanmış
fixture'lar, bağımsız hesap yöntemi ve izinli/redacted venue örnekleri ayrı kaynak olarak
tutulur. Property/metamorphic test: sıralamayı değiştirme, batch bölme/birleştirme ve
tekrar import ekonomik sonucu değiştirmez; gerçek correction değiştirir ve lineage taşır.
Scope dışı kaydın “başarı paydasından çıkarılarak” metriği iyileştirmesi engellenir.

## 5. G2: İlk değer ve haftalık review

| İş | Teslimat | Geçiş kanıtı |
|---|---|---|
| U01 | Import wizard: source/market seçimi, preview, destek/coverage, dry-run summary, explicit import | Hatalı dosya DB'yi değiştirmez; duplicate, partial, cancel, retry ve büyük dosya UI states; ilk başarılı import açıklanır |
| U02 | Reconciliation inbox: discrepancy türü, etkilenen trade, kaynak satırı ve çözüm tarihi | Resolve işlemi kanıtı silmez; yeniden import ile fark kapanırsa lineage korunur; unresolved filtrelenip saklanmaz |
| U03 | Trade Evidence Pack: timeline, fees/funding coverage, applicable rule, export | UI→API→canonical source tutarlılığı; redaction; CSV formula injection ve HTML escaping; unavailable analytics görünür |
| U04 | Weekly review: period/timezone, yeterli veri, rule breach, kullanıcı notu ve tamamlanma | As-of policy/effective time; hindsight rule ayrı; haftayı tekrar açınca aynı snapshot; late correction varsa revision/stale uyarısı |
| U05 | Erişilebilir ve anlaşılır shell | EN/TR/DE parity; keyboard/focus; kontrast/zoom; loading/error/retry; timezone/numeric locale; dar ekran/uzun içerik testleri |

U01 import/review/export akışı P1-WP22 ile bounded olarak uygulanmış ve `ea4e12c`
ile kanıtlanmıştır. U02 reconciliation inbox ve correction/user-decision boundary'si
P1-WP23 (`51ee968`) ile bounded olarak tamamlanmıştır. U03 canonical Trade Evidence
Pack, coverage/rule görünürlüğü, redaction ve deterministic export safety P1-WP24
(`afedb70`) ile bounded olarak tamamlanmıştır. U04 weekly review ve
period/timezone/as-of determinism P1-WP25 (`26751f7`) ile bounded olarak
tamamlanmıştır. U05 erişilebilir ve anlaşılır shell state'lerini P1-WP26
(`30dfcd7`) ile bounded olarak tamamlamıştır. H01 canonical persistence/recovery
hardening `006e86e` ile bounded olarak tamamlandı. H02 schema upgrade ve restore
boundary'si `169c446` ile tamamlandı. H04 threat model ve trust boundaries de
`1cf486e` ile bounded misuse testleri, fail-closed input/native boundary'leri ve
Mac local-CI kanıtıyla tamamlandı. H05 supply chain, SBOM, license ve secret
boundary machine gate'i `c089cd2` ile PASS oldu. Ürün lisansı/notices ve
default-branch Dependabot disposition geliştirme dönemi için ertelendi; bunlar ilk
ticari/release adayı öncesi yeniden açılacak zorunlu kapılardır. H06 non-release
privacy/data-lifecycle paketi `4270d33`/`a7b99b7` ile bounded olarak tamamlandı. H07
bounded performance/resource-limit paketi sıradaki aktif non-release iştir; production
iddiası yine açılamaz.

G2 acceptance: boş data directory → desteklenen fixture import → discrepancy açıklama
→ trade pack → rule review → haftalık review → export → yeniden açma akışı tek packaged
app'te tamamlanır. UI'da AI, live order veya plugin indirme success yolu oluşmaz.
Analitik sonuçlar trade sayısı, dönem, exposure, fee/funding/context coverage ve ölçüm
yöntemini gösterir; account balance bilinmiyorsa yüzde getiri uydurulmaz. Review
tamamlama, bir butona basmaktan ibaret olmayan açık bir olay sözleşmesine bağlanır.

## 6. G3: Dayanıklılık, güvenlik, gizlilik ve performans

| İş | Zorunlu senaryolar | Çıkış kanıtı |
|---|---|---|
| H01 — Canonical persistence | Process kill before/after ACK, disk full, read-only disk, transaction failure, concurrent import | ACK verilmiş event kaybı 0; no half-import; recovery açık; tekrar başlatma idempotent |
| H02 — Schema/upgrade/restore | Supported old schema, interrupted migration, corrupt backup, missing segment, incompatible future schema | Preflight/backup; integrity verify; invalid restore reddedilir; canonical/projection equivalence; upgrade sonrası veri korunur |
| H03 — Runtime offline/degraded | Network denied from startup; sleep/wake; DNS failure; feed stale; account sync unavailable | Import/local review/export çalışır; network opt-in/disable anlamlı; fail-open quote/complete yok; UI freeze yok |
| H04 — Threat model ve boundary tests | Untrusted CSV/JSON/HTML, path traversal/symlink, archive extraction/resource limits, WebView bridge, external navigation, gateway auth/origin | Her trust boundary için misuse testi; render/import data kod değildir; secrets diagnostics/export'a girmez |
| H05 — Supply chain ve build trust | Python/npm locks, transitive dependencies, SBOM/license notices, secret scan, build tooling ve artifact scan | Reachable critical/high açık yok; diğer bulgular owner/expiry/mitigation ile kayıtlı; güncel dependency raporu |
| H06 — Privacy/data lifecycle | Data directory izinleri, keychain unavailable/locked davranışı, redacted support pack, export/retention | UI “local-first” kapsamını doğru anlatır; telemetry opt-in; missing credential prompt kontrollü; gerçek secret fixture yok |
| H07 — Bounded performance | 1k/10k/100k trade history, ayrıca büyük dosya/resource-boundary fixtures; query/rebuild/import/cancel | Test host/dataset/percentile/RAM/disk baseline; Evidence Pack p95 <2s KPS hedefi; UI responsive; bütçe aşımında açık hata |

Benchmark boyutları plan teklifidir, maksimum destek sözü değildir. Release support
limitleri baseline ölçülmeden sabitlenmez. KPS'deki 10M market row/24h depth hedefleri
koşullu Faz 2 içindir, temel CSV review ürününe körlemesine uygulanmaz. Soak sırasında
memory/disk büyümesi ölçülür; retention canonical veriyi habersiz silmez.

Data migration yalnız izole sentetik kopyalarda test edilir. Mevcut “gerçek kullanıcı
verisi yok” Mac kararı sürer; Windows migration ZIP'i oluşturulmaz. Gerçek veri oluşunca
[migration runbook](../MACOS_MIGRATION.md) uygulanır ve destructive restore/apply için
açık onay alınır. Yeni schema ile açılmış DB'ye eski executable'ı çalıştırmak güvenli
rollback varsayılmaz: uyumluluk kanıtı, ayrı doğrulanmış backup veya forward fix gerekir.

G3 öncesi minimum tehdit incelemesi; G6 öncesi ikinci/bağımsız gözden geçirme gerekir.
ASVS web/API/bridge kontrollerine uyarlanır, desktop'ın tamamının sertifikalandığı
iddia edilmez. Güvenlik işlerini development/release/vulnerability-response boyunca
izleme yaklaşımı NIST SSDF'den yararlanır; bu plan bir standart sertifikası değildir.
[OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/),
[NIST SSDF](https://csrc.nist.gov/projects/ssdf).

## 7. G4: Native pilot dağıtımı

| İş | Kabul şartı |
|---|---|
| N01 | Build source SHA, tree state, lock hashes, toolchain/OS/arch, artifact/executable SHA manifest'te; UNKNOWN/provenance mismatch fail |
| N02 | Mac smoke actual WKWebView/controller hazır; preflight ve report validation fail-closed; DMG içinden explicit executable smoke |
| N03 | Temiz ikinci host/profilde quarantine dahil install → launch → import/review → close/reopen; geliştirici cache/data'sına bağımlı değil |
| N04 | Update önceki supported build'den; interrupted update; uninstall veriyi korur; restore ve schema rollback politikası kullanıcıya açık |
| N05 | Dağıtım imzası/notarization süreci, minimal entitlements, ticket/manifest verification, secretsiz signing logs |
| N06 | Windows P0-WP11 host blocker ve Linux native final artifact suite ayrı host'larda; OS/arch/version support tablosu kanıtla eşleşir |

Mac ad-hoc geliştirme DMG'si ticari distribution-signed artifact değildir. Apple'ın
doğrudan dağıtım akışı Developer ID signing/notarization ve distribution testi ayrımını
tanımlar; notarization sonucunun ticket'ı dağıtıma iliştirilir. Developer enrollment,
sertifika ve OS onayı kullanıcı sorumluluğudur; parola/sertifika secret'ı sohbete istenmez.
[Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[Apple distribution testing](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).

G4 Mac-only kapalı pilot olarak değerlendirilebilir; bu, mevcut KDG-002 üç-OS final
release politikasını kaldırmaz. İlk production'ı Mac-only yapma kararı istenirse ayrı
öneri/onay gerekir. Build çıktısının hash'i eşit olmayan imzalı artifact için eski
unsigned smoke'u final artifact testi diye yeniden kullanmayız.

## 8. G5: Gerçek kullanıcı değeri, kontrollü pilot

1. **Formative 5–8 kullanıcı:** hedef persona; ilk import, hata anlama ve review gözlemi.
   Önce sentetik demo, kullanıcı kendi verisini kullanacaksa açık rıza/veri sınırı.
   Tespit edilen kritik usability/accounting sorunları sonraki cohort öncesi kapanır.
2. **40 kişilik 8 haftalık pilot:** KPS-001 persona ve baseline; cohort tanımı,
   desteklenen market, drop-out ve consent koşulları ölçümden önce kaydedilir.
3. **Faz 1 exit:** kullanıcıların ≥%60'ı üç haftada en az iki weekly review tamamlar.
4. **Pilot go/no-go:** 8. haftada ≥16/40 weekly active, ≥6/40 ücretli ve açıklanamayan
   fill farkı sıfır. Bu plan ilk ticari production için bu kapıyı da önerir; ödeme
   süreci/fiyat ürün sahibince henüz onaylanmadı. Ödeme verisi yoksa ticari kapı
   `NOT_MEASURED` kalır; teknik beta ile paid production birbirine karıştırılmaz.
5. Metodoloji/bug nedeniyle ölçülemeyen hücre `PASS` değildir. Küçük cohort'un olumlu
   sonucu pazarın tamamına veya nedensel kârlılık artışına genellenmez.

KPS hedefleri: import success ≥%90; evidence completeness ≥%95; ilk import median
<10 dakika; ilk gün pack view ≥%60. Paydalar KRR-001 sözleşmesiyle önceden sabitlenir.
Telemetry sessizce açılmaz; yerel consent'li aggregate/export da ölçüm yöntemi olabilir.
Kritik veri/secret hatasında cohort büyütülmez. Pilot başarısızsa Faz 1 workflow'una
dönülür; AI veya canlı execution eklemek ölçüm başarısızlığının çözümü sayılmaz.

## 9. G6: Production release candidate ve durdurma kriterleri

Release dossier, **bir source commit + her platform için kendi final artifact hash'i**
ile tanımlanır. Platformların binary hash'leri birbirine eşit olmak zorunda değildir.
Dosya değişirse etkilenen testler, yeni binary oluşursa ilgili final smoke tekrar edilir.
Sadece tarihsel P0 Verified veya feature branch full CI sonucu dossier yerine geçmez.

| Kapı | İstenen kanıt | Hard stop |
|---|---|---|
| Scope/claims | Supported matrix, no-data/disabled truth matrix, kullanıcı dokümanı | Test edilmemiş market/OS/AI/execution vaadi |
| Correctness | G1 oracle/property/E2E raporları; açık discrepancy listesi | Bilinen silent loss/double count/wrong financial verdict |
| Safety/privacy | Threat review, dependency/secret scan ve negatif boundary tests | Yetkisiz order/credential exposure/risk fail-open; açık relevant critical/high |
| Durability | Crash/recovery, upgrade ve restore drill | ACK event kaybı, veri bozma, restore doğrulanamaması |
| Native artifacts | Windows/Mac/Linux final smoke, renderer/signature/manifest, clean install/update | Eksik platform kanıtı, UNKNOWN commit veya artifact mismatch |
| Product | G5 ölçüm raporu, support kapsamı ve owner kararı | Kullanıcı kanıtı yokken doğrulanmış değer/paid readiness iddiası |
| Distribution | Lisans metni/notices, privacy/support dokümanı, release notes, imza erişimi | Eksik dağıtım yetkisi/lisans veya güvenilir paketleme süreci |
| Operations | Incident owner, stop-distribution ve patch/rollback drill, evidence retention | Kritik hatada müdahale edebilecek sorumlu/runbook yok |

Önerilen severity politikası: veri kaybı, secret sızıntısı, yetkisiz emir ve sessiz
finansal yanlışlık **S0**; ana akışı kullanılamaz yapan crash/kurulum/import sorunu
**S1**. Açık S0/S1 ile production yok. S2/S3 için etkisi, workaround, owner, test ve
hedef düzeltme tarihi kaydedilir; bu etiketleme bir S0'ı kozmetik seviyeye düşüremez.
Güvenlik CVSS severity ile ürün bug severity ayrı tutulur; uyarı için applicability
değerlendirmesi delilli olmalıdır.

Release candidate freeze sırasında yeni feature eklenmez. Regression fix'leri ayrı
commit'tir. Full local CI, claim/packaging, final artifact ve dependency taraması
release adayı için günceldir. Main merge, sürüm/tag seçimi ve yayınlama kullanıcı
onayıyla yapılır; bu plan version bump veya release yetkisi vermez.

## 10. G7: Production bir bitiş değil, işletilen sözleşme

- İlk rollout küçük ve açıkça sınırlı cohort'a; support kanalı ve release notes hazır.
  Her genişlemeden önce install, crash, import discrepancy ve restore sinyalleri incelenir.
- S0 görülürse yeni dağıtım/güncelleme durur; etkilenen kullanıcıya kapsamı bilinen
  uyarı, kanıt koruma ve forward-fix/verified-restore yönlendirmesi sağlanır. Kullanıcı
  verisi otomatik silinmez; zorla eski schema'ya downgrade yapılmaz.
- Otomatik updater ilk sürüm için şart değildir. Kontrollü manuel signed update yeterli
  olabilir; auto-update eklenirse signature, anti-downgrade/compatibility ve interrupted
  update testleri ayrı WP'dir. Bir hash download kanalının kimlik doğrulaması değildir.
- Bağımlılık ve venue schema drift'i release öncesi ve önerilen haftalık bakımda
  incelenir. Bu plan otomasyon kurmaz; sıklık/sorumlu operasyon aşamasında kabul edilir.
- Evidence arşivi repo dışı kalıcı kontrollü yerde; kaynak commit/locks/fixture hash,
  komut/env (secretsiz), sonuç, log/hash, OS/arch ve reviewer kaydı içerir. `/tmp` kalıcı
  arşiv sayılmaz. Saklama süresi ve redaction pilot öncesi belirlenir.
- Destek yanıt ve düzeltme süreleri mevcut insan kapasitesine göre tanımlanır; 24/7
  on-call veya garantili SLA bugünden vaat edilmez. Incident tatbikatında sorumlu ve
  yedek karar kanalı doğrulanmadan ticari rollout büyütülmez.

## 11. İlk production'dan sonraki koşullu KPS fazları

| KPS fazı | Yeniden açılma şartı | Vazgeçilmez sınır |
|---|---|---|
| Faz 2 — Context/replay data plane | Review sorusunu cevaplamak için eksik context ve ölçülmüş ihtiyaç; existing M1 recovery düzeltilmiş | Sequence/gap görünür; matching instrument; verified coverage; 24h soak ve KPS replay/rule kullanım metrikleri |
| Faz 3 — Read-only AI auditor | Faz 1/2 evidence ve kullanıcı değeri; AI'sız ürün çalışıyor; eval corpus + consent | Citation/abstention/red-team; numeric target; no order tools; measured uplift olmadan genişleme yok |
| Faz 4 — Controlled execution | Ayrı talep, insan onayı, security/legal inceleme ve ADR-0003'ün 15 kapısı | 30 gün shadow; 10k testnet lifecycle/100 reconnect; 1M risk property cases; independent kill switch; hiçbirini local CI yerine koyma |
| Faz 5 — Teams/plugins | Design partner ve permission/support ekonomisi; ayrı kapsam kararı | Isolation/RBAC/signed out-of-process plugin; P0 disabled yüzeyleri otomatik açılmaz |

Faz 4, ilk read-only production'ın önkoşulu değildir. Bütün research modüllerini
production'a çevirmeye çalışmak “eksiksizlik” değil, yeni risk ve hedef pazar genişlemesidir.
Kullanıcı talebi veya ölçülmüş darboğaz yoksa Rust rewrite, Arrow Flight, yeni broker,
marketplace ve AI swarm backlog'a alınmaz. Kabul edilmiş ADR metni değiştirilmez;
gerçek karar değişikliği yeni ADR ve ürün sahibi onayı gerektirir.

## 12. Efor, takvim ve karar bağımlılıkları

Henüz story-level tahmin veya atanmış kapasite yok. Aşağıdakiler tek ana entegrasyon
hattı için **düşük güvenli planlama aralıkları**, teslim tarihi veya maliyet teklifi değil:

| Dilim | İlk efor tahmini | Tahmini yeniden açan risk |
|---|---|---|
| G0–G1 | 4–8 mühendis-hafta | Perps scope, fixture ve accounting yeniden tasarımı |
| G2 | 3–6 mühendis-hafta | Mevcut UI/API bağlantısı ve discrepancy UX |
| G3–G4 | 4–8 mühendis-hafta | Restore/upgrade, Windows blocker, signing ve host erişimi |
| G5 | 8 hafta gerçek cohort gözlemi + öncesinde recruitment/formative süre | Kullanıcı bulunması ve yeniden çalışma; agent ile sıkıştırılamaz |
| G6–G7 başlangıcı | 2–4 mühendis-hafta + rollout gözlem süresi | RC regressions, release onayı ve support hazırlığı |

Toplam mühendislik 13–26 hafta mertebesinde ilk tahmindir; buna recruitment, pilotun
8 haftası, dış onay beklemeleri ve keşfedilen yeniden çalışma eklenir. Paralel çalışma
toplam eforu yok etmez; pilot gözlemiyle bazı release işleri örtüşebilir. Bu aralık
“production şu tarihte hazır” sonucuna dönüştürülmez. İlk iki bounded doğruluk
paketinden sonra test/implementation bulgularıyla yeniden tahmin edilir.

Ürün sahibinden zamanı geldiğinde gerekenler: dar perps support scope, pilot kullanıcı
erişimi ve consent, ödeme/teklif kararı, lisans/notices, signing hesabı/host erişimi,
security reviewer ve operasyon sorumlusu. Bugün bunların eksikliği P1-WP20 fixture
çalışmasını engellemez; yapılabilecek işi bırakıp tüm kararları peşinen istemeyiz.

## 13. İlk uygulama sırası ve raporlama

1. P1-WP16: failing fixture → minimal fix → incomplete propagation → regression/full gate; verified `ef909d1`.
2. P1-WP17: source identity/support boundary; same-venue idempotency separation; verified `930d25a`.
3. P1-WP18: fee/precision/unknown doğruluğu; verified `0c7d11f`.
4. P1-WP19: funding/corrections/account coverage; verified `f67e732`.
5. P1-WP20: ekonomik dedup/lifecycle; verified `5d691b9`.
6. P1-WP21: journal/projection/evidence propagation; ardından N01, N02 ve H03 Mac
   kanıt kapıları.
7. P1-WP22 / U01: import preview → discrepancy görünürlüğü → source-linked Evidence
   Pack/export; tamamlandı `ea4e12c`.
8. P1-WP23 / U02: reconciliation inbox ve correction/user-decision boundary;
   tamamlandı `51ee968`.
9. P1-WP24 / U03: canonical Trade Evidence Pack, coverage/rule görünürlüğü,
   redaction ve deterministic export boundary; tamamlandı `afedb70`.
10. P1-WP25 / U04: weekly review ve period/timezone/as-of determinism; tamamlandı
    `26751f7`.
11. P1-WP26 / U05: accessible/understandable shell; ardından bağımlılığa göre
    tamamlandı `30dfcd7`. U05 yeni capability veya release gate açmaz.
12. H01: canonical persistence ve recovery; tamamlandı `006e86e`.
13. H02: schema upgrade ve restore; tamamlandı `169c446`.
14. H04: threat model ve trust boundaries; bounded olarak tamamlandı `1cf486e`.
15. H05: supply-chain, deterministic SBOM ve secret boundary machine gate'i
    uygulandı `c089cd2`; lock/scan/artifact kanıtı PASS. Ürün lisansı/notices ve
    default-branch alert disposition geliştirme dönemi için `DEFERRED`; ticari veya
    production release adayı öncesi yeniden açılmaları zorunlu.
16. H06: privacy/data-lifecycle ve credential availability boundary; bounded olarak
    tamamlandı `4270d33`/`a7b99b7`.
17. H07: deterministik sentetik performance/resource-limit baseline'ı; query
    mid-operation abort backend sınırı `5137383` ile, Evidence Pack/Reconciliation
    Inbox/Weekly Review/CSV preview read yüzeylerinin bounded cancellation/loading/
    error truth'i `27b3404` ile, Dashboard/Quant Analytics/Header portfolio read
    truth'i `42d67c6` ile, JournalView trade-list read truth'i `3de57c5` ile,
    MAE/MFE read truth'i `f57da9d` ile, SettingsView portfolio-summary read truth'i
    `3fa98a9` ile, Charts/TradingViewChart historical read truth'i `dd0639b` ile,
    plugin registry/ModStore read truth'i `950af74` ile, unchanged-ledger integrity
    verification cache'i `da9af9b` ile, projection verifier reuse'ı `2da9fe1` ile,
    post-write verifier connection release sınırı `f551b1f` ile ve ledger-only
    fingerprint/shared verifier `3863288` ile eklendi. Safe-persona görünür read
    listesi için bounded kanıt günceldir; cold 100k Evidence Pack
    planning target kararı açık kaldığı için paket hâlâ aktif non-release iştir.
18. N03–N06 owner/host bağımlılıkları çözüldükçe sırasıyla.

Her teslim raporu: WP/scope, changed files, failing→passing test kanıtı, tam komutlar,
platform/fixture/source SHA, açık acceptance kutuları, kalan risk, commit/push ve
sıradaki bağımlılık. Uygun testleri geçmeden “tamamlandı”, phase gate geçmeden
“production-ready” denmez. Bu planlama turunda runtime/testnet veya kullanıcı verisi
işlemi yapılmadı; docs-only diff/link/release-truth/packaging kontrolleri uygulanır.

## Değişiklik geçmişi

### 1.0.22 — 2026-09-08

- H07 ledger doğrulama cache sınırı `3863288` ile daraltıldı: cache anahtarı yalnız
  append-only `evidence_events` state fingerprint'ine bağlıdır; projection-only
  commit ledger verification cache'ini invalid etmez, ledger append'i eder. Projection
  repository ve `TradeReadAdapter` aynı verifier'ı paylaşır; persistent SQLite
  verifier bağlantısı tutulmadığı için apply sonrası WAL sayfası tutulmaz. Yeni schema,
  event type, funding/transfer kapsamı veya üretim capability'si eklenmedi.
- Red→green odak kanıtı H07 `20`, projection/H01 regression `41` test; full locked
  local CI `MERGE READY`, backend `713` (2 warning), frontend `25/100`, i18n `608/608`,
  Mac arm64 build/native WKWebView smoke ve exact disabled-market-data mounted DMG
  smoke PASS oldu. Source `3863288095af43aaa8918d71394994593efb8822`; local CI report
  SHA `f9a2e18620a68c3eb482c2e7412dc80de20beee96a925095e966d8f94068a382`; exact DMG
  smoke report SHA `7fe0761f474ad72dcfb2fc907e3b2611c3607d31d42ec9fc883d7e43a9306d14`;
  DMG SHA `5f84d80eea209167d52709fe1d1bf3da1ec8d54e848769933986e3f43fd85ccb`;
  mounted executable SHA `ffc1fd0358d54bafc5f44b4e22b6622a00945a9369d1c2c778fcb7766327c438`.
- Exact artifact-bound 100k benchmark report SHA
  `35c20c31fdab0391f6a39d1ac06722b2e8b37d4c0ccaf3ee5e397d4fbe4c2987` ölçtü:
  projection rebuild p95 `6316.4108 ms`, Evidence Pack p95 `4187.8654 ms`, export
  p95 `344.4804 ms`, projection operation temporary disk `0 B`; cold Evidence Pack
  `<2s` planning target karşılanmadı ve H07 `IMPLEMENTATION_REQUIRED` kaldı.

### 1.0.21 — 2026-09-08

- H07 projection verifier reuse/WAL boundary paketi `2da9fe1`/`f551b1f` ile kaydedildi:
  aynı projection repository içindeki unchanged ledger verification tekrar kullanıldı;
  apply rebuild sonrası verifier read connection'ı kapatılarak temporary WAL büyümesi
  engellendi. Full locked local CI `MERGE READY`, 712 backend, 100 frontend,
  i18n `608/608`, clean Mac arm64 build/native smoke ve exact disabled-market-data
  mounted DMG smoke PASS oldu. Artifact-bound 100k projection rebuild p95
  `6159.2185 ms`, temporary disk `0 B`; cold Evidence Pack p95 `4162.4495 ms` ve
  `<2s` planning target karşılanmadı. H07 açık tutuldu.

### 1.0.20 — 2026-09-08

- H07 unchanged-ledger integrity cache paketi `da9af9b` ile kaydedildi: append-only
  ledger doğrulaması yalnız değişmeyen SQLite `PRAGMA data_version` snapshot'ında
  tekrar kullanılıyor; yeni append/commit sonrası tam verification yeniden çalışıyor.
  Full locked local CI `MERGE READY`, 710 backend, 100 frontend, i18n `608/608`,
  clean Mac arm64 build/native smoke ve exact disabled-market-data mounted DMG smoke
  PASS oldu. Artifact-bound 100k benchmark cold Evidence Pack p95 `4132.1722 ms`,
  cache-warm export p95 `329.0577 ms`, projection rebuild p95 `8093.7152 ms` kaldı;
  `<2s` planning target karşılanmadı ve H07 açık tutuldu.

### 1.0.19 — 2026-09-08

- H07 plugin registry/ModStore read paketi `950af74` ile kaydedildi: strict installed
  metadata validation, explicit loading/cancel/error/retry truth, AbortSignal,
  stale-response ve provider unmount cleanup eklendi. Full local CI `MERGE READY`,
  709 backend, 100 frontend, i18n `608/608` ve explicit disabled market-data ile exact
  mounted Mac DMG/WKWebView smoke PASS oldu. Remote plugin download, activation ve
  runtime mounting kapalı kaldı; diğer core read yüzeyleri ve 100k planning target açık.

### 1.0.18 — 2026-09-08

- H07 Charts/TradingViewChart historical OHLCV read paketi `dd0639b` ile kaydedildi:
  strict response/candle validation, explicit loading/error/cancel/retry truth,
  AbortSignal, timeout ayrımı, stale-response/unmount suppression ve historical
  candle'ın synthetic live tick'e yükseltilmemesi eklendi. Full local CI `MERGE READY`,
  709 backend, 97 frontend, i18n `608/608` ve explicit disabled market-data ile exact
  mounted Mac DMG/WKWebView smoke PASS oldu. Diğer core read yüzeyleri ve 100k
  planning target açık kaldı.

### 1.0.17 — 2026-09-08

- H07 SettingsView portfolio-summary read paketi `3fa98a9` ile kaydedildi:
  strict finite/non-negative `initial_balance` validation, sahte `0` fallback yerine
  explicit loading/error/cancel/retry truth, AbortSignal, stale-response suppression
  ve unmount cleanup eklendi. Full local CI `MERGE READY`, 709 backend, 93 frontend,
  i18n `605/605` ve explicit disabled market-data ile exact mounted Mac DMG/WKWebView
  smoke PASS oldu. Kullanıcı tarafından submit edilen capital mutation'ı iptal
  edilebilir gibi sunulmadı; diğer core read yüzeyleri ve 100k planning target açık
  kaldı.

### 1.0.16 — 2026-09-08

- H07 MAE/MFE analytics read paketi `f57da9d` ile kaydedildi: strict response
  validation, `READY`/`NO_DATA`/`UNAVAILABLE` ayrımı, AbortSignal ve kullanıcı cancel'i,
  stale-response suppression, unmount cleanup, explicit loading/error/unavailable/retry
  state'leri ve malformed/HTTP failure'ın chart/empty success'e dönüşmesini engelleyen
  fail-closed UI sözleşmesi eklendi. Full local CI `MERGE READY`, 709 backend, 90
  frontend, i18n `600/600` ve exact mounted Mac DMG/WKWebView smoke PASS oldu.
  Diğer core read yüzeyleri ve 100k planning target açık kaldı.

### 1.0.15 — 2026-09-08

- H07 JournalView trade-list read paketi `3de57c5` ile kaydedildi: strict response
  validation, AbortSignal ve kullanıcı cancel'i, stale-response suppression, unmount
  cleanup, explicit loading/error/retry ve malformed/HTTP failure'ın boş journal'a
  dönüşmesini engelleyen fail-closed UI sözleşmesi eklendi. Full local CI `MERGE READY`,
  709 backend, 87 frontend, i18n `596/596` ve exact mounted Mac DMG/WKWebView smoke
  PASS oldu. MAE/MFE, diğer core read yüzeyleri ve 100k planning target açık kaldı.

### 1.0.12 — 2026-09-08

- H07 query read path'i `5137383` ile bounded resource-check callback'i aldı:
  legacy SQLite ve exact-coverage typed projection mid-operation limit aşımında
  partial list döndürmeden fail-closed kapanıyor. 709 backend, 71 frontend, i18n
  574/574 ve clean Mac arm64 local CI `MERGE READY`; exact read-only DMG/WKWebView
  smoke PASS. Frontend loading/cancellation/error truth, 100k planning target'i,
  signing/notarization ve commercial/release gates açık kaldı.

### 1.0.11 — 2026-09-08

- H06 privacy/data-lifecycle ve credential availability boundary `4270d33` ile
  uygulanıp `a7b99b7` üzerinde bounded kanıtla kapatıldı: 683 backend, 71 frontend,
  i18n 574/574, temiz Mac arm64 local CI ve exact mounted DMG/WKWebView smoke PASS.
- H06 arşivlendi ve H07 deterministik sentetik performance/resource-limit paketi tek
  güncel aktif non-release work package olarak seçildi. H05 ürün lisansı/notices ve
  default-branch Dependabot kapıları ertelenmiş ve release öncesi zorunlu kalmıştır.

### 1.0.13 — 2026-09-08

- H07 frontend bounded cancellation paketi `27b3404` ile kaydedildi: Evidence Pack,
  Reconciliation Inbox, Weekly Review ve CSV preview read/loading yüzeyleri
  AbortSignal, cancel, stale-response suppression ve explicit error truth ile
  doğrulandı. Import mutation'ı native bridge rollback garantisi olmadığı için
  kullanıcıya iptal edilebilir gibi sunulmadı. Dashboard/analytics ve diğer uzun
  read yüzeyleri ile 100k planning target kararı açık kaldı; local CI `MERGE READY`,
  709 backend, 76 frontend ve i18n `580/580` kanıtı güncellendi.

### 1.0.14 — 2026-09-08

- H07 core dashboard/analytics read paketi `42d67c6` ile kaydedildi: Dashboard'ın
  dört portföy endpoint'i, Quant Analytics scorecard/symbol response contract'ı ve
  Header portfolio telemetry için AbortSignal, stale-response suppression, explicit
  loading/error/cancel veya unavailable state ve malformed payload fail-closed
  doğrulandı. Backend erişilemezken sıfır scorecard veya sahte `$0.00` gösterilmez.
  Full local CI `MERGE READY`, 709 backend, 84 frontend, i18n `591/591` ve exact
  mounted Mac DMG/WKWebView smoke PASS; JournalView/MAE-MFE ve 100k target açık.

### 1.0.10 — 2026-09-08

- H05 machine gate kanıtı korunarak ürün lisansı/notices ve default-branch Dependabot
  işlemleri geliştirme dönemi için açıkça ertelendi; varsayımsal MIT/başka lisans metni
  eklenmedi ve merge yapılmadı. H05 arşivlendi, ticari dağıtım öncesi yeniden açma
  koşulları korundu. H06 privacy/data lifecycle, yalnız non-release geliştirme için
  güncel aktif paket olarak seçildi.

### 1.0.9 — 2026-09-08

- H05 machine gate `c089cd2` ile uygulandı: deterministic CycloneDX inventory (395
  component), lock/hash drift check, release-source/DMG secret scan, Python `pip-audit`
  80 dependency / 0 known vulnerability ve frontend `npm audit` 0 vulnerability.
  Mac local CI **MERGE READY** (675 backend, 67 frontend, i18n 560/560), exact
  read-only DMG/WKWebView smoke PASS. Root `LICENSE`/third-party notices yokluğu ve
  default branch'teki 5 Dependabot alert'i owner/repository kararı olarak açık kaldı;
  H05 `OWNER_DECISION_REQUIRED`, H06 coding başlamadı.

### 1.0.8 — 2026-09-08

- H04 Mac kanıtı `ca94b83` source checkout'ında yenilendi: local CI **MERGE READY**,
  exact read-only DMG/WKWebView smoke PASS. DMG SHA
  `cc1fab496a1cfbb66bdea5ee94da61c4ed9d64dc635019890a8216d01663189b`, smoke report
  SHA `5ebc294420567b3789be1ddf3986b7c05f8cb7cefdef7ede6a279ce23b119a66`, mounted
  executable SHA `00725e65ff915174a820d39e252646ff8cd54877feb32b22331fb73413201d7a`.
  `wkwebview`/controller identity ve clean detach doğrulandı. Signing/notarization,
  second-host ve default-branch Dependabot alerts açık sınır olarak kaldı.

### 1.0.7 — 2026-09-08

- H04 threat model/trust boundary paketi `1cf486e` ile bounded olarak kapatıldı:
  untrusted input, archive resource, WebView bridge, gateway origin ve secret/path
  redaction negative testleri PASS; full backend **669**, frontend **67**, temiz Mac
  local CI **MERGE READY**. H05 supply-chain, SBOM, license ve secret boundary tek
  güncel Ready work package olarak seçildi. Signing/notarization ve default-branch
  alerts açık sınırdır.

### 1.0.6 — 2026-09-08

- H02 schema upgrade/restore boundary'si `169c446` ile kapatıldı: supported legacy
  SQLite staged atomic upgrade, doğrulanabilir backup, interrupted failure injection,
  canonical backfill/projection rebuild, exact restore, checksum/integrity/schema/
  traversal/symlink fail-closed testleri. 19 focused/package test ve 651 backend testi
  PASS. H04 trust model/boundary tests tek güncel Ready pakettir.

### 1.0.5 — 2026-09-08

- H01 canonical persistence/recovery boundary'si `006e86e` ile process crash,
  transaction/read-only/disk-busy/concurrent import ve restart/rebuild kanıtlarıyla
  bounded olarak kapatıldı. H02 schema upgrade/restore tek güncel Ready work package
  olarak seçildi. H02 yalnız synthetic fixture, preflight, interrupted migration,
  corrupt restore ve future-schema fail-closed sınırlarını kapsar; gerçek kullanıcı
  migration'ı veya release yetkisi vermez.

### 1.0.4 — 2026-09-08

- P1-WP26/U05 accessible/understandable shell boundary'si `30dfcd7` ile kanıtla
  kapatıldı; H01 tek güncel Ready work package olarak seçildi. H01 yalnız canonical
  persistence/recovery testlerini kapsar; yeni schema/event veya release yetkisi
  vermez.

### 1.0.3 — 2026-09-08

- P1-WP25/U04 deterministic weekly review ve as-of boundary'si `26751f7` ile
  kanıtla kapatıldı; P1-WP26/U05 tek güncel Ready work package olarak seçildi.
  Sonraki paket yalnız erişilebilirlik, anlaşılabilir durumlar, locale ve retry
  sınırlarını kapsar; yeni ürün yetkisi veya production iddiası vermez.

### 1.0.2 — 2026-09-08

- P1-WP24/U03 kanıtla kapatıldı; P1-WP25/U04 tek güncel Ready work package olarak
  seçildi. U04 için weekly review, period/timezone/as-of ve late-correction
  determinism boundary'si bounded kapsam olarak tanımlandı.

### 1.0.1 — 2026-09-08

- P1-WP23/U02 kanıtla kapatıldı; P1-WP24/U03 tek güncel Ready work package olarak
  seçildi. U03 için canonical pack/export, redaction ve unavailable-analytics
  boundary'si bounded kapsam olarak tanımlandı.

### 1.0.0 — 2026-09-08

- KRR kalan işleri G0–G7 production kapılarına, bounded teslimatlara ve operasyon
  sözleşmesine ayrıldı. İlk read-only production ve koşullu Faz 2–5 yatırımları ayrıldı.
