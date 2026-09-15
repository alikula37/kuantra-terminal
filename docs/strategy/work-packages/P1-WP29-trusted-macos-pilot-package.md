<!-- doc-role: current-work-package -->
# P1-WP29 — Trusted macOS Pilot Package

```yaml
work_package: P1-WP29
version: 1.0.0
status: InProgress
date: 2026-09-10
baseline_commit: a58935a
implementation_commit: dd58142
latest_artifact_source_commit: 4298acdbfa2e7de0028dcaf7a1c3780b4f69c1d0
latest_evidence_date: 2026-09-13
branch: main
depends_on: P1-WP28 (arm64 chain for M-series; x86_64 chain for dual), N05
release_gate: owner-pilot-approval, exact-architecture-evidence
```

Selection note (2026-09-15): P1-WP39 (A1.1) completed its account-scope closure and is
archived, so this package is selected again strictly for its still-open owner-host
obligations (N03/N05/H05/pilot access). No development proceeds under it without explicit
owner approval; A1.2 and every other integration package remain unapproved.

## Current continuation evidence

P1-WP31 local TP tracking is completed and archived with full evidence at
[P1-WP31](../../archive/strategy/work-packages/P1-WP31-local-tp-tracking.md).
Source `4298acd`, native run `34721385803`: both architectures passed **879 backend /
1 skipped / 2 warnings**, **154 frontend**, **813-key** i18n and exact DMG/WKWebView
synthetic local-tracking lifecycle. Local canonical CI additionally passed **880 backend**.
The private Release contains exactly the two verified DMGs identified in current
RELEASE_NOTES/STATUS. The Mac mini installed executable matches the published arm64
artifact, with user data preserved. Original reports are in
`artifacts/evidence/p1-wp31/4298acd/`. Remaining unchecked pilot/owner/host criteria
below are unchanged; this refresh is not Developer ID/notarization or production evidence.

## Amaç

Üç kişilik kapalı macOS pilotu için exact mounted-DMG smoke/N05 kanıtını,
manifest/checksum dosyalarını ve teknik olmayan kullanıcı talimatını tek fail-closed
paket akışına bağlamak. Varsayılan yol iki native mimari DMG'yi aynı kaynak kimliğiyle
paketler; ilk pilot sırası için açıkça seçilen arm64 modu yalnız Apple Silicon/M-series
kapsamı üretir ve Intel desteği iddia etmez. Pilot ekip aynı zamanda kontrollü doğrulama
grubudur: Intel katılımcı, hazır x86_64 DMG üzerinde runtime ve N03 install-lifecycle
kanıtı sağlayabilir. Apple Developer ID alınmadığı sürece paket **trusted pilot only**
olarak kalır; production veya commercial support claim'i açılmaz.

## Kabul kriterleri

- [x] Periodic refresh UX regression: Dashboard retains validated cards during
      background polls and shows an explicit stale-data notice after failure;
      overlapping polls do not abort slow reads. Market Charts retain the visible
      canvas and user zoom during successful background refresh. Three failing
      regression scenarios now pass; focused DOM **13**, full frontend **141**,
      EN/TR/DE **763/763** on macOS arm64. Source `bea2bab` passed native build and
      WKWebView smoke with COMPLETE provenance; full local CI exposed two pre-existing
      Release-title assertion mismatches. These are corrected in this change;
      combined source `957c328` passed full local CI (`MERGE READY`, frontend **141**,
      i18n **763/763**, native WKWebView and COMPLETE provenance). Exact read-only DMG
      smoke with market data/gateway disabled also passed, including clean detach;
      `hdiutil verify` was VALID. DMG SHA-256
      `eccee8c4f571cd50c9e3d81de8ba7dd567d0be7bdacbaca3ab508035a9778b73`, executable
      `5b0ef8bbabaa576ee4d1590358dc743da9fb2bb90ee1d8e7c231cf3fc1c23e34`.
      Reports: `dist/ux-intel-guard-local-ci-arm64.json` and
      `dist/ux-intel-guard-dmg-smoke.json`. This candidate is not installed/published yet.
- [x] Native Intel host classification follows Apple's `sysctlbyname` contract:
      missing translation key (`ENOENT`) means native; Rosetta and other errors
      remain rejected. Packaging and workflow share the Python guard. Focused
      architecture/packaging/workflow/release tests **43 passed**; actual Mac mini
      arm64 acceptance and x86_64 mismatch rejection verified. This is code/fixture
      evidence, not an Intel artifact or pilot runtime pass.
- [x] New Trade provider search uses a separate empty search field and confirmed
      instrument display, keeps non-catalog/literal symbols, cancels stale quote requests,
      and clears prices on instrument changes. Focused New Trade DOM **13 passed**.
- [x] Explicit SPOT/LONG/SHORT persists through canonical snapshots, projection rebuild,
      reopen, close/cancel and CSV/JSON evidence export. Spot purchase contradicting SELL
      is rejected. Additive schema 005 leaves old positions UNKNOWN; stamped/unstamped
      v3/v4 synthetic upgrades pass. Full backend **853 passed / 2 warnings** before
      the final UI changes; focused spot lifecycle/export scenario also passes.
- [x] Chart prices no longer assert USD without currency evidence; small prices retain
      significant digits. New Trade no longer fabricates equity percentages from a
      $10,000 constant or fills in unrequested stop/target prices. Missing estimates
      remain unavailable. Frontend build and EN/TR/DE **771/771** parity pass.
- [x] Rebuild and validate the corrected dual-architecture candidate. Native arm64 and
      native Intel build, full backend/frontend checks, exact mounted-DMG smoke and
      provenance all passed in GitHub Actions run `34664574672`; the Intel path uses
      static OpenSSL for its source-built cryptography dependency.

