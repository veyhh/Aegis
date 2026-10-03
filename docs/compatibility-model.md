# Compatibility report modeli

Bir JSON dosyası bir testin bir execution run'ını temsil eder. Formatın
`schema_version` değeri `1`'dir. Makine sözleşmesi
[compatibility-report.schema.json](compatibility-report.schema.json) içinde.
Python producer/renderer standard library kullanır; CLI tam JSON Schema
validation yapmaz. Tüketici, isterse Draft 2020-12 validator kullanabilir.

Şemadaki test kimlikleri geleceğe ayrılmıştır:

| Kimlik | Primitive | Şu an implement edildi mi? |
|---|---|---|
| PushLock | Exclusive initialize/acquire/release smoke test | Evet |
| RundownProtection | Rundown yaşam döngüsü | Hayır |
| WorkItems | Queue/dispatch | Hayır |
| PreciseTiming | Hassas zaman sorgusu | Hayır |
| CpuIpi | CPU/IPI semantiği | Hayır |

Mevcut producer yalnızca PushLock üretir. Gelecek producer'lar aynı
loader/stage/environment alanlarını kullanıp primitive'e uygun `scope`,
`required_ntoskrnl` ve `client_fields` belirleyebilir. PushLock field
beklentileri başka primitive'lere uygulanmamalıdır. Kırıcı format değişikliği
yeni schema_version gerektirir.

## Aşamalar ve kanıt

| Alan | Anlam |
|---|---|
| driver_image_loaded | Hedef PE image map/load kanıtı |
| driver_init_address_found | Entry adresinin keşfedilmesi; execution iddiası yok |
| driver_init_reached | DriverEntry marker'ı, hedef init completion veya başarılı device open |
| loaded | Entry tamamlanması marker'ı veya başarılı client device open |
| device_created | Creation marker'ı veya başarılı open |
| device_opened | Ayrı client stdout'ta device open sonucu |
| ioctl_success | Client'ın DeviceIoControl transport sonucu |

Aşama değerleri `true`, `false`, `null`: observed success, observed failure,
yetersiz kanıt. `null` readable raporda **NOT VERIFIED** görünür. Driver
map edilmiş ama initialization başarısız olmuş olabilir; aşamalar tek
`loaded` boolean'ına indirgenmez. Açılış failure'ı ACL/link problemi de
olabileceğinden yalnızca client `driver_loaded=false` sonucu `loaded=false`
kanıtı sayılmaz.

`evidence` her çıkarımı destekleyen ham satırları veya `client:...`
satırlarını tutar. Aynı aşamaya çelişen açık kanıt varsa `failures` alanına
`conflicting_evidence:<stage>` yazılır; overall FAIL olur.

## Sonuç politikası

`result` her zaman PASS veya FAIL'dir. PASS için ayrı client çıktısı,
`AEGIS_PUSHLOCK_TEST` başlığı, tekil field'lar, process exit `0`, başarılı
open/IOCTL ve şu alanların tamamı gerekir:

```text
bytes_returned=20 version=1 passed=1
initial_value=0 final_value=1 error_code=0 result=PASS
```

Unimplemented çağrı, loader/start failure, çelişki, install/start/cleanup
veya harness çıkış hatası varsa overall FAIL olur. `result=PASS` yazan tek
satır veya sıfır hata satırı PASS için yeterli değildir.

`verification=OBSERVED` tanınan evidence/failure veya client output olduğunu
belirtir; başarı anlamına gelmez. Evidence yoksa `NOT_VERIFIED`. Boş logda
overall FAIL fail-closed politikasıdır; primitive'in bozuk olduğu iddiası
değildir. İnsan raporunda aşamaları ve verification alanını birlikte okuyun.

## Eksik API ve failure alanları

- `required_ntoskrnl`: bu primitive'in hedef API'leri; tüm PE importları değil.
- `missing_ntoskrnl`: raw diagnostic'te ismi gözlenmiş NTOSKRNL API'leri;
  sıralı, duplicate'siz. Listede olmamak implemented anlamına gelmez.
- `unimplemented`: module/function çiftleri; NTOSKRNL dışı çağrıları da tutar.
- `failures`: stable diagnostic etiketleri, örneğin `unimplemented_call`,
  `zw_load_driver_failed`, `service_start_failed`, `harness_stop_failed`.
- `client_result`, `client_exit_code`, `client_fields`: client evidence.
- `scope`: şu an `uncontended_exclusive_smoke_test`.

Environment run zamanı (UTC), host/architecture, Windows veya Wine ortamı,
Wine sürümü, WINEPREFIX/WINEDEBUG, driver/client SHA-256 ve gerçek step exit
code'larını kaydeder. Harness'te `255` adımın çalıştırılmadığını belirtir.
Wine kernel export coverage'ı bu rapordan tek başına çıkarılamaz.

Loglar yerel path ve prefix bilgisi içerebilir; paylaşmadan önce inceleyin.
Fixture raporları kendi gerçek runtime run'larınızdan ayrı tutulmalıdır.
