# PushLock MVP runtime doğrulaması

Kayıt: **3 Ekim 2026, Europe/Istanbul**. Bu takip çalışmasında yeni özellik,
primitive veya mimari değişikliği yapılmadı. Driver, client ve harness kodu
değiştirilmedi. Mevcut artifact'ler ve Windows runtime önkoşulları denetlendi;
native denemeler ve otomatik testler gerçekten çalıştırıldı. Windows üzerinde
Wine/WSL runtime denemesi yapılmadı.

## Doğrulama tablosu

| Kontrol | Durum | Kanıt / sınır |
|---|---|---|
| Build pipeline | PASS | Önceki gerçek Windows WDK + MSVC/CMake yerel build kanıtı; mevcut hash'ler aynı. Bu takipte yeniden build yapılmadı. |
| Driver build | PASS | Önceki gerçek WDK 10.0.28000.0 build'i; mevcut x64 Native PE ve üç hedef import dumpbin ile tekrar doğrulandı. |
| Client build | PASS | Önceki MSVC Release build'i; mevcut x64 Windows CUI PE ve gerçek client çalıştırması doğrulandı. |
| Parser tests | PASS | Bu takipte 23 parser/CLI testi yeniden çalıştırıldı. |
| Harness tests | PASS | Bu takipte 10 mock-Wine harness testi yeniden çalıştırıldı; gerçek Wine değildir. |
| Native Windows driver load | NOT VERIFIED | Servis oluşturma OpenSCManager FAILED 5 ile engellendi; driver start yapılmadı. |
| Native Windows IOCTL test | NOT VERIFIED | Driver yüklenemedi; başarılı IOCTL çalıştırılmadı. Client device open aşamasında hata verdi. |
| Real Wine driver install | NOT VERIFIED | Linux laptopta henüz çalıştırılmadı. |
| Real Wine driver start | NOT VERIFIED | Linux laptopta henüz çalıştırılmadı. |
| Real Wine client test | NOT VERIFIED | Linux laptopta henüz çalıştırılmadı. |
| Compatibility report | PASS | Gerçek Windows izin/client hata çıktılarından mevcut parser ile JSON ve text rapor üretildi. Raporun overall sonucu FAIL; native başarı iddiası değildir. |

Yerel supported build yolu önceki çalışmada başarılı olan doğrudan gerçek
WDK build script'idir. Visual Studio `.vcxproj` denemesi önceki çalışmada
**FAIL**, `MSB8020: WindowsKernelModeDriver10.0 toolset bulunamıyor` sonucunu
vermişti; bu yol veya uzak CI bu takipte yeniden doğrulanmadı.

## Artifact doğrulaması

| Artifact | Byte | İmza | SHA-256 |
|---|---:|---|---|
| `artifacts/driver/x64/Release/aegis_pushlock_test.sys` | 19456 | NotSigned | `420c5444278c33f3346dfa44352208f7a13f64d585fea52d5ebc2d3c5b81391b` |
| `build/client/Release/aegis_pushlock_client.exe` | 144896 | NotSigned | `48402aef70673b6ca8307439a9f9a7ee5357b3353d40ba1feabb7320164c5dd9` |

Her iki PE `8664 machine (x64)` olarak doğrulandı. Driver subsystem Native,
client subsystem Windows CUI. Driver'ın `ntoskrnl.exe` importları içinde
`ExInitializePushLock`, `ExAcquirePushLockExclusiveEx` ve
`ExReleasePushLockExclusiveEx` mevcut. Artifact'lere imza eklenmedi veya
binary değişikliği yapılmadı.

## Native Windows denemesi ve tam engeller

Ortam: Windows NT `10.0.26200.0`, AMD64.

1. WindowsPrincipal admin/elevation sorgusu: `elevated_admin=false`.
2. `Get-AuthenticodeSignature`: driver `NotSigned`.
3. `bcdedit /enum`: exit `1`, `The boot configuration data store could not
   be opened. Erişim engellendi.` Bu sonuçtan BCD boot ayarı tahmin edilmedi.
4. Salt okunur `NtQuerySystemInformation(SystemCodeIntegrityInformation)`:
   NTSTATUS `0x00000000`, return length `8`, options `0x0000f401`.
   Kernel code integrity enabled `true`, test-signed content allowed `false`,
   kernel debug mode enabled `false`, HVCI kernel enabled `true`. Bunlar
   aktif runtime state'idir; BCD içeriğini okuyabildiğimiz iddia edilmez.
5. Ön kontrol `sc.exe query aegis_pushlock_test`: `1060`, servis yok.
6. Gerçek `sc.exe create ... type= kernel start= demand binPath= <artifact>`:
   exit `5`, **`[SC] OpenSCManager FAILED 5: Erişim engellendi.`** Servis
   oluşturulamadı. Bu, imza doğrulama hatası veya PushLock hatası değildir.
7. Mevcut `windows-run-test.ps1` gerçek çalıştırma: exit `1`,
   **`Run this reference test from an elevated PowerShell in your Windows
   test environment.`** Önkoşul aşamasında durdu.