- [x] Settings manual pilot Release action replaces the fabricated update check;
      seven direct DOM tests cover native URL dispatch, browser link, failure/retry,
      missing bridge and timeout/late response. EN/TR/DE 742-key parity and build pass.
- [x] Refreshed clean arm64 package includes the manual update action; native browser
      handoff and exact DMG evidence are recorded before Release asset replacement.
      Source `119ae573`, DMG SHA-256 `7a07847d`, mounted executable SHA-256
      `9d70f2ac`, exact smoke SHA-256 `b59489cd`; native click-through opened the fixed
      private Release URL in Chrome from a clean temporary profile.
- [x] Pilot journal UI correction keeps the persisted theme toggle visible across the
      shell by applying light/dark DOM tokens, root `color-scheme` and a guarded settings
      sync; the standard journal exposes an explicit, confirmed `CANCELED` action for
      OPEN/CLOSED rows, preserves the tombstone instead of physically deleting evidence,
      validates the response and exposes a CANCELED filter. Canceled tombstones remain
      in the journal/evidence chain but are excluded from the dashboard asset-performance
      breakdown; canceling an OPEN row also removes it from the in-memory open-position
      list. The market-chart page is named and translated as `Market Charts` /
      `Piyasa Grafikleri` / `Marktcharts`, including its visible OHLCV and error content.
      Journal/Chart DOM coverage is `13 passed`; the portfolio regression is `11 passed`,
      full frontend coverage is `29 files / 138 tests`, i18n is `762/762`, and the arm64
      local candidate from source `0a5b8aa` passed locked local CI plus exact mounted-DMG
      smoke with `COMPLETE` provenance. The chart page now has a persistent symbol
      watchlist with provider-backed search, add/remove controls and an exact free
      XAUUSD OHLC fallback. Both New Trade and Market Charts require a candidate
      selection followed by an explicit confirmation; Enter never silently activates or
      fetches another instrument, while an unlisted exact symbol has an explicit
      UNKNOWN/manual confirmation path. The existing private
      Release asset still requires a later package refresh before pilot distribution.

- [x] Market symbol identity is user-confirmed on both New Trade and Market Charts. A
      typed `LINK` search returns exact provider candidates with name, exchange and source
      identity; selecting one opens a confirmation step, and only confirmation changes the
      committed symbol and permits a quote/candle request. Enter alone does not add,
      activate or fetch a symbol. The default catalog is only a starter watchlist, not the
      supported-instrument universe; when providers return no result, an exact manual
      symbol can be explicitly confirmed as `UNKNOWN/manual` without being rewritten.
      Focused Chart/New Trade DOM coverage is `13 passed`; full frontend coverage is
      `29 files / 138 tests`, i18n is `762/762`, and no paid data service, credential or
      broker path was added.

- [x] Provider-backed free instrument search is implemented for Binance Spot exchange
      inventory, Yahoo public search results and the exact Biquote XAU/USD route. Provider
      results preserve the exact source symbol and distinguish `READY`, `NO_MATCH` and
      `UNAVAILABLE`; crypto pair ranking prefers the usual USDT pair without hiding other
      exact candidates. Generic tickers such as `AAPL`, `BRK-B` and `MSFT` remain generic
      Yahoo/Stooq symbols and are never invented as USDT pairs. Mac live read-only checks
      returned results for `LINK`, `AAPL` and `XAUUSD`; no credential, trade or user data
      was used.

- [x] GitHub private Release'ın yalnızca repository read erişimi olan kullanıcılara
      dağıtım sağlayabildiği; Apple signing/notarization yerine geçmediği resmi kaynaklarla
      kaydedildi.
- [x] `scripts/prepare_pilot_package.py` exact `arm64` ve `x86_64` DMG, final mounted
      WKWebView smoke ve N05 raporlarını aynı source/tree/lock/truth identity ile doğrular.
- [x] Varsayılan dual package builder, Intel kanıtı eksikse exit 2 ile durur; açık
      `--architecture arm64` modu ise yalnız M-series kapsamını, `TRUSTED_MACOS_PILOT_ARM64`
      paket tipini ve Intel desteği olmadığını manifestte görünür kılar.
- [x] Ad-hoc N05 sonucu pakete yalnızca `AD_HOC_TRUSTED_PILOT_ONLY` olarak girer;
      production, commercial support, real-user outcome ve live execution claim'leri false kalır.
- [x] Paket `PILOT-MANIFEST.json`, evidence JSON'ları, `SHA256SUMS` ve standalone
      `PILOT-INSTRUCTIONS.md` üretir; mevcut user data, credential, Keychain veya migration
      bundle'ına dokunmaz.
- [x] Rosetta ile çevrilmiş x86_64 process native Intel build/package/smoke kanıtı olarak
      kabul edilmez; build job write izni read ile sınırlandırılır.
- [x] Private Release, Actions artifact, Apple Gatekeeper ve macOS model/OS sınırları
      [araştırma kaydında](../../release/PILOT-DISTRIBUTION-RESEARCH.md) açıkça ayrılır.
- [x] DMG build ve exact mounted-DMG smoke öncesinde `hdiutil verify` ile image/container
      bütünlüğü kontrol edilir; pilot talimatı indirilen DMG'de aynı kontrolü ister.
      Bu kontrol Gatekeeper, malware taraması, Developer ID veya notarization yerine
      geçmez; hiçbir güvenlik bypass'ı eklenmez.
