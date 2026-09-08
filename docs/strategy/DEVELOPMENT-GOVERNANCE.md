# KDG-001 — Kuantra Geliştirme Yönetişimi

```yaml
document_id: KDG-001
version: 1.0.2
status: Accepted
date: 2026-09-08
strategy: KPS-001@1.1.0
```

## Amaç

Ürün/mimari kararının, agent tarafından üretilen kodun ve GitHub'a giden değişikliğin aynı
kanıt zincirinde kalmasını sağlamak. Hız, yalnız test ve acceptance criteria korunuyorsa değerdir.

## Roller

2026-09-08 açıklaması: aşağıdaki model adları tarihsel görev dağılımıdır; kullanıcının
güncel direktifi önceliklidir (Mac devamında istenen subagent: GPT-5.6 Luna). Subagent
zorunlu değildir. Lead agent entegrasyon/review yürütür; nihai ürün/mimari kararı
ürün sahibinindir. Güncel kalan iş sırası [STATUS](STATUS.md) ve
[tek roadmap](PRODUCTION-READINESS-PLAN.md)
ile okunur; eski `Active` paket sayısı faz çıkışı veya sonraki iş sırası değildir.

### Lead agent — ürün/mimari sınırlarının korunması ve entegrasyon

- Faz sırasını, ürün sınırını ve ADR'leri korur.
- Her değişikliği küçük, ölçülebilir work package'a böler.
- Kullanılırsa scoped coding agent'a implementation brief verir.
- Diff'i güvenlik, veri bütünlüğü ve scope bakımından inceler.
- Test/benchmark kanıtını doğrular; gerektiğinde işi geri gönderir.
- Kullanıcı onayı olmadan dış servis, production secret, release veya canlı işlem açmaz.

### Coding agent — güncel kullanıcı model direktifiyle

- Yalnız verilen work package kapsamında kod değiştirir.
- Önce ilgili kod/testleri okur; architecture scope genişletmez.
- Test-first veya en az regression-test-with-fix yaklaşımı kullanır.
- Var olan kullanıcı değişikliklerini korur.
- Başarı ölçütü olarak “kod yazıldı” değil, acceptance criteria + test kanıtı verir.
- ADR değiştirmez; çelişki görürse işi durdurup lead agent'a bildirir.

### Kullanıcı — ürün sahibi

- Major strateji/ADR değişikliği, fiyat/marka, mevzuat risk kabulü ve release zamanını onaylar.
- GitHub kimlik doğrulamasını kendi cihazında güvenli biçimde yapar.
- Token veya private key'i sohbet mesajına yapıştırmaz.

## Tercih edilen çalışma biçimi

1. Lead agent Faz backlog'undan tek bir work package seçer.
2. Paket `Ready` olmadan coding başlamaz.
3. Gerekliyse coding agent aynı chat içinde subagent olarak çalışır. Böylece kullanıcı prompt taşımaz ve lead agent
   bağlamı, diff'i ve test sonucunu aynı görev içinde denetler.
4. Aynı working tree'ye iki yazıcı agent paralel verilmez. Paralel agent yalnız read-only audit,
   test veya bağımsız dosya alanlarında kullanılır.
5. Implementasyon tamamlanınca lead agent diff'i okur, eksik testleri çalıştırır ve acceptance criteria'yı
   madde madde kapatır.
6. Her work package ayrı commit olur. Commit edilmemiş kullanıcı değişiklikleri asla ezilmez.
7. Push/PR ancak local gate'ler geçince yapılır.

Local gate'in resmi sözleşmesi ve tek komutu KDG-002
([Yerel CI ve merge gate politikası](LOCAL-CI-POLICY.md)) içindedir. GitHub Actions kotası
doluyken remote workflow sonucu beklenmez; KDG-002 raporu olmadan `main` merge edilmez.

Kullanıcının ayrı chat'te Terra kullanması mümkündür; bu durumda KWT-001 şablonuyla tam prompt
taşınmalı, Terra'nın commit SHA'sı bu chat'e geri verilmelidir. Tercih edilen yol aynı chat içindeki
subagent'tır; bağlam ve entegrasyon kaybı daha düşüktür.

## Branch, commit ve PR standardı

- Branch: `codex/<phase>-<work-package>-<short-name>`
- Work package: `P0-WP01`, `P1-WP03` gibi kalıcı kimlik.
- Commit: `<type>(<scope>): <özet> [P0-WP01]`
- Types: `fix`, `feat`, `refactor`, `test`, `docs`, `build`, `security`.
- PR başlığı: `[P0-WP01] Truth-safe market data states`
- PR açıklaması: problem, kapsam, kapsam dışı, risk, migration, test kanıtı, rollback.
- Bir PR tek work package taşır; mekanik refactor ile davranış değişikliği ayrılır.

## Definition of Ready

Bir work package ancak şunlar varsa `Ready` olur:

- problem ve kullanıcı riski;
- dosya/modül kapsamı;
- davranış sözleşmesi ve acceptance criteria;
- kapsam dışı maddeler;
- migration/backward compatibility kararı;
- gerekli test sınıfları;
- güvenlik/data-loss kontrolü;
- bağlı ADR ve strateji sürümü.

## Definition of Done

- Acceptance criteria'nın tamamı otomatik test veya açık doğrulama kanıtıyla kapalı.
- Yeni sentetik/default production davranışı eklenmemiş.
- Error/no-data/stale durumları sessizce success'e çevrilmemiş.
- Loglarda secret/PII yok.
- Migration idempotent ve rollback/restore yolu belgeli.
- Backend/frontend ilgili testleri, compile/type/lint gate'leri geçmiş.
- Kullanıcı-görünür davranış docs/release note'a işlenmiş.
- Kod ile claim aynı şeyi söylüyor.

## Faz kapısı

Work package'ların bitmesi fazın bittiği anlamına gelmez. Faz exit criteria'sı güncel roadmap'teki
ürün metriği ve soak/pilot kanıtıyla kapanır. Coding agent fazı kendi başına “complete” ilan edemez.

## GitHub secret politikası

- Remote URL credential içermez: `https://github.com/alikula37/kuantra-terminal.git`.
- Tercih: işletim sistemi Git Credential Manager veya `gh auth login --web`.
- Fine-grained PAT gerekirse yalnız bu repo, kısa son kullanma tarihi ve asgari izin:
  `Contents: Read and write`, PR kullanılacaksa `Pull requests: Read and write`.
- `Workflows: Read and write` yalnız workflow dosyası gerçekten değiştirilecekse eklenir.
- Token chat'e, `.env` örneğine, shell history'ye, remote URL'ye veya test output'una yazılmaz.
- Yanlışlıkla görünen token derhal revoke edilir; yalnız metinden silmek yeterli değildir.

## Değişiklik geçmişi

### 1.0.2 — 2026-09-08

- Başlangıç AGENTS/PRODUCT/roadmap/STATUS/aktif WP olarak tekilleştirildi; tarihsel
  paketler arşivlendi. Güncel sıra STATUS'tan okunur, model rolü çoğaltılmaz.

### 1.0.1 — 2026-09-08

- İnsan ürün otoritesi, güncel model direktifi ve KRR-001 backlog önceliği netleştirildi.

### 1.0.0 — 2026-09-05

- Lead-agent/Terra ayrımı, work package lifecycle, Git/PR standardı ve secret politikası tanımlandı.
