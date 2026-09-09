<!-- doc-role: archived -->
<!-- Historical evidence: this file is not a current implementation instruction. -->
# N04 — macOS Manual Update / Uninstall Data-Preservation Audit

```yaml
work_package: N04
version: 1.0.0
status: Complete
date: 2026-09-10
baseline_commit: f858321
implementation_commit: 3f4ba822cf367c588cc9e9fe13e6404a5a6d4512
branch: codex/p1-wp01-evidence-ledger
strategy: KPR-001@current
depends_on: H01, H02, H04, H06, N01, N02, P1-WP27
release_gate: H05-commercial-distribution-deferred
```

## Amaç

Kuantra'nın mevcut ürün sözleşmesine uygun manuel `.app` güncelleme sınırını
kanıtlamak: yeni artifact staging/promotion sırasında hata olursa eski artifact
ve sentetik data korunmalı; uygulama kaldırılırken yalnız uygulama silinmeli, data
directory korunmalı; eski executable yeni schema ile çalıştırılmamalı. Bu paket
ürüne automatic updater veya yeni ledger/migration schema eklemez.

N03 temiz profil/host çalıştırması bu paketin önkoşulu değildir. N03 owner kararıyla
son macOS distribution/pilot validation kapısına ertelenmiştir; N03 acceptance
checkbox'ları açık kalır ve production/pilot öncesi yeniden çalıştırılır.

## Kapsam

- Önceki supported build ve güncel build'in explicit `.app` yolları ile seçilmesi.
- Her iki artifact için source commit, tree/provenance ve executable hash'inin
  doğrulanması; aynı artifact veya yalnızca metadata ile yapılan testin reddi.
- İzole bir install root içinde manual update transaction: stage → backup → promote.
- `after_stage`, `after_backup` ve `after_promotion` failure injection noktalarında
  eski uygulamanın ve sentetik data snapshot'ının korunması.
- Uygulama path'inin kaldırılması sırasında ayrı data directory'nin byte-for-byte
  korunması.
- Restore/schema rollback politikasının fail-closed kullanıcı sözleşmesi olarak
  görünür olması: eski executable daha yeni schema'yı doğrudan açamaz; güvenli yol
  doğrulanmış backup restore veya ileri yönlü düzeltmedir.

## Kapsam dışı

- Automatic updater, background update service veya silent replacement.
- Gerçek kullanıcı data'sı, credential, Keychain, migration ZIP veya migration apply.
- Signing/notarization, Gatekeeper clean-profile kanıtı (N03) ve Windows/Linux host.
- Gerçek broker/exchange bağlantısı, canlı order veya yeni funding/transfer schema'sı.
- Eski build'i yeni schema üzerinde çalıştırmayı zorlamak ya da otomatik schema
  downgrade yapmak.

## Kabul kriterleri

- [x] Önceki ve güncel supported `.app` explicit seçilir; provenance, source commit,
      tree state, executable hash ve artifact hash her ikisi için eşleşir. Eksik veya
      mismatch kanıt fail-closed olur.
- [x] Başarılı manual update active app hash'ini yeni artifact'e taşır; ayrı durable
      data snapshot'ı değişmez.
- [x] Staging, backup veya promotion sonrasındaki injected/interrupted failure,
      eski app'i active konumda ve data'yı aynı snapshot'ta bırakır; yarım staging /
      backup kalıntısı bırakmaz.
- [x] App-only uninstall uygulama path'ini kaldırır; data directory ve hash'i
      değiştirmez. Gerçek kullanıcı path'i bu audit tarafından kabul edilmez.
- [x] Yeni schema karşısında eski executable için rollback kararı fail-closed'dur;
      otomatik downgrade yoktur ve güvenli seçenekler kullanıcıya açıkça raporlanır.
- [x] Focused red→green testler, `check_docs.py`, ilgili backend suite ve canonical
      local CI sonucu kaydedilir. Bu sonuç N03 clean-profile veya signing kanıtı
      sayılmaz.

## Uygulama sırası

1. Transaction ve rollback-policy contract'ı için red testleri yaz.
2. Yalnız isolated test root üzerinde çalışan stdlib audit harness'ını uygula.
3. Başarılı update, üç interruption noktası, uninstall/data preservation ve schema
   rollback fail-closed testlerini green yap.
4. Exact artifact/provenance gereksinimini ve unsupported boundaries'i raporla.
5. Focused regression, docs/link check ve canonical local CI çalıştır.
6. Acceptance checkbox'larını yalnız gerçek kanıtla güncelle; sonra N05'e geçişi
   STATUS/roadmap bağımlılıklarıyla birlikte değerlendir.

## Kanıt günlüğü

Bu bölüm gerçek komut/platform/artifact kanıtı oluştukça doldurulur. Source-level
transaction testleri N04 implementation kanıtıdır; önceki/current packaged artifact
ve host evidence olmadan N04 production gate'i kapatılmaz.

- Implementation commit: `3f4ba822cf367c588cc9e9fe13e6404a5a6d4512`.
- Platform/toolchain: macOS 26.6.2 arm64, Python 3.11.16, Node 20.20.2, npm
  10.8.2, uv 0.12.10, PyInstaller 6.22.2.
- Focused tests: `uv run --offline --no-project --with-requirements
  backend/requirements.lock pytest -q
  backend/tests/test_n04_macos_update_uninstall_audit.py` — **13 passed**.
- Full suite/local CI: clean commit `3f4ba822cf367c588cc9e9fe13e6404a5a6d4512`
  passed the canonical default behavior gate: backend **788 passed, 2 warnings**,
  frontend **25 files / 104 tests**, i18n **608/608**, production build, arm64
  desktop build, native `wkwebview` smoke and packaging/provenance contract steps
  PASS. Report: `dist/n04-local-ci-report-3f4ba82.json`, SHA-256
  `1990759706893589b7411133c51a624a3a265d3dadafc4a47d35955bf0777576`;
  provenance `COMPLETE`, tracked tree SHA-256
  `b200a27bc8ff110dd4ce13c7c2346771be8e0148c1d4cd80de4e527a2bfb0a0e`, app tree
  SHA-256 `3d97e2a412662f5701d21eb4a8ab8bf0b2a809532ad1377e3b92c80b13f63b1f`,
  executable SHA-256
  `11d9e1085c306574a97c233f646b286e3a29ad8c9baf14d0431397d34a7fdb0a`.
- Packaged audit: `dist/n04-packaged-audit-3f4ba82.json`, SHA-256
  `24492ae5ff85047c2a979bcbdf1c85a987b9b5aeee885ededfb132407d987868`, Mac
  26.6.2 arm64. Previous artifact commit `ec162429d4f79e9f6fd581d3e1c81e8cb8b48d42`,
  app SHA-256 `d1b0041f57a41b3e6a819171e7f03254f15a469eaf5eb5298ee6444d2f331228`,
  executable SHA-256 `1184f105364160ce19a915cf2336f3778b476886df442e198738e7e8353b1937`;
  current artifact commit `3f4ba822cf367c588cc9e9fe13e6404a5a6d4512`, app SHA-256
  `3d97e2a412662f5701d21eb4a8ab8bf0b2a809532ad1377e3b92c80b13f63b1f`, executable
  SHA-256 `11d9e1085c306574a97c233f646b286e3a29ad8c9baf14d0431397d34a7fdb0a`;
  both provenance statuses `COMPLETE`.
- Known limits/blockers: N03 final clean-profile host evidence; H05 commercial
  license/notices and default-branch Dependabot disposition; signing/notarization.
