<!-- doc-role: archived -->
> Historical reference only. Not a current work order. Unchecked acceptance items remain open;
> see [current status](../../../strategy/STATUS.md). Read only for a relevant task.

# P0-WP05 — Python Universal Dependency Lock

```yaml
work_package: P0-WP05
status: Verified
phase: Phase 0 - Truth & Safety Release
strategy: KPS-001@1.0.0
baseline_commit: 04f168ced12d74d4d1ad540d6ec2456d0af01755
owner: Axiom (GPT-5.6 SOL)
implementer: gpt-5.6-terra
```

## Problem

`backend/requirements.txt` ve `backend/requirements-desktop.txt` yalnız alt sınır kullanır.
Aynı checkout yerelde FastAPI 0.128.8, temiz CI'da FastAPI 0.141.1 çözümlemiştir. İki sürümün
route yapısı farklıdır ve P0-WP04 sırasında üç platformu aynı anda kırmıştır. Bir release'in
dependency grafiği tag içeriğinden yeniden üretilemiyorsa test ve audit kanıtı release'e ait
sayılmaz.

## Mimari karar

Kaynak manifestler insanlar tarafından düzenlenen minimum aralıkları korur. Python 3.11 için
tek, platform marker'larını koruyan universal lock `uv 0.12.1` ile üretilir. CI, release ve Linux
smoke container yalnız hash doğrulamalı lock dosyasından kurar. Lock elle düzenlenmez.

Bu paket `pyproject.toml`/`uv.lock` proje migrasyonu yapmaz. Phase 0'da en küçük güvenli geçiş,
mevcut pip/PyInstaller akışını koruyan universal hashed requirements çıktısıdır.

## Dosya kapsamı

- Yeni `backend/requirements-all.in`
- Yeni, generated `backend/requirements.lock`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `packaging/linux/Dockerfile.smoke`
- Yeni `backend/tests/test_python_dependency_lock_contract.py`
- Bu paket için gerekli strateji durum belgeleri

## Davranış sözleşmesi

1. `requirements-all.in`, iki mevcut kaynak manifesti include eder; dependency kaynağı
   kopyalanmaz.
2. Lock şu komutun semantiğiyle üretilir: `uv pip compile --universal --python-version 3.11
   --generate-hashes backend/requirements-all.in -o backend/requirements.lock`.
3. Lock tüm çözümlenmiş paketleri exact `==` sürüm ve SHA-256 hash ile taşır; Windows/Linux/macOS
   marker'ları tek dosyada korunur.
4. CI ve release `pip install --require-hashes -r backend/requirements.lock` kullanır. Kaynak
   manifestlerden doğrudan install yasaktır.
5. Linux smoke Dockerfile aynı lock'u kullanır.
6. Setup cache key yalnız manifestlere değil lock'a da bağlıdır.
7. Contract testi unhashed/unpinned dependency, workflow bypass ve eski doğrudan install
   komutlarını reddeder.
8. Kullanılan GitHub action major sürümleri Node 24 uyumlu güncel majorlara yükseltilir; action
   referansları floating branch değil sabit major etiketi kullanır.

## Acceptance criteria

- [x] Universal lock oluşturuldu ve generated header/komut kaydı var.
- [x] Lock'ta 90 exact package entry ve 2.408 SHA-256 hash var.
- [x] CI/release/Docker yalnız lock'tan kuruyor; bypass contract testiyle engelleniyor.
- [x] Lock ve source-drift contract testleri geçiyor: ilgili grup 8 passed.
- [x] Temiz Python 3.11 venv lock install başarılı; FastAPI 0.141.1 çözümlemesi doğrulandı.
- [x] Locked venv full backend suite: 263 passed, 1 skipped.
- [x] Frontend: audit 0; 29 test passed; production build başarılı.
- [x] Remote Windows/macOS/Ubuntu CI ve desktop smoke yeşil: run `33960912844`.
- [x] GitHub Actions Node 20 deprecation uyarısı kalktı.

Docker image'ın uçtan uca yeniden build edilmesi P0-WP10 packaging exit paketinde yapılır. Bu
paketin kapısı Dockerfile'ın yalnız lock kurduğunu kontrat testiyle ve aynı lock'ın Ubuntu runner
üzerinde gerçek kurulumuyla doğrulamaktır.

## Kapsam dışı

- Python 3.12/3.13 desteği
- `pyproject.toml` veya tam `uv sync` proje migrasyonu
- Otomatik Dependabot/Renovate merge
- Model ağırlıkları veya market-data binary asset'leri
- Uygulama davranış değişikliği

## Durdurma koşulları

- Universal çözüm PyQt6/WebEngine ile macOS WebKit koşullarını doğru marker'layamazsa tek lock
  zorlanmaz; OS-bazlı lock dosyalarına dönülür.
- Hash mode editable/local path dependency gerektirirse paket genişletilmez; istisna açık ADR
  olmadan `--no-deps`, `--no-verify` veya unhashed fallback eklenmez.

## Teslim

Terra lock ve install yüzeylerini uygular, commit/push yapmaz. Axiom generated diff'i, dependency
grafiğini, üç platform marker'larını ve bütün gate sonuçlarını inceler; remote CI kanıtını kapatır.

## Remote kanıt

- PR run: `33960912844` — Windows, macOS ve Ubuntu başarılı.
- Aynı SHA push run: `33960910675` — başarılı.
- Doğrulanan head: `1326e5ecc3503cc8b08d12dc64a15a7413399213`.
- GitHub-hosted runner çıktısında eski Node 20 action-runtime anotasyonu yoktur.
