# P0-WP03 — Frontend Dev-Toolchain Güvenlik Güncellemesi

```yaml
work_package: P0-WP03
status: Verified
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
baseline_commit: c110b948e3004790e2deafe8b95f202b1c4b9234
owner: lead-agent
implementer: gpt-5.6-terra
verified_by: Axiom (GPT-5.6 SOL)
```

## Problem

`frontend/package-lock.json`, Vitest 2.1.9 üzerinden vulnerable nested Vite/esbuild zinciri taşır.
GitHub Dependabot 1 critical, 1 high ve 3 moderate alert; local `npm audit` toplam 5 vulnerability
raporlar. Root Vite 6.4.3 ve esbuild 0.25.12 patched olsa da test runner'ın nested bağımlılıkları
eski kalmıştır.

## Karar

Vitest `3.2.6` hedeflenir. Bu sürüm kritik GHSA-5xrq-8626-4rwp için ilk patched sürümdür,
Node 20 CI ile uyumludur ve Vite 6'yı peer/dependency aralığında destekler. Vitest 5.0.0,
Node 22.12+ gerektirdiği ve CI Node 20 olduğu için bu pakette kullanılmaz.

## Dosya kapsamı

- `frontend/package.json`
- `frontend/package-lock.json`
- Yalnız Vitest 3 uyumluluğu için zorunluysa frontend test/config dosyaları
- `docs/strategy/README.md` ve `PHASE-0-STATUS.md` lead agent tarafından kapanışta güncellenir

## Davranış ve acceptance criteria

- [x] Direct Vitest sürümü `^3.2.6`; resolved sürüm en az 3.2.6.
- [x] Lockfile'da vulnerable nested Vite `<=6.4.2` ve esbuild `<=0.24.2` kalmaz.
- [x] `npm --prefix frontend audit --json` toplam vulnerability = 0.
- [x] `npm test` tam suite geçer.
- [x] `npm run build` i18n + TypeScript + Vite geçer.
- [x] `npm --prefix frontend ci` temiz kurulum sözleşmesini doğrular; mevcut test/build sonrasında
  tekrar geçer.
- [x] Runtime production dependency veya uygulama davranışı değişmez.
- [x] Gereksiz başka major dependency upgrade'i yapılmaz.
- [x] `git diff --check` temizdir.

## Kapsam dışı

- Node 22/24 CI migration
- Vite 7/8, React veya UI dependency upgrade'i
- Test refactor'ı ve coverage sistemi
- Uygulama kodu değişikliği

## Teslim

Terra commit/push yapmaz. Exact install/audit/test/build komutlarını ve sonuçlarını, resolved
dependency tree'yi, değiştirdiği dosyaları ve bilinen riski raporlar.

## Doğrulama kaydı — 2026-09-05

- Resolved: Vitest 3.2.7, Vite/vite-node üzerinde Vite 6.4.3, esbuild 0.25.12.
- Eski nested Vite 5.4.21 ve esbuild 0.21.5 ağacı lockfile'dan kaldırıldı.
- `npm --prefix frontend ci`: başarılı, `0 vulnerabilities`.
- Lead bağımsız `npm audit`: info/low/moderate/high/critical toplamı `0`.
- Frontend: 6 dosyada `29 passed`.
- i18n 478 TR/EN/DE key, TypeScript ve Vite production build: başarılı.
