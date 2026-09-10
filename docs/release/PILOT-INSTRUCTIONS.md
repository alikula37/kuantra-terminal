# Kuantra Terminal v1.0.0 — kapalı macOS pilotu

Bu paket üç kişilik, davetli pilot içindir. Public bir indirme veya production
ürünü değildir. Apple Developer ID imzası ve notarization yoksa macOS ilk açılışta
uyarı gösterir; bu bilinçli ve geçici pilot sınırıdır.

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

İsteğe bağlı olarak, immutable GitHub Release kullanıma açılmışsa release ve asset
kanıtını GitHub CLI ile de kontrol edin:

```text
gh release verify v1.0.0 --repo alikula37/kuantra-terminal
gh release verify-asset v1.0.0 Kuantra-Terminal-1.0.0-arm64.dmg --repo alikula37/kuantra-terminal
```

Bu GitHub kanıtı Apple Gatekeeper güveninin yerine geçmez. Release public değilse
komutları çalıştıran hesabın repository read erişimi olmalıdır.

## Kurulum ve ilk açılış

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
- Import → reconciliation/review → Trade Evidence Pack → export akışını izleyin.
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
