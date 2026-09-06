# P2-WP17 — Binance Depth Soak Operator Attestation

```yaml
document_id: P2-WP17
version: 1.0.0
status: Active
date: 2026-09-07
baseline: 3d3ff67
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP16 Binance Depth Soak Report Hash Archive
implementation_commits: 1dc6be2
```

## Problem

P2-WP16 raporu hash'leyip saklıyor; ancak hangi local operator/key sahibinin
raporu arşivlediği cryptographic olarak bağlanmıyordu. Hash retention ile
operator attestation aynı şey değildir ve bu ayrım açık tutulmalıdır.

## Karar

1. Ed25519 attestation yalnızca archived `report_sha256`, report metadata,
   operator label ve UTC attestation timestamp'ını imzalar. Raporun içeriği
   archive tarafından zaten hash'lenmiş olmalıdır.
2. `source_verified` ve `execution_authority` hem signed payload'da hem store
   validation'ında `false` olmak zorundadır. Attestation hiçbir şekilde live
   market truth veya emir yetkisi vermez.
3. Key bundle local JSON'da raw Ed25519 bytes'ın base64 formudur; key generator
   mevcut dosyayı overwrite etmez. Private key log'lanmaz ve cloud'a çıkmaz.
4. Attestation sidecar manifest'i archive root altında fsync-backed append-only
   tutulur. Duplicate attestation idempotent; dosya/manifest/signature tamper'ı
   strict reopen'da fail-closed olur.

## Teknik teslimatlar

- Ed25519 key bundle generator.
- Archive record metadata attestation/signature verifier.
- Append-only `attestations.jsonl` ve sidecar JSON store.
- Attestation CLI ve key generator CLI.
- Signature, truth tamper, reopen, multi-operator ve CLI regression testleri.

## Kullanım

Key oluşturma (private key'i koru):

```powershell
uv run python scripts/generate_binance_depth_attestation_key.py `
  --output "$PWD/.local-operator-key.json"
```

Attestation ekleme:

```powershell
uv run python scripts/attest_binance_depth_soak_report.py `
  --archive-root "$PWD/.local-testnet-archive" `
  --report-id <report-id> `
  --key-bundle "$PWD/.local-operator-key.json" `
  --operator-label "operator-a"
```

## Acceptance criteria

- [x] Archived report hash/metadata'sı Ed25519 ile doğrulanıyor.
- [x] Truth flag veya signature tamper'ı reddediliyor.
- [x] Attestation sidecar reopen/recovery geçiyor.
- [x] Aynı attestation idempotent, farklı operator attestations ayrı kayıt.
- [x] Key ve attestation CLI'ları explicit ve overwrite-safe.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `492 passed, 1 skipped`.
- [ ] Gerçek testnet raporunun operator attestation'ı.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Private key escrow, HSM/KMS/cloud signing veya account recovery.
- Attestation ile `source_verified=true`, execution authority veya release
  approval yükseltmesi.
- Multi-user authorization policy, revocation registry veya team sharing.

## Risk ve sonraki sınır

Attestation key sahibinin raporu imzaladığını kanıtlar; operator'un gerçekten
Binance testnet'e bağlandığını veya market-data completeness'i kanıtlamaz. Sonraki
kapı key rotation/revocation ve retention policy olabilir; bunlar oluşmadan
attestation product release approval sayılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Hash-archive report metadata'sı için local Ed25519 operator attestation ve
  strict sidecar store eklendi.
