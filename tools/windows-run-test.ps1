param(
    [Parameter(Mandatory = $true)][string]$Driver,
    [Parameter(Mandatory = $true)][string]$Client,
    [string]$PythonExe = 'python'
)
$ErrorActionPreference = 'Stop'
$taskIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$taskPrincipal = [Security.Principal.WindowsPrincipal]::new($taskIdentity)
if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this reference test from an elevated PowerShell in your Windows test environment.'
}
$taskDriver = (Resolve-Path -LiteralPath $Driver).Path
$taskClient = (Resolve-Path -LiteralPath $Client).Path
Get-Command $PythonExe -ErrorAction Stop | Out-Null
$taskService = 'aegis_pushlock_test'
if (Get-Service -Name $taskService -ErrorAction SilentlyContinue) {
    throw 'An AEGIS service already exists. Inspect and remove it explicitly before this run.'
}
$taskReportDir = Join-Path $PSScriptRoot ("..\reports\windows-pushlock-" + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $taskReportDir -Force | Out-Null
$taskReportDir = (Resolve-Path -LiteralPath $taskReportDir).Path
$taskLog = Join-Path $taskReportDir 'native.log'
$taskClientOutput = Join-Path $taskReportDir 'client.stdout'
$taskUtf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($taskLog, '', $taskUtf8)
$taskOwned = $false
$taskCodes = @{ install=255; start=255; client=255; stop=255; delete=255; harness=0 }
function Invoke-AegisSc([string[]]$ScArguments) {
    $taskScOutput = & sc.exe @ScArguments 2>&1
    $taskScCode = $LASTEXITCODE
    [IO.File]::AppendAllText($taskLog, (($taskScOutput -join "`n") + "`n"), $taskUtf8)
    return $taskScCode
}
try {
    $taskCodes.install = Invoke-AegisSc -ScArguments @('create', $taskService, 'type=', 'kernel', 'start=', 'demand', 'binPath=', $taskDriver)
    if ($taskCodes.install -eq 0) {
        $taskOwned = $true
        $taskCodes.start = Invoke-AegisSc -ScArguments @('start', $taskService)
        if ($taskCodes.start -eq 0) {
            $taskOutput = & $taskClient
            $taskCodes.client = $LASTEXITCODE
            [IO.File]::WriteAllText($taskClientOutput, (($taskOutput -join "`n") + "`n"), $taskUtf8)
        }
    }
} catch {
    $taskCodes.harness = 1
    [IO.File]::AppendAllText($taskLog, ($_.Exception.Message + "`n"), $taskUtf8)
} finally {
    if ($taskOwned) {
        $taskCodes.stop = Invoke-AegisSc -ScArguments @('stop', $taskService)
        if ($taskCodes.stop -eq 1062) { $taskCodes.stop = 0 }
        $taskCodes.delete = Invoke-AegisSc -ScArguments @('delete', $taskService)
    }
}
$taskMetadata = @{
    platform='windows'; timestamp_utc=[DateTime]::UtcNow.ToString('o')
    host=[Environment]::OSVersion.VersionString; architecture=$env:PROCESSOR_ARCHITECTURE
    driver_sha256=(Get-FileHash -LiteralPath $taskDriver -Algorithm SHA256).Hash.ToLowerInvariant()
    client_sha256=(Get-FileHash -LiteralPath $taskClient -Algorithm SHA256).Hash.ToLowerInvariant()
}
foreach ($taskStep in $taskCodes.Keys) { $taskMetadata["${taskStep}_exit_code"] = $taskCodes[$taskStep] }
$taskMetadataFile = Join-Path $taskReportDir 'metadata.json'
[IO.File]::WriteAllText($taskMetadataFile, ($taskMetadata | ConvertTo-Json), $taskUtf8)
$taskJson = Join-Path $taskReportDir 'report.json'
$taskParseArgs = @((Join-Path $PSScriptRoot 'parse-wine-log.py'), $taskLog, '--metadata', $taskMetadataFile, '--output', $taskJson)
if (Test-Path -LiteralPath $taskClientOutput) {
    $taskParseArgs += @('--client-output', $taskClientOutput, '--client-exit-code', [string]$taskCodes.client)
}
& $PythonExe @taskParseArgs
$taskParseCode = $LASTEXITCODE
& $PythonExe (Join-Path $PSScriptRoot 'aegis-report.py') $taskJson --output (Join-Path $taskReportDir 'report.txt')
$taskReportCode = $LASTEXITCODE
Write-Output "AEGIS native reference report: $taskReportDir"
if ($taskParseCode -eq 0 -and $taskReportCode -eq 0) { exit 0 }
exit 1
