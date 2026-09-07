# P2-WP19 — Binance Depth Attestation Review Gate

```yaml
document_id: P2-WP19
version: 1.0.1
status: Active
date: 2026-09-07
baseline: c09da6c
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP18 Binance Depth Attestation Key Registry
implementation_commits: 75b7579, 7bc8092
```

## Problem

P2-WP18, imzayı ve anahtar yaşam döngüsünü denetliyordu; ancak bir attestation
raporunun insan incelemesine alınması için gereken birleşik karar sınırı yoktu.
İmza geçerli olsa bile rapor fixture olabilir, anahtar revoked olabilir veya
attestation çok eski olabilir. Bu koşullar ayrıştırılmadan release veya ürün
gerçeği iddiası üretilemez.

## Karar

1. Review gate yalnızca şu koşulların tamamı geçerse `ELIGIBLE_FOR_REVIEW`
   üretir: arşiv kaydı strict doğrulanmış, verdict
   `VALID_TESTNET_OBSERVATION_UNVERIFIED`, attestation imzası geçerli, key
   registry durumu `ACTIVE_KEY` ve attestation timestamp'i freshness penceresi
   içindedir.
2. Varsayılan freshness penceresi 24 saattir. Saatin küçük ileri kayması 60
   saniyeye kadar warning olarak görünür; daha büyük gelecek timestamp'i
   reddedilir. Çoklu operator attestation varsa seçim açık `attestation_id` ile
   yapılmalıdır; belirsiz seçim fail-closed'dur.
3. Karar adı özellikle `ELIGIBLE_FOR_REVIEW`'dur. Gate hiçbir durumda
   `source_verified=true`, `execution_authority=true`, production data proof veya
   order submission authority üretmez.
4. CLI, aynı kararı JSON veya insan okunabilir çıktı olarak verir ve yalnızca
   eligible sonucu exit code `0` yapar. Fixture veya revoked key için exit code
   `1` kalır.

## Teknik teslimatlar

- `binance_depth_attestation_gate.py`: typed gate result, freshness ve key/status
  değerlendirmesi.
- `evaluate_binance_depth_attestation_gate.py`: local archive/registry üzerinde
  tek rapor için fail-closed CLI.
- Active, fixture, revoked, stale/future ve multiple-attestation regression'ları.

## Kullanım

```powershell
uv run python scripts/evaluate_binance_depth_attestation_gate.py `
  --archive-root "$PWD/.local-testnet-archive" `
  --registry "$PWD/.local-testnet-archive/keys.jsonl" `
  --report-id <report-id> `
  --max-age-seconds 86400 `
  --json
```

Birden fazla attestation varsa `--attestation-id <id>` zorunludur. Başarılı
çıktı review eligibility'dir; otomatik execution veya source truth değildir.

## Kabul kriterleri

- [x] Active registered key + valid signature + testnet verdict + freshness gate.
- [x] Fixture, revoked, stale/future ve ambiguous attestation fail-closed.
- [x] CLI JSON/human output ve non-zero rejection exit code.
- [x] `source_verified` ve `execution_authority` false kalıyor.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `525 passed, 1 skipped`.
- [x] Gerçek operatör testnet runbook'unda gate çıktısı imzalı review kaydına
      bağlandı: gate `ELIGIBLE_FOR_REVIEW`, review `da5d4a9b329ecbc9`.
- [ ] Remote CI doğrulaması (şu an bilinçli olarak disabled).

## Kapsam dışı ve sonraki risk

Gate, gerçek Binance network doğruluğunu, market-data completeness'i, broker
execution'ı veya insan review kararını kanıtlamaz. HSM/KMS, distributed policy,
otomatik release promotion, source verification terfisi ve AI kararı kapsam
dışıdır. Sonraki sınır, gerçek testnet operator runbook'unda bu sonucu insan
imzalı review kaydına bağlamak ve key rotation/retention SLA'sını ölçmektir.

## Operasyon kanıtı — 2026-09-07

Gate çıktısı `50925819189b9d60` attestation'ı, aktif key registry ve
`VALID_TESTNET_OBSERVATION_UNVERIFIED` verdict'i ile değerlendirildi. Sonuç
`ELIGIBLE_FOR_REVIEW` olsa da source verification ve emir yetkisi false kaldı.

## Değişiklik geçmişi

### 1.0.1 — 2026-09-07

- Gerçek public testnet operator gate ve imzalı review bağlantısı belgelendi.