- [x] Pilot ekip yalnızca paket tüketicisi olarak değil, native Intel Mac runtime/N03
      doğrulama hostu olarak da kullanılabilir; expected architecture, source provenance
      ve temiz profil koşulu kanıtlanmadan Intel veya production claim'i açılmaz. `75a4188`
      ile `run_local_ci.py --expected-architecture x86_64` native host/executable/provenance
      zincirini fail-closed doğrular; Mac mini'de yanlış x86_64 isteği exit 2 ile reddedildi.
- [x] Mac mini üzerinde `6646332` source commit'i için arm64 exact DMG, `hdiutil verify`
      (`VALID`), read-only mounted WKWebView smoke ve ad-hoc N05 evidence zinciri yeniden
      üretildi; N05 sonucu bilinçli olarak `BLOCKED/OWNER_REVIEW_REQUIRED` kaldı.
- [x] İlk M-series arm64-only pilot paketi source commit `6f8b1ed`'dan üretildi;
      manifest, checksum doğrulaması ve standalone M-series talimatı aynı pakette bulunur.
      Paket `dual_architecture_complete=false`, `intel_artifact_included=false` ve
      `intel_support_claim=false` alanlarını taşır. Paket durumu
      `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`'tır; pilot tag'i
      `pilot-v1.0.0-arm64`, manifest SHA-256
      `cdcb68b0cc662e2d54a2805b4d8672c258f1ad9f2df37d44420bca5c56594f10`,
      `SHA256SUMS` SHA-256 `53610c49f7dd10e89cf13070e5d423e88fb1e50100352df90fa956967dcdeab9`.
- [x] Önceki `6f8b1ed` paket kanıtı superseded historical evidence olarak korunur; güncel
      M-series package doğrulamasında kullanılmaz.
- [x] Önceki M-series arm64-only pilot paketi temiz source commit `119ae57`'dan üretildi;
      manifest, checksum doğrulaması ve standalone M-series talimatı aynı pakette bulunur.
      Paket `dual_architecture_complete=false`, `intel_artifact_included=false` ve
      `intel_support_claim=false` alanlarını taşır. Paket durumu
      `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`'tır; manifest SHA-256
      `4ed1e6cc4521223c6282257190d76deac50122c9763ccaa525f06bd1831cc9c2`,
      `SHA256SUMS` SHA-256 `a0bbf709e4236738f3f980f3a1b99e31e01faf908fb2e499030c8d9345bba18c`.
- [x] Önceki M-series private prerelease Release, `pilot-v1.0.0-arm64` tag'i ile
      yayımlandı; o zamanki altı asset'in GitHub SHA-256 digest'i local `SHA256SUMS` ve
      manifest ile eşleşti. Release URL'si:
      `https://github.com/alikula37/kuantra-terminal/releases/tag/pilot-v1.0.0-arm64`.
- [x] Mevcut `pilot-v1.0.0-arm64` private prerelease yeni tag oluşturmadan source commit
      `876efe0`'a bağlı arm64 DMG ile in-place yenilendi. Pilot kullanıcılarının kafasını
      karıştırmamak için Release indirme alanında yalnızca DMG bırakıldı; teknik evidence,
      manifest, checksum ve talimatlar repository/local audit paketinde tutulur. Güncel
      release body aynı pilot sınırını taşır;
      canonical `v1.0.0` Release/tag'i oluşturulmadı.
- [x] Gerçek x86_64 native host (`macos-15-intel`) exact DMG ve smoke/N05 zincirini
      üretti. Run `34664574672`, job `103473798705`, native `x86_64`, `hdiutil verify`
      VALID, mounted `wkwebview` smoke PASS ve provenance COMPLETE oldu.
- [ ] N03 temiz ikinci Mac profil/host install → launch → import/review → close/reopen
      kanıtı tamamlanır; pilot Intel Mac'i bu host olabilir. Bu paket kodla varsayılan
      olarak PASS ilan etmez.
- [x] Owner-approved `pilot-v1.0.0-arm64` private prerelease aynı tag korunarak iki
      native DMG ile güncellenir: arm64 ve x86_64. Canonical `v1.0.0` product Release/tag'i
      bu paketle oluşturulmaz.
- [ ] Owner, üç pilot kullanıcı için private repository read erişimini verir; erişim
      davetleri bu çalışma sırasında otomatik gönderilmez.

## Ürün ve güvenlik sınırı

Bu paket Kuantra'yı local-first Execution Intelligence & Trade Forensics Workstation
olarak tutar. AI order authority, live broker order, funding/transfer schema, tam hesap
PnL, Windows/Linux veya macOS 11 ve altı desteği eklemez. `SHA256SUMS` dosyasının geçmesi
dosya bütünlüğünü doğrular; Apple malware/notarization güveni veya finansal doğruluk
garantisi değildir. Kullanıcı Gatekeeper'ı kapatmaz ve karantina etiketini komutla silmez.

## Doğrulama

Focus testleri ve tam suite, gerçek mimari kanıtı üretene kadar her kod değişikliğinde
çalıştırılır. Package builder'ın güncel sonucu:

```text
python scripts/prepare_pilot_package.py --output dist/pilot-package-v1.0.0
→ PASS (dual native trusted-pilot package; N05 remains explicitly blocked)

python scripts/prepare_pilot_package.py --architecture arm64 \
  --output dist/pilot-package-v1.0.0-arm64
→ PASS (AD_HOC_TRUSTED_PILOT_ONLY_ARM64), optional arm64-only package mode
```

İlk çağrının önceki `BLOCKED` sonucu uygulama hatası değil, o tarihte eksik olan Intel
kanıtının doğru şekilde reddedilmesiydi. İki zincir hazır olduğunda varsayılan dual çağrı
artık **PASS** üretir; Phase 0 release-exit audit'i ise N05 ad-hoc signing/notarization
sınırı nedeniyle ayrı tutulur ve production PASS sayılmaz:

```text
shasum -a 256 -c dist/pilot-package-v1.0.0/SHA256SUMS
```

### Previous dual native pilot package evidence (2026-09-12; superseded by WP31)

GitHub Actions run `34664574672` source commit
`dd581425c2c298664512f0434fa93a726a9cacb5` üzerinden native `macos-latest/arm64` ve
`macos-15-intel/x86_64` job'larını PASS tamamladı. Her iki job Python `3.11.9`, Node
`20.20.2`, PyInstaller `6.22.2`, temiz tracked tree, aynı backend/frontend lock hash'leri
ve truth-matrix SHA-256 `8c647721dc2349cc8fd99d046bf14738121ac4f9a0b7c8b87cdb9f1ccfe681ab`
ile çalıştı. ARM64 backend sonucu **852 passed / 1 skipped / 2 warnings**, Intel backend
sonucu **852 passed / 1 skipped / 2 warnings**; her iki frontend job'unda **29 test file /
148 tests passed**, i18n parity **771/771**, TypeScript ve production build PASS oldu.

Güncel artifact/evidence kimlikleri:

- arm64 DMG SHA-256 `f8a4d4189ca6786f9ddb1e6d47f765ac6a3b4b11ffe8bc71a40bae8975189463`,
  mounted executable SHA-256 `31d709963c2cb4d1ad1bea72f5e2b020423ed9b9ce151eb292f5a94ad0def2ca`;
- x86_64 DMG SHA-256 `786370ff03270203fc95868e7c7faa17e214059d1a2625538609d48d36347f4c`,
  mounted executable SHA-256 `4a5991ad1cd8b98dce79aab69581542b970043d8a12894050af83c14ce419cfc`;
- final smoke report SHA-256 arm64 `c75ace0918bf48092d306c90b1ff06abc19d69c7cb06bb597e2a4dc1381d0685`,
  x86_64 `12ac288398f0efcca678b7e295d498794ed9e908060a96f36b192cc6480f7c97`;
- N05 report SHA-256 arm64 `67a97c45a7d6bacf5cdf3c908e50b2e0b32044f85e909988f2cfd958d590aa94`,
  x86_64 `f923ed7ada2632691c12d73ce4044976980d7f939b4df967393a776dcaa87f9b`.

Her iki DMG de read-only mount edilmiş, native matching executable çalıştırılmış,
`wkwebview`/controller smoke ve detach PASS olmuş, `hdiutil verify` sonucu VALID olmuştur.
N05 raporları `BLOCKED/OWNER_REVIEW_REQUIRED` durumunu korur: codesign yapısal olarak PASS
olsa da identity AD_HOC, Developer ID/hardened runtime/notarization yoktur. Bu nedenle
paket yalnızca üç kişilik trusted pilot içindir; production, Apple-trusted veya commercial
support claim'i açmaz. Paketleme adımı ve package içindeki `SHA256SUMS` doğrulaması da PASS
oldu; private `pilot-v1.0.0-arm64` Release aynı tag korunarak güncellendi ve doğrulanan
asset setinde yalnızca iki DMG bulunuyor. JSON/MD evidence dosyaları Release asset'i
yapılmayacak, repository ve audit package içinde kalacaktır.

### Superseded M-series package evidence (2026-09-11)

Temiz source commit `119ae573ce4e4885c2c83e0e8619ebd6038131dd` üzerinden arm64 pilot
zinciri yeniden üretildi. `uv run --offline --no-project --with-requirements
backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64
--report dist/manual-update-local-ci-final.json` **MERGE READY** döndürdü: backend
**829 passed / 2 warnings**, frontend **28 test files / 128 tests**, EN/TR/DE **703/703**,
TypeScript, production build, native arm64 PyInstaller ve native WKWebView smoke PASS;
provenance `COMPLETE`. Local-CI report SHA-256:
`9345f70dbe4b28ef419931faceb90f4650d06fc8e97dfa0f8afcc4e146d4715b`.

`bash scripts/package_macos.sh --architecture arm64 --output
dist/Kuantra-Terminal-1.0.0-arm64.dmg` **PASS** oldu; `hdiutil verify` sonucu `VALID`.
DMG SHA-256:
`7a07847da1134f6a098a491ee97a74db4e949b4ab373a99fa8bb086ada7f3e5d`.
`.venv/bin/python scripts/smoke_macos_dmg.py --dmg
dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report
dist/final-smoke-arm64.json` exact read-only mounted executable üzerinde **PASS** oldu;
native arm64, WKWebView/controller identity ve detach doğrulandı. Mounted executable
SHA-256 `9d70f2acfdd1b81b124323d0ad1c4b0f280ff76f526a462774c076791161a90b`, smoke report
SHA-256 `b59489cdd444447297da51b249936ddf8ddb0d5054da4c11c60623fb6e54b3ef`.

