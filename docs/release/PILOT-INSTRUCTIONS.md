# Kuantra Terminal v1.0.0 — kapalı macOS pilotu

**Güncel pilot Release:** [`pilot-v1.0.0-arm64`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64)<br>
**Kaynak ve artifact kimliği:** Release ile gelen `PILOT-MANIFEST.json` ve
`SHA256SUMS` dosyaları authoritative'tir; source commit, mimari ve exact hash'ler
bu dosyalardan doğrulanmalıdır.

Bu paket üç kişilik, davetli pilot içindir. Public bir indirme veya production
ürünü değildir. Apple Developer ID imzası ve notarization yoksa macOS ilk açılışta
uyarı gösterir; bu bilinçli ve geçici pilot sınırıdır.

Mevcut private Release yalnızca Apple Silicon native `arm64` DMG taşır. Intel pilotu
ayrı native `x86_64` artifact yayımlanana kadar beklemelidir; arm64 dosyasını Intel'de
denemeyin. Aynı Release'teki `PILOT-MANIFEST.json`, `SHA256SUMS` ve evidence dosyaları
DMG ile birlikte dağıtılan teknik kanıttır.

## Trade entry boundary

The New Trade screen defaults to **External Trade Record**. It records a trade that
you executed elsewhere; Kuantra does not send a broker order. Any asset symbol may be
entered for journaling. Search results must be reviewed and explicitly confirmed: check
the candidate name, exchange and source, select the intended candidate, then confirm it.
Until confirmation, the symbol is not activated and no quote/candle request starts;
pressing Enter never silently selects another instrument. **Fetch Mark Price** tries only
exact free public sources and shows the source identity plus `LIVE`, `DELAYED`, `EOD` or
`UNAVAILABLE` status. Market Charts uses the same search → select → confirm flow.

If public providers return no match, you may explicitly confirm the exact typed symbol as
`UNKNOWN/manual`. This records your external symbol without inventing a provider mapping;
it is not price evidence and does not silently turn the symbol into another asset.

When the free quote is unavailable, enter the actual external fill price manually.
Kuantra does not substitute another instrument and does not silently switch to
simulation. Simulation is available only after an explicit choice and also sends no
order. A TradingView webhook is a pending observation until the user confirms the fill;
it is not quote or execution proof. No paid data service or quote API key is required.

## İndirmeden önce

1. GitHub hesabınızla giriş yapın ve size gönderilen private repository Release
   sayfasını açın. Bu sayfa yalnızca repository read erişimi olan pilotlara açıktır.
2. Mac'inizi öğrenin: Apple menüsü → **Bu Mac Hakkında**. Apple Silicon için
   `arm64`, Intel için `x86_64` DMG indirin. macOS 12 Monterey veya üzeri gerekir.
3. Aynı Release içindeki `SHA256SUMS`, `PILOT-MANIFEST.json` ve ilgili kanıt
   dosyalarını da indirin.
4. Terminal'de indirme klasöründe şu kontrolü çalıştırın:

   ```text
   shasum -a 256 -c SHA256SUMS
   ```

   Her satır `OK` değilse uygulamayı açmayın; dosyayı silmeden önce pilot sahibine
   yalnızca dosya adı, Mac modeli/OS sürümü ve hata metnini bildirin.
5. İndirdiğiniz DMG'nin disk-imaj bütünlüğünü mount etmeden önce doğrulayın:

   ```text
   hdiutil verify Kuantra-Terminal-1.0.0-arm64.dmg
   # Intel Mac için bunun yerine:
   hdiutil verify Kuantra-Terminal-1.0.0-x86_64.dmg
   ```

   Yalnızca kullandığınız mimarinin çıktısı başarılı olmalıdır. Bu kontrol DMG
   container'ının bozulmadığını doğrular; Apple malware taraması, Developer ID veya
   notarization yerine geçmez.

İsteğe bağlı olarak Release metadata'sını GitHub CLI ile de kontrol edebilirsiniz:

```text
gh release view pilot-v1.0.0-arm64 --repo alikula37/kuantra-terminal
```

GitHub metadata'sı Apple Gatekeeper güveninin yerine geçmez; asıl dosya doğrulaması
`SHA256SUMS` ve `hdiutil verify` ile yapılır. Release private olduğu için komutu
çalıştıran hesabın repository read erişimi olmalıdır.

## Pilot ekibinin teknik doğrulama rolü

Bu ekip yalnızca uygulamayı kullanmayacak; farklı Mac mimarilerinde gerçek cihaz
kanıtı da sağlayabilir. Apple Silicon kullanan kişi `arm64`, Intel kullanan kişi
`x86_64` DMG'yi indirmelidir. Intel Mac arm64 DMG'yi çalıştırmaz; iki mimari dosya
birbirinin yerine kullanılmaz.

