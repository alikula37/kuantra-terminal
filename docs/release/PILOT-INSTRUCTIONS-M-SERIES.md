<!-- doc-role: reference -->
# Kuantra Terminal v1.0.0 — M-series arm64 pilotu

**Güncel pilot Release:** [`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)<br>
**Kaynak ve artifact kimliği:** Release ile gelen `PILOT-MANIFEST.json` ve
`SHA256SUMS` dosyaları authoritative'tir; source commit, mimari ve exact hash'ler
bu dosyalardan doğrulanmalıdır.

Bu belge Release asset'i olarak da dağıtılır. Aynı Release sayfasından DMG ile birlikte
`PILOT-MANIFEST.json`, `SHA256SUMS`, `final-smoke-arm64.json`,
`n05-macos-distribution-arm64.json` ve bu talimat dosyasını indirin. Tag ve indirme linki
aynıdır; asset seti güncel frontend pilot hardening commit'ine göre yenilenmiştir.

Bu paket yalnızca Apple Silicon **M işlemcili Mac'ler** içindir: M1, M2, M3,
M4 ve aynı native `arm64` ailesindeki cihazlar. macOS 12 Monterey veya üzeri
gerekir. Intel Mac bu paketin kapsamı değildir; Intel için ayrı `x86_64` DMG
beklenmelidir.

Bu paket `TRUSTED_MACOS_PILOT_ARM64` kapsamındadır. Kapalı teknik pilot içindir;
public dağıtım, production, ticari destek veya Apple tarafından doğrulanmış güven
iddiası değildir. Apple Developer ID alınmadığı için ilk açılışta manuel Gatekeeper
onayı gerekebilir. Bu Release Intel desteği iddia etmez; Intel katılımcı yalnızca ayrı
native `x86_64` artifact verildiğinde Intel lane'ini izlemelidir.

## İndirmeden ve açmadan önce

1. Apple menüsü → **Bu Mac Hakkında** bölümünde cihazın Apple Silicon olduğunu ve
   macOS 12 veya üzeri kullandığını kontrol edin.
2. Terminal'de mimariyi doğrulayın:

   ```text
   uname -m
   ```

   Sonuç `arm64` olmalıdır. Farklı bir sonuçta kurulumu durdurun.
3. Paket klasöründe checksum doğrulaması yapın:

   ```text
   shasum -a 256 -c SHA256SUMS
   ```

   Her satır `OK` değilse uygulamayı açmayın.
4. DMG container bütünlüğünü mount etmeden kontrol edin:

   ```text
   hdiutil verify Kuantra-Terminal-1.0.0-arm64.dmg
   ```

   Başarısız olursa kurulumu durdurup yalnızca dosya adı, Mac modeli, macOS sürümü
   ve hata metnini pilot sahibine gönderin.

`hdiutil verify` dosyanın bozulmadığını kontrol eder; Apple malware taraması,
Developer ID veya notarization yerine geçmez.

## Kurulum ve ilk açılış

Ayarlar → **Uygulama güncellemeleri → Güncelleme sayfasını aç** düğmesi pilot
Release sayfasını varsayılan tarayıcınızda açar. GitHub hesabınızla giriş yapmanız
gerekebilir. Bu düğme sürüm karşılaştırması veya otomatik kurulum yapmaz. Yeni DMG'yi
indirip doğrulayın; uygulamayı kapatarak Applications içindeki uygulamayı değiştirin.
Eski kurulumun bu düğmeyi alması için bir defalık manuel güncelleme gerekir.
Mevcut veriyle ilk açılıştan önce schema uyumluluğunu doğrulayın; uygulama dosyasının
değiştirilmesi, veritabanı geçişinin doğrulandığı anlamına gelmez.

1. `Kuantra-Terminal-1.0.0-arm64.dmg` dosyasını çift tıklayın.
2. `Kuantra Terminal.app` dosyasını **Applications** klasörüne sürükleyin.
3. İlk açılışta Finder'da uygulamaya sağ tıklayıp **Open** seçin.
4. macOS engellerse uygulamayı bir kez açmayı denedikten sonra **System Settings →
   Privacy & Security → Open Anyway → Open** adımlarını uygulayın.

Gatekeeper'ı kapatmayın ve `xattr` ile karantina etiketini silmeyin. “Bilgisayarınıza
zarar verecek” veya “uygulama bozuk” uyarısında **Open Anyway** kullanmayın; kurulumu
durdurun ve bildirin.

## Pilot doğrulama akışı

Uygulama açıldıktan sonra yalnızca sentetik veya onaylanmış/redakte edilmiş CSV ile:

1. import preview;
2. reconciliation/review;
3. Trade Evidence Pack;
4. JSON, HTML ve CSV export;
5. uygulamayı kapatıp yeniden açma ve aynı review/Evidence Pack kimliğini kontrol etme.

Review tamamla/yeniden aç kontrolleri period, timezone veya as-of snapshot değişmişse
bilinçli olarak devre dışı kalabilir. Evidence Pack export'u yalnızca native save bridge
gerçekten dosya kaydettiğini bildirdiğinde hazır görünür; kullanıcı iptali ile kayıt hatası
başarı sayılmaz. Import edilen dosya değiştirildiğinde eski preview kullanılmaz.

## Yeni işlem kaydı ve ücretsiz fiyat sınırı

Yeni işlem ekranında varsayılan **Harici İşlem Kaydı** seçeneği, başka bir yerde
gerçekleştirdiğiniz işlemi günlüğe yazar; Kuantra borsaya emir göndermez. Sembol alanına
`BTCUSDT`, `EURUSD`, `XAUUSD`, `AAPL` veya kaydetmek istediğiniz başka bir varlığı
girebilirsiniz. **Son Fiyatı Çek** yalnızca tam sembolü destekleyen ücretsiz public
kaynakları dener. Sonuçta kaynak sembolü ve `LIVE`, `DELAYED`, `EOD` ya da
`UNAVAILABLE` durumu gösterilir.

Ücretsiz kaynak sonucu `UNAVAILABLE` ise otomatik olarak simülasyona geçilmez ve başka
bir varlık fiyatı kullanılmaz; dışarıda gerçekleşen işlemin gerçek fiyatını manuel girin.
**Simülasyon** yalnızca açıkça seçildiğinde kullanılır ve o da emir göndermez. TradingView
webhook'u gelen bir gözlemdir; işlem günlüğüne fill olarak geçmesi için kullanıcı onayı
gerekir. Ücretli veri hesabı veya API anahtarı pilot için gerekli değildir.

`PARTIAL`, `UNKNOWN`, `NOT_AVAILABLE` ve `NO_DATA` sonuçlarını başarı veya sıfır
olarak yorumlamayın. Bu pilotta gerçek broker emri, para transferi, API credential,
`.env`, Windows migration ZIP'i veya gerçek kullanıcı geçmişi kullanılmaz.

Uygulama veriyi yerel olarak `~/Library/Application Support/Kuantra Terminal`
altında tutar. Uygulamayı kaldırmak için yalnızca Applications içindeki `.app`
dosyasını taşıyın; kullanıcı verisini silmeyin.

## Sorun bildirimi

Şunları gönderin: paket sürümü, DMG dosya adı, `SHA256SUMS` sonucu, `hdiutil verify`
sonucu, Mac modeli, macOS sürümü, `uname -m` sonucu, açılış/akış sonucu ve redakte
edilmiş hata metni. API anahtarı, cookie, credential, kişisel işlem geçmişi veya
tam log dosyası göndermeyin.
