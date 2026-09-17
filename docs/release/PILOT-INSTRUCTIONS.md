# Kuantra Terminal v1.1.5 — kapalı macOS pilotu

**Güncel pilot Release:** [`pilot-v1.1.5`](https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.1.5)<br>
**Kaynak ve artifact kimliği:** Teknik manifest, checksum ve smoke kanıtları repository
ve local audit paketinde tutulur. Güncel Release indirme alanında yalnızca iki native
DMG bulunur: `arm64` Apple Silicon ve `x86_64` Intel.

Bu paket üç kişilik, davetli pilot içindir. Public bir indirme veya production
ürünü değildir. Apple Developer ID imzası ve notarization yoksa macOS ilk açılışta
uyarı gösterir; bu bilinçli ve geçici pilot sınırıdır.

Mevcut private Release iki ayrı native DMG taşır. Apple Silicon/M-serisi Mac için
`arm64`, Intel Mac için `x86_64` dosyasını indirin; bir mimarinin dosyasını
diğerinde kullanmayın. Teknik manifest, checksum ve evidence dosyaları repository/local
audit paketindedir; Release indirme alanında yalnızca iki DMG bulunur.

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

## Yerel TP1/TP2/TP3 takibi

- Yeni manuel kayıtta otomatik yerel takip varsayılan açıktır; kapatabilirsiniz.
  Eski/import edilmiş kayıtlarda kendiliğinden açılmaz. Yerel takip ve parasal
  hesaplar için **miktarın temel birim olduğunu açıkça beyan etmeniz** gerekir;
  sağlayıcı etiketi veya fiyat tek başına sözleşme büyüklüğünü doğrulamaz.
- Long veya short için 1–3 hedef fiyatı ve her hedefte kapanacak yüzdeyi girin.
  Yüzdeleri siz belirlersiniz; toplam %100 olmalıdır. Yalnız SL de kullanılabilir.
- Yerel takip panelindeki **TP/SL düzenle** ile kalan hedefleri ve SL'yi değiştirin.
  Gerçekleşmiş hedefler kilitlidir; değişiklik geçmişi korunur.
- Uygulama açık ve Mac uyanıkken, doğru sağlayıcı/sembole ait en fazla 60 saniyelik
  doğrulanabilir güncel gözlem hedefi tetikleyebilir. Binance/Bybit son işlem akışları
  bu kontrolü destekler. Mevcut Yahoo/Stooq/Biquote fiyatları (altın dahil) görüntülenebilir,
  ancak güncellik kanıtı uygun değilse otomatik kapanış yapmaz; takip fiyat bekler.
- Kapanışlar **uygulama içi** tahmini brüt sonuçtur: borsaya emir göndermez,
  gerçek pozisyonunuzu kapatmaz, gerçek ücret/net kazanç veya borsa gerçekleşmesi değildir.
  Harici işlem günlüğü ve gerçek işlem analitiği ayrı kalır.
- İlk denemede sentetik kayıtla üç hedef girin, düzenleme ekranını açın, kalan miktarı
  ve geçmişi kontrol edin. Uygulama kapalıyken geçmişe dönük kapanış üretilmez.

## İndirmeden önce

1. GitHub hesabınızla giriş yapın ve size gönderilen private repository Release
   sayfasını açın. Bu sayfa yalnızca repository read erişimi olan pilotlara açıktır.
2. Mac'inizi öğrenin: Apple menüsü → **Bu Mac Hakkında**. Apple Silicon/M-serisi için
   `arm64`, Intel için `x86_64` DMG'yi seçin. Intel Mac'te arm64, M-serisi
   Mac'te x86_64 dosyasını kullanmayın.
   macOS 12 Monterey veya üzeri gerekir.
3. Pilot Release indirme alanında yalnızca doğrulanmış `arm64` ve `x86_64`
   DMG'ler bulunur. Teknik manifest, checksum ve evidence dosyaları repository/local audit
   paketindedir.
4. İndirdiğiniz DMG'nin disk-imaj bütünlüğünü mount etmeden önce doğrulayın:

   ```text
   hdiutil verify Kuantra-Terminal-1.1.5-<architecture>.dmg
   ```

   Çıktı başarılı olmalıdır. Bu kontrol DMG
   container'ının bozulmadığını doğrular; Apple malware taraması, Developer ID veya
   notarization yerine geçmez.

İsteğe bağlı olarak Release metadata'sını GitHub CLI ile de kontrol edebilirsiniz:

