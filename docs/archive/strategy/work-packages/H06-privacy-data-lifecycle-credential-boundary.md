<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# H06 — Privacy, Data Lifecycle & Credential Availability Boundary

```yaml
work_package: H06
version: 1.1.0
status: Complete
date: 2026-09-08
baseline_commit: a864d61
implementation_commit: 4270d33
evidence_commit: a7b99b7
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H01, H02, H04, H05-machine-gate
release_gate: H05-commercial-distribution-deferred
```

## Amaç

Kuantra'nın local-first Execution Intelligence & Trade Forensics Workstation
ürün sözleşmesinde data directory, OS credential store, telemetry consent ve
support/export yüzeylerinin kullanıcı verisini ve secret'ları koruduğunu kanıtlamak.
Bu paket yeni broker connector'ı, live order yetkisini, AI order authority'yi veya
ticari lisans kararını açmaz.

H05'in ticari dağıtım kapısı 2026-09-08 tarihinde bilinçli olarak ertelenmiştir.
H06 geliştirme/test yapılabilir; ancak license/notices, default-branch Dependabot,
signing, pilot ve release kapıları çözülmeden hiçbir production veya ücretli paket
iddiası kurulamaz.

## Davranış sözleşmesi

- Varsayılan data directory uygulamanın kullanıcı alanında olur; uygulama ilk
  çalıştırmada temiz directory ile başlar. Testler `KUANTRA_DATA_DIR` ile izole
  fixture kullanır ve kullanıcı dosyalarını silmez, resetlemez veya migration apply
  etmez.
- Unix/macOS data, log, queue ve export çıktıları mümkün olan en dar kullanıcı
  izinleriyle oluşturulur. İzin ayarlanamıyor veya directory yazılabilir değilse
  güvenli, açıklanabilir hata verilir; daha gevşek izinli veya plaintext fallback
  kullanılmaz.
- OS keychain unavailable/locked/error durumunda credential save/read/test işlemi
  fail-closed ve yapılandırılmış durum üretir. Secret SQLite, log, export veya
  support bundle içine yazılmaz; test provider yalnız explicit test modunda açıktır.
- Telemetry varsayılan olarak opt-out'tur. Explicit consent olmadan network flush
  yapılmaz; local crash spool bounded, redacted ve consent yokken korunur. Network
  hatası retry ile veri uydurmaz ve kullanıcıya başarılı gönderim gibi gösterilmez.
- Support/diagnostic export explicit kullanıcı eylemiyle oluşturulur, secret/token,
  credential, kişisel e-posta ve mutlak local path içermez. Export başarısızsa kısmi
  veya güvenilmeyen paket başarı olarak sunulmaz.
- UI local-first sınırını, credential store unavailable durumunu ve telemetry
  consent'ini doğru gösterir. Missing credential prompt kullanıcıyı gerçek secret
  girmeye zorlamaz ve disabled/live execution yüzeyini açmaz.

## Red test kapsamı

- Fresh temporary data directory oluşturma, Unix mode/ownership kontrolü,
  read-only veya gevşek izinli directory negatif testi ve path escape kontrolü.
- Keychain unavailable, locked/rejected read-write-delete ve missing account
  fixture'larında structured response, no plaintext persistence ve no live fallback.
- Telemetry default opt-out, opt-in/opt-out geçişi, bounded queue, redacted spool,
  consent yokken no network ve network-denied fixture davranışı.
- Diagnostics/support archive içinde secret, token, e-posta, absolute path,
  environment value ve user database içeriği sızıntısı negatif testi.
- Explicit export/retention metadata determinism'i; unknown/unavailable sonucunun
  `complete`, zero veya başarılı gönderim olarak dönüştürülmemesi.
- Backend API, frontend settings/onboarding ve native bridge arasında aynı
  unavailable/degraded truth'un korunması; i18n ve accessibility regression.

## Bounded uygulama sırası

1. Mevcut paths, keychain, telemetry, logging/export ve UI davranışını test matrisi
   ile ölç; mevcut güvenli davranışı varsayım olarak değil kanıt olarak kaydet.
2. Önce red testleri ekle; yalnız gerekli minimum boundary düzeltmesini uygula.
3. Gerçek credential, gerçek kullanıcı data directory'si, migration bundle veya
   remote telemetry endpoint kullanmadan focused test çalıştır.
4. Backend/frontend full suite, local CI, Mac native smoke ve docs evidence aynı
   source commit ile doğrula.
