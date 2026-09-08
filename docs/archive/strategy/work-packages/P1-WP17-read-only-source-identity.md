<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P1-WP17 — Read-Only Source Identity & Support Contract

```yaml
work_package: P1-WP17
version: 1.0.0
status: Verified
date: 2026-09-08
baseline_commit: ef909d1
implementation_commit: 930d25a
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: P1-WP16
```

## Problem ve karar

Read-only API snapshot'ı canonical venue adıyla (`BINANCE`/`OKX`) raporlamak,
aynı canonical venue altında Binance Spot ve Binance USD-M Futures kaynak kimliğini
provenance ve idempotency seviyesinde kaybedebilirdi. Bu paket yeni venue veya market
modu eklemez; mevcut connector sınırındaki source identity'yi açıkça taşır.

Canonical venue, source exchange id ve market type ayrı alanlardır:

- `binance_spot` → `BINANCE` + `spot`
- `binance_futures` → `BINANCE` + `swap`
- `okx` → `OKX` + `swap`

v2 read-only manifest bu iki source alanını imzalı stable payload'a dahil eder. Eski v1
manifestler geriye dönük kabul edilir; v2 source/venue/market tutarsızlığı fail-closed
reddedilir. Ledger idempotency kimliği source exchange id'yi içerir; aynı venue/account
altında Spot ve Futures snapshot'ları birbirine çarpmaz. Secret, raw CCXT payload ve
credential yine evidence ledger'a girmez.

## Dosya kapsamı

- `backend/app/services/exchange/read_only_broker_sync.py`
- `backend/app/services/broker_import_service.py`
- `backend/tests/test_p1_wp12_read_only_api_sync.py`

## Acceptance evidence

- [x] Aynı `BINANCE` venue/account için Spot ve Futures snapshot'ları ayrı source
  identity, market type, provenance ve ledger idempotency üretir.
- [x] v2 manifest stable hash'e source identity/market type dahil eder; source/venue/type
  mismatch ve importer sınırındaki tutarsız v2 metadata fail-closed reddedilir.
- [x] v1 manifest compatibility korunur; v1 manifest source identity yokken eski
  canonical venue davranışı bozulmaz.
- [x] Yeni venue, market, credential scope veya canlı order yüzeyi açılmadı; read-only
  method sınırı ve secret/raw payload koruması korunmuştur.
- [x] Odak testleri: `21 passed, 2 warnings`.
- [x] Tam backend regresyonu: `570 passed, 2 warnings`; Mac local CI: `MERGE READY`;
  frontend `51 passed`, production build, arm64 desktop build ve WKWebView native smoke
  geçti. Smoke `build_commit=UNKNOWN` B4 olarak açık kaldı.
- [x] Exact implementation commit: `930d25a`; değişen dosya ve kalan kapsam sınırı
  bu kayıtta sabitlendi.

## Kapsam dışı / sonraki bağımlılık

Instrument/settlement/position-mode ayrıntılı support matrix, fee currency/precision,
funding, economic dedup ve full account accounting bu paketin kapsamı değildir. Bunlar
güncel P1-WP18 ve sonraki bounded paketlerde ayrıca kanıtlanmadan production capability
olarak açılmaz.
