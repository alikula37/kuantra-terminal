# P2-WP16 — Binance Depth Soak Report Hash Archive

```yaml
document_id: P2-WP16
version: 1.0.0
status: Active
date: 2026-09-07
baseline: 18a1c68
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P2-WP15 Binance Depth Soak Report Verification Gate
implementation_commits: 196fba4
```

## Problem

P2-WP15 raporu doğruluyordu; fakat doğrulanan dosyanın local-first retention'ı,
sonradan değiştirilmediğinin hash kanıtı ve process reopen recovery'si yoktu.
Dosya kopyalamak tek başına audit/evidence pack için yeterli değildir.

## Karar

1. `BinanceDepthReportArchive` yalnızca P2-WP15 verifier'dan geçen raporu kabul
   eder. Rapor canonical JSON + newline olarak hash'lenir; dosya adı SHA-256 ile
   adreslenir.
2. Rapor JSON'u fsync ile yazılır; manifest JSONL append-only ve fsync-backed'dir.
   Aynı hash tekrar arşivlenirse idempotent mevcut kayıt döner; farklı byte'lar
   aynı hash/path iddiasıyla gelirse fail-closed olur.
3. Strict reopen her manifest satırını, report hash'ini, verifier sonucunu,
   metadata eşleşmesini ve orphan report dosyalarını kontrol eder. Repair veya
   truncate yapılmaz.
4. Archive yalnızca evidence retention sağlar; operator signature, production
   approval, source verification veya order authority sağlamaz.

## Teknik teslimatlar

- Hash-adresli `reports/report-<sha256>.json` store.
- Fsync-backed `manifest.jsonl` ve reopen recovery.
- Idempotent duplicate handling.
- Manifest/report tamper ve orphan detection.
- Archive CLI: `scripts/archive_binance_depth_soak_report.py`.

## Kullanım

```powershell
uv run python scripts/archive_binance_depth_soak_report.py `
  .local-testnet-soak/report.json `
  --archive-root "$PWD/.local-testnet-archive" `
  --json
```

## Acceptance criteria

- [x] Yalnızca verifier'dan geçen rapor arşivleniyor.
- [x] Aynı rapor hash'i idempotent, manifest tek kayıt kalıyor.
- [x] Archive reopen sonrası hash/metadata/recovery geçiyor.
- [x] Report byte veya manifest truth flag tamper'ı strict recovery'de reddediliyor.
- [x] Focused suite: `5 passed`.
- [x] Full backend suite: `487 passed, 1 skipped`.
- [ ] Gerçek testnet raporunun operator-run archive retention'ı.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- Private key, digital signature, cloud upload veya team sharing.
- Archive'dan `source_verified`/execution authority yükseltmesi.
- Multi-process distributed writer veya Parquet/DuckDB compaction.

## Risk ve sonraki sınır

Hash archive dosya bütünlüğünü ve local retention'ı kanıtlar; operatörün gerçekten
testnet'te çalıştırdığını veya verinin ekonomik doğruluğunu kanıtlamaz. Sonraki
kapı operator identity/attestation ve retention policy olabilir; bu kapı gelmeden
archive kaydı product release approval olarak kullanılmamalıdır.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-07

- Verified Binance depth soak raporları için hash-adresli append-only local archive
  ve strict reopen verifier eklendi.