8. Mevcut client gerçek çalıştırma: exit `2`:

   ```text
   AEGIS_PUSHLOCK_TEST
   driver_loaded=false
   device_opened=false
   ioctl_success=false
   win32_error=2
   result=FAIL
   ```

   Device açılamadığı için `initial_value`/`final_value` gözlenmedi. Başarılı
   IOCTL yapılmış veya counter değişmiş varsayılmadı. Bu, client'ın beklenen
   failure davranışıdır; native PushLock başarı testi **NOT VERIFIED**.

9. Son kontrol `sc.exe query aegis_pushlock_test`: `1060`, servis yok.
   Owned service oluşmadığından stop/delete çağrılmadı; temizlenecek servis
   veya yüklendiği gözlenmiş driver yok. Artifact'ler yerinde korundu.

Standart x64 test-driver yolu, mevcut test ortamının kabul ettiği dijital
imzalı/test-signed driver ve elevated SCM erişimi gerektirir. HVCI altında
unsigned binary desteklenmez. Burada test-sign kabulü kapalı ve servis
oluşturma yetkisi yok olduğundan runtime testi ilerletilemedi. Test-signing,
Secure Boot, HVCI, code integrity, sertifika trust store veya boot ayarları
değiştirilmedi; başka bir driver üzerinden yükleme denenmedi.

Kaynaklar: [Microsoft test-signed driver yükleme kuralları](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/the-testsigning-boot-configuration-option),
[Code Integrity runtime bit alanları](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation).

## Gerçek çalıştırılan ek kontroller

```text
python -m unittest discover -s tests -v
Ran 33 tests ... OK
unittest exit: 0
bash -n (üç shell script): 0
ShellCheck 0.11.0 (üç shell script): 0
dumpbin driver headers/imports ve client headers: 0
```

33 testin 23'ü parser/CLI, 10'u mock-Wine harness testidir. Bunlar Linux/Wine
runtime sonuçlarının yerine kullanılmaz. Mevcut `wine-install-driver.sh`,
`wine-run-test.sh`, `parse-wine-log.py`, `aegis-report.py` gereken akışı
destekliyor; minimal kod düzeltmesi gerekmedi.

Gerçek Windows deneme çıktıları mevcut parser/renderer'a verildi. JSON/text
rapor dosyaları üretildi; her iki CLI beklenen FAIL sonucu için exit `1`
döndürdü. Bu exit code bir rapor üretim hatası değildir. Native load ve
DriverInit aşamaları NOT VERIFIED, device open/IOCTL transport alanları FAIL,
overall FAIL. Missing NTOSKRNL listesi boş; henüz driver'a ulaşılmadığı için
bu durum API desteği kanıtı değildir.

Yerel kanıt dizini: [`reports/runtime-closure-20261003/`](../reports/runtime-closure-20261003/).
İçeriği: artifact/session/Code Integrity JSON, native runner ve SCM logları,
client stdout, PE header/import dump'ları, unittest logu, metadata ve
[readable compatibility report](../reports/runtime-closure-20261003/report.txt).
Bu kanıtlar `reports/` ignore kuralı nedeniyle Git'e eklenmez.

## Linux laptopta tam ve sıralı komutlar

Önce repository'yi Linux laptopta `$HOME/AEGIS` konumuna taşıyın (farklıysa
`cd` satırını değiştirin). **Git clone tek başına artifact'leri getirmez:**
yukarıdaki iki build dosyasını aynı relative path'lerine ayrıca kopyalayın.
Linux'ta gerçek Wine/wineboot, Bash, GNU coreutils ve Python 3.10+ önceden
kurulu olmalı. Bu komutlar bu Windows oturumunda çalıştırılmadı.

