# sara.ps1 — Sara full stop/start cycle (owner utility, 2026-09-01)
# Usage:  .\sara.bat            -> stop everything, then relaunch core + bridge windows
#         .\sara.bat -StopOnly  -> stop only
#         .\sara.bat -Port 9000 -> launch core on a different public port
param(
    [string]$Port = '8443',
    [switch]$StopOnly
)

$Root = $PSScriptRoot
Set-Location -LiteralPath $Root

Write-Host '=== SARA: stopping stale instances ===' -ForegroundColor Cyan

function Stop-Matching([string]$pattern, [string]$label) {
    $procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match $pattern }
    foreach ($p in $procs) {
        Write-Host ("  stopping {0} PID {1}" -f $label, $p.ProcessId)
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (-not $procs) { Write-Host ("  no {0} process running" -f $label) }
}

Stop-Matching 'src\.main' 'core (src.main)'
Stop-Matching 'bridge\.daemon' 'bridge (bridge.daemon)'
Start-Sleep -Seconds 2  # let the OS free port / Telegram polling

if ($StopOnly) {
    Write-Host '=== SARA: stopped ===' -ForegroundColor Cyan
    exit 0
}

Write-Host '=== SARA: preflight ===' -ForegroundColor Cyan
$gateway = Test-NetConnection -ComputerName localhost -Port 20128 `
    -InformationLevel Quiet -WarningAction SilentlyContinue
if ($gateway) {
    Write-Host '  OmniRoute gateway :20128 reachable'
} else {
    Write-Host '  WARNING: OmniRoute gateway :20128 NOT reachable — open the OmniRoute app first!' -ForegroundColor Yellow
    Write-Host '  (continuing; the bot will boot but the brain will fail until the gateway is up)' -ForegroundColor Yellow
}

Write-Host '=== SARA: launching windows ===' -ForegroundColor Cyan
$core = "Set-Location -LiteralPath '$Root'; `$env:PORT='$Port'; make run-core"
$coreEnc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($core))
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', `
    '-EncodedCommand', $coreEnc

$bridge = "Set-Location -LiteralPath '$Root'; make run-bridge"
$bridgeEnc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($bridge))
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', `
    '-EncodedCommand', $bridgeEnc

Write-Host ("  core window  (PORT={0}) launched" -f $Port)
Write-Host '  bridge window launched'
Write-Host '=== SARA: cycle done — wait ~15s, then test Sara on Telegram ===' -ForegroundColor Green