```text
gh release view pilot-v1.1.5 --repo alikula37/kuantra-terminal
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

## İşlem tarihi ve düzenleme

- Yeni işlemde tarih ve saat **Türkiye saatine** göre dakika hassasiyetinde girilir.
  İşlem hâlâ açık mı, daha önce mi kapandı açıkça seçilir; geçmiş tarihli açık kayıt
  için yerel takip ancak kayıttan sonraki ilk uygun fiyat gözlemiyle başlar.
- Jurnal satırındaki **Düzenle** ile giriş fiyatı, işlem zamanı, miktar, kaldıraç,
  notlar ve plan TP/SL değerleri düzeltilebilir. Kısmi kapanıştan sonra giriş
  fiyatı ve miktar kilitlidir.
- Düzenleme ekranındaki **durum** seçimiyle işlem açık, kapalı veya iptal edildi
  yapılabilir: iptal edilmiş kayıt geri açılabilir, kapanmış kayıt yeniden açılabilir
  (kayıtlı kapanış sonucu temizlenir, önceki değerler düzeltme geçmişinde kalır).
  Bir işlemi kapatmak için gerçekleşen çıkış fiyatı ve saati gerekir; tamamlanmış
  işlemde durum değiştirilmeden yalnızca not düzeltilebilir.
- Her düzeltme revizyonlanır ve önceki değerler kanıt geçmişinde korunur; eski bir
  ekran yeni değişikliğin üzerine yazamaz.

## Dışa aktarma ve raporlar (çalışma kopyası — henüz yayımlanmadı)

İşlem Günlüğü başlığındaki **Dışa aktar** düğmesi CSV veya PDF üretir:

- **Kapsam:** *Filtrelenmiş sonuçlar* ekranda yüklü sayfayı değil, mevcut filtreye uyan
  **tüm** kayıtları dışa aktarır; *Tüm kayıtlar* filtreyi yok sayar. Ekran size kaç kaydın
  seçildiğini ve varsa veri kalitesi uyarılarını önceden gösterir.
- **Dönem:** Başlangıç/bitiş tarihi veya tek adımda **ay** seçilebilir. Tarihler
  **Europe/Istanbul** takvim gününe göredir ve artefakt bunu açıkça yazar. Filtre
  **giriş tarihine** ya da **kapanış tarihine** göre uygulanır; seçim belgede belirtilir.
- **CSV:** Excel uyumlu (UTF-8 BOM), formül enjeksiyonuna karşı korumalı hücreler.
  **PDF:** dönem özeti + açık/kapanmış listeler, sayfa numaralı ve uzun tabloları böler.
- **Güvenilirlik:** İptal edilen kayıtlar performansa katılmaz; bilinmeyen PnL sıfır
  sayılmaz (sayısı ve kapsamı gösterilir); para toplamları yalnızca sunucu tarafından
  doğrulanmış kotasyon birimi içinde üretilir ve doğrulanmamış kayıtlar toplama katılmaz
  (dönüşüm uygulanmaz); yerel TP/SL tahminleri gerçekleşmiş sonuca eklenmez, ayrı bir
  "tahmini brüt sonuç (ücretler hariç)" bölümünde gösterilir.
- **Sınırlar:** Seçim 2.000 kaydı veya 8 MiB artefaktı aşarsa dışa aktarma sessizce
  kırpılmaz; açık bir hata gösterilir (tarih aralığını daraltın). Kaydetme iptal edilirse
  "kaydedildi" denmez.
- **Tek işlem kanıt paketi:** JSON/HTML/CSV yanında doğrudan **PDF** özeti
  kaydedilebilir; tam kanıt yükü JSON artefaktındadır.

## Grafik incelemesi ve günlük düzeltmeleri (v1.1.4)

- **Grafikte incele (salt okunur):** Kapanmış işlem kaydedilmiş giriş–çıkış mumlarını,
  planlanan seviyeleri ve kayıtlı kapanış kaynağını gösterir; bu bir 1 dakikalık bar
  yaklaşımdır, broker gerçekleşmesi değildir. **Açık** işlemde inceleme, sahip olmadığı
  veriyi varmış gibi göstermez: oturumda doğrulanmış mum yoksa **Yenile** istenir ve
  önbellekten hiçbir satır gösterilmez; yenileme mumları yalnızca işlemde beyan edilen
  ücretsiz sağlayıcıdan ve tam sağlayıcı sembolünden çeker (yedek sağlayıcı yok, ürün
  değiştirme yok; `GOLD` asla sessizce `GC=F` vadelines dönüşmez).
- **Ürün tutarlılık kontrolü:** Aynı yenilemede en fazla bir ek ücretsiz istek, beyan edilen
  spot ürünü (örneğin XAUUSD) bir bağımsız kaynakla karşılaştırır ve ölçülen örtüşme ile
  medyan sapmayı `CONSISTENT` / `DIVERGENT` / `UNVERIFIABLE` olarak yazar. Vadeli ve token
  ürünler yapısal olarak karşılaştırılamaz; "tutarlı" yalnızca bağımsız kaynak uzlaşmasıdır,
  broker kanıtı değildir.
- **Manuel giriş fiyatı kimliği silmez:** Onayladığınız piyasa (örneğin Binance BTCUSDT)
  kayıtta kalır; giriş fiyatını elle yazsanız da günlük fiyat yenilemesi, düzenleme ve
  grafik incelemesi aynı kimliği kullanır. Fiyatın kendisi "manuel, gözlemlenmemiş" olarak
  işaretlenir; sembolden sağlayıcı uydurulmaz.
- **Simülasyon ve yerel takip ayrımı:** Simülasyon kayıtları günlükte ve açık işlemler
  tablosunda açıkça etiketlenir; günlük satırı yerel plan durumunu ve kalan miktarı ayrı
  gösterir; yerel plan tamamlandığında harici işlem hâlâ açıktır ve bu bir tahmindir.
  Simülasyonlar gerçek para toplamlarına (portföy özeti, varlık kırılımı, equity eğrisi,
  günlük ısı haritası) karışmaz; ayrı sayaçlarla raporlanır.
- **Eylemler erişilebilir:** Günlük satır eylemleri (Düzenle / Kanıt / Grafikte incele /
  İptal et) dar pencerede sağ kenara sabitlenir ve klavyeyle odaklanabilir; yazı boyutları
  değiştirilmedi.

## USD pozisyon değeri (v1.1.5)

- Artık tek boyut alanı **Pozisyon değeri (USD)**'dir: gerçekte bağladığınız tutarı yazın.
  K/Z, marjin ve R bu değerden hesaplanır; kontrat büyüklüğü doğrulaması gerekmez.
- Kotasyonu USD olmayan paritelerde (ör. ETHBTC) USD değeri sonucu **yaklaşıktır** ve
  arayüz bunu açıkça etiketler.
- Günlük, açık işlemler, düzenleme, yerel takip ve dışa aktarımlar değeri USD olarak
  gösterir. Eski `BASE`/`UNKNOWN` kayıtlar okunabilir kalır; yalnızca değeri değiştirip
  kaydettiğinizde USD'ye dönüşür.
- **Günlük sıfırlandı (sahip kararı):** eski miktar modeli pilot iş akışına uymadığı için
  tüm işlem kayıtları silindi; silmeden önce tüm veri dizini yedeklendi
  (`Documents/Kuantra-Backups/` altında zaman damgalı kopya). Tercihler, playbook'lar ve
  piyasa mumu önbelleği korundu.

## Kurulum ve ilk açılış

Ayarlar → **Uygulama güncellemeleri → Releases sayfasını aç** düğmesi deponun GitHub
Releases listesini varsayılan tarayıcınızda açar; sabit bir sürüm bağlantısı kullanmaz.
GitHub hesabınızla giriş yapmanız gerekebilir. Bu düğme sürüm karşılaştırması veya
otomatik kurulum yapmaz; başarısız açılışta hata gösterir, "güncelsiniz" demez. Yeni DMG'yi
indirip doğrulayın; uygulamayı kapatarak Applications içindeki uygulamayı değiştirin.
1.1.5 öncesi kurulumlarda bu düğme daha eski bir sayfayı açabilir; bu durumda bir defalık
manuel güncelleme gerekir.
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

Şunları gönderin: Release etiketi, DMG dosya adı, `hdiutil verify` sonucu, Mac modeli,
macOS sürümü, ekran görüntüsü veya redakte edilmiş hata metni ve tekrar üretme
adımları. API anahtarı, cookie, credential, kişisel işlem geçmişi veya tam log
dosyası göndermeyin.

Uygulamayı kaldırmak için yalnızca Applications içindeki `.app` dosyasını taşıyın.
Bu işlem kullanıcı veri klasörünü silmez. Veri silme, reset veya migration işlemi
pilot sahibinin açık onayı olmadan yapılmaz.
