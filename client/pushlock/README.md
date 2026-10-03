# PushLock user-mode client

Client `\\.\AegisPushLockTest` device'ını read/write açar ve bir kez
`AEGIS_IOCTL_RUN_PUSHLOCK_TEST` gönderir. Admin/SYSTEM device ACL'i nedeniyle
native reference test elevated çalıştırılır.

```powershell
cmake -S client/pushlock -B build/client -A x64
cmake --build build/client --config Release
.\build\client\Release\aegis_pushlock_client.exe
```

Yalnızca Windows toolchain kullanılır. MSVC client statik CRT ile build olur;
Wine prefix'e ayrıca Visual C++ runtime kurmak gerekmez. CMake driver build
yapmaz.

Stdout her durumda `AEGIS_PUSHLOCK_TEST` başlığı ve `key=value` satırlarıdır.
Başarıda:

```text
AEGIS_PUSHLOCK_TEST
driver_loaded=true
device_opened=true
ioctl_success=true
bytes_returned=20
version=1
passed=1
initial_value=0
final_value=1
error_code=0
result=PASS
```

| Exit code | Anlam |
|---|---|
| 0 | Tam ABI ve counter sonucu PASS |
| 2 | Device açılamadı; `win32_error` kaydedilir |
| 3 | IOCTL transport başarısız |
| 4 | IOCTL tamamlandı fakat boyut/version/alan kontrolü başarısız |

`ioctl_success=true` yalnızca transport sonucudur. PASS için `bytes_returned`,
version, Passed, counter ve ErrorCode birlikte denetlenir. Device her
tamamlanmış açılıştan sonra kapatılır. Client servisi kurmaz/başlatmaz.

Başarısız açılışta `driver_loaded=false` client'ın device'a erişemediğini
anlatır; driver'ın hiç map edilmediğinin kanıtı değildir. Parser, raw logda
başka kanıt yoksa `loaded=null` tutar. Client stdout Wine debug logundan
ayrı dosyada tutulur.
