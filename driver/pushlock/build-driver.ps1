param(
    [string]$KitsRoot = "${env:ProgramFiles(x86)}\Windows Kits\10",
    [string]$WdkVersion = ""
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    throw 'Run from an x64 Native Tools / Developer PowerShell environment for Visual Studio.'
}
if (-not $WdkVersion) {
    $taskVersions = Get-ChildItem -LiteralPath (Join-Path $KitsRoot 'Include') -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'km\ntddk.h') } |
        Sort-Object { [version]$_.Name } -Descending
    if (-not $taskVersions) { throw 'No real WDK kernel headers found.' }
    $WdkVersion = $taskVersions[0].Name
}
$taskInclude = Join-Path $KitsRoot "Include\$WdkVersion"
$taskLib = Join-Path $KitsRoot "Lib\$WdkVersion\km\x64"
foreach ($taskFile in @("$taskInclude\km\ntddk.h", "$taskLib\ntoskrnl.lib", "$taskLib\wdmsec.lib", "$taskLib\BufferOverflowK.lib")) {
    if (-not (Test-Path -LiteralPath $taskFile)) { throw "Missing WDK file: $taskFile" }
}
$taskOutput = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\artifacts\driver\x64\Release'))
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskObject = Join-Path $taskOutput 'aegis_pushlock_test.obj'
$taskImage = Join-Path $taskOutput 'aegis_pushlock_test.sys'
$taskCompile = @('/nologo', '/c', '/kernel', '/O2', '/GS', '/Zl', '/W4', '/WX', '/TC',
    '/D_AMD64_', '/DAMD64', '/D_WIN64', '/D_WIN32_WINNT=0x0A00',
    '/DNTDDI_VERSION=0x0A000006', "/I$taskInclude\km", "/I$taskInclude\shared",
    "/I$taskInclude\km\crt", "/Fo$taskObject", (Join-Path $PSScriptRoot 'aegis_pushlock_test.c'))
& cl.exe @taskCompile
if ($LASTEXITCODE -ne 0) { throw "Driver compilation failed: $LASTEXITCODE" }
$taskLink = @('/nologo', '/driver', '/subsystem:native,10.00', '/machine:x64',
    '/entry:GsDriverEntry', '/nodefaultlib', '/release', '/dynamicbase', '/nxcompat',
    "/libpath:$taskLib", "/out:$taskImage", $taskObject,
    'ntoskrnl.lib', 'hal.lib', 'wdmsec.lib', 'BufferOverflowK.lib')
& link.exe @taskLink
if ($LASTEXITCODE -ne 0) { throw "Driver link failed: $LASTEXITCODE" }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'aegis_pushlock_test.inf') -Destination $taskOutput
Write-Output "Built unsigned x64 driver using real WDK $WdkVersion`: $taskImage"
