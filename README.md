# AEGIS

AEGIS, Wine/Linux altında meşru Windows NT kernel driver uyumluluğunu ve
bütünlük mekanizmalarını araştırmak için oluşturulmuş deneysel bir test
framework'üdür. Modern driver importlarının nerede ve nasıl başarısız
olduğunu küçük, bize ait test driver'larıyla görünür kılar.

**AEGIS bir anti-cheat bypass projesi değildir.** Bağımsız çalışır; oyun,
Vanguard veya başka üçüncü taraf driver dosyası gerektirmez.

## Neden var?

Bir PE image'ın map edilmesi, driver servisinin kayıtlı olması veya
DriverInit adresinin bulunması, driver'ın çalıştığını göstermez. AEGIS bu
aşamaları ayrı raporlar ve gerçek IOCTL sonucu olmadan PASS üretmez.
Paylaşılan gerçek dünya gözlemleri araştırma bağlamıdır; bu repository'nin
driver'ıyla elde edilmiş test sonucu olarak sunulmaz.

## Mimari

```text
Windows: gerçek WDK -> aegis_pushlock_test.sys
         MSVC/CMake -> aegis_pushlock_client.exe

Reference: Windows SCM -> kendi driver'ımız -> client -> IOCTL sonucu
Wine:      dedicated prefix -> SCM -> Wine ntoskrnl -> aynı driver/client
                                      |
                             raw log + client stdout + exit codes
                                      |
                           JSON compatibility report -> text report
```

- `driver/pushlock/`: minimal x64 WDM test driver'ı, ortak ABI, INF ve build.
- `client/pushlock/`: Windows user-mode client ve CMake.
- `tools/`: Windows reference script'i, Wine harness, parser ve renderer.
- `tests/`: sentetik parser fixture'ları ve taklit Wine ile harness testleri.
- `reports/`: yerel test çıktıları; Git'e eklenmez.
- `docs/`: [mimari](docs/architecture.md), [MVP](docs/mvp.md),
  [rapor modeli](docs/compatibility-model.md), [doğrulama kaydı](docs/verification.md).

## MVP kapsamı

Yalnızca **PushLock**: `ExInitializePushLock`,
`ExAcquirePushLockExclusiveEx`, `ExReleasePushLockExclusiveEx`.
IOCTL her seferinde kendisine ait bir push lock initialize eder, exclusive
acquire yapar, korunan counter'ı `0 -> 1` değiştirir, release eder ve 20 byte
structured result döndürür. DriverEntry ayrıca initialize çağrısını yoklar.

Bu repository şu an uyumluluğu ölçen test altyapısıdır. Wine ntoskrnl için
PushLock implementasyonu veya no-op/fallback eklemez. Wine'da eksik API
bulunması beklenen ve değerli bir FAIL sonucudur. Bir smoke-test PASS'i,
contention, shared locks, fairness veya kernel güvenlik eşdeğerliği kanıtı
değildir. Diğer primitive'ler implement edilmemiştir.

## Güvenlik ve etik sınırlar

- Anti-cheat atlatma, spoofing, sanallaştırmayı gizleme ve sahte security
  state üretme yoktur.
- Integrity check devre dışı bırakılmaz. Boot/code-integrity policy
  değiştirilmez; testler mevcut policy'ye uygun imzalı driver kullanmalıdır.
- Riot process'lerine müdahale, driver injection, üçüncü taraf binary
  analizi veya patchleme yoktur.
- Device yalnızca SYSTEM ve administrators için açılır; IOCTL read/write
  erişimi ve bounded `METHOD_BUFFERED` output gerektirir.
- Windows yükleme testi kendi araştırma ortamınızda yapılır. Wine tarafında
  ayrı, açıkça seçilmiş prefix kullanılır; mevcut servis/image korunur.

## Windows build

Gerekenler: x64 Windows 10 1809+ hedefi, Visual Studio C++ araçları,
gerçek Windows SDK/WDK ve client için CMake 3.20+. Rapor script'leri Python
3.10+ kullanır. Linux üzerinde WDK taklit edilmez.