N05 preflight structurally valid fakat ad-hoc artifact ve Developer ID/notarization kanıtı
olmadığı için exit 2 ile beklenen `BLOCKED/OWNER_REVIEW_REQUIRED` sonucunu verdi. N05 report
SHA-256 `2ebf924aa122042f409522cc3637c017ba90530e81ced130f2008ad0365d061f`.
`prepare_pilot_package.py --architecture arm64 --pilot-tag pilot-v1.0.0-arm64` **PASS**
oldu; package type `TRUSTED_MACOS_PILOT_ARM64`, scope `APPLE_SILICON_M_SERIES_ONLY`,
status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`. Package yolu:
`dist/pilot-package-pilot-v1.0.0-arm64-119ae57/`; manifest SHA-256
`4ed1e6cc4521223c6282257190d76deac50122c9763ccaa525f06bd1831cc9c2`, `SHA256SUMS` SHA-256
`a0bbf709e4236738f3f980f3a1b99e31e01faf908fb2e499030c8d9345bba18c`. Paketteki beş payload dosyası
`shasum -a 256 -c SHA256SUMS` ile `OK` oldu. Package, P1-WP30 değişikliklerini içerir;
Intel artifact, production/commercial-support, live execution veya Apple-trusted claim
taşımaz.

Settings → Application updates → Open update page düğmesi, final mounted DMG içindeki
uygulamada temiz geçici profille native olarak doğrulandı. Düğme Chrome'da sabit private
Release URL'sini açtı; otomatik sürüm karşılaştırması, indirme, kurulum veya veri migration'ı
yapmaz. Bu click-through kanıtı kullanıcı verisine dokunmadı.

### Superseded provider-backed instrument-search candidate evidence (2026-09-11)

Implementation source commit `0a5b8aa2cbdc6528ba4b4b9ce52fb3d728ac6c00` is the exact
artifact source. It adds the provider search endpoint and hook, preserves provider symbol
identity through generic candle routing, keeps the static list as a default watchlist only,
and offers an explicit `UNKNOWN/manual` confirmation path when public providers have no
match. `LINK` is returned with Binance Spot `LINKUSDT`/`LINKUSDC` candidates and any exact
Yahoo candidates separately; `XAUUSD` has a deterministic exact Biquote candidate. The
Mac read-only provider check returned `READY` for `LINK`, `AAPL` and `XAUUSD`; it used no
credential, trade, user data or paid service. `NO_MATCH` and provider `UNAVAILABLE` are
different UI states, and Enter never activates a symbol.

Focused backend/provider/API regression is **31 passed / 2 warnings**. Full backend is
**838 passed / 2 warnings**. Focused New Trade/Market Charts DOM coverage is **13 passed**;
full frontend is **29 files / 138 tests**. `npm run check:i18n` reports **762/762** EN/TR/DE;
TypeScript and production build pass. The canonical local-CI command:

```text
uv run --offline --no-project --with-requirements backend/requirements.lock python
scripts/run_local_ci.py --expected-architecture arm64 --report
dist/p1-wp30-provider-backed-search-local-ci-arm64.json --smoke-timeout 90
```

returned **MERGE READY** on the Mac mini: backend **838 passed / 2 warnings**, frontend
**29 files / 138 tests**, i18n **762/762**, native arm64 PyInstaller, native WKWebView
smoke and provenance **COMPLETE**. The `uv --offline` flag records dependency-resolution
mode only; it is not runtime offline evidence. Local-CI report SHA-256:
`e0f094ae0fc9f1d6ed514b5329315db07f4f6837b6ea55e4e8128564acbfd5ab`.

The exact arm64 DMG
`dist/Kuantra-Terminal-1.0.0-arm64-provider-search.dmg` passed `hdiutil verify` with
**VALID**. DMG SHA-256:
`9b3eeb4a0e345010ebd9f089cd5eb90428867c4cbe902a937dc9afa9e960671b`. Exact read-only
mounted-DMG smoke passed native arm64, WKWebView/controller identity and detach;
mounted executable SHA-256:
`4eb94e83b54ff7f9c03878483d73f4469e18bf65437a9ed18538d3cca768f23e`, smoke report
SHA-256:
`40ff61d3a668b002f49355f3fdaae18369bc7a4afaeabe37b232dfc855cedeee`. Provenance is
`COMPLETE`; signing remains ad-hoc and this is not a notarization or production claim.
The private GitHub Release was not changed by this task.

### Superseded arm64 pilot Release refresh evidence (2026-09-11, source `876efe0`)

The provider-backed symbol-search runtime and the clarified pilot instructions were rebuilt
from source commit `876efe06fdac3e328d09b6ade429f792bf795314`. The tracked source tree was
clean with SHA-256 `18dc9ab63d139df23c5d97912a68691c25d7ed5d7d636343dfe2246a42764b6c`;
backend and frontend lock hashes remain `6291588602869af34e2a4db5d7244a627f4e139cbbd4b034b7cc07d890812399`
and `396c757d5733e9618aa71f665aa3f23f5d53fcdaa8d9ff67c11d172464fcc6bc`.

- Locked arm64 local CI returned **MERGE READY**: backend **838 passed / 2 warnings**,
  frontend **29 files / 138 tests**, EN/TR/DE **762/762**, TypeScript and production
  build, native arm64 PyInstaller/WKWebView smoke and provenance **COMPLETE**. Report
  SHA-256: `c30d9eb7930edc40d6468f38eb99b124dff59d65f1f605cc35dbb2f79f195e34`.
- Canonical `dist/Kuantra-Terminal-1.0.0-arm64.dmg` passed `hdiutil verify` with
  **VALID**. DMG SHA-256:
  `9d4c7e44b83483ce794d6f628b710bd7c651b8f42ae8e98d4b40c5341d3f627d`.
- Exact read-only mounted-DMG smoke passed native arm64 and WKWebView/controller identity;
  mounted executable SHA-256:
  `f6fef3f39e2e8d591c133ac1607a6ef62f1abffea186223a07c61f4086a26082`, smoke report
  SHA-256: `fcb1a469bdfe2330c2c5093af984fbb4389153e83a7206a12efacfec2517fd5c`.
- N05 preflight remains intentionally **BLOCKED/OWNER_REVIEW_REQUIRED** with exit 2
  because the pilot DMG is ad-hoc and has no Developer ID/notarization proof. Report
  SHA-256: `58dd0b39d298cedd8d4e5e28669e4c04c5595292d80f3242580cb5ce37ab6ddf`.
- `prepare_pilot_package.py --architecture arm64 --pilot-tag pilot-v1.0.0-arm64`
  returned **PASS**. The six-file package is
  `dist/pilot-package-pilot-v1.0.0-arm64-current/`; manifest SHA-256 is
  `04d220ff4bcef12fb4dfdc0ed8f9ccea1bea3e0f60e617f14c50167ed439886a`,
  `SHA256SUMS` SHA-256 is
  `6ca82cd3e36a8b879f2be234c2d846ead36cd5099ab064f858805f0677963d5a`, and all five
  payload entries passed `shasum -a 256 -c SHA256SUMS` with `OK`.
- The existing private `pilot-v1.0.0-arm64` prerelease was refreshed in place with
  `gh release edit` and `gh release upload --clobber`; no tag was created and the
  canonical `v1.0.0` Release was not changed. The installed
  `/Applications/Kuantra Terminal.app` now has executable SHA-256
  `f6fef3f39e2e8d591c133ac1607a6ef62f1abffea186223a07c61f4086a26082`; the previous
  bundle was moved recoverably to the user's Trash and the application data directory
  was not touched.

### Historical confirmed-symbol-selection candidate evidence (2026-09-11)

Source commit `d6c8c3a7c5c053e3c89e32af3195ab1262ae6219` ve tracked source tree
`bd28325800c52d404e7257f20142b7a5c8ff6ebbd50176623916221b5d21d265` temizken:

- `npm test` → **29 test files / 136 tests passed**; focused chart/New Trade DOM
  coverage is **11 passed**. `npm run check:i18n` → **754/754** EN/TR/DE; `npx tsc
  --noEmit` and `npm run build` → **PASS**.
- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-confirmed-symbol-selection-clean-local-ci-arm64.json --smoke-timeout 90`
  → **MERGE READY**; backend **832 passed / 2 warnings**, frontend **29 test files / 136
  tests**, i18n **754/754**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. The `uv --offline` flag only describes
  dependency-resolution mode; it is not runtime offline evidence. Report SHA-256:
  `2156c5fe343d704fd9263a5611364d4391ee7c7d125ab1881f397da06c4a6551`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64-confirmed-symbol-selection.dmg` → **PASS**;
  `hdiutil verify` → **VALID**. DMG SHA-256:
  `2cdfbdb729ceae5e4ace4bf2c8eb8fcce2b6a6938e8fd8c134867b36152b920e`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64-confirmed-symbol-selection.dmg --expected-architecture
  arm64 --report dist/final-smoke-arm64-confirmed-symbol-selection.json` → **PASS** on
  the exact read-only mounted executable; native `arm64`, WKWebView/controller identity
  and detach passed. Executable SHA-256:
  `4e24c7000fda993b0ac20dfc5126d3b4d76540edff84a5815e343ac6d8e3045e`; smoke report
  SHA-256: `548c9a2becf499dbad62fdb31240d953c8d7fc9eaf60a9edb425a8ba8bbf53e5`.
