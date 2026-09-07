# ADR-0004 — Windows production renderer: Evergreen WebView2

```yaml
adr: ADR-0004
status: Accepted
date: 2026-09-07
owners: Kuantra desktop/platform
supersedes: none
```

## Bağlam

Kuantra'nın Windows frozen uygulaması pywebview ile React arayüzünü host eder. Önceki Qt
WebEngine yolu iki ayrı üretim riski gösterdi:

1. PyInstaller'ın makinedeki ilgisiz ICU DLL'lerini payload'a alması Qt6Core import'unu
   sembol sürümü uyuşmazlığıyla bozabiliyordu.
2. Qt WebEngine Chromium child-process sandbox'ı bu Windows build'inde `Erişim engellendi`
   (`0x5`) ile başlatılamadı. `--single-process`/`--no-sandbox` ile geçen smoke, üretim için
   kabul edilemez bir güvenlik ve izolasyon gerilemesidir.

WebView2'nin görünür WinForms host process'i aynı makinede ayağa kalktı; ancak tam controller/JS
smoke'u bu makinede `E_ABORT` ile tamamlanmadı. Hidden WebView2 host'u da bazı Windows
build'lerinde aynı nedenle güvenilir değildi; bu nedenle Windows smoke görünür pencereyle çalışır
ve kontrollerden sonra pencereyi kapatır. Bu ADR yön kararıdır; production merge'i için aşağıdaki
controller-ready smoke kanıtı ayrıca zorunludur.

## Karar

- Windows production default renderer `edgechromium` (Microsoft Evergreen WebView2) olacaktır.
- Windows production PyInstaller payload'ı `PyQt6`, Qt WebEngine ve alternatif Qt binding'lerini
  içermez. Bu hem installer boyutunu küçültür hem de Qt/ICU host bağımlılığını üretimden çıkarır.
- `PYWEBVIEW_GUI=qt` yalnızca source veya ayrıca oluşturulmuş diagnostic build için desteklenir;
  production bundle'da Qt bulunmadığından fallback değildir.
- Frozen startup seçilen renderer'ın native binding'lerini ve WebView2 runtime kaydını fail-closed
  preflight eder. Pywebview'in başka backend'e sessiz fallback'i başarılı smoke kanıtı sayılmaz;
  initialized renderer kimliği ve controller readiness smoke raporunda ve local CI logunda
  eşleşmelidir.
- Windows smoke görünür WebView2 host'unda çalışır. Bu UI açılmasını gerektiren bir test
  değişikliğidir; kullanıcı desktop oturumu olmayan CI runner'ı production Windows gate'i olarak
  kabul edilmez.
- WebView2 Evergreen Runtime kurulum önkoşuludur. Fixed Version runtime'ı payload'a gömmek bu
  karara dahil değildir; boyut ve bakım maliyeti ayrı bir ADR gerektirir.

## Reddedilen alternatifler

### Qt'yi Windows default olarak bırakmak

Reddedildi: gerçek host'ta child-process sandbox başlatma hatası gözlendi. Qt'yi `--no-sandbox`
veya `--single-process` ile zorlamak güvenlik/izolasyon iddiasını düşürür.

### Qt fallback'ini production payload'da tutmak

Reddedildi: fallback, hangi native runtime'ın doğrulandığını belirsizleştirir ve ICU/Qt DLL
çakışmasını tekrar üretir. Diagnostic ihtiyacı ayrı build ile karşılanır.

### WebView2 Fixed Version runtime'ını bundle etmek

Şimdilik reddedildi: yüzlerce MB ek payload ve ayrı güvenlik güncelleme sorumluluğu getirir.
Evergreen runtime bulunamayan kurulumlar için installer preflight/yardım akışı uygulanır.

## Sonuçlar ve doğrulama

- Windows paketinde `PyQt6`/`PyQt6-WebEngine` dosyaları bulunmamalı; `webview/lib` ve WebView2
  interop assembly'leri bulunmalı.
- `backend/desktop_main.py --smoke` paketlenmiş WebView2 ile `SMOKE_OK` ve schema v2 report
  üretmeli; görünür smoke penceresi kapatılabilmeli ve `renderer_actual=edgechromium` yazmalı.
- Local CI, platform renderer preflight adımını ve smoke raporundaki renderer provenance'ını
  merge öncesi zorunlu tutar.
- Installer, WebView2 runtime kayıt değeri yoksa mevcut kurulumu değiştirmeden durmalıdır.
- Linux Qt ve macOS cocoa yolları bu ADR ile değiştirilmez.
- Karar, gerçek temiz Windows imajında Evergreen Runtime eksikliği, upgrade ve WebView2 runtime
  versiyon değişimi için ayrı validation işi gerektirir.