WDK entegrasyonu kurulu bir Developer Command Prompt'ta:

```powershell
msbuild driver\pushlock\aegis_pushlock_test.vcxproj /p:Configuration=Release /p:Platform=x64
cmake -S client/pushlock -B build/client -A x64
cmake --build build/client --config Release
```

WDK dosyaları kurulu olduğu halde VS toolset kaydı eksikse x64 Developer
PowerShell'de gerçek WDK header/library'leriyle alternatif build:

```powershell
.\driver\pushlock\build-driver.ps1 -WdkVersion 10.0.28000.0
```

Sürümü kendi kurulu WDK'nızla değiştirin; parametre verilmezse kurulu kernel
başlıklarına sahip en yeni sürüm seçilir. Her iki driver yolu **unsigned**
`artifacts/driver/x64/Release/aegis_pushlock_test.sys` üretir. Script güvenlik
ayarlarını değiştirmez. Windows yüklemesi için mevcut laboratuvar
code-integrity policy'nize uygun imzalama gerekir; signing/load rejection
sonucunu PushLock hatası olarak yorumlamayın.

### Windows reference test

Policy'nizin kabul ettiği imzalı driver ile elevated PowerShell'de:

```powershell
.\tools\windows-run-test.ps1 `
  -Driver .\artifacts\driver\x64\Release\aegis_pushlock_test.sys `
  -Client .\build\client\Release\aegis_pushlock_client.exe
```

Script yalnızca `aegis_pushlock_test` servisini oluşturur, başlatır, client'ı
çalıştırır, `finally` içinde stop/delete dener ve `reports/windows-pushlock-*`
altına rapor yazar. Başarıda exit `0`, failure/inconclusive durumda `1`;
önkoşul hataları PowerShell error üretir. Mevcut AEGIS servisi varsa durur.
Driver/client ABI build detayları için [driver README](driver/pushlock/README.md)
ve [client README](client/pushlock/README.md).

## Linux / Wine test

Gerekenler: Linux, x64 driver/client ile uyumlu Wine, Bash, GNU coreutils
(`timeout`, `mktemp`) ve Python 3.10+. Windows'ta build ettiğiniz **aynı**
driver/client dosyalarını Linux'a taşıyın; rapor SHA-256 değerlerini kaydeder.
Wine sürümüne göre sonuç değişebilir; prefix architecture ve sürümünü kaydedin.

```bash
export WINEPREFIX="$HOME/.local/share/aegis/wine-prefix"
mkdir -p "$WINEPREFIX"
WINEDEBUG=+ntoskrnl,+module,+service wineboot -u > /tmp/aegis-wineboot.log 2>&1
bash tools/wine-run-test.sh \
  /absolute/path/aegis_pushlock_test.sys \
  /absolute/path/aegis_pushlock_client.exe
```

`wine-run-test.sh` kurulum script'ini kendisi çağırır. Önceden manuel kurulum
yapmayın. `WINEDEBUG=+ntoskrnl,+module,+service` tüm test komutlarında
kullanılır. Terminalde yalnızca sonuç ve çıktı dizini gösterilir:

```text
AEGIS PushLock: FAIL
Reports and raw logs: .../reports/pushlock-.../
```

Her run: `wine.log`, komut bazlı `.sc.*` raw logları, `client.stdout`
(çalıştırıldıysa), `wine-version.txt`, `metadata.json`, `report.json`,
`report.txt`. `AEGIS_TIMEOUT_SECONDS=30` varsayılandır; 124 timeout sonucu
FAIL olur. `AEGIS_WINE_BIN`, `AEGIS_PYTHON`, `AEGIS_REPORT_DIR` isteğe bağlıdır.
Client verilmezse yalnızca failure mapping yapılır; IOCTL NOT VERIFIED ve
overall FAIL olur. Stop/delete failure da overall FAIL üretir; kurtarma için
driver image korunur. Cleanup hatalarını raw logdan inceleyin. Paylaşılan
prefix süreçleri öldürülmez ve alakasız registry ayarları değiştirilmez.

