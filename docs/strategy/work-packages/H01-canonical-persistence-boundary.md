<!-- doc-role: current-work-package -->
# H01 — Canonical Persistence & Recovery Boundary

```yaml
work_package: H01
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 30dfcd7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP21, P1-WP25, P1-WP26
```

## Amaç

Canonical evidence ledger ile compatibility projection/journal yazılarının process
crash, transaction error, disk sınırı ve concurrent import altında ACK doğruluğunu
kanıtlamak. H01 yalnız mevcut persistence sözleşmesinin durability/recovery testidir;
yeni ledger schema/event, funding/transfer modeli, migration veya kullanıcı verisi
işlemi eklemez.

## Davranış sözleşmesi

- Append ACK yalnız canonical event ve bağlı compatibility projection aynı transaction
  içinde commit olduktan sonra verilir; failure/rollback sonrası half-import görünmez.
- Process kill before commit, after canonical insert ve after projection update için
  yeniden başlatma verify/replay sonucu idempotent ve source-linked kalır.
- Disk-full, read-only directory/database ve SQLite busy/concurrent import hataları
  fail-closed raporlanır; sessiz başarı, event kaybı veya duplicate ACK oluşmaz.
- `verify_chain`, projection rebuild ve Evidence Pack aynı immutable event lineage'ını
  korur; eski event silinmez ve kullanıcı verisi otomatik resetlenmez.
- Test fixture'ları geçici/sentetik data directory kullanır. Gerçek kullanıcı verisi,
  credential, migration restore/apply veya live broker işlemi yapılmaz.

## Red test kapsamı

- Process kill/failure injection: ACK öncesi/sonrası canonical/projection atomicity,
  rollback ve tekrar import idempotency.
- SQLite transaction failure, read-only database/directory ve bounded disk-full
  simulation; error response ve chain integrity negative assertions.
- Concurrent duplicate import ve distinct import yarışları; no half-import, no
  duplicate semantic event, deterministic projection/evidence snapshot.
- Restart/rebuild/verify chain sonrası source event hash, projection ve Evidence Pack
  equivalence; unsupported/malformed failure görünür kalır.

## Acceptance criteria

- [ ] Process/transaction failure hiçbir ACK verilmiş event'i kaybetmez ve half-import
  üretmez; rollback kanıtı vardır.
- [ ] Read-only/disk-full/busy/concurrent import hataları fail-closed, bounded ve
  tekrar çalıştırılabilir; duplicate ACK veya sessiz veri kaybı yoktur.
- [ ] Restart/rebuild/verify chain canonical event, projection ve Evidence Pack
  lineage'ını korur; eski immutable evidence silinmez.
- [ ] Red→green focused tests, full backend/frontend suite ve Mac local CI aynı source
  commit üzerinde PASS; synthetic temporary data dışında veri kullanılmaz.
- [ ] Yeni schema/event, funding/transfer, connector, live order, AI authority,
  migration apply veya release/pilot claim'i eklenmez.

## Kesinlikle kapsam dışı

Schema upgrade/restore (H02), threat model ve archive extraction (H04), dependency/SBOM
(H05), privacy/keychain (H06), performance benchmark (H07), signing/notarization,
Windows/Linux host proof, pilot, release ve full-account PnL/tax accounting.

## İlk uygulama alanı

Önce mevcut `EvidenceLedgerRepository` transaction/failure-injector ve P1-WP21
projection boundary'sini okuyup red testleri yaz. Test harness'i kanıtlamıyorsa
bounded implementation yap; yeni persistence abstraction veya schema açma. H01
tamamlanmadan H02 restore/upgrade veya release durability iddiası açılmaz.
