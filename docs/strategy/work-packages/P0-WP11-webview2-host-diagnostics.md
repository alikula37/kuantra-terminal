# P0-WP11 — WebView2 Host Diagnostics

```yaml
document_id: P0-WP11
version: 1.0.0
status: Active
date: 2026-09-07
baseline: d508ff9
strategy: KPS-001@1.0.0
adr: ADR-0004
depends_on: P0-WP10 Phase 0 exit audit, ADR-0004 Windows WebView2 renderer
implementation_commits: eda6f4b
```

## Problem

Mevcut Windows host'ta registry/runtime ve pywebview WebView2 binding'leri
görünür olsa da gerçek controller `0x80004004 E_ABORT` ile hazır olmuyor.
Farklı bir fiziksel Windows makinesi olmadan sorunun runtime, kullanıcı profili,
native host, DPI/policy veya JavaScript roundtrip katmanında ayrıştırılması
gerekiyor.

## Karar

1. Teşhis aracı Kuantra backend'ini ve frontend'ini başlatmayan bağımsız bir
   WebView2 probe child process'i kullanır.
2. Parent process bounded timeout uygular; native GUI loop rapor yazdıktan sonra
   kapanmıyorsa child'ı terminate/kill eder.
3. Her run yeni veya açıkça verilen WebView2 user-data klasörünü kullanır ve
   klasörü otomatik silmez. Böylece forensic inceleme mümkündür.
4. Rapor runtime registry, pywebview/pythonnet sürümleri, ilgili environment
   değişkenleri, DPI, actual renderer, controller readiness ve JS roundtrip
   sonuçlarını taşır. Secret veya genel environment dump edilmez.
5. GPU/DPI browser flag'leri üretim yapılandırmasına eklenmez; gerekiyorsa
   yalnızca ayrı bir manuel teşhis koşusunda kullanılır.

## Teknik teslimatlar

- `scripts/diagnose_webview2.py` bounded parent/child probe ve JSON raporu.
- `backend/tests/test_webview2_diagnostics.py` saf rapor/versiyon/environment testleri.
- Bu iş paketi ve Windows build/runbook bağlantısı.

## Kullanım

```powershell
uv run --offline --no-project --with-requirements backend/requirements.lock `
  python scripts/diagnose_webview2.py `
  --report "$PWD/dist/webview2-probe.json" `
  --timeout 15
```

Başarısız rapor ürün release kanıtı değildir; yalnızca blocker katmanını
daraltan teşhis kanıtıdır. `user_data_dir` ve `report` forensic inceleme için
korunur.

## Kabul kriterleri

- [ ] Aynı Windows host'ta bağımsız probe çalıştırıldı.
- [ ] Evergreen registry/runtime ve interop import sonucu raporlandı.
- [ ] Controller readiness ve JS roundtrip sonucu ayrıştırıldı.
- [ ] Timeout sonrası child process kalmadığı doğrulandı.
- [ ] Temiz user-data klasörü ve mevcut profil koşulları karşılaştırıldı.
- [ ] Focused test suite geçiyor.
- [ ] Bu sonuç Windows packaged smoke gate'ini geçerli şekilde `READY` veya
      `BLOCKED` olarak güncelledi.

## Kesinlikle kapsam dışı

- WebView2 yerine Qt/MSHTML fallback'i üretim default'u yapmak.
- `--no-sandbox` veya benzeri güvenlik azaltıcı flag'i üretime eklemek.
- Probe başarısını Kuantra UI smoke başarısı veya execution authority olarak
  yorumlamak.
- Kullanıcının genel environment'ını veya credential'larını rapora yazmak.

## 2026-09-07 çalışma kanıtı

- Aynı Windows host'ta Evergreen WebView2 `152.0.4191.66`, pywebview `6.2.1`,
  pythonnet `3.1.0` ve `edgechromium` interop import'u doğrulandı.
- Bağımsız probe'da renderer seçimi doğru olsa da `initialized`, `shown`, `loaded`
  ve `_pywebviewready` event'leri readiness timeout'u boyunca set edilmedi.
- Paketlenmiş gerçek `--smoke` de aynı host'ta `CreateCoreWebView2ControllerAsync`
  kaynaklı `0x80004004 E_ABORT` ile başarısız oldu. Bu nedenle Windows packaged
  release gate'i **BLOCKED**; probe veya registry başarısı bunu yeşile çevirmiyor.
- Probe ve smoke runner, kendi child process ağacını `taskkill /T /F` ile bounded
  biçimde sonlandıracak şekilde güncellendi; diagnostic WebView2 süreçlerinin
  sonraki denemeleri kirletmesi engellendi.

Bu sonuç runtime'ın kurulu olmadığını değil, mevcut Windows oturumunda native
WebView2 controller başlatma katmanının güvenilir biçimde kanıtlanamadığını gösterir.
Farklı fiziksel Windows makinesi olmadan sonraki güvenli doğrulama sırası: aynı
makinede yeniden başlatılmış etkileşimli oturum, mümkünse Windows Sandbox/VM;
macOS smoke'u ise ayrı WKWebView kapısıdır ve Windows kapısını geçmez.

## Sonraki sınır

Probe sonucu runtime/profile katmanını dışlarsa, küçük native WebView2 sidecar
veya Windows external-browser app-window seçeneği ayrı bir ADR olarak
değerlendirilebilir. O zamana kadar Windows packaged release fail-closed kalır.
