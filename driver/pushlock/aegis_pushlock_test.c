#include <ntddk.h>
#include <wdmsec.h>
#include "public.h"

DRIVER_INITIALIZE DriverEntry;
static DRIVER_UNLOAD AegisUnload;
static DRIVER_DISPATCH AegisUnsupported;
static DRIVER_DISPATCH AegisOpenClose;
static DRIVER_DISPATCH AegisDeviceControl;

/* Private device class; never shares another driver's security configuration. */
static const GUID AegisDeviceClass = {
    0xc44b7487, 0x82b1, 0x45d0,
    {0x8d, 0xa0, 0x1a, 0x26, 0xc3, 0xb2, 0x0b, 0xd7}
};

static NTSTATUS
AegisComplete(PIRP Irp, NTSTATUS Status, ULONG_PTR Information)
{
    Irp->IoStatus.Status = Status;
    Irp->IoStatus.Information = Information;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return Status;
}

static NTSTATUS
AegisUnsupported(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DeviceObject);
    return AegisComplete(Irp, STATUS_INVALID_DEVICE_REQUEST, 0);
}

static NTSTATUS
AegisOpenClose(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    UNREFERENCED_PARAMETER(DeviceObject);
    if (stack->MajorFunction == IRP_MJ_CREATE &&
        stack->FileObject->FileName.Length != 0) {
        return AegisComplete(Irp, STATUS_OBJECT_NAME_NOT_FOUND, 0);
    }
    return AegisComplete(Irp, STATUS_SUCCESS, 0);
}

static NTSTATUS
AegisDeviceControl(PDEVICE_OBJECT DeviceObject, PIRP Irp)
{
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    AEGIS_PUSHLOCK_RESULT *result;
    EX_PUSH_LOCK lock;
    volatile ULONG counter = 0;
    UNREFERENCED_PARAMETER(DeviceObject);

    if (stack->Parameters.DeviceIoControl.IoControlCode !=
        AEGIS_IOCTL_RUN_PUSHLOCK_TEST) {
        return AegisComplete(Irp, STATUS_INVALID_DEVICE_REQUEST, 0);
    }
    if (stack->Parameters.DeviceIoControl.InputBufferLength != 0) {
        return AegisComplete(Irp, STATUS_INVALID_PARAMETER, 0);
    }
    if (stack->Parameters.DeviceIoControl.OutputBufferLength <
            sizeof(AEGIS_PUSHLOCK_RESULT) ||
        Irp->AssociatedIrp.SystemBuffer == NULL) {
        return AegisComplete(Irp, STATUS_BUFFER_TOO_SMALL, 0);
    }
    if (KeGetCurrentIrql() > APC_LEVEL) {
        return AegisComplete(Irp, STATUS_INVALID_DEVICE_STATE, 0);
    }

    result = (AEGIS_PUSHLOCK_RESULT *)Irp->AssociatedIrp.SystemBuffer;
    RtlZeroMemory(result, sizeof(*result));
    result->Version = AEGIS_RESULT_VERSION;

    /* Each request owns its lock: reinitialization never races a live lock.
       This deliberately tests an uncontended sequence, not concurrency. */
    ExInitializePushLock(&lock);
    KeEnterCriticalRegion();
    ExAcquirePushLockExclusiveEx(&lock, 0);
    result->InitialValue = counter;
    counter += 1;
    result->FinalValue = counter;
    ExReleasePushLockExclusiveEx(&lock, 0);
    KeLeaveCriticalRegion();

    result->Passed = (result->InitialValue == 0 && result->FinalValue == 1);
    result->ErrorCode = result->Passed ? AEGIS_ERROR_NONE :
                                        AEGIS_ERROR_COUNTER_MISMATCH;
    return AegisComplete(Irp, STATUS_SUCCESS, sizeof(*result));
}

static VOID
AegisUnload(PDRIVER_OBJECT DriverObject)
{
    UNICODE_STRING link;
    RtlInitUnicodeString(&link, AEGIS_DOS_DEVICE_NAME);
    IoDeleteSymbolicLink(&link);
    if (DriverObject->DeviceObject != NULL) {
        IoDeleteDevice(DriverObject->DeviceObject);
    }
    DbgPrint("AEGIS: driver_unloaded=true\n");
}

NTSTATUS
DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath)
{
    UNICODE_STRING name, link, sddl;
    PDEVICE_OBJECT device = NULL;
    EX_PUSH_LOCK initializationProbe;
    NTSTATUS status;
    ULONG i;
    UNREFERENCED_PARAMETER(RegistryPath);

    DbgPrint("AEGIS: driver_init_reached=true\n");
    /* Entry-time initialization probe. It is never acquired or shared. */
    ExInitializePushLock(&initializationProbe);

    for (i = 0; i <= IRP_MJ_MAXIMUM_FUNCTION; ++i) {
        DriverObject->MajorFunction[i] = AegisUnsupported;
    }
    DriverObject->MajorFunction[IRP_MJ_CREATE] = AegisOpenClose;
    DriverObject->MajorFunction[IRP_MJ_CLOSE] = AegisOpenClose;
    DriverObject->MajorFunction[IRP_MJ_CLEANUP] = AegisOpenClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = AegisDeviceControl;
    DriverObject->DriverUnload = AegisUnload;

    RtlInitUnicodeString(&name, AEGIS_DEVICE_NAME);
    RtlInitUnicodeString(&link, AEGIS_DOS_DEVICE_NAME);
    RtlInitUnicodeString(&sddl, L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    status = IoCreateDeviceSecure(DriverObject, 0, &name, AEGIS_DEVICE_TYPE,
        FILE_DEVICE_SECURE_OPEN, FALSE, &sddl, &AegisDeviceClass, &device);
    if (!NT_SUCCESS(status)) {
        DbgPrint("AEGIS: device_created=false status=0x%08lx\n", status);
        return status;
    }
    DbgPrint("AEGIS: device_created=true\n");
    status = IoCreateSymbolicLink(&link, &name);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(device);
        return status;
    }
    device->Flags &= ~DO_DEVICE_INITIALIZING;
    DbgPrint("AEGIS: driver_loaded=true\n");
    return STATUS_SUCCESS;
}
