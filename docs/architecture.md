# Mimari

## Araştırma sınırı

AEGIS kendi test driver'ını, client'ını ve ölçüm araçlarını içerir.
Wine, Windows loader veya güvenlik state'i değiştirilmez. Wine PushLock
implementasyonu geliştirilecekse bu smoke test önce bir baseline üretir;
ayrı bir Wine kaynak değişikliği bu MVP kapsamında değildir.

Üç katman vardır:

1. **Native test oracle:** gerçek Windows kernel'da kendi driver/client
   çiftimiz. API sözleşmesi, ABI ve temel sequence beklenen sonuçla ölçülür.
2. **Compatibility execution:** aynı artifact'ler Wine SCM/ntoskrnl/device
   katmanından geçirilir. Wine version ve SHA-256 değerleri kaydedilir.
3. **Evidence/reporting:** raw log, ayrı client stdout, process exit codes ve
   aşama kanıtlarından sürümlü JSON/text raporu üretilir.

## Driver yaşam döngüsü

DriverEntry başında açık bir `AEGIS: driver_init_reached=true` marker'ı
vardır. Initialize probe'u, güvenli device creation, symbolic link ve
dispatch registration tamamlanınca `driver_loaded=true` marker'ı basılır.
Bu marker'ların Wine sürümündeki DbgPrint loglamasına bağlı olarak görünmesi
garanti değildir. Başarılı client device open, image/entry/device aşamalarının
gerçekleştiğine dolaylı kanıt sağlar; rapor bu kanıtın kaynağını saklar.

Her IOCTL'de stack üzerinde naturally aligned EX_PUSH_LOCK bulunur.
Bu lock/counter başka request'lerle paylaşılmaz. Entry initialization probe'u
yalnızca initialize çağrısını çalıştırmak içindir; daha sonra kullanılmaz.
Global/shared lock yeniden initialize edilmez. Acquire/release flags `0`;
normal kernel APC delivery critical region ile kontrol edilir.

IRP completion tek helper'da yapılır. Unsupported IRP/IOCTL, invalid input
ve kısa output buffer hata döndürür; output uzunluğu success haricinde sıfırdır.
Create/close/cleanup synchronous tamamlanır. Driver başka device stack'ine
attach olmaz; callback, thread, worker veya timer oluşturmaz. Açık client
handle'ları kapandıktan sonra normal SCM unload link/device'ı temizler.

## Harness yaşam döngüsü

`wine-run-test.sh` önkoşulları denetler, benzersiz rapor dizini oluşturur ve
prefix'te `.aegis-pushlock.lock` diziniyle AEGIS run'larını seri hale getirir.
Installer servis yokluğunu numeric SCM error `1060` ile doğrular. Existing
service, image veya dışarıya çözülen drivers dizini üzerinde işlem yapmaz.
Servis yalnızca Type=1, demand-start olarak kurulur.

Start/client/stop/delete işlemleri GNU timeout ile sınırlandırılır. Linux
process exit code'ları Windows error code'larının düşük byte'ı olabilir;
`1060/1062` ayrımı bu nedenle komutun raw diagnostic metninden yapılır.
Start başarısız olsa da owned service için cleanup çalışır. 1062 (already
stopped) temizleme başarısıdır; diğer stop/delete hataları overall FAIL
oluşturur. Stop/delete teyit edilemezse image korunur.

Normal çıkış ve INT/TERM için EXIT trap cleanup ve raporlama yapar. SIGKILL,
host kapanması veya file-system failure için cleanup garanti değildir.
Stale lock/service durumunda önce raw log ve prefix'i inceleyin; AEGIS dışı
süreçleri kapatmayın. Wineserver kill veya prefix'in recursive silinmesi
harness'in parçası değildir. Harici bir süreç aynı prefix'te registry/service
değiştirirse lock onu engellemez.

`windows-run-test.ps1` native SCM ve aynı rapor modelini kullanır; yalnızca
owned service'i stop/delete eder, kaynak artifact'i silmez. Mevcut driver
imzalama/code-integrity policy'sini değiştirmez. İzin/driver signing önkoşulu
karşılanmadığında native test NOT VERIFIED kalır.

## Log güvenilirliği

Wine debug metni kararlı bir API değildir. Parser bilinen missing-function ve
loader-error pattern'lerini, hedef `.sys` için image/entry trace'lerini ve
driver marker'larını tanır. `DriverInit = address` yalnızca address discovery
alanını etkiler; entry execution veya PASS olarak yorumlanmaz. Image/entry
aşamaları sonraki hatalarda silinmez.

Missing/unimplemented diagnostic'ler bu run logunda gözlenmiş çağrılardır;
call site'a kesin attribution her Wine sürümünde sağlanamaz. Dedicated prefix
bu belirsizliği azaltır. Parser başka module'lardaki unimplemented çağrıları
da ayrı listeler ve konservatif şekilde FAIL verir. İlk crash sonraki API
çağrılarının gözlenmesini engelleyebilir. Eksik API listesi Wine'ın tam
export inventory'si değildir.

Client stdout ayrı parse edilir. Header, tekrar etmeyen field'lar, ABI
boyutu/version, tüm result değerleri ve exit `0` gerekir. Diagnostic veya
cleanup failure bu sonucu FAIL'e çevirir. Boş/malformed log ve client'sız
mapping için overall FAIL, ilgili aşamalarda NOT VERIFIED gösterilir.

Kaynak: [Wine ntoskrnl loader](https://github.com/wine-mirror/wine/blob/master/dlls/ntoskrnl.exe/ntoskrnl.c)
ve [Wine sc.exe kaynak kodu](https://github.com/wine-mirror/wine/blob/master/programs/sc/sc.c).
Bu bağlantılar sürüm pin'i değildir; gerçek run'ın Wine version'ı raporlanır.
