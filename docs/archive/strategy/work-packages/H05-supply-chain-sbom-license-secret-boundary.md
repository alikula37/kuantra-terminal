<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# H05 — Supply Chain, SBOM, License & Secret Boundary

```yaml
work_package: H05
version: 1.1.0
status: Deferred
date: 2026-09-08
baseline_commit: 1cf486e
implementation_commit: c089cd2
evidence_commit: c089cd2
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H04
```

## Amaç

Kuantra'nın locked dependency, build input, generated artifact ve support/export
çıktısı arasındaki supply-chain güvenini kanıtlamak. Bu paket vulnerability scan,
deterministic inventory ve secret boundary'sini bounded biçimde ele alır; hukuki
lisans onayı, remote signing, notarization, pilot veya release yetkisi vermez.

## Davranış sözleşmesi

- Backend ve frontend lock dosyaları doğrulanır; test/production dependency ayrımı
  ve mevcut branch bulguları açıkça raporlanır.
- SBOM/package inventory aynı source ve lock girdileri için deterministik üretilir;
  dependency adı/sürümü/hash bilgisi uydurulmaz.
- Tracked source, configuration, reports ve build outputs üzerinde secret scan
  gerçek credential kullanmadan çalışır; synthetic canary negatif testte yakalanır.
- Secret veya local environment değeri artifact, support pack, log ve release-facing
  rapora girerse fail-closed sonuç üretilir.
- GitHub default branch Dependabot bulguları branch `npm audit` sonucundan ayrı
  tutulur; merge edilmeden kapatılmış sayılamaz.

## Red test kapsamı

- Lock hash değişimi, missing lock, resolver drift ve production/test dependency
  sınıflandırması.
- Synthetic API key, bearer token, private key, `.env` değeri ve credential-like
  path'in source/report/artifact scan tarafından yakalanması.
- Temiz repository'de false positive ayrımı; generated report ve archive çıktısında
  redaction/absence kontrolü.
- SBOM sıralaması, duplicate package, direct/transitive provenance ve tekrar üretim
  determinism'i.
- Lisans metadata'sı eksik/uyuşmaz olduğunda `UNKNOWN` veya owner review; otomatik
  legal approval yok.

## Uygulama sınırı

İlk adım mevcut lock dosyaları, package metadata, CI/release truth validator ve
rapor akışını okuyup red test matrisi yazmaktır. Reachable critical/high bulgu varsa
önce applicability ve düzeltme/owner kaydı yapılır. Branch'teki `npm audit` temizliği
GitHub default branch'teki beş açık Dependabot alert'ini kapatmış sayılmaz.

## Acceptance criteria

- [x] Locked backend/frontend dependency ve hash doğrulaması red→green geçer.
- [x] Deterministic SBOM/package inventory aynı girdide aynı snapshot'ı üretir.
- [x] Synthetic secret canary source/report/artifact sınırında yakalanır; temiz
  repository false-positive olmadan geçer.
- [x] Current branch vulnerability sonuçları ve GitHub default-branch alerts ayrı,
  kaynak/tarih/platform ile kaydedilir; ilgili critical/high bulgu varsa açık kalır.
- [ ] Ticari dağıtımdan önce root `LICENSE` ve third-party notices ürün sahibi/lisans
  incelemesiyle tamamlanır; lisans varsayımı veya otomatik legal approval yapılmaz.
- [x] 2026-09-08 owner disposition kaydedildi: ürün lisansı şimdilik seçilmedi; ticari
  paket hedefi nedeniyle notices/license inventory release öncesi zorunlu yeniden açma
  kapısıdır. Default-branch Dependabot merge'i bu geliştirme aşamasında yapılmayacaktır.
- [x] Focused → full suite/local CI ve docs evidence aynı source commit ile PASS;
  gerçek credential/user data kullanılmaz.

## Uygulama ve kanıt

- `scripts/supply_chain_audit.py` backend `requirements.lock` ve frontend
  `package-lock.json` için lock/hash/spec drift kontrolü yapar; CycloneDX 1.5
  inventory'yi deterministik üretir. Aynı lock girdileriyle 395 component snapshot'ı
  ve stable serial üretildi; package path, direct/transitive scope, resolved URL,
  integrity ve environment marker bilgisi korunur.
- Release source scan test/history fixture'larını ayrı policy ile dışarıda bırakır;
  runtime/config ve current release source'larını tarar. Private key, cloud key,
  bearer/JWT, GitHub/Stripe token, credential assignment ve tracked `.env` için
  secret değeri rapora yazmadan fail-closed fingerprint üretir. Generated DMG
  artifact scan PASS oldu. CLI vault audit artık executable içine sabit secret-like
  literal gömmek yerine runtime ephemeral canary kullanır.
- Red→green H05 focused suite: **6 passed**. H04 regression dahil focused set:
  **11 passed, 2 warnings**. Full backend: **675 passed, 2 warnings**. Frontend:
  **17 files / 67 tests passed**.
