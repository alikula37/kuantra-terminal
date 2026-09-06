# P2-WP18 — Binance Depth Attestation Key Registry

```yaml
document_id: P2-WP18
version: 1.0.0
status: Active
date: 2026-09-07
baseline: a8ec989
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP17 Binance Depth Soak Operator Attestation
implementation_commits: pending
```

## Problem

P2-WP17, arşivlenmiş depth soak raporlarına Ed25519 imzası ekliyordu; ancak
yerel operasyon anahtarının kayıt, operatör etiketi, iptal ve denetim yaşam
döngüsü yoktu. Bu durum bir anahtarın artık güvenilmemesi ile geçmişteki
imzanın kriptografik olarak geçerli kalması arasındaki ayrımı görünür kılmıyordu.

## Kararlar

1. Registry, tek yazarlı append-only JSONL event log'dur. `REGISTER` ve
   `REVOKE` olayları fsync ile kalıcılaştırılır; strict recovery şema, event id,
   key id, public key ve metadata tutarlılığını fail-closed doğrular.
2. `key_id`, ham Ed25519 public key'in SHA-256 özetinin ilk 16 hex karakteridir.
   Registry private key saklamaz. Aynı key/etiket ile tekrar kayıt idempotent,
   farklı metadata ile kayıt conflict'tir; revoked key yeniden etkinleştirilemez.
3. Revoke işlemi geçmiş imzanın `signature_valid` sonucunu değiştirmez. Audit
   sonucu `REVOKED_KEY` olur; operasyon isterse CLI'da `--fail-on-revoked` ile
   kapı koyabilir.
4. Operator etiketi ve revoke nedeni bounded printable metin, timestamp ise
   timezone içeren ISO-8601 metindir. Bu kayıtlar kimlik kanıtı veya network
   truth kanıtı değildir; yalnızca yerel anahtar yaşam döngüsü kanıtıdır.

## Teslimatlar

- `BinanceDepthAttestationKeyRegistry`: register, revoke, audit ve strict
  recovery API'si.
- `manage_binance_depth_keys.py`: `register`, `revoke` ve `audit` komutları;
  `--require-registered`, `--fail-on-revoked` ve JSON çıktı kapıları.
- Metadata conflict, registry tamper, unknown key ve historical signature
  preservation testleri.

## Kullanım

```powershell
uv run python scripts/manage_binance_depth_keys.py register `
  --registry "$PWD/.local-testnet-archive/keys.jsonl" `
  --key-bundle "$PWD/.local-operator-key.json" `
  --operator-label "operator-a"

uv run python scripts/manage_binance_depth_keys.py revoke `
  --registry "$PWD/.local-testnet-archive/keys.jsonl" `
  --key-id <key-id> `
  --reason "rotation"

uv run python scripts/manage_binance_depth_keys.py audit `
  --registry "$PWD/.local-testnet-archive/keys.jsonl" `
  --archive-root "$PWD/.local-testnet-archive" `
  --require-registered `
  --fail-on-revoked `
  --json
```

`--fail-on-revoked`, historical olarak geçerli imzayı silmez; yalnızca mevcut
operasyon politikasında revoked key ile rapor kabulünü başarısız kılar.

## Kabul kriterleri

- [x] Register/revoke event log ve strict restart recovery.
- [x] Unknown key, metadata conflict ve tamper fail-closed.
- [x] Revoked status imza geçerliliğinden ayrıştırılıyor.
- [x] CLI register/revoke/audit kapıları.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `497 passed, 1 skipped`.
- [ ] Gerçek operatör tarafından testnet registry/attestation runbook'u.
- [ ] Remote CI doğrulaması (şu an bilinçli olarak disabled).

## Kapsam dışı ve sonraki risk

HSM/KMS/cloud key custody, anahtar kurtarma, dağıtık registry consensus,
otomatik key rotation/retention politikası, `source_verified` veya execution
authority terfisi bu paketin kapsamı dışındadır. Sonraki güvenlik sınırı, gerçek
operatör testnet çalışması ile key rotation/retention runbook'unun kanıtlanmasıdır.
