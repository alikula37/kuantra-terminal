# P2-WP21 — Binance Depth Evidence Bundle ve Restore Drill

```yaml
document_id: P2-WP21
version: 1.0.0
status: Active
date: 2026-09-07
baseline: 94bd412
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP20 Binance Depth Operator Review ve Key Policy
implementation_commits: pending
```

## Problem

P2-WP20 review ve key policy kanıtını local dosyalara bağlıyordu; ancak bu
kanıtın başka bir makineye taşınması, bütünlüğünün doğrulanması ve restore
sonrası aynı strict recovery'den geçmesi için standart bundle sözleşmesi yoktu.
Private key materyalinin backup'a yanlışlıkla girmesi ayrıca kritik bir riskti.

## Kararlar

1. Bundle, archive root içindeki report/attestation/review manifest ve dosyalarını
   ve açıkça verilen public-key registry JSONL'ini deterministic ZIP içine alır.
   Her dosya için SHA-256, byte size ve relative POSIX path manifest'te tutulur;
   `bundle_id` bu içeriğin canonical hash'idir.
2. `private_key_b64`, PEM/OpenSSH private key marker'ı veya symlink kabul edilmez.
   Bundle manifest'i `contains_private_keys=false`, `source_verified=false` ve
   `execution_authority=false` değerlerini zorunlu tutar. Private key bundle'a
   hiç yazılmaz; operator key ayrı ve offline korunur.
3. Restore mevcut dolu hedefi overwrite etmez. Yeni/boş hedefe çıkardıktan sonra
   archive, attestation store, review store ve registry strict recovery ile
   yeniden açılır. Başarısız restore hedefi otomatik silinmez; forensics için
   bırakılır.
4. Bundle doğrulaması retention/backup bütünlüğünü kanıtlar; gerçek testnet
   network truth, market-data completeness veya execution authority üretmez.

## Teknik teslimatlar

- `binance_depth_evidence_bundle.py`: deterministic create/verify/restore API,
  manifest ve strict recovery.
- `bundle_binance_depth_evidence.py`: `create`, `verify`, `restore` CLI'ı.
- Private marker, path traversal, payload tamper ve restore regression'ları.

## Kullanım

```powershell
uv run python scripts/bundle_binance_depth_evidence.py create `
  --archive-root "$PWD/.local-testnet-archive" `
  --registry "$PWD/.local-testnet-archive/registry/keys.jsonl" `
  --output "$PWD/.local-testnet-archive/evidence.zip" `
  --created-at "2026-09-07T12:00:00Z" `
  --json

uv run python scripts/bundle_binance_depth_evidence.py verify `
  --bundle "$PWD/.local-testnet-archive/evidence.zip" `
  --json

uv run python scripts/bundle_binance_depth_evidence.py restore `
  --bundle "$PWD/.local-testnet-archive/evidence.zip" `
  --target-root "$PWD/.local-testnet-archive-restore" `
  --json
```

## Kabul kriterleri

- [x] Deterministic ZIP ve canonical bundle manifest.
- [x] Per-file SHA-256/size/path doğrulaması.
- [x] Private key marker ve path traversal fail-closed.
- [x] Archive, attestation, review ve registry strict restore recovery.
- [x] Dolu hedefin overwrite edilmemesi.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `512 passed, 1 skipped`.
- [ ] Gerçek operator testnet bundle'ının farklı makinede restore edilmesi.
- [ ] Remote CI doğrulaması (şu an bilinçli olarak disabled).

## Kapsam dışı ve sonraki risk

Cloud backup, KMS/HSM, encrypted-at-rest transport, remote object storage,
automatic retention deletion ve live broker execution kapsam dışıdır. Sonraki
sınır, gerçek testnet operator run'ının bu bundle ile iki ayrı makinede restore
drill'ine bağlanmasıdır.
