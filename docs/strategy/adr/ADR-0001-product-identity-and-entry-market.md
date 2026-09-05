# ADR-0001 — Ürün Kimliği ve İlk Giriş Pazarı

- Durum: Accepted
- Tarih: 2026-09-05
- Karar sahibi: Ürün/Mimari liderliği
- Strateji: KPS-001 v1.0.0

## Bağlam

Kuantra aynı anda journal, HFT, FIX/DMA, order flow, AI swarm, copy trading, DeFi ve
çoklu varlık terminali olmayı iddia ediyor. v1.4.0 kod tabanı bu yüzeylerin çoğunu
üretim güvenilirliğiyle desteklemiyor. Bu genişlik, kanıtlanabilir tek bir kullanıcı
sonucunu güçlendirmek yerine güven ve geliştirme kapasitesini parçalıyor.

## Karar

Kuantra'nın ürün kimliği:

> Discretionary crypto/perps traderının her işlemini broker lifecycle'ı, piyasa
> bağlamı, risk kararı, playbook disiplini ve kaynak bağlı AI incelemesiyle yeniden
> üretilebilir bir Trade Evidence Pack'e dönüştüren local-first Execution Intelligence
> & Trade Forensics Workstation.

İlk pazar Binance ve OKX kullanan aktif discretionary crypto perpetual traderlarıdır.
İlk entegrasyon read-only import ve reconciliation olacaktır; canlı emir girişi ilk
ürün vaadi değildir.

## Sonuçlar

- MT5/forex, futures/prop, BIST ve genel multi-asset girişleri Faz 4 sonrasına kadar
  ürün yol haritasında yer almaz.
- HFT, institutional DMA ve "her şeyi yapan terminal" konumlandırması terk edilir.
- Başarı trade sayısıyla değil; evidence completeness, weekly review, kural uyumu ve
  açıklanamayan broker farkı metrikleriyle ölçülür.
- Doğrudan ürün rakipleri TradesViz, TradeZella ve TraderSync'tir. QuantConnect,
  Freqtrade, Bookmap ve Quantower yetenek referansıdır; ilk GTM rakibi değildir.

## Reddedilen alternatifler

- **Futures/prop ile başlamak:** lisanslı tick/depth verisi ve çok sayıda execution
  adaptörü nedeniyle sermaye ve sertifikasyon yükü erken aşamada orantısızdır.
- **MT5/forex ile başlamak:** mevcut adaptör demo seviyesindedir; Windows/terminal
  bağımlılığı ve broker parçalanması güvenilir reconciliation'ı geciktirir.
- **BIST ile başlamak:** veri, broker ve hedef kullanıcı kanıtı yoktur.
- **Multi-asset terminal:** farklı piyasa mikro-yapılarını tek soyutlamada ezerek
  güvenilirlik yerine yüzey alanını büyütür.
