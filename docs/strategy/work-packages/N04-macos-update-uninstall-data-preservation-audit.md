<!-- doc-role: current-work-package -->
# N04 — macOS Manual Update / Uninstall Data-Preservation Audit

```yaml
work_package: N04
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: f858321
implementation_commit: fcb24d7bf8a197c5c592e8b421f04691e92dbe98
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

- [ ] Önceki ve güncel supported `.app` explicit seçilir; provenance, source commit,
      tree state, executable hash ve artifact hash her ikisi için eşleşir. Eksik veya
      mismatch kanıt fail-closed olur.
- [ ] Başarılı manual update active app hash'ini yeni artifact'e taşır; ayrı durable
      data snapshot'ı değişmez.
- [ ] Staging, backup veya promotion sonrasındaki injected/interrupted failure,
      eski app'i active konumda ve data'yı aynı snapshot'ta bırakır; yarım staging /
      backup kalıntısı bırakmaz.
- [ ] App-only uninstall uygulama path'ini kaldırır; data directory ve hash'i
      değiştirmez. Gerçek kullanıcı path'i bu audit tarafından kabul edilmez.
- [ ] Yeni schema karşısında eski executable için rollback kararı fail-closed'dur;
      otomatik downgrade yoktur ve güvenli seçenekler kullanıcıya açıkça raporlanır.
- [ ] Focused red→green testler, `check_docs.py`, ilgili backend suite ve canonical
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

- Implementation commit: `fcb24d7bf8a197c5c592e8b421f04691e92dbe98`.
- Platform/toolchain: macOS 26.6.2 arm64, Python 3.11.16, Node 20.20.2, npm
  10.8.2, uv 0.12.10, PyInstaller 6.22.2.
- Focused tests: `uv run --offline --no-project --with-requirements
  backend/requirements.lock pytest -q
  backend/tests/test_n04_macos_update_uninstall_audit.py` — **12 passed**;
  N03 regression pairing (`...test_n04... ...test_n03...`) — **18 passed**.
- Full suite/local CI: clean commit `fcb24d7bf8a197c5c592e8b421f04691e92dbe98`
  passed the canonical default behavior gate: backend **787 passed, 2 warnings**,
  frontend **25 files / 104 tests**, i18n **608/608**, production build, arm64
  desktop build, native `wkwebview` smoke and packaging/provenance contract steps
  PASS. Report: `dist/n04-local-ci-report-fcb24d7.json`, SHA-256
  `312d3b2665f192e91b12880a38811974db1a2f4bceb1112a02cd410e4f099e7f`;
  provenance `COMPLETE`, tracked tree SHA-256
  `c984912ecef812d9609b43579d14f32bd62971cb9edb85671b12439e9edf0db0`, app tree
  SHA-256 `7250b2cafd16352851031f194a2972f640bce2f61eaac840c0e4de5f9d65c26b`,
  executable SHA-256
  `e79ea0c9e882b0573ab93dcf591ca784eb114ccf4ae5eb988c5e5734df48a6c9`.
- Previous artifact/provenance/hash: `TBD`
- Current artifact/provenance/hash: `TBD`
- Known limits/blockers: N03 final clean-profile host evidence; H05 commercial
  license/notices and default-branch Dependabot disposition; signing/notarization.