5. H06 tamamlanınca H07 performance'a geçişi STATUS üzerinden açıkça seç; H05
   ticari dağıtım koşullarını release gate olarak koru.

## Acceptance criteria

- [x] Data directory ve generated support/telemetry files için platforma uygun
  private-permission contract red→green testlerle kanıtlandı.
- [x] Keychain unavailable/locked/missing durumları fail-closed; secret fallback
  veya SQLite/log/export sızıntısı yok.
- [x] Telemetry consent default opt-out; spool/flush/retention status deterministic
  ve network-denied fixture ile kanıtlı.
- [x] Redacted support/export archive secret, credential, PII ve absolute path
  sızıntısı olmadan oluşturuluyor; failure partial success gibi görünmüyor.
- [x] UI ve native boundary local-first, unavailable/degraded ve credential scope'u
  doğru gösteriyor; live execution/AI authority açılmıyor.
- [x] Focused → full backend/frontend → local CI → Mac smoke ve docs checks PASS;
  gerçek kullanıcı verisi/credential kullanılmıyor.

## Uygulama ve kanıt

- Bounded implementation `4270d33`, keychain/UI truth coverage ve final evidence
  `a7b99b7` üzerinde tamamlandı. H06 focused suite **8 passed**; full backend
  **683 passed, 2 warnings**; frontend **19 files / 71 tests passed**; i18n
  **574/574** ve production build PASS.
- Temiz Mac local-CI source commit `a7b99b7c540629eb3d9b595c05691200c8c0b81e`:
  **MERGE READY**, provenance **COMPLETE**, tracked source tree SHA-256
  `837fee0b94e43cecb06b49195d20b1d13b3b1b235eb8f7e3c521fcc546527c52`, local-CI
  report SHA-256 `ab71a75f8740a6ed444b14e2bfed429f3b6ad3197ddec8124289edde19220283`,
  local smoke report SHA-256 `c20b7313069a1217b119989102903c5a6311432c798b2d5a090afe6ab0b16176`.
  macOS arm64, Python `3.11.16`, Node `20.20.2`, npm `10.8.2`, uv `0.12.10`,
  PyInstaller `6.22.2`; executable SHA-256
  `967cf5db996b91bf948763b0d1fe0a003d8cee228883bfc3abe6599dce1815bc`, app SHA-256
  `a0acd018b2366cb72209c4028473dbd2b5b31c7370f9b9c3c8c68f4e0e48f46e`.
- Exact read-only mounted DMG/WKWebView smoke on the same source passed: DMG
  SHA-256 `7ec5226771dc3b9619c37b17b179043412d140d84b5e89a0262b5ed4805eaca3`,
  smoke report SHA-256 `5e4980ae1813eb36812d15032afe5d351060d5eb460ca7b41ca263c3603a1582`,
  mounted executable SHA-256 matched the local smoke value, renderer `wkwebview`,
  controller ready and clean detach PASS. The smoke used the configured public
  Binance stream; it is not offline runtime proof.
- `uv --offline` was dependency-preparation evidence only. No real user data,
  credential, migration apply, live broker or remote telemetry delivery was used.

## Kapsam dışı ve yeniden açma koşulları

Kapsam dışı: MIT veya başka ürün lisansı seçimi, root `LICENSE`, third-party notices,
default-branch Dependabot merge/remediation, Developer ID/notarization, Windows/Linux
host kanıtı, pilot/release, gerçek broker bağlantısı, live order, funding/transfer
schema ve gerçek kullanıcı verisi.

H05 ticari dağıtım kapısı, ilk ücretli/paketlenmiş release adayı hazırlanırken yeniden
açılacaktır. O noktada ürün lisansı seçilmeli, locked 395 component için notice/lisans
kanıtı ve unverified metadata owner/legal review'i tamamlanmalı, beş default-branch
Dependabot alert'i remediation veya süreli risk kabulüyle sonuçlandırılmalı ve tüm
kanıtlar tek release source commit/artifact manifestine bağlanmalıdır.

## Kapanış kararı

H06'in bounded privacy/data-lifecycle ve credential availability sözleşmesi `4270d33`
uygulaması ve `a7b99b7` kanıtı ile kapatılmıştır. Kapanış yalnız bu paketin belirtilen
sentetik/test sınırları içindir; H05'in ticari dağıtım kapısını, production readiness'i
veya Kuantra'nın read-only, local-first ürün sınırını gevşetmez. Sonraki aktif paket H07
bounded performance/resource-limit kanıtıdır.
