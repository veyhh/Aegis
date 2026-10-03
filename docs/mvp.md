# PushLock MVP

## Teslim edilen kapsam

- Bize ait minimal x64 Windows test driver'ı ve unsigned `.sys` build yolu.
- Üç hedef PushLock API'sine gerçek, doğrudan çağrı.
- Version 1, 20-byte shared driver/client ABI ve tek IOCTL.
- Windows client, exact-result validation ve machine-readable stdout.
- Windows reference SCM script'i.
- Wine installer, start/client/stop/delete harness'i ve bounded execution.
- Missing-call extraction, loader aşamaları, JSON schema ve text reporting.
- Sentetik parser fixture'ları, CLI testleri ve mock-Wine harness testleri.

## Başarı kriterlerinin karşılığı

| Kullanıcı kriteri | Doğrulama | Durum |
|---|---|---|
| `.sys` Windows üzerinde build olur | Gerçek MSVC/WDK native build + PE import inspection | PASS |
| Windows driver load + IOCTL PASS | Mevcut CI policy'ye uygun imzalı artifact ve elevated native run | NOT VERIFIED |
| Aynı artifact Wine altında test edilir | Gerçek Linux/Wine runtime run | NOT VERIFIED |
| Wine failure logları otomatik analiz edilir | Missing/loader/malformed fixture ve CLI testleri | PASS, sentetik |
| Compatibility report üretilir | JSON -> readable report CLI ve harness testleri | PASS, sentetik |
| Harness/parser testleri çalışır | Python unittest + Bash syntax | PASS |

MVP runtime başarı kriterleri henüz tamamlanmış değildir. Build PASS'i driver'ın
kernel'da güvenli veya semantik olarak doğru çalıştığı iddiası değildir.
Yerel ölçüm ayrıntıları [verification.md](verification.md) içindedir.

## Beklenen sonuçlar

Native Windows reference test tamamlandığında client `0`, transport success,
20 byte, version `1`, passed `1`, initial `0`, final `1`, error `0` beklenir.
Bunlardan biri farklıysa FAIL. Windows code-integrity veya erişim hataları
ayrı `win32_error`/SCM logs ile açıklanır; policy değiştirilmez.

Wine'da üç API veya destekleyici driver importları implement edilmemişse
overall FAIL beklenir. Image map/entry discovery başarılı kalabilir. Bir
Wine sürümü bu sequence'i tamamlayabilirse PASS yalnızca uncontended test
kapsamında geçerlidir. Log-only run hiçbir zaman PASS üretmez.

## Limitler

- Shared acquisition, contention, waiter wake-up, starvation/fairness,
  recursive acquisition, APC stress ve memory ordering test edilmez.
- No-op acquire/release, tek-thread smoke test'i geçebilir. Bu nedenle PASS
  kernel synchronization equivalence iddiası değildir.
- Driver test dispatch'i synchronous; API hang'i native kernel thread'ini
  engelleyebilir. Gerçek reference run uygun araştırma ortamında yapılır.
- x86/ARM64, PnP, package certification ve signing automation kapsam dışı.
- `Wdmsec.lib` ek importları Wine yüklemesini PushLock'a ulaşmadan durdurabilir.
- Wine log parser'ı tüm Wine sürümleri için doğrulanmış değildir.
- Wine'ın user-space kernel-driver katmanı Windows kernel güvenlik ve IPI
  semantiğiyle eşdeğer kabul edilmez.
- Native ve gerçek Wine runtime henüz NOT VERIFIED.

## Bir sonraki çalışma

Önce imzalı artifact ile native baseline ve aynı hash'lerle gerçek Wine
run'ı kaydedilir. İlk çalışmada görülen eksik importlar sınıflandırılır;
yalnızca PushLock kapsamındaki araştırma sürdürülür. Rundown Protection,
Work Items, Timing veya CPU/IPI implementasyonuna bu MVP içinde geçilmez.