- No trade, user data or credentials were used or changed. The private GitHub Release was
  not changed by this task; its existing asset must be refreshed explicitly before pilot
  users receive this confirmed-symbol-selection build. The current installed app is the
  local candidate at `/Applications/Kuantra Terminal.app` only after an explicit install;
  this evidence does not create a notarization or production claim.

### Previous chart watchlist/XAU candidate evidence (2026-09-11)

Source commit `e0e7b75dc1078221504cad84618bce828d818c56` ve tracked source tree
`86431a850220fcdbee714cf6fe112182ce0662efcc679057edbb209b8d3e2d8f` temizken:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-chart-watchlist-xauusd-clean-local-ci-arm64.json --smoke-timeout 90`
  → **MERGE READY**; backend **832 passed / 2 warnings**, frontend **29 test files / 135
  tests**, i18n **742/742**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. Report SHA-256:
  `679d9335512324b749f1d9976cc1fcff5e2710b22d3c888101190046a8f8c126`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64-chart-watchlist-xauusd.dmg` → **PASS**;
  `hdiutil verify` **VALID**. DMG SHA-256:
  `3a4c8dcd48d72def7cd8b956f360335e384c1660c594315b67500709eb63558b`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64-chart-watchlist-xauusd.dmg --expected-architecture
  arm64 --report dist/final-smoke-arm64-chart-watchlist-xauusd.json` → **PASS** on the
  exact read-only mounted executable; native `arm64`, WKWebView/controller identity and
  detach passed. Mounted executable SHA-256:
  `9fefa2e5a6d97a5ff07053fdcf352761fafa600ca21b8aef945a3746e0fd101c`; smoke report
  SHA-256: `d3ecc0ed180ab7d0a0e6e61371d9c78bca8317191de10c4e6002affbea976cd9`.
- Exact XAUUSD request was manually verified against the free public Biquote OHLC path;
  a real 15-minute response returned **193** valid bars. The source identity stays
  `XAUUSD`; no `GC=F` futures or `PAXGUSDT` substitution occurs. The native app was
  installed at `/Applications/Kuantra Terminal.app`; the previous bundle was moved
  recoverably to `/Users/kula/.Trash/Kuantra Terminal.app.before-chart-watchlist-xauusd`.
  No real trade or user data was changed. The private GitHub Release was not changed;
  its assets require an explicit refresh before pilot distribution.

### Previous analytics/chart correction candidate evidence (2026-09-11)

Source commit `8db2e533f0dde972c0aba8ad6617da5ca722ec06` ve tracked source tree
`42600b6fb58197473b29c968ad82b21e4e356abab5a23c834ed8c8ea19ae402e` temizken:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-cancel-breakdown-chart-i18n-clean-local-ci-arm64.json --smoke-timeout 90`
  → **MERGE READY**; backend **830 passed / 2 warnings**, frontend **29 test files / 133
  tests**, i18n **734/734**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. Report SHA-256:
  `6dea4f5dbec9bb98696031fdf0a5f7ebc517d017f98426f9be361e01d3cc4a31`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64-cancel-breakdown-chart.dmg` → **PASS**;
  `hdiutil verify` **VALID**. DMG SHA-256:
  `99c4849becfdb17472af035d05aa01ac6c815b1b1c7459e4776fad54d9b69fc9`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64-cancel-breakdown-chart.dmg --expected-architecture
  arm64 --report dist/final-smoke-arm64-cancel-breakdown-chart.json` → **PASS** on the
  exact read-only mounted executable; native `arm64`, WKWebView/controller identity and
  detach passed. Mounted executable SHA-256:
  `615e4cc7933d3f8b50b1e2fcba618f704db0b96fb29af2ca2aa2b0a96eb15e1d`; smoke report
  SHA-256: `1a1a1ddca0d5fff89767b9e3194f0ffe1c19e0be1a604c83e8334c2b89e7701b`.