Yalnızca kurulum yapmak için:

```bash
bash tools/wine-install-driver.sh /absolute/path/aegis_pushlock_test.sys
```

Bu bağımsız komut servisi kurulu bırakır. Kaldırmak için aynı prefix ile
`wine sc.exe stop aegis_pushlock_test`, ardından
`wine sc.exe delete aegis_pushlock_test` çalıştırın; yalnızca başarılı
temizlemeden sonra kendi kopyalanmış image'ınızı silin. Tekrar test için
servis ve önceki image kaldırılmış olmalıdır.

## Compatibility report örneği

Aşağıdaki örnek **sentetik fixture** sonucudur:

```text
AEGIS Compatibility Report

Test: PushLock
Driver image loaded: PASS
DriverInit address found: NOT VERIFIED
DriverInit reached: PASS
Driver loaded: FAIL
Device created: NOT VERIFIED
Device opened: NOT VERIFIED
IOCTL completed: NOT VERIFIED

Missing NTOSKRNL APIs:
- ExAcquirePushLockExclusiveEx
- ExInitializePushLock
- ExReleasePushLockExclusiveEx

Overall:
FAIL
```

Logu tekrar analiz etmek veya raporu okumak için:

```bash
python3 tools/parse-wine-log.py reports/<run>/wine.log \
  --client-output reports/<run>/client.stdout --client-exit-code 0 \
  --metadata reports/<run>/metadata.json --output reports/<run>/report.json
python3 tools/aegis-report.py reports/<run>/report.json
```

`--client-exit-code` değerini gerçek process exit code'dan alın. Başarısız
çalıştırma için `0` yazmayın. Parser/renderer exit kodları: `0` PASS, `1`
FAIL veya yetersiz kanıt, `2` input/report hatası. Log-only analizde client
argümanlarını çıkarın. JSON `null`, görüntüde **NOT VERIFIED** anlamındadır.

## Testler ve mevcut doğrulama

```bash
python3 -m unittest discover -s tests -v
bash -n tools/wine-common.sh tools/wine-install-driver.sh tools/wine-run-test.sh
```

Python testleri üçüncü taraf paket istemez. Harness testleri Wine yerine
açıkça sentetik bir process kullanır ve platformda Bash yoksa SKIP üretir.
CI Ubuntu'da parser/harness/shellcheck, Windows'ta yalnızca client build yapar.
CI bir native driver veya gerçek Wine uyumluluk sertifikası değildir.

Yerel doğrulama: driver/client build ve otomatik testler PASS. Native Windows
driver yükleme + IOCTL PASS ve gerçek Linux/Wine run **NOT VERIFIED**.
MVP'nin tüm başarı kriterleri henüz karşılanmış sayılmaz.
[Doğrulama kaydı](docs/verification.md) kanıtları ve ortam limitlerini listeler.

## Roadmap

| Milestone | Amaç | Durum |
|---|---|---|
| M0 — Failure Mapping | Loader aşamaları ve eksik import raporları | Altyapı ve sentetik testler mevcut |
| M1 — PushLock | Kendi driver'ımızla initialize/acquire/release | Kod ve build mevcut; runtime doğrulaması bekliyor |
| M2 — Rundown Protection | Yaşam döngüsü semantiği | Kapsam dışı |
| M3 — Work Items | Kuyruk ve dispatch semantiği | Kapsam dışı |
| M4 — Precise Timing | Hassas zaman kaynakları | Kapsam dışı |
| M5 — CPU/IPI Semantics | CPU/IPI davranışı | Kapsam dışı |
| M6 — Real-world Driver Compatibility | Meşru, izinli driver uyumluluğu | Sonraki araştırma |

MIT lisansı: [LICENSE](LICENSE).
