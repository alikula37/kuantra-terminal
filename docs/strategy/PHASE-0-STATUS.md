# Faz 0 — Truth & Safety Durum Panosu

```yaml
document_id: KPS-P0-STATUS
status: Active
last_updated: 2026-09-05
branch: codex/p0-truth-safety
pull_request: https://github.com/alikula37/kuantra-terminal/pull/3
strategy: KPS-001@1.0.0
```

Bu belge chat geçmişinden bağımsız devam noktasıdır. Her work package sonunda test kanıtı ve
commit SHA buraya yazılır. Ayrıntılı acceptance kaydı ilgili work-package belgesindedir.

## Durum

| Paket | Durum | Commit | Son doğrulama |
|---|---|---|---|
| P0-WP00 Strateji/ADR tabanı | Verified | `b88767a` | Doküman kataloğu ve immutable ADR düzeni |
| P0-WP01 Execution/risk contract | Verified | `ab5a2cf` | Backend 243 passed, 1 skipped |
| P0-WP02 Market-data truth contract | Verified | `c110b94` | Backend 257 passed, 1 skipped; frontend 29 passed; build pass |
| P0-WP03 Frontend dev-toolchain security | Verified | `c72d599` | Audit 0; frontend 29 passed; build pass |

## Aktif güvenlik durumu

2026-09-05 GitHub Dependabot ve local `npm audit` aynı beş bulguyu raporladı. Root Vite 6.4.3
ve esbuild 0.25.12 patched durumdadır; kalan vulnerable transitive zincir Vitest 2.1.9'un nested
Vite/esbuild bağımlılıklarıdır. CI Node 20 kullanır. Bu nedenle en küçük uyumlu güvenli hedef
Vitest 3.2.6'dır; Vitest 5 Node 22.12+ istediği için seçilmemiştir.

## Context devam protokolü

1. Yeni oturum/compaction sonrası önce bu dosya, `docs/strategy/README.md` ve son aktif WP okunur.
2. `git status --short`, `git log --oneline -5` ve draft PR durumu doğrulanır.
3. Working tree temiz değilse değişiklik sahibi ve paket sınırı belirlenmeden yeni iş başlamaz.
4. Her paket ayrı commit olur; draft PR Phase 0 tamamlanana kadar açık kalır.
5. Faz çıkışı yalnız KPS-001 başarı metrikleri ve tüm Phase 0 gate'leri ile verilir.

## Sıradaki sıra

1. P0-WP03 — Vitest/nested Vite güvenlik zinciri.
2. P0-WP04 — Replay/MAE-MFE/order-flow synthetic evidence temizliği.
3. P0-WP05 — Credentials, gateway secret ve OS keychain geçiş planı/uygulaması.
4. P0-WP06 — Experimental yüzeylerin default UI/API'dan kaldırılması.
5. P0-WP07 — README/release claim ve CI truth matrix.
6. P0-WP08 — Üç platform packaging/smoke ve Faz 0 exit audit.
