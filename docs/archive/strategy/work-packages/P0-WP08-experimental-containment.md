<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

---
id: P0-WP08
title: Experimental Capability Containment
status: Verified
version: 1.0.0
owner: Lead agent (GPT-5.6)
reviewer: GPT-5.6 Terra
phase: Phase 0 — Truth & Safety Release
depends_on:
  - P0-WP06B
  - P0-WP07
---

# P0-WP08 — Experimental Capability Containment

## Karar

Kuantra v1.4.0’ın üretim yüzeyi yalnızca kanıtlanabilir journal, import, replay,
analytics, deterministic risk ve desktop shell kabiliyetlerini göstermelidir.
Gerçek transport, hardware, model inference, source provenance veya signed
plugin registry bulunmayan yüzeyler normal başarı cevabı üretmeyecek; açıkça
`EXPERIMENTAL_DISABLED` / `NOT_AVAILABLE` dönecek ve UI’da etkin yetenek gibi
listelenmeyecektir.

Bu paket gerçek AI, DEX, biometric, provider connector veya plugin sandbox
uygulamaz. Bu entegrasyonlar sonraki ayrı iş paketleridir.

## Kapsam

1. Plugin indirme ve dinamik yükleme yolunu varsayılan üretim API’sinden kapatmak.
2. Plugin manager varsayılanını `kuantra_lite` yapmak; DeFAI/institutional/full
   profillerini üretim persona seçicisinden kaldırmak veya disabled olarak sunmak.
3. Frontend backend erişilemediğinde sahte plugin metadata/aktiflik üretmemeli.
4. GPU/LLM swarm, DEX/DeFAI, biometric hardware/FIDO, MCP live source,
   reverse-skill deploy ve MT5/Polygon/TwelveData transport yüzeylerini
   typed fail-closed sözleşmesine geçirmek.
5. Manifest, README ve ModStore metinlerindeki doğrulanmamış “live”, “verified”,
   “sub-10µs”, “DMA”, “flash loan”, “production” iddialarını temizlemek.
6. Her kapı için backend contract testleri ve frontend no-claim/no-action testleri
   eklemek.

## Mevcut implementasyon

- `backend/app/core/availability.py` ile canonical disabled response/HTTP 503
  sözleşmesi eklendi.
- `/plugins/download`, runtime toggle/persona activation ve ModStore catalog
  signed registry yokken fail-closed; plugin allowlist şu an bilinçli olarak boş.
- AI/GPU/swarm, DEX/DeFAI, biometric/WebAuthn, MCP, live adapter ve reverse
  deploy endpoint’leri 503 `EXPERIMENTAL_DISABLED` veriyor.
- MT5/Polygon/TwelveData adapter’ları artık demo quote/connected state üretmiyor;
  yalnız raw-payload normalizer olarak kalıyor.
- Frontend backend yokken statik plugin capability uydurmuyor; persona ve
  ModStore sahte marketplace/download/verified iddialarını göstermiyor.
- UAT script’i fake senaryoları `PASSED` diye raporlamak yerine `DISABLED` truth
  sonucu kaydediyor; README v1.4.0 ürün sınırına çekildi.
- Paketlenmiş desktop smoke testi unsigned plugin toggle’ını başarı yolu olarak
  kabul etmiyor; typed `503` containment cevabını doğruluyor.

## Sözleşme

Disabled response minimum alanları:

```json
{
  "status": "EXPERIMENTAL_DISABLED",
  "capability": "local_llm_inference",
  "provenance": "SYNTHETIC_MODEL",
  "reason": "REAL_INTEGRATION_NOT_CONFIGURED",
  "execution_authority": false,
  "data_connected": false,
  "transport_connected": false
}
```

HTTP endpoint’leri kullanıcıya normal başarı gibi görünmemesi için `503`
(`FEATURE_DISABLED`) döndürür; pure parser/normalizer fonksiyonları yalnızca
raw payload verildiğinde çalışmaya devam edebilir.

## Kapsam dışı

- Gerçek llama.cpp/OpenAI-compatible sidecar veya model indirme.
- Gerçek BLE/WebAuthn doğrulaması.
- Gerçek DEX RPC, MEV veya flash-loan execution.
- Signed plugin registry, Ed25519 publisher verification veya process sandbox.
- MT5/Polygon/TwelveData session/transport implementasyonu.
- WebView2 geçişi ve Rust data-plane geçişi.

## Risk ve geri dönüş

Ana ürün riski UI’nın daha boş görünmesidir; bu kabul edilebilir ve truth gate’in
gereğidir. Her değişiklik ayrı commit’te tutulur. Disabled response ve feature
flag sözleşmesi geri alınırsa önce ilgili truth testleri de geri alınmadan merge
edilemez.

## Kabul kriterleri

- Uygulama açılışında hiçbir experimental plugin otomatik aktif değildir.
- `/plugins/download` uzaktan kod indirme/çalıştırma yolu üretimde `503` verir.
- Backend erişilemezken frontend plugin kartı, aktiflik veya verified katalog
  uydurmaz.
- Fake AI/DEX/biometric/MCP/adapter/reverse deploy endpoint’leri normal veri,
  latency, fill, approval veya live bağlantı iddiası döndürmez.
- Full backend/frontend/desktop smoke ve 3-OS CI yeşildir.

## Doğrulama kanıtı

- Local isolated backend: `343 passed, 1 skipped`.
- Local frontend: `49 passed`; i18n `480/480`; production build başarılı.
- Focused post-fix desktop/backend checks: `7 passed, 1 skipped`.
- Push CI `34025225053`: Ubuntu `101464886563`, Windows `101464886625`, macOS
  `101464886688` — backend, frontend, audit, build ve desktop smoke yeşil.
- PR CI `34025227211`: Ubuntu `101464892547`, Windows `101464892553`, macOS
  `101464892622` — aynı üç-OS release kapısı yeşil.
- Implementation commit: `d0eda56`; smoke alignment follow-up: `f8653e2`.

## Değişiklik geçmişi

- 0.1.0 — Paket kapsamı ve fail-closed sözleşmesi tanımlandı; implementasyon
  henüz başlamadı.
- 0.2.0 — Working-tree containment implementation: API/UI/plugin/adapter/UAT
  truth gates eklendi; remote CI doğrulaması bekleniyor.
- 1.0.0 — Fail-closed API/UI/adapter/plugin containment ve packaged desktop smoke
  boundary doğrulandı; push/PR üç-OS CI yeşil.
