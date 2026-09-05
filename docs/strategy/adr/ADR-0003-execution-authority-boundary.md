# ADR-0003 — Execution ve AI Yetki Sınırı

- Durum: Accepted
- Tarih: 2026-09-05
- Karar sahibi: Ürün/Mimari liderliği
- Strateji: KPS-001 v1.0.0

## Karar

- Emir verme yetkisi AI'a, agent swarm'a, plugin'e veya copy-trade sinyaline verilmez.
- Deterministic risk motoru execution hattında fail-closed otoritedir.
- AI Auditor yalnızca kaynak bağlı okuma araçları çağırabilir; execution aracı bulunmaz.
- AI çıktısı schema-constrained olur ve observation, evidence, confidence, counterexample
  ile model/prompt/tool provenance taşır.
- Canlı execution Faz 4'te, tek venue ve tek order ailesiyle; shadow → testnet → düşük
  limitli canary sırasıyla açılır.
- CCXT read-only veri/import için kullanılabilir. Kritik canlı order lifecycle için native
  venue adapter yazılır.

## Canlı işlem öncesi asgari kapılar

1. Append-only order/fill/risk event lifecycle.
2. Versioned deterministic risk policy ve aynı girdide aynı sonuç.
3. Bir milyon property-based risk vakasında fail-open olmaması.
4. OS keychain; withdrawal yetkisi olmayan API anahtarı.
5. Stable `clientOrderId`, retry öncesi venue query ve duplicate-order önleme.
6. Startup/reconnect sırasında user stream + REST reconciliation.
7. Partial fill, reject, cancel/replace, fee ve correction lifecycle desteği.
8. 30 günlük shadow modunda sıfır açıklanamayan order/position farkı.
9. Zorunlu disconnect testlerinde reconciliation p99 < 60 saniye.
10. Fault injection altında ACK verilmiş event kaybı = 0.
11. En az 10.000 testnet lifecycle ve 100 kontrollü reconnect.
12. Execution prosesinden bağımsız kill switch.
13. Clock skew, sequence gap ve stale market data durumunda fail-closed davranış.
14. Harici güvenlik incelemesi ve ülke/venue bazlı hukuki ürün matrisi.
15. İlk canlı kapsam: tek venue, tek hesap, temel limit/market ailesi; bot, AI, copy ve FIX yok.

Bu kapılardan biri kapanmadan UI'da "live-ready" veya "production execution" ifadesi kullanılamaz.