- Native click-through confirmed that existing `CANCELED` tombstones no longer create
  dashboard performance buckets, while journal audit history is preserved. Turkish,
  English and German market-chart navigation, title, subtitle, OHLCV labels and error
  states were checked; light/dark chart rendering was toggled and restored. No real trade
  or user data was changed. The candidate is installed at
  `/Applications/Kuantra Terminal.app`; the previous bundle was moved recoverably to
  `/Users/kula/.Trash/Kuantra Terminal.app.before-cancel-chart-fix`. The private GitHub
  Release was not changed in this code task, so its assets must be refreshed explicitly
  before pilot distribution.

### Previous pilot UI correction candidate evidence (2026-09-11)

Source commit `e9f702b6b49da41e6249a0044abb3f2f0363bfc7` ve tracked source tree
`c1bdf652b2b84301ed7fa3eb33fc625e7c6f97b8176af5ac471296ab2a906509` temizken:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python
  scripts/run_local_ci.py --expected-architecture arm64 --report
  dist/p1-wp29-ui-corrections-clean-local-ci-arm64.json --smoke-timeout 90` →
  **MERGE READY**; backend **829 passed / 2 warnings**, frontend **29 test files / 133
  tests**, i18n **716/716**, TypeScript, production build, native arm64 PyInstaller,
  WKWebView smoke and provenance **COMPLETE**. Report SHA-256:
  `82d63f1193dc16e0e2c14fb48f07f86fb847863bcaa81bf628ee00f1266f1046`.
- `bash scripts/package_macos.sh --architecture arm64 --output
  dist/Kuantra-Terminal-1.0.0-arm64.dmg` → **PASS**; `hdiutil verify` **VALID**.
  DMG SHA-256: `be1773896472e1827a359104954f4b025067959884ef01e890dac468b7b1b4b1`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg
  dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report
  dist/final-smoke-arm64-ui-corrections-clean.json` → **PASS** on the exact read-only
  mounted executable; native `arm64`, WKWebView/controller identity and detach passed.
  Mounted executable SHA-256: `155913f6ebc268d863a30977a0e48a889a29c5badab5f8afa43e8233d5e4902a`;
  smoke report SHA-256: `cd76d0a9a26c6de6233b3b355445f6915d47251f7128a1d84bca4107fd657d90`.
- Native app click-through showed the translated Light/Dark control and `İptal et`
  action on existing OPEN/CLOSED rows. No real trade was canceled; the original dark
  preference was restored. The candidate is installed locally at
  `/Applications/Kuantra Terminal.app`; the previous app bundle was moved recoverably
  to the user's Trash. The private GitHub Release was not changed in this code task, so
  its assets must be refreshed explicitly before pilot distribution.

### Superseded M-series çalıştırması (2026-09-10)

2026-09-10 tarihinde `6f8b1ed` source commit'i ile aşağıdaki zincir PASS oldu:

- `uv run --offline --no-project --with-requirements backend/requirements.lock python scripts/run_local_ci.py --expected-architecture arm64 --report dist/p1-wp29-local-ci-arm64-release.json --smoke-timeout 90` → **MERGE READY**; backend **816 passed / 2 warnings**, frontend **25/104**, i18n **608/608**, native arm64 build/smoke ve provenance `COMPLETE`. Local-CI report SHA-256: `d2dd6d663441c0202e8940018111a8190589ce82a3e1324c040ab6aea02595ae`.
- `bash scripts/package_macos.sh --architecture arm64 --output dist/Kuantra-Terminal-1.0.0-arm64.dmg` → **PASS**; `hdiutil verify` exact image için `VALID`. DMG SHA-256: `d2f8151e24e29ae0a3800165d823dfd3e6f44a2ef3b95f04674a6ed9ead6e540`.
- `.venv/bin/python scripts/smoke_macos_dmg.py --dmg dist/Kuantra-Terminal-1.0.0-arm64.dmg --expected-architecture arm64 --report dist/final-smoke-arm64-release.json` → **PASS**; exact read-only mounted executable, native WKWebView/controller ve detach. Mounted executable SHA-256: `c76315073ef72687bef2bb90dc9c0ec5adfdc1aff912898aa717562aaae2e870`; report SHA-256: `40573464091be5d43a3c31b973980559ebc4fe1112a4fa87948f37a428cda080`.
- `.venv/bin/python scripts/run_n05_macos_distribution_preflight.py ...` → **BLOCKED/OWNER_REVIEW_REQUIRED** (exit 2), çünkü ad-hoc artifact Developer ID/notarization ticket taşımıyor. Report SHA-256: `19fa90a538db42d9a110b58359c2c55a33e87cb3a082f9494f25fa948a092eb4`.
- `.venv/bin/python scripts/prepare_pilot_package.py --architecture arm64 --pilot-tag pilot-v1.0.0-arm64 --dist dist --output dist/pilot-package-pilot-v1.0.0-arm64` → **PASS**; package type `TRUSTED_MACOS_PILOT_ARM64`, scope `APPLE_SILICON_M_SERIES_ONLY`, status `AD_HOC_TRUSTED_PILOT_ONLY_ARM64`. Paket içindeki beş dosyanın `shasum -a 256 -c SHA256SUMS` doğrulaması **OK**; manifest SHA-256 `cdcb68b0cc662e2d54a2805b4d8672c258f1ad9f2df37d44420bca5c56594f10`, `SHA256SUMS` SHA-256 `53610c49f7dd10e89cf13070e5d423e88fb1e50100352df90fa956967dcdeab9`.