- Branch lock evidence: `uv pip check --python .venv/bin/python` PASS, `npm audit`
  **0 vulnerabilities**, Python 3.11 `pip-audit -r backend/requirements.lock`
  **80 dependencies / 0 known vulnerabilities**. `npm audit` and `pip-audit` use
  network advisory services; these are not offline evidence. `uv --offline` remains
  dependency-preparation evidence only.
- GitHub default branch evidence collected read-only on 2026-09-08: five open
  Dependabot alerts in `frontend/package-lock.json`: one critical (Vitest), one high
  (Vite), three moderate (Vite/esbuild). They remain open until an approved default
  branch action/merge; this branch was not used to close them.
- Mac local CI on source `c089cd2b48f0a849bd67c6da3e652d1ab65a1d37`: **MERGE READY**;
  report SHA-256 `4ca05d22d9fc459dac1de76ef0bcb889595372a5f3478824a718a940fa903c52`,
  local smoke report SHA-256
  `36c097f6a0b4918de820edb95e4cfd7f433d10e5013b1a625b55b19c0a659d63`, tracked
  source tree SHA-256 `ac09ccce98b8b2d79a3115c390066edb1cd7eed375da14901e8b847d0edcc74f`,
  Python `3.11.16`, Node `20.20.2`, npm `10.8.2`, uv `0.12.10`, PyInstaller
  `6.22.2`, macOS arm64, provenance **COMPLETE**. Executable SHA-256
  `a4ae72354581032dca2cef42f2a27bac7e6a204a1bdbdbee0b9b7b154149181c`, `.app` SHA-256
  `9f3357d433b82ea372c8d07867c09bf6dd7ff386485cfa71d9f661e5747ab06b`.
- H05 supply-chain report with DMG artifact scan: **OWNER_REVIEW_REQUIRED**, report
  SHA-256 `c180de2bffb92f279f1995c9fe4061a4e1c6b28628b428679b4aa01b5d74646f`, 395
  components, lock contract PASS, source/artifact secret scan PASS. Python audit
  report SHA-256 `fd8d91aa438cee28cfc25575394c9b3f35d4ae59511659c96cbe8cbf36234f31`;
  frontend audit report SHA-256
  `f3ff707e3ec193e8e0e5d725180374b4e93657ebea4f844a1f67a2acdb7cccd3`.
- Exact read-only DMG/WKWebView smoke on the same source: report SHA-256
  `c6d935c8fa6f5b4e816ab09e9d1c741eff66a0cd4ab941f66b3fdc44e5c53a2f`, DMG SHA-256
  `6d517542848a04d16e8e326432b79f683f4722c28413e62c34a494bfadfd7b2e`, mounted
  executable SHA-256 `a4ae72354581032dca2cef42f2a27bac7e6a204a1bdbdbee0b9b7b154149181c`;
  `wkwebview`, controller ready and clean detach PASS. The smoke attempted the
  configured public Binance stream; it is not offline runtime evidence.

## Ertelenen dağıtım kapısı

H05 makine doğrulaması PASS, ancak ticari dağıtım kararları ürün geliştirme aşaması için
**DEFERRED** olarak kaydedilmiştir. Bu karar makine kanıtını silmez ve production/release
izni vermez:

- `package.json` içindeki metadata root `LICENSE` metni değildir. Ürün lisansı
  seçilene kadar repo'ya varsayımsal MIT veya başka bir lisans metni eklenmeyecek.
- İleride ücretli/paketlenmiş dağıtım başlamadan önce 395 locked component için
  third-party notices, lisans kaynakları ve özellikle 100 unverified Python kaydı
  ürün sahibi/lisans incelemesinden geçmelidir.
- Default branch'teki beş Dependabot uyarısı bu branch'te `npm audit` PASS olduğu için
  kapanmış sayılamaz. Şimdilik merge yoktur; release öncesi remediation veya süreli,
  sahipli risk kabulü yeniden açılmalıdır.

H06 privacy/data lifecycle, bu ertelenmiş ticari kapıyı bypass etmeden yalnızca geliştirme
ve doğrulama kapsamıyla aktif edilebilir. H05, ilk ticari/release adayı hazırlanırken
yeniden açılmadan production-ready sayılamaz.

## Kesinlikle kapsam dışı

H06 privacy/data lifecycle ve keychain unavailable davranışı, H07 performance,
Developer ID/notarization/Gatekeeper, Windows/Linux final artifact, pilot/release,
new connector, live execution, AI order authority, full-account PnL/tax accounting,
funding/transfer schema ve gerçek kullanıcı secret'ları.

## Tarihsel kapanış/erteleme kararı

H04 `1cf486e` ile trust-boundary misuse testleri ve Mac local-CI kanıtı üzerinden
bounded olarak kapandı. H05 `c089cd2` ile machine-checkable supply-chain, SBOM ve
secret-boundary kanıtını tamamladı. Ürün lisansı/notices ve default-branch alert
disposition kararları 2026-09-08 tarihinde geliştirme dönemi için ertelendi; bu nedenle
bu belge `Deferred` olarak arşivlendi. Hiçbir UNKNOWN veya ertelenmiş release koşulu
PASS olarak yazılmamıştır.
