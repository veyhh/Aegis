# PushLock test driver

`aegis_pushlock_test.sys` tamamen AEGIS kaynak kodundan üretilir. Legacy
non-PnP x64 WDM control driver'ıdır; hardware, üçüncü taraf driver veya oyun
bağımlılığı yoktur. Hedef Windows 10 1809+; şu an x86/ARM64 build sunulmaz.

`DriverEntry` initialization probe'u yapar; dispatch tablosunu doldurur,
`IoCreateDeviceSecure` ile `\Device\AegisPushLockTest` device'ını oluşturur
ve `\DosDevices\AegisPushLockTest` symbolic link'ini kurar. SYSTEM ve
administrators ACL'i, özel security class GUID'i ve `FILE_DEVICE_SECURE_OPEN`
kullanır. Alt device isimleri reddedilir. Symbolic link failure halinde
device silinir; unload link'i ve device'ı siler.

`AEGIS_IOCTL_RUN_PUSHLOCK_TEST` vendor device type `0x8000`, function `0x800`,
`METHOD_BUFFERED`, read/write access kullanır. Input yoktur; output en az 20
byte olmalıdır. Yetersiz buffer, beklenmeyen input, bilinmeyen IOCTL veya
APC_LEVEL üstü IRQL hata döndürür. Invalid isteklerde `Information=0`.

Başarılı IOCTL transport sonucu `STATUS_SUCCESS` ve `Information=20` döner:

| Alan | Beklenen |
|---|---|
| Version | 1 |
| Passed | 1 |
| InitialValue | 0 |
| FinalValue | 1 |
| ErrorCode | 0 |

Her request bağımsız stack lock/counter kullanır. Acquire'dan önce
`KeEnterCriticalRegion`, release'den sonra `KeLeaveCriticalRegion` çağrılır.
EX_PUSH_LOCK opaque tutulur; bit layout'u okunmaz, API'ler emüle edilmez.
Yerel lock kullanımı, başka request'in tuttuğu lock'ı reinitialize etme riskini
önler; contention/mutual-exclusion doğrulaması sağlamaz.

## Build

WDK VS extension/toolset kurulu Developer Command Prompt:

```powershell
msbuild driver\pushlock\aegis_pushlock_test.vcxproj /p:Configuration=Release /p:Platform=x64
```

Alternatif: x64 Developer PowerShell, gerçek WDK ile:

```powershell
.\driver\pushlock\build-driver.ps1 -WdkVersion 10.0.28000.0
dumpbin /imports artifacts\driver\x64\Release\aegis_pushlock_test.sys
```

Alternatif yol `/kernel`, `/GS`, x64 native driver subsystem ve gerçek
`ntoskrnl.lib`, `hal.lib`, `Wdmsec.lib`, `BufferOverflowK.lib` kullanır.
Stack cookie entry `GsDriverEntry`'dir; üç PushLock çağrısı PE import
tablosunda görünmelidir. Bu, API'lerin gerçekten linklendiğini denetler.

Output unsigned'dır. İmzalama mevcut laboratuvar Windows policy'nize uygun
yapılmalıdır. Bu repo sertifika trust, boot veya code-integrity ayarlarını
değiştirmez. Native SCM testi [ana README](../../README.md) üzerinden yapılır.

INF, Type=1/StartType=3 legacy install metadata'sıdır. Harness INF'yi çalıştırmaz;
SCM kullanır. Catalog üretimi, InfVerif ve signed INF package kurulumu ayrıca
NOT VERIFIED; proje otomatik signing/Inf2Cat yapmaz.

`Wdmsec.lib` güvenli device creation için ek NTOSKRNL importları getirir.
Wine bunlarda da başarısız olabilir; parser hepsini raporlar. Bu durum
PushLock fonksiyonlarının kendi semantiğinin hatalı olduğunu tek başına
göstermez. Raporlardaki `required_ntoskrnl` yalnızca üç hedef API listesidir,
tüm importların listesi değildir.

Kaynaklar: [Microsoft PushLock initialization](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-exinitializepushlock),
[acquire/APC gereksinimi](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdm/nf-wdm-exacquirepushlockexclusive),
[güvenli named device creation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/wdmsec/nf-wdmsec-wdmlibiocreatedevicesecure).
