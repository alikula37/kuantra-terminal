<!-- doc-role: current-roadmap -->
# KPR-001 — İlk production sürümüne kadar geliştirme ve doğrulama planı

```yaml
document_id: KPR-001
version: 1.0.1
status: Proposed
date: 2026-09-08
reviewed_commit: 51ee968e07b9463d1b6d316c7d8419f8aaf7a7c3
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
kanıtlarıyla kapatılmıştır. P1-WP23 / U02 de bounded kanıtla kapatılmış; mevcut
`Ready` iş P1-WP24 / U03'tür. Aşağıdaki
diğer iş kimlikleri plan satırıdır, topluca coding yetkisi veya tamamlanmış WP değildir.

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
`D03 / P1-WP18`, `D04 / P1-WP19`, `D05 / P1-WP20` ve `D06 / P1-WP21` kanıtla kapatılmıştır. P1-WP22, G2/R4 değer zinciri geçidini bounded olarak kapatmış; P1-WP23, U02 reconciliation inbox ve correction/user-decision boundary'sini bounded olarak kapatmıştır. Sonraki işler hazır
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
P1-WP23 (`51ee968`) ile bounded olarak tamamlanmıştır. Sıradaki aktif paket
**P1-WP24 / U03**'tür: canonical Trade Evidence Pack, coverage/rule görünürlüğü,
redaction ve deterministic export safety. U03 tamamlanmadan R5 weekly review veya
release/pilot iddiası açılmaz.

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
   redaction ve deterministic export boundary; ardından U04–U05/R5 ve bağımlılığa
   göre H01–H07/N03–N06.

Her teslim raporu: WP/scope, changed files, failing→passing test kanıtı, tam komutlar,
platform/fixture/source SHA, açık acceptance kutuları, kalan risk, commit/push ve
sıradaki bağımlılık. Uygun testleri geçmeden “tamamlandı”, phase gate geçmeden
“production-ready” denmez. Bu planlama turunda runtime/testnet veya kullanıcı verisi
işlemi yapılmadı; docs-only diff/link/release-truth/packaging kontrolleri uygulanır.

## Değişiklik geçmişi

### 1.0.1 — 2026-09-08

- P1-WP23/U02 kanıtla kapatıldı; P1-WP24/U03 tek güncel Ready work package olarak
  seçildi. U03 için canonical pack/export, redaction ve unavailable-analytics
  boundary'si bounded kapsam olarak tanımlandı.

### 1.0.0 — 2026-09-08

- KRR kalan işleri G0–G7 production kapılarına, bounded teslimatlara ve operasyon
  sözleşmesine ayrıldı. İlk read-only production ve koşullu Faz 2–5 yatırımları ayrıldı.
