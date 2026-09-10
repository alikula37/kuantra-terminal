# macOS Intel ve private GitHub Release pilot dağıtımı — araştırma ve karar kaydı

**Araştırma tarihi:** 2026-09-10
**Kapsam:** Kuantra Terminal v1.0.0, üç kişilik kapalı macOS pilotu, Apple
Developer ID satın almadan güvenli ve dürüst dağıtım sınırı.
**Ürün sınırı:** Local-first Execution Intelligence & Trade Forensics Workstation.

Bu belge teknik karar kaydıdır; canonical product release/tag veya pilot daveti oluşturmaz.
M-series arm64-only private prerelease, `pilot-v1.0.0-arm64` tag'iyle yayımlanmıştır.
Kaynakların güncel koşulları değişebileceği için resmi bağlantılar aşağıda ayrıca
listelenmiştir.

## Sonuç — basit karar

Evet, private GitHub repository Releases bölümü üç kişilik pilot için DMG taşıma
kanalı olarak kullanılabilir. GitHub, repository'ye read erişimi olan kişilerin
release'leri görmesine izin verir; release varlıkları için de browser/API indirme
bağlantıları ve SHA-256 digest alanı sağlar. [GitHub Releases açıklaması](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
ve [release asset API sözleşmesi](https://docs.github.com/en/rest/releases/assets).

Bu, Apple'ın “bu uygulama güvenilir geliştiriciden geldi ve değiştirilmedi” kararının
yerine geçmez. GitHub yalnızca erişim, sürümleme ve dosya bütünlüğü taşımasıdır;
macOS Gatekeeper güveni değildir. Ücretsiz pilot için uygulanabilir sınır:

> private GitHub Release + açıkça kapsamlandırılmış native DMG(ler) + SHA-256 doğrulaması +
> ad-hoc imza + kullanıcının bilinçli Gatekeeper onayı = **trusted pilot only**.

İlk pilot sırası M-series arm64 ile başlayabilir: tek arm64 DMG, paket manifestinde
`TRUSTED_MACOS_PILOT_ARM64` ve `APPLE_SILICON_M_SERIES_ONLY` olarak açıkça işaretlenir.
Bu, Intel veya genel macOS desteği iddiası değildir. İki mimarili paket ayrı bir sonraki
hedeftir ve native x86_64 kanıtı gelmeden üretilmez.

Bu yol public dağıtım, ticari satış veya production-ready iddiası değildir.

## İndirme, DMG bütünlüğü ve macOS güveni aynı şey değildir

Pilot güvenliği üç ayrı kontrol olarak ele alınmalıdır:

1. GitHub Release erişim ve taşıma katmanıdır. `SHA256SUMS`, GitHub asset digest'i
   ve mümkünse immutable Release, kullanıcının indirdiği dosyanın beklenen asset
   olduğunu kontrol eder.
2. `hdiutil verify`, DMG disk imajının/container'ının bozulmadığını doğrular. Kuantra
   bunu build sonrasında ve final read-only mounted-DMG smoke öncesinde zorunlu kılar;
   pilot talimatı indirilmiş dosyada tekrar çalıştırır.
3. Developer ID + notarization, Apple'ın Gatekeeper trust katmanıdır. Developer ID
   olmadan macOS uygulamayı Apple tarafından doğrulanmış geliştirici uygulaması olarak
   kabul etmez; kullanıcıdan bilinçli bir istisna onayı istenebilir. Bu pilot için
   kullanılan ad-hoc imza bu güven katmanını sağlamaz.

Apple, bilinen malware tespitinde XProtect'in uygulamayı engelleyip Trash'e
taşıyabileceğini; değiştirilmiş/bozuk uygulamanın da açılmayabileceğini belirtir.
Bu davranışı devre dışı bırakmak için `xattr`, Gatekeeper kapatma veya benzeri bir
bypass eklenmez. “Bilgisayarınıza zarar verecek” ya da “uygulama bozuk” uyarısı
pilotta fail-closed durma sebebidir. [Apple XProtect](https://support.apple.com/en-ie/guide/security/sec469d47bd8/web)
ve [Apple uygulamaları güvenle açma](https://support.apple.com/en-us/102445).

## Apple Developer ID alınmadan ne olur?

Apple, App Store dışı Mac dağıtımında Developer ID imzasını Gatekeeper'ın tanıdığı
geliştirici kimliği olarak tanımlar; Developer ID sertifikası Apple Developer
Program hesap sahibinin erişimini gerektirir. [Apple Developer ID](https://developer.apple.com/developer-id/)
ve [üyelik karşılaştırması](https://developer.apple.com/support/compare-memberships/).

Apple'ın kendi desteğine göre imzasız/notarize edilmemiş bir uygulama ilk açılışta
uyarı verir. Kullanıcı dosyanın güvenilir ve değiştirilmemiş olduğundan eminse,
uygulamayı denedikten sonra **System Settings → Privacy & Security → Open Anyway**
ile istisna verebilir; Apple aynı sayfada bu override'ın güvenlik riskini açıkça
belirtir. [Apple: Safely open apps](https://support.apple.com/en-us/102445) ve
[Apple: unknown developer override](https://support.apple.com/en-us/guide/mac-help/mh40616/mac).

Bu nedenle pilot dokümanı kullanıcıya güvenlik korumalarını kapattırmaz, `xattr`
ile karantina kaldırmayı önermez ve “uygulama zarar verecek/bozuk” uyarısında
override yapılmamasını söyler. Hash doğrulaması ile kullanıcı onayı birlikte
uygulanır; ikisinden biri yoksa kurulum durur.

Apple'ın notarization akışı Developer ID imzası, hardened runtime ve Apple notary
ticket'ı ister. Notarization yalnızca otomatik malware/signing kontrolüdür; ürünün
finansal doğruluğunu veya Kuantra'nın production readiness'ini kanıtlamaz.
[Apple notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

## GitHub Releases, Actions artifacts ve diğer kanallar

| Kanal | Pilot için değerlendirme | Karar |
|---|---|---|
| Private GitHub Release | Read erişimi olan pilotlara sürüm sayfası ve kalıcı asset bağlantısı verir; DMG, manifest, kanıt ve checksum aynı pakette tutulur. Apple trust sağlamaz. | **Önerilen taşıma kanalı** |
| GitHub Actions artifact | CI çıktısını paylaşmak için uygundur; GitHub dokümanına göre giriş yapmış read erişimli kullanıcılar indirir ve varsayılan saklama süresi 90 gündür. | İç CI/teknik inceleme, pilotun kalıcı dağıtım kanalı değil |
| Public GitHub Release | İndirme kolaylaşır fakat private ürün kodu/varlığı ve ad-hoc uygulama herkese açılır. | Şimdilik kullanılmaz |
| Drive/mesaj eki | Erişim kontrolü ve bütünlük prosedürü GitHub kadar tek yerde değildir; bağlantı kopyalanabilir. | Yalnız GitHub erişimi mümkün değilse yedek kanal |
| Developer ID + notarization | En iyi son kullanıcı deneyimi ve Gatekeeper güveni; Apple üyeliği/sertifika/notary erişimi gerektirir. | Pilot sonrası production kapısı |

GitHub, release asset'lerini 2 GiB'den küçük dosyalar için destekler ve release'leri
tag tabanlı sürümler olarak yönetir. Immutable releases etkinse yayımlandıktan sonra
tag ve asset değiştirilemez; GitHub ayrıca release attestation üretebilir. Tüm asset'leri
önce draft'a yükleyip sonra yayımlamak güvenli işlemdir. [GitHub release yönetimi](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
ve [GitHub CLI release oluşturma](https://cli.github.com/manual/gh_release_create).

Pilot kullanıcısı private repository'de read erişimine sahip değilse Release linki
tek başına çalışmaz. Üç kişiye write/admin vermek gerekmez; erişim sahibi onları
yalnızca read düzeyinde davet etmelidir. Kullanıcı erişimi verilmesi ayrı owner
kararıdır ve bu çalışma sırasında yapılmamıştır.

## Intel için sıkı teknik karar

PyInstaller varsayılan olarak çalışan mimariyi hedefler; dokümanı aynı mimariye sahip
build ortamını kullanmanın sorunları azalttığını belirtir. Intel kanıtı bu yüzden
Apple Silicon üzerindeki Rosetta sürecinden veya dosya adına bakarak türetilmez.
[PyInstaller macOS/cross-build notları](https://pyinstaller.org/en/stable/feature-notes.html).

Kuantra release workflow şu ayrımı korur:

- Apple Silicon: `macos-latest`, gerçek `arm64` executable, ayrı DMG.
- Intel: `macos-15-intel` (ve desteklenen güncel Intel etiketi), gerçek `x86_64`
  executable, ayrı DMG.
- `lipo -archs` executable'da tek mimariyi doğrular; Universal2/fat binary kabul
  edilmez.
- Build, package ve mounted-DMG smoke aynı mimari için çalışır.
- Yeni guard, x86_64 süreci Rosetta ile çalışıyorsa veya translation durumu
  kanıtlanamıyorsa build/package/smoke'u durdurur.

GitHub'ın güncel runner tablosunda private repository'ler için `macos-15-intel`
ve `macos-26-intel` Intel etiketleri, Apple Silicon için `macos-latest` ve benzeri
etiketler listelenir. Private repository hosted-runner işleri hesap dakikalarını
kullanır ve ücretlendirilebilir; mevcut hesabın billing/spending-limit problemi
Intel job'ını job başlamadan durdurduğu için x86_64 kanıtı henüz üretilmemiştir.
[GitHub runner seçimi](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
ve [runner fiyatlandırması](https://docs.github.com/en/billing/reference/actions-runner-pricing).

### “Son 10 yıldaki her Mac” ifadesinin doğru sınırı

Native x86_64 DMG, Intel mimarisi için gerekli ama tek başına yeterli değildir. Ürün
minimumu macOS 12 Monterey'dir. Apple'ın uyumluluk sayfaları bazı 2014 Intel
modellerinin en fazla macOS Big Sur çalıştırdığını, bazı 2015/2016 modellerin ise
Monterey çalıştırabildiğini gösterir. Dolayısıyla doğru claim “macOS 12+ çalıştıran
native arm64 veya x86_64 Mac”; “son 10 yıldaki her fiziksel Mac” değildir.
Kullanıcı model ve OS'yi **About This Mac** ekranından kontrol etmelidir.
[Apple macOS sürüm/uyumluluk tablosu](https://support.apple.com/en-us/109033),
[MacBook Air model listesi](https://support.apple.com/en-gb/102869) ve
[MacBook Pro model listesi](https://support.apple.com/en-gb/108052).

Bu sınır ürünün daha geniş kitleye ulaşmasını engelleyen keyfi bir tercih değil;
eski OS'lerde güncel WebKit/Python/native wheel ve güvenlik kanıtını yeniden üretmeden
destek iddiası açmama kuralıdır. macOS 12+ dışındaki Intel makineler unsupported/untested
olarak kalır.

## Üç pilot için önerilen işlem zinciri

1. M-series pilotu için aynı source commit üzerinde native arm64 locked dependency,
   backend/frontend test, build, package ve exact read-only mounted-DMG WKWebView smoke
   sonuçları PASS olur. `--architecture arm64` açıkça seçilerek tek mimarili paket üretilir;
   paket manifesti Intel desteği iddia etmez. İki mimarili pilot için ayrıca hosted Intel
   runner veya açıkça kontrollü Intel pilot Mac üzerinde native x86_64 zinciri tamamlanır.
2. `scripts/prepare_pilot_package.py --architecture arm64` M-series DMG'yi, final smoke/N05
   raporunu, standalone M-series talimatını, `PILOT-MANIFEST.json` ve `SHA256SUMS` dosyasını
   üretir. Varsayılan `scripts/prepare_pilot_package.py` çağrısı ise iki DMG'yi, iki final
   smoke raporunu ve iki N05 raporunu ister; Intel kanıtı eksikse exit 2 ile durur. Aynı
   builder, dual package için arm64'ü tek başına paketlemez. Her iki mod da Release oluşturmadan
   local candidate üretir; Actions artifact saklama süresi bitince pilotun kalıcı taşıma kanalı
   değildir.
3. Ad-hoc N05 raporu `AD_HOC_BLOCKED` olarak pakete yazılır. Bu durum pilotta
   beklenir; `production_ready`, `commercial_support`, `real_user_outcome` ve
   `live_broker_execution` her zaman false kalır.
4. Owner, source commit'i önceden doğrulanmış ayrı bir prerelease/pilot tag'iyle
   eşleştirip draft private Release oluşturur. M-series arm64-only kanalında bu tag
   `pilot-v1.0.0-arm64` olur; `v*` ile başlamadığı için dual production workflow'unu
   yanlışlıkla tetiklemez. Tüm asset'ler yüklenir, checksum ve manifest kontrol edilir;
   immutable release etkinse draft → tüm asset'ler → publish sırası kullanılır. Canonical
   `v1.0.0` product tag'i dual release kapıları geçmeden kullanılmaz. Mevcut M-series
   prerelease linki [`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)'dir.
5. Pilotlara yalnızca repository read erişimi verilir. Pilot sayfası ve doğru
   architecture DMG'si paylaşılır; kullanıcı `shasum -a 256 -c SHA256SUMS` çalıştırır
   ve ilk açılışta manuel Gatekeeper onayı verir.
6. Pilot akışı import preview → reconciliation → review → Evidence Pack → export
   olarak izlenir. Intel katılımcı, kendisine verilen x86_64 DMG üzerinde gerçek cihaz
   açılışı ve close/reopen sonucunu da doğrular. Kullanıcı verisi consent/redaction
   sınırında tutulur; credential, gerçek broker order veya transfer işlemi kullanılmaz.
7. Sorun raporu yalnızca sürüm, architecture, OS/model, checksum sonucu ve redakte
   edilmiş hata bilgisi içerir. User-value, production veya ticari support sonucu
   bu küçük pilotun teknik paketinden türetilmez.

## Uygulanan paket ve açık kanıtlar

Bu araştırmanın kod karşılığı:

- `scripts/prepare_pilot_package.py`: varsayılan dual modda iki mimari exact
  artifact/evidence zincirini doğrular. Açık `--architecture arm64` modu M-series
  pilotunun önce başlamasına izin verir; paket tipini, hardware scope'unu ve Intel
  desteği yokluğunu manifestte görünür tutar. Her iki mod source/tree/lock/truth
  identity eşitliğini kontrol eder; ad-hoc N05'i pilot-only olarak sınıflandırır;
  checksum üretir.
- `scripts/macos_architecture.py`: Rosetta translation durumunu fail-closed kontrol
  eder; x86_64 native host kanıtı yoksa build/package/smoke reddedilir.
- `scripts/build_desktop.py`, `scripts/smoke_desktop.py`,
  `scripts/package_macos.sh` ve `.github/workflows/release.yml`: aynı native host
  sözleşmesini uygular; build job'larının GitHub write izni daraltılmıştır.
- `docs/release/PILOT-INSTRUCTIONS.md`: teknik olmayan pilot kullanıcısı için
  checksum, kurulum, Gatekeeper ve veri sınırı talimatlarıdır.

Dual package assembly'nin kapanması için gerekli Intel `x86_64` DMG ve exact smoke/N05
raporu hâlâ yoktur. Mevcut GitHub billing/spending-limit blocker hosted yolu kapatmaktadır;
dual mod script'i kontrollü native Intel pilot Mac'inden aynı provenance kanıtı gelene kadar
bilinçli olarak paket üretmez. Bununla birlikte M-series için explicit arm64-only paket yolu
bu dış kanıta bağlı değildir ve hardware scope'u daraltılmış trusted pilot olarak hazırlanabilir.
Intel pilot hostu sonrasında runtime/N03 kanıtını da sağlayabilir. N03 temiz ikinci profil/host,
Apple Developer ID/notarization ve owner pilot erişim/approval kararları ayrı kapılardır.

## Açık kararlar ve sınırlar

- Üç pilot kullanıcının private repository read erişimine eklenmesi owner tarafından
  yapılmalıdır; bu kod değişikliği sırasında yapılmadı.
- GitHub Release, Apple Developer ID yerine geçmez; ad-hoc DMG yalnız güvenilen küçük
  pilot için uygundur.
- Apple Developer Program satın alma/notarization işlemi pilot için yapılmayacak;
  production distribution gate'i kapalı kalacaktır.
- v1 macOS 12+ ile sınırlıdır; Windows/Linux veya macOS 11 ve altı iddia edilmez.
- MIT/third-party notices kararı bu paket tarafından çözülmez; ticari dağıtım öncesi
  ayrı release gate'i olarak kalır.
- Hiçbir release/tag, upload, user-data migration, credential veya canlı execution
  bu araştırma ve implementasyonla yapılmamıştır.

## Kaynaklar

- [GitHub — About releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [GitHub — Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub — Immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
- [GitHub — Release assets API](https://docs.github.com/en/rest/releases/assets)
- [GitHub — Workflow artifacts](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
- [GitHub — Choosing runners](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
- [GitHub — Runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)
- [Apple — Developer ID](https://developer.apple.com/developer-id/)
- [Apple — Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
- [Apple — Safely open apps](https://support.apple.com/en-us/102445)
- [Apple — Open an unknown-developer app](https://support.apple.com/en-us/guide/mac-help/mh40616/mac)
- [Apple — Membership comparison](https://developer.apple.com/support/compare-memberships/)
- [Apple — macOS compatibility](https://support.apple.com/en-us/109033)
- [PyInstaller — Feature notes](https://pyinstaller.org/en/stable/feature-notes.html)