Intel katılımcıdan şu bilgiler ve sonuçlar istenir: **About This Mac** ekranındaki
model ve macOS sürümü, Terminal'de `uname -m` çıktısı, uygulamanın açılış sonucu ve
sentetik test akışında import preview → review → Evidence Pack → export → close/reopen
sonuçları. Bu kayıtlar Intel cihazın runtime doğrulamasıdır; başka Mac modelleri için
genel destek garantisi değildir.

Pilot sahibi Intel Mac'i kontrollü native build hostu olarak da seçerse, checkout edilmiş
onaylı source commit'inde [macOS build runbook'taki Intel lane](../BUILD_MACOS.md#controlled-intel-pilot-build-lane)
çalıştırılabilir. `run_local_ci.py --expected-architecture x86_64` native host, executable
ve provenance eşleşmesini zorunlu kılar; Rosetta altında çalışan süreç veya arm64 artifact
başarılı kabul edilmez. Bu yol sonunda oluşan x86_64 DMG, exact mounted-DMG smoke ve N05
raporları hazır olmadan pilot Release'a yüklenmez.

Pilot sahibi teknik N03 install-lifecycle kanıtı istiyorsa, ayrı temiz bir macOS
profilinde `run_n03_macos_clean_profile_audit.py` çalıştırılmalı ve
`--expected-architecture x86_64` Intel cihazda açıkça verilmelidir. Normal kişisel
profilde yapılan deneme pilot runtime kanıtıdır; temiz profil kanıtı olarak yazılmaz.

## Kurulum ve ilk açılış

Ayarlar → **Uygulama güncellemeleri → Güncelleme sayfasını aç** düğmesi pilot
Release sayfasını varsayılan tarayıcınızda açar. GitHub hesabınızla giriş yapmanız
gerekebilir. Bu düğme sürüm karşılaştırması veya otomatik kurulum yapmaz. Yeni DMG'yi
indirip doğrulayın; uygulamayı kapatarak Applications içindeki uygulamayı değiştirin.
Eski kurulumun bu düğmeyi alması için bir defalık manuel güncelleme gerekir.
Mevcut veriyle ilk açılıştan önce schema uyumluluğunu doğrulayın; uygulama dosyasının
değiştirilmesi, veritabanı geçişinin doğrulandığı anlamına gelmez.

1. Doğru DMG'yi çift tıklayın.
2. `Kuantra Terminal.app` dosyasını **Applications** klasörüne sürükleyin.
3. İlk açılışta Finder'da uygulamaya sağ tıklayın ve **Open** seçin.
4. macOS engellerse uygulamayı bir kez açmayı denedikten sonra **System Settings →
   Privacy & Security → Open Anyway → Open** yolunu kullanın. Bu onay yalnızca
   hash'i doğrulanmış ve pilot sahibinden gelen uygulama için verilmelidir.

Gatekeeper'ı kapatmayın ve karantina etiketini komutla kaldırmayın. “Uygulama
bilgisayarınıza zarar verecek” veya “uygulama bozuk” uyarısı alırsanız **Open Anyway
kullanmayın**; kurulumu durdurup bildirin.

## Pilot kullanımı

- Uygulama veriyi yerel olarak şu klasörde tutar:
  `~/Library/Application Support/Kuantra Terminal`
- İlk denemeye sentetik veya onaylanmış/redakte edilmiş CSV ile başlayın. Windows
  klasörleri, migration ZIP'leri, `.env`, API anahtarı veya credential taşımayın.
- Import → reconciliation/review → Trade Evidence Pack → JSON/HTML/CSV export akışını
  izleyin. Export ancak native save bridge gerçek kaydı onaylarsa başarılı kabul edilir;
  cancel veya failure başarı değildir.
- `PARTIAL`, `UNKNOWN`, `NOT_AVAILABLE` ve `NO_DATA` sonuçlarını başarı veya sıfır
  olarak yorumlamayın; eksik kanıtı not olarak işaretleyin.
- Live broker order, para transferi, AI order authority ve gerçek execution bu pilotta
  kapalıdır. Uygulama bu yüzeylerde emir göndermez.

## Sorun bildirme

Şunları gönderin: Release etiketi, DMG dosya adı, `SHA256SUMS` sonucu, Mac modeli,
macOS sürümü, ekran görüntüsü veya redakte edilmiş hata metni ve tekrar üretme
adımları. API anahtarı, cookie, credential, kişisel işlem geçmişi veya tam log
dosyası göndermeyin.

Uygulamayı kaldırmak için yalnızca Applications içindeki `.app` dosyasını taşıyın.
Bu işlem kullanıcı veri klasörünü silmez. Veri silme, reset veya migration işlemi
pilot sahibinin açık onayı olmadan yapılmaz.
