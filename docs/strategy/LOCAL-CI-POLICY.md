# KDG-002 — Yerel CI ve Merge Gate Politikası

```yaml
document_id: KDG-002
version: 1.0.0
status: Accepted
date: 2026-09-07
strategy: KPS-001@1.0.0
implementation: scripts/run_local_ci.py
```

## Karar

GitHub Actions, bu özel repository için kota ve bütçe nedeniyle şu anda kanıt kaynağı
değildir. `main` dalına merge kararı bu nedenle yerel, tekrarlanabilir gate ile verilir.
Remote workflow dosyaları silinmez; kota geri geldiğinde aynı sözleşmenin ek kanıt kaynağı
olarak yeniden etkinleştirilebilir. Remote yeşil görünmüyorsa yerel gate sonucu override
edilmez.

Merge öncesi tek resmi komut:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py
```

`uv` kullanılmıyorsa aynı script, kilitli gereksinimlerle hazırlanmış Python 3.11 ortamında
`python scripts/run_local_ci.py` olarak çalıştırılabilir. `npm --prefix frontend test` ve
`npm --prefix frontend run build` için frontend bağımlılıkları önceden kurulmuş olmalıdır.

## Zorunlu sıralı kapılar

1. `git diff --check`
2. Python compileall
3. `scripts/check_release_truth.py`
4. `scripts/verify_packaging.py`
5. izole veri dizininde tam backend pytest
6. frontend Vitest ve production build
7. kilitli ortamla PyInstaller desktop build
8. paketlenmiş uygulama smoke raporu (`react_mounted`, `bridge_roundtrip`, `health`,
   `push_sink`, `plugin_boundary`)
9. Windows/Linux'ta frozen Qt preflight; Qt yüklenemeyip başka renderer'a fallback edilmesi
   smoke kontrolleri yeşil olsa bile merge'i bloklar. macOS native WKWebView olduğu için bu
   kapı uygulanmaz.

Her komutun sonucu `dist/local-ci-report.json` içinde `KDG-002@1.0.0` policy kimliği,
platform, Python sürümü, süre, smoke hash/provenance ve başarısız adımlarla birlikte tutulur.
Başarılı koşuda geçici test/smoke verisi silinir; başarısız koşuda tanı için korunur.

## Merge ve push protokolü

- `MERGE READY` görülmeden commit push edilebilir ama `main` merge edilemez.
- `MERGE BLOCKED` raporunda listelenen adım çözülmeden başarısız koşu “bilinen sorun” diye
  kapatılamaz.
- Desktop build/smoke değişikliği varsa Windows host gate'i zorunludur; yalnız backend veya
  frontend değişikliklerinde bile tam gate tercih edilir.
- Linux ve macOS kanıtı bu makinede üretilemiyorsa Phase/release kanıtı olarak “3-OS geçti”
  yazılmaz. Bu durumda `main` merge kararı ürün sahibinin açık risk kabulü olmadan verilmez.
- Release/tag için ayrıca final artifact smoke, manifest ve insan release onayı gerekir; local
  merge gate canlı broker execution veya release yayınlama yetkisi vermez.

## Kapsam dışı

- GitHub Actions kotasını artırmak veya billing/spending limit değiştirmek.
- Branch protection kuralı olmayan özel repository'de bunu varmış gibi göstermek.
- Qt preflight hatasını WebView2 fallback'i ile gizlemek.
- Local gate'i bypass etmek için `--skip-*` benzeri sessiz seçenek eklemek.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Actions kapalı/kota dolu dönemde yerel merge gate, rapor şeması ve frozen renderer
  fail-closed kontrolü kabul edildi.
