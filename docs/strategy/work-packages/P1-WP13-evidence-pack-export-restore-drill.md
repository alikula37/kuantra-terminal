# P1-WP13 — Evidence Pack Export ve Backup/Restore Drill

```yaml
document_id: P1-WP13
version: 1.0.0
status: Active
date: 2026-09-06
baseline: 5aa2723
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002
depends_on: P1-WP07 Trade Evidence Pack API, P1-WP12 read-only snapshot adapter
implementation_commits: 1665d6c
```

## Problem

Evidence Pack API üzerinden okunabiliyordu; fakat kullanıcıya deterministik,
hash'li ve taşınabilir JSON/HTML artefaktı olarak verilmiyordu. SQLite shadow
backup testi yalnız dosyanın oluştuğunu kontrol ediyor, restore sonrası evidence
hash-chain ve DuckDB projection'ın yeniden üretilebildiğini kanıtlamıyordu.

## Karar

1. Export yalnızca `TradeReadAdapter` tarafından üretilen raw-payload-free pack'i
   kabul eder. Secret-bearing key adı görülürse export fail-closed olur.
2. JSON artifact canonical JSON kullanır; `payload_sha256` payload'ı, HTTP header'daki
   `artifact_sha256` ise indirilen tam dosyayı doğrular. HTML, aynı canonical JSON'u
   JavaScript çalıştırmadan static `<pre>` içinde sunar.
3. Backup işlemi `VACUUM INTO` ile source SQLite'tan alınır; SHA-256, SQLite
   `integrity_check`, evidence ledger hash-chain ve geçici kopyaya DuckDB hydration
   birlikte doğrulanmadan `SUCCESS` dönmez.
4. Restore drill orijinal backup'ı değiştirmez. Geçici SQLite/DuckDB hedefinde yapılır;
   gerçek database replacement veya silent overwrite bu paketin parçası değildir.
5. Yeni endpoint `GET /api/v1/trades/{trade_id}/evidence/export?format=json|html`
   yalnızca download üretir; broker, ledger veya trade state mutasyonu yapmaz.

## Teknik teslimatlar

- `EvidencePackExportService` ve deterministic JSON/HTML artifact modeli.
- Payload/artifact SHA-256 response header'ları.
- Unsafe trade ID ve secret-bearing field fail-closed validation.
- `DatabaseMaintenanceEngine.verify_sqlite_restore`.
- Backup sonucu hash, ledger integrity ve DuckDB restore kanıtı.
- Evidence export ve Windows restore-lock regression testleri.

## Acceptance criteria

- [x] JSON export aynı inputta byte-for-byte deterministik.
- [x] HTML export aynı payload hash'ini ve static canonical JSON'u taşıyor.
- [x] Secret alan veya unsafe trade ID export'u reddediyor.
- [x] Export endpoint content disposition ve üç doğrulama header'ı dönüyor.
- [x] Backup SHA-256 doğrulanıyor.
- [x] Backup SQLite integrity ve evidence chain doğrulanıyor.
- [x] Geçici DuckDB projection backup kopyasından yeniden oluşturuluyor.
- [x] Restore başarısızsa backup operasyonu `ERROR` dönüyor.
- [x] Focused suite: `4 passed`.
- [x] Full backend suite: `402 passed, 1 skipped`.
- [ ] Remote three-OS CI: GitHub Actions kota/bütçe nedeniyle geçici disabled;
  reset sonrası implementation commit'i için yeniden çalıştırılacak.

## Kesinlikle kapsam dışı

- Gerçek database replacement, otomatik rollback veya cloud backup.
- Şifreli remote export, ekip paylaşımı veya tenant storage.
- Evidence Pack'i journal trade state'ine geri yazmak.
- Yeni broker connector veya live execution.

## Risk ve sonraki sınır

Her günlük backup'ta DuckDB restore drill'i büyük database'lerde ek IO/CPU maliyeti
yaratabilir. Pilot telemetry ile restore süresi ölçülmeli; gerekirse backup alma ile
restore certification ayrı scheduled işlere ayrılmalıdır. Bir sonraki Phase 1 sınırı
versioned playbook/risk-policy event'leridir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Deterministic Evidence Pack JSON/HTML export ve hash-chain/OLAP restore drill'i
  tanımlandı ve uygulandı.