```bash
(
  set -eu
  cd "$HOME/AEGIS"
  test "$(uname -s)" = Linux
  for tool in wine wineboot python3 bash timeout sha256sum; do
    command -v "$tool" >/dev/null
  done
  python3 -c 'import sys; assert sys.version_info >= (3, 10)'

  printf '%s  %s\n' \
    420c5444278c33f3346dfa44352208f7a13f64d585fea52d5ebc2d3c5b81391b \
    artifacts/driver/x64/Release/aegis_pushlock_test.sys \
    48402aef70673b6ca8307439a9f9a7ee5357b3353d40ba1feabb7320164c5dd9 \
    build/client/Release/aegis_pushlock_client.exe | sha256sum -c -

  mkdir -p reports "$HOME/.local/share/aegis"
  export AEGIS_REPORT_DIR
  AEGIS_REPORT_DIR=$(mktemp -d "$PWD/reports/linux-runtime-XXXXXX")
  export WINEPREFIX
  WINEPREFIX=$(mktemp -d "$HOME/.local/share/aegis/pushlock-XXXXXX")
  export WINEARCH=win64
  export WINEDEBUG=+ntoskrnl,+module,+service
  export AEGIS_TIMEOUT_SECONDS=30

  wine --version > "$AEGIS_REPORT_DIR/wine-version.txt"
  timeout --kill-after=5s 90s wineboot -u \
    > "$AEGIS_REPORT_DIR/wineboot.log" 2>&1

  # FAIL normal bir araştırma sonucu olabilir; log analizini durdurmayın.
  set +e
  bash tools/wine-run-test.sh \
    "$PWD/artifacts/driver/x64/Release/aegis_pushlock_test.sys" \
    "$PWD/build/client/Release/aegis_pushlock_client.exe"
  aegis_run_rc=$?

  aegis_run_dir=$(find "$AEGIS_REPORT_DIR" -mindepth 1 -maxdepth 1 \
    -type d -name 'pushlock-*' -print -quit)
  if [[ -z "$aegis_run_dir" || ! -f "$aegis_run_dir/metadata.json" ]]; then
    printf 'Harness tamamlanmadı; önkoşul/boot loglarını inceleyin: %s\n' "$AEGIS_REPORT_DIR"
    exit 2
  fi

  # Bootstrap ve komut bazlı raw logları da dahil ederek logları birleştir.
  # Tekrarlanan diagnostic'ler parser tarafından deduplicate edilir.
  shopt -s nullglob
  cat "$AEGIS_REPORT_DIR/wineboot.log" "$aegis_run_dir/wine.log" \
    "$aegis_run_dir"/wine.log.sc.* > "$aegis_run_dir/wine-complete.log"

  # Harness zaten parser/report çalıştırır. Gerçek client exit code ile
  # birleştirilmiş raw logu açıkça tekrar analiz edip raporu gösteriyoruz.
  aegis_parse_args=("$aegis_run_dir/wine-complete.log" \
    --metadata "$aegis_run_dir/metadata.json" \
    --output "$aegis_run_dir/report.json")
  if [[ -f "$aegis_run_dir/client.stdout" ]]; then
    aegis_client_rc=$(python3 -c \
      'import json,sys; print(json.load(open(sys.argv[1]))["client_exit_code"])' \
      "$aegis_run_dir/metadata.json")
    aegis_parse_args+=(--client-output "$aegis_run_dir/client.stdout" \
      --client-exit-code "$aegis_client_rc")
  fi
  python3 tools/parse-wine-log.py "${aegis_parse_args[@]}"
  aegis_parser_rc=$?
  python3 tools/aegis-report.py "$aegis_run_dir/report.json" \
    --output "$aegis_run_dir/report.txt"
  aegis_report_rc=$?
  cat "$aegis_run_dir/report.txt"
  printf '\nHarness=%s Parser=%s Report=%s\nPrefix: %s\nEvidence: %s\n' \
    "$aegis_run_rc" "$aegis_parser_rc" "$aegis_report_rc" \
    "$WINEPREFIX" "$aegis_run_dir"
  if (( aegis_run_rc == 0 && aegis_parser_rc == 0 && aegis_report_rc == 0 )); then
    exit 0
  elif (( aegis_run_rc == 2 || aegis_parser_rc == 2 || aegis_report_rc == 2 )); then
    exit 2
  else
    exit 1
  fi
)
```

Akış `wine-run-test.sh` içinde sıralı olarak gerçekleşir:

1. Installer `.sys` dosyasını prefix'e kopyalar; `sc.exe create ... type= kernel`
   ile Type=1/demand-start servisini kurar. **Installer'ı önce ayrıca
   çalıştırmayın:** run script kurulumunu kendi yapar ve mevcut servisi reddeder.
2. Servis start edilir; başarılıysa client çalışır. Wine stderr raw `wine.log`,
   client stdout ayrı `client.stdout` dosyasına yazılır.
3. EXIT trap owned service'i stop/delete eder. Başarılı cleanup'tan sonra
   kopyalanmış image silinir; prefix ve kaynak artifact'ler korunur.
4. Metadata, parser, JSON ve readable report üretilir. Başarı `0`, failure
   veya inconclusive test `1`, önkoşul/report üretim hatası `2` olabilir.

Cleanup için metadata'daki gerçek `stop_exit_code`/`delete_exit_code` değerlerini
ve `.sc.*` loglarını inceleyin. `0/0` başarılı SCM cleanup kanıtıdır; `255`
çalıştırılmamış adımdır. Cleanup hatası varsa image korunur. Başka bir mevcut
servisi veya paylaşılan prefix'i silmeyin. Normal stop/delete sonucundan
bağımsız olarak gerçek Wine aşamaları laptop run'ı görülene kadar NOT VERIFIED.

Native Windows'ta beklenen fakat bu oturumda gözlenmeyen başarı:

```text
driver_loaded=true
ioctl_success=true
initial_value=0
final_value=1
result=PASS
```

**MVP tamamlandı mı: NO.** Native driver load/IOCTL PASS ve aynı artifact'lerle
gerçek Linux/Wine ölçümü hâlâ doğrulanmadı.
