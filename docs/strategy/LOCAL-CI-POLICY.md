# KDG-002 — Yerel CI ve Merge Gate Politikası

```yaml
document_id: KDG-002
version: 1.1.2
status: Accepted
date: 2026-09-08
strategy: KPS-001@1.1.0
implementation: scripts/run_local_ci.py
```

## Karar

GitHub Actions için 2026-09-07 kaydında kota/bütçe nedeniyle kanıt alınamıyordu;
bu kayıt güncel billing sorgusu değildir. `main` dalına merge kararı yerel,
tekrarlanabilir gate ve ayrıca ürün sahibinin onayı ile verilir.
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
9. Platform renderer preflight; Windows WebView2 veya Linux Qt yüklenemeyip başka renderer'a
   fallback edilmesi
   smoke kontrolleri yeşil olsa bile merge'i bloklar. macOS native WKWebView olduğu için bu
   kapı uygulanmaz.

Her komutun sonucu `dist/local-ci-report.json` içinde `KDG-002@1.1.0` policy kimliği,
platform, Python sürümü, süre, smoke hash/provenance ve başarısız adımlarla birlikte tutulur.
Başarılı koşuda geçici test/smoke verisi silinir; başarısız koşuda tanı için korunur.

## Merge ve push protokolü

### Kanıtın yorumlanması — 2026-09-08 açıklaması

- `uv --offline` dependency resolution içindir; runtime network isolation değildir.
  Mevcut startup public Binance bağlantısı açabilir. İlk network install ve public
  testnet koşuları offline kanıt diye yazılmaz.
- macOS `_desktop_preflight` atlanır ve smoke validator renderer equality'yi macOS için
  zorunlu tutmaz. Native smoke başarısı otomatik WKWebView identity enforcement değildir.
- `--artifact` yalnız hash metadata'sı ekler; final DMG kanıtı mount edilmiş artifact'ın
  executable'ını çalıştırmayı gerektirir. `build_commit=UNKNOWN` provenance eksiğidir.
- Full local CI mühendislik kanıtıdır; broker completeness, tüm perps accounting,
  kullanıcı review başarısı veya üç-OS final artifact doğrulaması yerine geçmez.
- Yalnız doküman değişikliklerinde diff/link/release-truth/packaging kontrolleriyle
  branch commit/push yapılabilir; çalıştırılmayan full gate yeni koşu gibi raporlanmaz.
  `main` merge ve release kapıları bundan muaf değildir.

Bu açıklama script/report policy kimliğini değiştirmez (`KDG-002@1.1.0`). Açık
runtime sertleştirme işleri [STATUS](STATUS.md) içinde takip edilir.

Doküman rol/bağlantı kapısı `python3.11 scripts/check_docs.py` ile çalışır ve
`verify_packaging.py` tarafından da zorunlu çağrılır. Tek roadmap, beş güncel başlangıç
belgesi, seçili WP ve arşivde korunmuş açık kabul sayıları doğrulanır. Gate semantic
doğruluk, dış URL veya tarihsel kod satırı doğrulaması iddiası taşımaz.

### İşlem sınırı

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
- Renderer preflight hatasını başka bir backend fallback'i ile gizlemek.
- Local gate'i bypass etmek için `--skip-*` benzeri sessiz seçenek eklemek.

## Değişiklik geçmişi

### 1.1.2 — 2026-09-08

- Doküman role/link gate packaging preflight'a bağlandı; runtime rapor kimliği
  değişmedi. Güncel blocker referansı STATUS oldu.

### 1.1.1 — 2026-09-08

- Offline, Mac renderer, DMG provenance ve docs-only branch doğrulaması sınırları eklendi.

### 1.1.0 — 2026-09-07

- Actions kapalı/kota dolu dönemde yerel merge gate, rapor şeması ve frozen renderer
  fail-closed kontrolü kabul edildi.
- Windows production smoke'u görünür WebView2 host'u ile doğrular; Qt WebEngine yalnızca Linux
  production payload'ında veya ayrı bir Windows diagnostic build'inde kullanılabilir. Renderer
  seçimi başarısız olduğunda pywebview fallback'i başarılı smoke kanıtı sayılmaz.
