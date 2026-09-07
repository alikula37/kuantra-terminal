# P2-WP20 — Binance Depth Operator Review ve Key Policy

```yaml
document_id: P2-WP20
version: 1.0.2
status: Active
date: 2026-09-07
baseline: be0d49d
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP19 Binance Depth Attestation Review Gate
implementation_commits: 0fcd1cc
```

## Problem

P2-WP19 yalnızca bir gözlemin insan incelemesine uygun olup olmadığını
hesaplıyordu. Bu kararın hangi operatör tarafından, hangi key policy snapshot'ı
ve hangi retention taahhüdüyle kabul edildiği kalıcı bir kayda bağlı değildi.
Registry'de iki aktif key'in üst üste kalması veya yaşlanmış key ile review
üretilmesi de tek bir release sınırı olarak kontrol edilmiyordu.

## Kararlar

1. Review yalnızca `ELIGIBLE_FOR_REVIEW` gate sonucu için üretilebilir. Kayıt,
   gate snapshot'ını ve SHA-256 hash'ini, key policy snapshot'ını ve hash'ini,
   reviewer public key'ini, `reviewed_at` ve `retention_until` değerlerini
   Ed25519 ile imzalar.
2. Varsayılan policy tek aktif key (`max_active_keys=1`), aktif key yaş sınırı
   90 gün ve revoke kayıtları için 365 günlük minimum retention window'dur.
   Overlap, yaş aşımı, gelecekteki timestamp veya aktif key yokluğu fail-closed
   olur. Registry append-only olduğu için mevcut dosyanın retention'ı kanıtlanır;
   gelecekteki backup/replication SLA'sı otomatik garanti edilmez.
3. CLI, review key'inin registry'de aktif olmasını ve reviewer label ile
   eşleşmesini zorunlu kılar. `retention_until`, varsayılan 365 günlük review
   retention minimumundan kısa olamaz.
4. Review kaydı hiçbir koşulda `source_verified=true`, production market truth,
   broker execution veya order submission authority vermez.

## Teknik teslimatlar

- `binance_depth_key_policy.py`: key rotation/age/retention policy result.
- `binance_depth_review_record.py`: signed gate + policy snapshot ve strict
  append-only `reviews.jsonl` store.
- `record_binance_depth_review.py`: active key, gate ve retention kapılarını
  birlikte çalıştıran CLI.
- Tamper, overlap, stale key, ineligible gate, retention ve CLI regression'ları.

## Kullanım

```powershell
uv run python scripts/record_binance_depth_review.py `
  --archive-root "$PWD/.local-testnet-archive" `
  --registry "$PWD/.local-testnet-archive/keys.jsonl" `
  --report-id <report-id> `
  --key-bundle "$PWD/.local-operator-key.json" `
  --reviewer-label "operator-a" `
  --retention-until "2027-09-07T12:00:00Z" `
  --json
```

Başarılı kayıt yalnızca operator review evidence üretir. Gerçek Binance testnet
bağlantısı, ağ doğruluğu ve insanın gerçekten işlemi izlediği bu CLI tarafından
kanıtlanmaz.

## Kabul kriterleri

- [x] Gate + key policy snapshot hash'leri review imzasına bağlandı.
- [x] Tek aktif key, aktif key age ve revoke-retention policy sonucu üretildi.
- [x] Review store append-only, fsync-backed ve strict tamper recovery'li.
- [x] Ineligible gate, overlap, stale key ve revoked reviewer reddediliyor.
- [x] Review kaydı truth/execution flag'lerini false tutuyor.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `530 passed, 1 skipped`.
- [x] Gerçek testnet operator run'ı review kaydına bağlandı:
  review `da5d4a9b329ecbc9`, retention `2027-09-07T14:51:00Z`.
- [x] V2 120 saniyelik operator run'ı review kaydına bağlandı:
  review `da47fc62c67c0bf4`, retention `2027-09-08T16:00:00Z`.
- [ ] Remote CI doğrulaması (şu an bilinçli olarak disabled).

## Kapsam dışı ve sonraki risk

HSM/KMS, distributed key custody, otomatik key rotation, backup replication,
cloud retention SLA'sı, canlı broker execution, source verification terfisi ve
AI review kararı kapsam dışıdır. Sonraki sınır, gerçek operatörün testnet run'ını
bu kayıtla ilişkilendiren manuel runbook ve retention backup drill'idir.

## Operasyon kanıtı — 2026-09-07

Review kaydı gate snapshot hash'ini, key policy snapshot hash'ini ve bir yıllık
retention taahhüdünü imzaladı. `source_verified=false` ve
`execution_authority=false` korunmuştur.
V2 review kaydı da aynı truth/execution sınırlarını korudu.

## Değişiklik geçmişi

### 1.0.2 — 2026-09-07

- V2 120 saniyelik valid testnet run için signed review/retention kanıtı eklendi.

### 1.0.1 — 2026-09-07

- Geçerli public testnet operator run'ının imzalı review ve retention kaydı
  belgelendi.
