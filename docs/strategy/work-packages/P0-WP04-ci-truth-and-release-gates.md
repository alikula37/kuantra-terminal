# P0-WP04 — CI Truth ve Release Güvenlik Kapıları

```yaml
work_package: P0-WP04
status: Remote validation pending
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
baseline_commit: 0b757b96df7adac6407e19fd4eea160fae6fdbee
owner: Axiom (GPT-5.6 SOL)
implementer: gpt-5.6-terra
```

## Problem

CI tam backend/frontend testlerini çalıştırsa da test verisini açıkça izole etmez, dependency
audit'ini gate yapmaz ve Python compile gate'i yoktur. Release workflow ise tag'i üç platformda
paketlemeden önce backend veya frontend testlerini çalıştırmaz; yalnız build/smoke yapar. Böylece
bir test regresyonu veya bilinen vulnerable dependency tag release'ine girebilir.

İlk PR run'ı üç platformda testin framework-internal `_IncludedRouter.path` varsayımı nedeniyle
başarısız olmuştur. Test portability patch'i `a199fb1` ile hazırlanmıştır; bu paketin remote CI
kanıtı yeni run üzerinden alınacaktır.

İkinci remote run, taze kurulumun FastAPI 0.141.1 çözümlemesi nedeniyle route ağacını lazy
`_IncludedRouter` düğümlerinde tuttuğunu gösterdi. P0-WP01 testi efektif prefix ağacını dolaşacak
şekilde taşındı. Bu olay, yalnız alt sınır kullanan Python bağımlılıklarının ayrı bir
reproducibility paketiyle kilitlenmesi gerektiğini de doğruladı; dependency lock bu paketin
kapsamına sonradan gizlice eklenmeyecektir.

## İstenen sonuç

Pull request ve tag release yolları aynı minimum truth/safety contract'ını uygular: temiz data
dizini, Python compile, tam backend suite, deterministic frontend install, dependency audit,
frontend tests ve production build. Bu kapılardan biri geçmezse paketleme/release başlamaz.

## Dosya kapsamı

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- Yeni bir `backend/tests/test_ci_workflow_contract.py`
- Mevcut `backend/tests/test_ci_cd_workflows.py` sözleşme testinin yeni gate adlarına taşınması
- Uygulama kodu değiştirilemez.

## Davranış sözleşmesi

1. CI push filtresi `main`, `codex/**` ve mevcut `feat/**` branch'lerini kapsar; PR→main kalır.
2. Her matrix job'ı, step bağlamında kullanılabilen `${{ runner.temp }}` değerinden
   `GITHUB_ENV` aracılığıyla `KUANTRA_DATA_DIR` üretir. `runner` bağlamı job-level `env`
   değerlendirmesinde kullanılamaz.
3. CI sırası Python dependencies → `compileall` → full backend tests → `npm ci` →
   `npm audit --audit-level=moderate` → frontend tests → frontend build → desktop package/smoke.
4. Release job'ı da izole data dir, compileall, full backend tests, npm audit, frontend tests ve
   build kapılarını packaging'den önce çalıştırır.
5. Audit moderate/high/critical bulguda fail eder. `--force` veya audit ignore kullanılmaz.
6. Workflow contract testi iki YAML dosyasındaki zorunlu gate'leri ve sıralarını doğrular;
   implementation whitespace'ına aşırı bağlı olmaz.
7. Release publish job'ı yalnız bütün matrix package job'ları geçince çalışmaya devam eder.

## Acceptance criteria

- [x] CI ve release workflow'larında izole `KUANTRA_DATA_DIR`.
- [x] İki workflow'da compile, backend test, npm ci/audit/test/build gate'leri.
- [x] CI `codex/**` push trigger'ı.
- [x] Workflow contract regression testi: 5 passed.
- [x] Full backend suite: 260 passed, 1 skipped.
- [x] Frontend: audit 0; 29 test passed; production build başarılı.
- [x] YAML parse edilir; GitHub expression'ları bozulmaz.
- [x] `git diff --check` hata vermeden geçer (Windows line-ending bilgilendirmesi hariç).
- [ ] Push sonrası Windows/macOS/Ubuntu PR checks yeşildir.

## Kapsam dışı

- Release signing/notarization ve deployment
- Python dependency lock çözümü
- Coverage yüzdesi veya synthetic HFT benchmark yeniden tasarımı
- GitHub branch protection ayarı

## Teslim

Terra commit/push yapmaz. Workflow diff'i, local contract/backend/frontend sonuçları ve bilinen
platform risklerini Axiom'a raporlar. Remote PR checks Axiom tarafından doğrulanır.
