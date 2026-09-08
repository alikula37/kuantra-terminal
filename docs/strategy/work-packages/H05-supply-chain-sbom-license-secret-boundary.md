<!-- doc-role: current-work-package -->
# H05 — Supply Chain, SBOM, License & Secret Boundary

```yaml
work_package: H05
version: 1.0.0
status: Ready
date: 2026-09-08
baseline_commit: 1cf486e
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H04
```

## Amaç

Kuantra'nın locked dependency, build input, generated artifact ve support/export
çıktısı arasındaki supply-chain güvenini kanıtlamak. Bu paket vulnerability scan,
deterministic inventory ve secret boundary'sini bounded biçimde ele alır; hukuki
lisans onayı, remote signing, notarization, pilot veya release yetkisi vermez.

## Davranış sözleşmesi

- Backend ve frontend lock dosyaları doğrulanır; test/production dependency ayrımı
  ve mevcut branch bulguları açıkça raporlanır.
- SBOM/package inventory aynı source ve lock girdileri için deterministik üretilir;
  dependency adı/sürümü/hash bilgisi uydurulmaz.
- Tracked source, configuration, reports ve build outputs üzerinde secret scan
  gerçek credential kullanmadan çalışır; synthetic canary negatif testte yakalanır.
- Secret veya local environment değeri artifact, support pack, log ve release-facing
  rapora girerse fail-closed sonuç üretilir.
- GitHub default branch Dependabot bulguları branch `npm audit` sonucundan ayrı
  tutulur; merge edilmeden kapatılmış sayılamaz.

## Red test kapsamı

- Lock hash değişimi, missing lock, resolver drift ve production/test dependency
  sınıflandırması.
- Synthetic API key, bearer token, private key, `.env` değeri ve credential-like
  path'in source/report/artifact scan tarafından yakalanması.
- Temiz repository'de false positive ayrımı; generated report ve archive çıktısında
  redaction/absence kontrolü.
- SBOM sıralaması, duplicate package, direct/transitive provenance ve tekrar üretim
  determinism'i.
- Lisans metadata'sı eksik/uyuşmaz olduğunda `UNKNOWN` veya owner review; otomatik
  legal approval yok.

## Uygulama sınırı

İlk adım mevcut lock dosyaları, package metadata, CI/release truth validator ve
rapor akışını okuyup red test matrisi yazmaktır. Reachable critical/high bulgu varsa
önce applicability ve düzeltme/owner kaydı yapılır. Branch'teki `npm audit` temizliği
GitHub default branch'teki beş açık Dependabot alert'ini kapatmış sayılmaz.

## Acceptance criteria

- [ ] Locked backend/frontend dependency ve hash doğrulaması red→green geçer.
- [ ] Deterministic SBOM/package inventory aynı girdide aynı snapshot'ı üretir.
- [ ] Synthetic secret canary source/report/artifact sınırında yakalanır; temiz
  repository false-positive olmadan geçer.
- [ ] Current branch vulnerability sonuçları ve GitHub default-branch alerts ayrı,
  kaynak/tarih/platform ile kaydedilir; ilgili critical/high bulgu varsa açık kalır.
- [ ] `LICENSE` ve third-party notices için ürün sahibi/lisans sahibi kararı açıkça
  kaydedilir; lisans varsayımı veya otomatik legal approval yapılmaz.
- [ ] Focused → full suite/local CI ve docs evidence aynı source commit ile PASS;
  gerçek credential/user data kullanılmaz.

## Kesinlikle kapsam dışı

H06 privacy/data lifecycle ve keychain unavailable davranışı, H07 performance,
Developer ID/notarization/Gatekeeper, Windows/Linux final artifact, pilot/release,
new connector, live execution, AI order authority, full-account PnL/tax accounting,
funding/transfer schema ve gerçek kullanıcı secret'ları.

## Başlangıç kararı

H04 `1cf486e` ile trust-boundary misuse testleri ve Mac local-CI kanıtı üzerinden
bounded olarak kapandı. H05'in sonucu yalnız kanıtla `Complete` yapılacak; GitHub
default branch alert'leri, lisans/notice owner kararı veya eksik platform kanıtı
UNKNOWN/PASS olarak yazılmayacaktır.
