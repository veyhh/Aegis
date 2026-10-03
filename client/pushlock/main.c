#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>
#include <stdio.h>
#include "public.h"

int main(void)
{
    HANDLE device;
    AEGIS_PUSHLOCK_RESULT result = {0};
    DWORD returned = 0;
    DWORD error;
    BOOL ok;
    int passed;

    puts("AEGIS_PUSHLOCK_TEST");
    device = CreateFileW(AEGIS_WIN32_DEVICE_NAME,
        GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL, OPEN_EXISTING, 0, NULL);
    if (device == INVALID_HANDLE_VALUE) {
        error = GetLastError();
        printf("driver_loaded=false\ndevice_opened=false\nioctl_success=false\n"
               "win32_error=%lu\nresult=FAIL\n", (unsigned long)error);
        return 2;
    }
    puts("driver_loaded=true\ndevice_opened=true");
    ok = DeviceIoControl(device, AEGIS_IOCTL_RUN_PUSHLOCK_TEST,
        NULL, 0, &result, sizeof(result), &returned, NULL);
    error = ok ? ERROR_SUCCESS : GetLastError();
    CloseHandle(device);
    if (!ok) {
        printf("ioctl_success=false\nwin32_error=%lu\nresult=FAIL\n",
               (unsigned long)error);
        return 3;
    }
    puts("ioctl_success=true");
    passed = returned == sizeof(result) &&
             result.Version == AEGIS_RESULT_VERSION && result.Passed == 1 &&
             result.InitialValue == 0 && result.FinalValue == 1 &&
             result.ErrorCode == AEGIS_ERROR_NONE;
    printf("bytes_returned=%lu\nversion=%lu\npassed=%lu\n"
           "initial_value=%lu\nfinal_value=%lu\nerror_code=%lu\nresult=%s\n",
           (unsigned long)returned, (unsigned long)result.Version,
           (unsigned long)result.Passed, (unsigned long)result.InitialValue,
           (unsigned long)result.FinalValue, (unsigned long)result.ErrorCode,
           passed ? "PASS" : "FAIL");
    return passed ? 0 : 4;
}
