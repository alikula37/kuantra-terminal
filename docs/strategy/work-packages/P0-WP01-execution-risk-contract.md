# P0-WP01 — Tekil Paper Execution Rotası ve Risk/Compliance Sözleşmesi

```yaml
work_package: P0-WP01
status: Verified
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
adr: ADR-0003
baseline_commit: b88767a11993de0b53b8db5430f23d419e3d02e0
owner: lead-agent
implementer: gpt-5.6-terra
verified_by: lead-agent
```

## Problem ve risk

`POST /api/v1/execution/order` iki farklı handler/schema ile kayıtlıdır. İlk handler CCXT
engine'e, ikinci handler ise sentetik/experimental order router'a gider; route sırası hangi
uygulamanın çalıştığını belirler. Aynı public yüzey `LIVE` modunu kabul etmektedir ancak lifecycle,
idempotency ve reconciliation kapıları tamamlanmamıştır.

Risk katmanı compliance engine'in döndürmediği `status`, `daily_loss_pct` ve
`max_daily_loss_limit_pct` alanlarını okumaktadır. Bu nedenle prop breach ve yakın-limit kontrolü
sessizce atlanabilir. `sqlite_driver.get_setting` çağrılarından bazıları desteklenmeyen `default`
argümanı verip exception fallback'ine düşmektedir.

## İstenen sonuç

Public execution rotası tek olmalı ve Faz 4'e kadar yalnız PAPER order kabul etmelidir. LIVE
isteği hiçbir adapter/order router çağrılmadan açık, kararlı bir hata koduyla reddedilmelidir.
Compliance breach ve yakın günlük limit durumları gerçek, belgeli response alanları üzerinden
deterministic ve fail-closed biçimde order'ı reddetmelidir. Setting default davranışı TypeError'a
dayanmamalıdır.

## Dosya kapsamı

Değiştirilebilir:

- `backend/app/api/endpoints.py`
- `backend/app/quant/risk_guard.py`
- `backend/app/services/compliance_engine.py`
- `backend/app/services/execution/risk_interceptor.py`
- `backend/app/services/p2p/copy_engine.py` — yalnız hatalı `get_setting` çağrısı
- İlgili `backend/tests/` testleri

Kapsam dışı:

- `ccxt_engine.py` order/fill lifecycle refactor'ı
- Credential/keychain değişikliği
- UI redesign
- Fake data temizliğinin geri kalanı
- FIX, order-book, AI veya biometrics refactor'ı
- Evidence Ledger

## Davranış sözleşmesi

1. Uygulama route tablosunda `POST /api/v1/execution/order` tam olarak bir kez bulunur.
2. Route mevcut `OrderDispatchSchema` paper request sözleşmesini korur.
3. `mode` case-insensitive normalize edilir; yalnız `PAPER` kabul edilir.
4. `LIVE` ve bilinmeyen modlar adapter çağrılmadan HTTP 403 döner. Response detail içinde
   kararlı `code: LIVE_EXECUTION_DISABLED` veya `UNSUPPORTED_EXECUTION_MODE` bulunur.
5. Compliance response canonical alanı `overall_status` olur. Breach her iki risk yolunda da
   reddedilir.
6. Near-drawdown hesabı response'ta gerçekten bulunan, anlamı açık numeric alanlara dayanır;
   hayalî key/default ile bypass olmaz.
7. Configured `user_initial_balance` account size'a uygulanır; değer yok/bozuksa açık default
   kullanılır. Desteklenmeyen method argümanı nedeniyle exception fallback'i kullanılmaz.
8. Bu pakette biometrics/swarm kaldırılmaz; sadece compliance key bug'ı düzeltilir.

## Acceptance criteria

- [x] Duplicate public route regression testi.
- [x] LIVE request'in CCXT/order router çağırmadan 403 verdiğini doğrulayan API testi.
- [x] PAPER API davranışının çalışmaya devam ettiğini doğrulayan test.
- [x] `overall_status=BREACHED` için `RiskGuard` reject testi.
- [x] `overall_status=BREACHED` için `RiskGuardrailInterceptor` reject testi; önceki kapılar mocklandı.
- [x] Günlük limite 0.5 yüzde puandan yakın senaryoda deterministic reject testi.
- [x] Configured account size ve missing/invalid fallback testleri.
- [x] İlgili focused suite ve tam backend suite geçer.
- [x] `git diff --check` temizdir.

## Teslim raporu

Terra değişen davranışı, test komutlarını/sonuçlarını, acceptance eşlemesini, bilinen riski ve
`git status --short` çıktısını lead agent'a iletir. Commit veya push yapmaz.

## Doğrulama kaydı — 2026-09-05

- Terra focused suite: `27 passed`.
- Lead-agent temiz ve izole `KUANTRA_DATA_DIR` ile tam backend suite: `243 passed, 1 skipped`
  (`35.83s`). Skip, desteklenmeyen platformdaki GUI smoke testidir.
- İlgili Python modülleri compile: exit `0`.
- `git diff --check`: exit `0`; Windows checkout için yalnız line-ending uyarıları.
- Public `POST /api/v1/execution/order` tekildir ve PAPER-only'dir.
- LIVE/unknown modları execution engine çağrılmadan kararlı 403 kodlarıyla reddedilir.
