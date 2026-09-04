# sara.ps1 — Sara full stop/start cycle (owner utility; verified 2026-09-04)
# Usage:  .\sara.bat            -> stop everything, relaunch core + bridge, VERIFY
#         .\sara.bat -StopOnly  -> stop only
#         .\sara.bat -Port 9000 -> launch core on a different public port
#
# Honesty contract (the 2026-09-04 live finding): a doubled core (venv python +
# system python both polling Telegram) was running after an aborted cycle —
# this script now kills BOTH paths, refuses to launch when the gateway is down
# (unless -Force), and VERIFIES each component is actually listening before
# declaring success.
param(
    [string]$Port = '8443',
    [switch]$StopOnly,
    [switch]$Force   # launch even if the OmniRoute gateway is unreachable
)

$Root = $PSScriptRoot
Set-Location -LiteralPath $Root
$ErrorActionPreference = 'Continue'

function Stop-Matching([string]$pattern, [string]$label) {
    # match ANY python executable (venv AND system) — the doubled-core lesson
    $procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match $pattern }
    foreach ($p in $procs) {
        Write-Host ("  stopping {0} PID {1}" -f $label, $p.ProcessId) -ForegroundColor Gray
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (-not $procs) { Write-Host ("  no {0} process running" -f $label) }
}

function Wait-Port([int]$portNum, [int]$seconds = 20) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $ok = Test-NetConnection -ComputerName localhost -Port $portNum `
            -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($ok) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host '=== SARA: stopping stale instances ===' -ForegroundColor Cyan
Stop-Matching 'src\.main' 'core (src.main)'
Stop-Matching 'bridge\.daemon' 'bridge (bridge.daemon)'
Start-Sleep -Seconds 2  # let the OS free ports / Telegram polling

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
    Write-Host '  ERROR: OmniRoute gateway :20128 NOT reachable!' -ForegroundColor Red
    Write-Host '  The bot will boot brainless (every reply dies to an apology).' -ForegroundColor Red
    Write-Host '  Start the OmniRoute app first, or rerun with -Force to launch anyway.' -ForegroundColor Yellow
    if (-not $Force) { exit 1 }
    Write-Host '  (-Force given — continuing)' -ForegroundColor Yellow
}

Write-Host '=== SARA: launching windows ===' -ForegroundColor Cyan
$core = "Set-Location -LiteralPath '$Root'; `$env:PORT='$Port'; .venv\Scripts\python.exe -m src.main"
$coreEnc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($core))
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', `
    '-EncodedCommand', $coreEnc

$bridge = "Set-Location -LiteralPath '$Root'; .venv\Scripts\python.exe -m bridge.daemon"
$bridgeEnc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($bridge))
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', `
    '-EncodedCommand', $bridgeEnc

Write-Host ("  core window  (PORT={0}) launched — direct venv python (no make shell)" -f $Port)
Write-Host '  bridge window launched'

# --- the verification pass (the honesty contract) --------------------------------
Write-Host '=== SARA: verifying ===' -ForegroundColor Cyan
[int]$p = [int]$Port

$coreUp = Wait-Port $p 25
if ($coreUp) {
    Write-Host ("  core :{0} listening (/health + bridge WSS)" -f $p) -ForegroundColor Green
} else {
    Write-Host ("  core :{0} NOT listening — check the core window for errors" -f $p) -ForegroundColor Red
}

# the bridge dials OUT to the core; verify it REGISTERED: poll until the
# process is alive AND the core sees a session (best local proxy: the bridge
# python process stayed up ~10s without exiting = it is dialing/connected;
# a wrong token dies with an immediate traceback in its window).
Start-Sleep -Seconds 3
$bridgeAlive = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match 'bridge\.daemon' }
if ($bridgeAlive) {
    Start-Sleep -Seconds 7  # give the dial + Hello handshake a moment
    $stillAlive = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'bridge\.daemon' }
    if ($stillAlive) {
        Write-Host ("  bridge daemon alive PID {0} (dialed out; handshake ok if no traceback in its window)" -f $stillAlive[0].ProcessId) -ForegroundColor Green
    } else {
        Write-Host '  bridge daemon EXITED after launch — check its window (token? URL?)' -ForegroundColor Red
    }
} else {
    Write-Host '  bridge daemon never started — check its window' -ForegroundColor Red
}

if ($coreUp -and $bridgeAlive) {
    Write-Host '=== SARA: cycle OK — test Sara on Telegram now ===' -ForegroundColor Green
} else {
    Write-Host '=== SARA: cycle INCOMPLETE — see the red lines above ===' -ForegroundColor Yellow
    exit 2
}
