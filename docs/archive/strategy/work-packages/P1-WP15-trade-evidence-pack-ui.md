<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP15 — Trade Evidence Pack UI ve Provenance Review

```yaml
document_id: P1-WP15
version: 1.0.0
status: Active
date: 2026-09-06
baseline: e5a756e
strategy: KPS-001@1.0.0
adr: ADR-0001, ADR-0002, ADR-0003
depends_on: P1-WP07 Trade Evidence Pack API, P1-WP13 Evidence Pack Export ve Backup/Restore Drill, P1-WP14 Versioned Playbook ve Risk Policy Events
implementation_commits: 40d5c6c
```

## Problem

Trade Evidence Pack backend'de source-linked ve hash-chain doğrulamalı olmasına
rağmen Journal kullanıcı akışında görünür değildi. Kullanıcı ledger bütünlüğünü,
okuma kaynağını, policy/playbook sürümünü veya market-context verisinin doğrulanmış
olup olmadığını görmek için API veya export dosyası açmak zorundaydı. Bu, ürünün
karar-sonrası öğrenme değerini ve “kanıtlanabilir” konumlandırmasını zayıflatıyordu.

## Karar

1. Journal satırına eklenen `Evidence` aksiyonu read-only Evidence Pack panelini
   açar. Panel trade state değiştirmez, emir göndermez ve AI çağırmaz.
2. Panel yalnızca backend'in döndürdüğü olayları gösterir. Policy/playbook id,
   version ve snapshot hash event payload/provenance içinde yoksa UI bunları
   tahmin etmez.
3. `ledger_integrity.valid` yeşil “Verified chain” olarak, legacy compatibility
   read ve `source_verified=false` market context ise açık uyarı olarak gösterilir.
   Bar approximation hiçbir yerde gerçek tick/order-book kanıtı gibi etiketlenmez.
4. JSON/HTML export butonları mevcut deterministic export endpoint'ini çağırır;
   tarayıcı/desktop yüzeyinde yalnızca response blob'ı indirir. UI export içeriğini
   yeniden üretmez veya server state'ini değiştirmez.

## Teknik teslimatlar

- `TradeEvidencePack`, ledger integrity, event, coverage ve market-context frontend tipleri.
- `TradeEvidencePanel` yükleme/error/read-source/ledger/event/provenance/export görünümü.
- Journal satırlarından Evidence Pack erişimi.
- Policy/playbook snapshot referanslarının event payload/provenance'dan güvenli çıkarımı.
- JSON/HTML local download akışı ve bounded hata gösterimi.
- DOM regression testleri.

## Acceptance criteria

- [x] Journal'dan bir trade Evidence Pack paneli açılabiliyor.
- [x] Ledger integrity geçerli/geçersiz durumu ve kontrol edilen event sayısı gösteriliyor.
- [x] Typed projection ile compatibility legacy okuma ayrımı görünür.
- [x] Risk policy ve playbook snapshot id/version/hash bilgisi yalnız event varsa gösteriliyor.
- [x] Market context `source_verified=false` ise “unverified / descriptive” olarak işaretleniyor.
- [x] JSON ve HTML export mevcut endpoint üzerinden indirilebiliyor.
- [x] API 404/5xx cevapları kanıt varmış gibi gösterilmiyor.
- [x] Frontend suite: `51 passed`.
- [x] `npm run build`: tri-locale parity, TypeScript ve Vite production build geçti.
- [ ] Remote CI: GitHub Actions kota/bütçe nedeniyle geçici disabled.

## Kesinlikle kapsam dışı

- UI içinden playbook/risk policy değiştirmek.
- UI içinden emir oluşturmak, iptal etmek veya risk guard'ı bypass etmek.
- Market data'yı “verified” yapmak, sentetik candle/tick üretmek veya order-book iddiası.
- AI özetleri, cloud sync, ekip paylaşımı veya yeni broker connector.

## Risk ve sonraki sınır

Evidence paneli çok uzun event zincirlerinde modal scroll maliyeti oluşturabilir;
Phase 2 replay/data-plane paketi öncesi event pagination veya bounded virtualization
ölçülmelidir. Bir sonraki teknik sınır, Evidence Pack içindeki market-context
attachment'ını sequence/gap-aware replay ile güçlendirmektir; execution yetkisi
eklenmeyecektir.

## Değişiklik geçmişi

### 1.0.0 — 2026-09-06

- Trade Evidence Pack'in Journal'dan erişilebilir, provenance-aware ve deterministic
  export kontrollü read-only UI yüzeyi tanımlandı ve uygulandı.
