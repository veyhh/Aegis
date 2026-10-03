#ifndef AEGIS_PUSHLOCK_PUBLIC_H
#define AEGIS_PUSHLOCK_PUBLIC_H

/* Include ntddk.h (kernel) or windows.h + winioctl.h (client) first. */
#define AEGIS_SERVICE_NAME L"aegis_pushlock_test"
#define AEGIS_DEVICE_NAME L"\\Device\\AegisPushLockTest"
#define AEGIS_DOS_DEVICE_NAME L"\\DosDevices\\AegisPushLockTest"
#define AEGIS_WIN32_DEVICE_NAME L"\\\\.\\AegisPushLockTest"
#define AEGIS_RESULT_VERSION 1UL
#define AEGIS_DEVICE_TYPE 0x8000u
#define AEGIS_IOCTL_RUN_PUSHLOCK_TEST \
    CTL_CODE(AEGIS_DEVICE_TYPE, 0x800u, METHOD_BUFFERED, \
             FILE_READ_ACCESS | FILE_WRITE_ACCESS)

#define AEGIS_ERROR_NONE 0UL
#define AEGIS_ERROR_COUNTER_MISMATCH 1UL

typedef struct _AEGIS_PUSHLOCK_RESULT {
    ULONG Version;
    ULONG Passed;
    ULONG InitialValue;
    ULONG FinalValue;
    ULONG ErrorCode;
} AEGIS_PUSHLOCK_RESULT;

/* The ABI is five 32-bit integers; no pointers or platform-sized fields. */
typedef char AEGIS_RESULT_SIZE_CHECK[
    sizeof(AEGIS_PUSHLOCK_RESULT) == 20 ? 1 : -1];

#endif
