<!-- doc-role: current-work-package -->
# N02 — Exact macOS DMG ve WKWebView Smoke

```yaml
work_package: N02
version: 1.0.0
status: InProgress
date: 2026-09-08
baseline_commit: 05e826d
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: N01
```

## Amaç

DMG’nin içinde bulunan final `.app` executable’ını read-only mount üzerinden açıkça
seçip yalnızca o executable ile smoke çalıştırmak. DMG hash’i, mounted executable
hash’i, source provenance ve native WKWebView controller identity aynı raporda
bağlanacak; mount her durumda güvenli biçimde detach edilecek.

## Sözleşme

- DMG üretimi tamamlanmadan smoke başlamaz;
- `hdiutil attach -readonly` ile mount edilir, executable mount içinden seçilir;
- smoke `--artifact` ile DMG’yi hash’ler; standalone `.app` smoke DMG smoke yerine geçmez;
- `renderer_actual` tam olarak `wkwebview`, `renderer_controller_ready=true` olmalıdır;
- executable/artifact path ve SHA-256 raporda eşleşmezse fail-closed olur;
- release-facing provenance validator çalışır; mount detach failure PASS olamaz;
- kullanıcı verisi, credential, restore/migration veya canlı execution kullanılmaz.

## Acceptance criteria

- [ ] Mac DMG packaging preflight PASS olur.
- [ ] Read-only mounted DMG içinden explicit executable smoke PASS olur.
- [ ] WKWebView identity/controller readiness raporda doğrulanır.
- [ ] DMG ve mounted executable hash/provenance ilişkisi doğrulanır.
- [ ] Detach ve failure cleanup test edilir; mounted path yanlışsa PASS olmaz.
- [ ] Mac local CI ve exact DMG smoke kanıtı commit’e yazılır.

## Kapsam dışı

Developer ID signing/notarization/ticket, Gatekeeper approval, second host/profile,
H03 network-degraded runtime, Windows WebView2, Linux artifact, live order,
credentials, user data migration, funding/transfer schema ve release/tag işlemleri.

