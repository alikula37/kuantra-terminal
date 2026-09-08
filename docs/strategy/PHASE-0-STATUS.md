<!-- doc-role: historical-reference -->
> Historical Phase 0 evidence, retained at this path for audit tooling. Not current release status.
> See [current status](STATUS.md).

# Faz 0 — Truth & Safety Durum Panosu

```yaml
document_id: KPS-P0-STATUS
status: Verified
last_updated: 2026-09-06
branch: codex/p1-wp01-evidence-ledger
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
| P0-WP04 CI truth/release gates | Verified | `a920319` + `04f168c` | 3-OS PR/push CI green; local backend 260 passed, 1 skipped |
| P0-WP05 Python universal lock | Verified | `1326e5e` | 3-OS CI green; backend 263 passed, 1 skipped; 90 packages / 2,408 hashes |
| P0-WP06A Replay/MAE-MFE evidence truth | Verified | `d517c34` | 3-OS CI `34018288308` green; local backend 328 passed, 1 skipped; frontend 42 passed; build/audit pass |
| P0-WP06B Order-flow/L2/FIX truth boundary | Verified | `1cfd778` + `564beed` | Isolated local backend 339 passed, 1 skipped; focused truth suite 30 passed; frontend 45 passed; i18n 480/480; push `34022495908` + PR `34022498837` green on 3 OS |
| P0-WP07 Credential/OS keychain truth boundary | Verified | `a09ad80` | Isolated local backend 339 passed, 1 skipped; frontend 45 passed; i18n 480/480; build/audit pass; push `34021489108` + PR `34021491017` green on 3 OS |
| P0-WP08 Experimental capability containment | Verified | `d0eda56` + `f8653e2` | Isolated backend 343 passed, 1 skipped; frontend 49 passed; i18n 480/480; push `34025225053` + PR `34025227211` green on 3 OS |
| P0-WP09 Release truth matrix and current claims | Verified | `7217610` | Local backend 347 passed/1 skipped; frontend 49 passed; i18n 480/480; push `34027220927` + PR `34027222829` green on 3 OS |
| P0-WP10 Three-OS final artifact smoke / Phase 0 exit audit | Verified | `df46f27` | Candidate run `34035766242`: macOS/Ubuntu/Windows final artifacts ve publish audit success; release publication separately gated |

## Aktif güvenlik durumu

2026-09-05 GitHub Dependabot ve local `npm audit` aynı beş bulguyu raporladı. P0-WP03 ile
Vitest 3.2.7, Vite 6.4.3 ve esbuild 0.25.12 çözümlemesine geçildi; local audit sonucu sıfırdır.
CI Node 20 kullandığı için Node 22.12+ isteyen Vitest 5 seçilmedi. P0-WP04, yeni bir moderate
veya daha yüksek npm bulgusunun CI ve release paketlemesini durdurmasını zorunlu kılar.

## Context devam protokolü

1. Yeni oturum/compaction sonrası önce bu dosya, `docs/archive/strategy/CATALOG-2026-09-08.md` ve son aktif WP okunur.
2. `git status --short`, `git log --oneline -5` ve draft PR durumu doğrulanır.
3. Working tree temiz değilse değişiklik sahibi ve paket sınırı belirlenmeden yeni iş başlamaz.
4. Her paket ayrı commit olur; draft PR Phase 0 tamamlanana kadar açık kalır.
5. Faz çıkışı yalnız KPS-001 başarı metrikleri ve tüm Phase 0 gate'leri ile verilir.

## Sıradaki sıra

1. P1-WP01 — [Canonical Evidence Ledger Foundation](../archive/strategy/work-packages/P1-WP01-canonical-evidence-ledger.md) Active; implementation commits `43641e1`/`25e4640`/`db80a77`, last green CI `34038244922`; latest CI attempt billing nedeniyle başlayamadı, pilot metrikleri bekleniyor.
2. Release publication — `publish=true` adayını çalıştırmak ayrı bir ürün sahibi release onayı ister; bu karar canlı execution yetkisi vermez.

## Phase 0 final kanıtı

- Release candidate: [34035766242](https://github.com/alikula37/kuantra-terminal/actions/runs/34035766242)
- Package jobs: macOS `101493427867`, Ubuntu `101493427995`, Windows `101493428000` — success.
- Publish audit: `101495589738` — success; verdict `READY_FOR_HUMAN_RELEASE_APPROVAL`.
- Normal push CI: [34035432817](https://github.com/alikula37/kuantra-terminal/actions/runs/34035432817) — üç OS success.
- `publish=false`: yeni GitHub Release/tag yayımlanmadı; mevcut tarihsel `v1.4.0` release’i değiştirilmedi.