Paket yolu: `dist/pilot-package-pilot-v1.0.0-arm64/`. Bu çalışma kullanıcı verisi,
credential, Keychain veya migration bundle kullanmadı. Release private prerelease olarak
yayındadır; üç pilot kullanıcısının repository read erişimi ve gerçek cihazlarda
install-lifecycle çalıştırması hâlâ owner/host kapısıdır. Canonical `v1.0.0` product
Release/tag'i ve dual package bu işlemle oluşturulmadı.

## Superseded frontend pilot-flow hardening (`8da8019`)

The pilot-facing import → review → Evidence Pack path now has an explicit truth and
failure boundary in the UI:

- [x] Missing or `null` PnL/R values remain visibly unknown in the journal, open-position
      and CSV preview surfaces; they are never rendered as zero. Weekly review completion
      and reopen actions are disabled when period, timezone or as-of inputs differ from
      the loaded snapshot.
- [x] Evidence Pack JSON responses, weekly review responses and CSV preview/import
      responses are runtime-validated before rendering. Malformed successful responses
      remain visible errors and cannot be interpreted as empty, complete or successful
      evidence.
- [x] Evidence Pack JSON/HTML/CSV export uses the native desktop save bridge on pywebview;
      the UI reports ready only when the bridge confirms an actual save, and reports
      cancellation/failure separately. Browser fallback behavior remains bounded.
- [x] CSV file replacement clears the previous preview/review, accepts case-insensitive
      `.csv`/`.txt` extensions, aborts stale preview requests and exposes a keyboard-
      accessible dropzone/modal.
- [x] Journal reads `201` records as a page sentinel, keeps the first `200`, loads older
      pages with an offset, de-duplicates by trade ID and preserves the loaded page when
      a load-more request fails.
- [x] Journal, CSV import, weekly review and Evidence Pack additions are covered by the
      synchronized EN/TR/DE translation contract.

Verification for this bounded change is recorded by `8da8019`: frontend **25 test
files / 116 tests**, i18n **670/670**, TypeScript `--noEmit` and production build pass;
the locked arm64 local CI also passes backend **816 tests / 2 warnings**, native arm64
PyInstaller build, WKWebView smoke and `COMPLETE` provenance on a clean commit. The
native bridge/export path has focused unit/DOM coverage, but the exact rebuilt DMG still
requires a manual pilot click-through of import → review → Evidence Pack → native
JSON/HTML/CSV save before this package can be called end-to-end pilot-validated. The
existing private prerelease asset set was then refreshed in place from this source commit;
that asset set is superseded by the clean `119ae57` package above; no new Release/tag was
created for the historical refresh.

Dual GitHub Release, Apple signing/notarization, pilot kullanıcı erişimi ve
clean-host yürütmesi bu work package'ın otomatik kod kapıları değildir; owner/host
kapılarıdır. M-series private prerelease yayımlanmış olsa da canonical product Release
yetkisi verilmiş değildir.

## Superseded private Release asset yenilemesi (2026-09-10)

2026-09-10 tarihinde mevcut `pilot-v1.0.0-arm64` private prerelease, aynı tag korunarak
source commit `8da8019ae93513c474a3122d450cffb40f66261b` ile üretilen arm64 paketle
yenilenmişti. Bu bölüm yalnızca audit history içindir; güncel DMG SHA-256
`900ce30ebe93bc9a1ded399c0067edfa2f7475b892da9193ff608e579f291a76`, mounted executable
SHA-256 `6b3b9985058933f655b2a0e1ece69a41b7d51eb28f00c2c2c0023a7792e41ce1`, final smoke
report SHA-256 `81eb80f7a77191325c43e313a4ce1664aefe4ba27f4f76292adaaaf97d34d6fd` ve N05
report SHA-256 `5b24b09d1d42aef456777ab398a71e23d1e1a9ee42e0bfad8dc74840454b1ca3` olarak
kanıtlandı. N05 ad-hoc artifact nedeniyle `BLOCKED/OWNER_REVIEW_REQUIRED` durumundadır;
bu beklenen pilot sınırıdır. Release body, DMG, evidence JSON'ları, manifest, checksums ve
standalone talimat asset'leri aynı arm64 pilot kapsamını taşır. Local-CI report SHA-256
`cde81fe18e0346b534b4828589c462bc4d7381719611df959b5a7000f6bf0c79`, tracked source tree
SHA-256 `964e672c8c05da2b490de83856a8a4e81e2c4b77f2a333751bdc783547f764cd`, package
manifest SHA-256 `1b196a795a82d2dc7b9fea006f0e12e4cf55690956a75b797bbedce4235bc548` ve
`SHA256SUMS` SHA-256 `5577f7ae8b69197b36b754a4290472ad9dcca8314c74d62fbce72911af67e89e` olarak
doğrulandı.
