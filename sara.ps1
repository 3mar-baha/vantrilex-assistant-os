# sara.ps1 — Sara full-stack 1-click launcher (hardened 2026-09-17)
# Usage:  .\sara.bat            -> stop stale, ensure OmniRoute, launch core + bridge, VERIFY
#         .\sara.bat -StopOnly  -> stop only
#         .\sara.bat -Port 9000 -> launch core on a different public port
#         .\sara.bat -Force     -> launch even if the OmniRoute gateway stays down
#
# Honesty contract (2026-09-04 live finding + 2026-09-17 audit): a doubled core
# was running after an aborted cycle — this script kills by NAME and by PORT
# ownership, validates preflight before spawning windows, probes real HTTP
# health (never bare TCP), and VERIFIES each component before declaring success.
param(
    [string]$Port = '8443',
    [switch]$StopOnly,
    [switch]$Force   # launch even if the OmniRoute gateway stays unreachable
)

$Root = $PSScriptRoot
Set-Location -LiteralPath $Root
$ErrorActionPreference = 'Continue'

# one shell-selection rule (sara.bat prefers pwsh the same way)
$PSExe = 'powershell'
if (Get-Command pwsh -ErrorAction SilentlyContinue) { $PSExe = 'pwsh' }
$RootEsc = $Root -replace "'", "''"  # quote-safe on any Windows username path

# parent-side diagnostics: every boot leaves a timestamped trail in logs/
$logDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir ('sara-{0:yyyyMMdd-HHmmss}.log' -f (Get-Date))) -Append | Out-Null
function Exit-Sara([int]$code) { Stop-Transcript | Out-Null; exit $code }

# --- port validation (fail-fast usage error, never a cast stack trace) --------
[int]$p = 0
if (-not [int]::TryParse($Port, [ref]$p) -or $p -lt 1 -or $p -gt 65535) {
    Write-Host ("  ERROR: -Port '{0}' is not a valid TCP port" -f $Port) -ForegroundColor Red
    Exit-Sara 1
}

function Stop-Matching([string]$pattern, [string]$label) {
    # match ANY python executable (venv AND system) — the doubled-core lesson
    $procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match $pattern }
    foreach ($proc in $procs) {
        Write-Host ("  stopping {0} PID {1}" -f $label, $proc.ProcessId) -ForegroundColor Gray
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if (-not $procs) { Write-Host ("  no {0} process running" -f $label) }
}

function Stop-PortOwner([int]$portNum, [string]$label) {
    # port-true teardown: whoever LISTENS dies, whatever its exe name
    # (stale node.exe gateway, orphaned hosts) — the name filter above misses these
    $owners = Get-NetTCPConnection -LocalPort $portNum -State Listen `
        -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        Write-Host ("  stopping {0} port-holder PID {1}" -f $label, $id) -ForegroundColor Gray
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}

function Wait-PortFree([int]$portNum, [int]$seconds = 10) {
    # reactive release wait — returns the moment the port frees, never a flat sleep
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $held = Get-NetTCPConnection -LocalPort $portNum -State Listen `
            -ErrorAction SilentlyContinue
        if (-not $held) { return $true }
        Start-Sleep -Milliseconds 200
    }
    return $false
}

function Test-Gateway {
    # real API health (/v1/models JSON) — a bound socket proves nothing by itself
    try {
        $r = Invoke-RestMethod 'http://localhost:20128/v1/models' -TimeoutSec 5
        return ($null -ne $r)
    } catch { return $false }
}

function Wait-Gateway([int]$seconds = 20) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Gateway) { return $true }
        Start-Sleep -Milliseconds 200
    }
    return $false
}

function Wait-Health([int]$portNum, [int]$seconds = 25) {
    # the core's /health responder (GET -> {"status":"ok"}) certifies the
    # WSS+health stack, not just a listening socket
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod ("http://localhost:{0}/health" -f $portNum) -TimeoutSec 2
            if ($r.status -eq 'ok') { return $true }
        } catch { }
        Start-Sleep -Milliseconds 200
    }
    return $false
}

function Test-BridgeDial([int]$corePort, [int]$seconds = 15) {
    # the bridge dials OUT to the core: an ESTABLISHED tuple owned by the
    # bridge PID against the core port is a live-socket proof of the handshake
    # path (far stronger than "process still alive")
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $bridge = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
            Where-Object { $_.CommandLine -match 'bridge\.daemon' } | Select-Object -First 1
        if ($bridge) {
            $dial = Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
                Where-Object { $_.OwningProcess -eq $bridge.ProcessId -and $_.RemotePort -eq $corePort }
            if ($dial) { return $bridge.ProcessId }
        }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

function Start-Child([string]$title, [string]$body) {
    $cmd = "`$Host.UI.RawUI.WindowTitle='{0}'; {1}" -f $title, $body
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
    return Start-Process $PSExe -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass',
        '-EncodedCommand', $enc -PassThru
}

Write-Host '=== SARA: stopping stale instances ===' -ForegroundColor Cyan
Stop-Matching 'src\.main' 'core (src.main)'
Stop-Matching 'bridge\.daemon' 'bridge (bridge.daemon)'
Stop-PortOwner $p 'core'
if (-not (Wait-PortFree $p 10)) {
    Write-Host ("  ERROR: :{0} still held after teardown — kill it manually or pick -Port" -f $p) -ForegroundColor Red
    Exit-Sara 1
}

if ($StopOnly) {
    Write-Host '=== SARA: stopped ===' -ForegroundColor Cyan
    Exit-Sara 0
}

Write-Host '=== SARA: preflight ===' -ForegroundColor Cyan
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    Write-Host '  ERROR: .venv missing — run make setup first' -ForegroundColor Red
    Exit-Sara 1
}
if (-not (Test-Path "$Root\.env")) {
    Write-Host '  ERROR: .env missing (tokens live there, never in git)' -ForegroundColor Red
    Exit-Sara 1
}

# --- OmniRoute gateway: reuse when healthy, auto-launch when not --------------
if (Test-Gateway) {
    Write-Host '  OmniRoute gateway :20128 already healthy (reusing)' -ForegroundColor Green
} else {
    Write-Host '  OmniRoute gateway :20128 not responding — auto-launching OmniRoute...' -ForegroundColor Yellow
    Stop-PortOwner 20128 'stale gateway'  # clear a hung squatter before respawning
    $omni = $null
    if (Get-Command omniroute -ErrorAction SilentlyContinue) { $omni = 'omniroute' }
    elseif (Get-Command npx -ErrorAction SilentlyContinue) { $omni = 'npx omniroute' }
    if (-not $omni) {
        Write-Host '  ERROR: no omniroute (npm global) and no npx on PATH' -ForegroundColor Red
        if (-not $Force) { Exit-Sara 1 }
    } else {
        $gw = Start-Child '[SARA OmniRoute Gateway :20128]' ("Set-Location -LiteralPath '{0}'; {1}" -f $RootEsc, $omni)
        Write-Host ("  gateway window launched (PID {0}) — waiting for /v1/models..." -f $gw.Id) -ForegroundColor Gray
        if (Wait-Gateway 20) {
            Write-Host '  OmniRoute gateway started & healthy' -ForegroundColor Green
        } else {
            Write-Host '  ERROR: OmniRoute did not answer /v1/models within 20s.' -ForegroundColor Red
            Write-Host '  Check the gateway window, or rerun with -Force to boot brainless.' -ForegroundColor Yellow
            if (-not $Force) { Exit-Sara 1 }
            Write-Host '  (-Force given — continuing)' -ForegroundColor Yellow
        }
    }
}

# in-repo health probe: gateway/vault/google/ffmpeg/token as JSON, exit 0/1
& "$Root\.venv\Scripts\python.exe" -m src.main --health
if ($LASTEXITCODE -ne 0 -and -not $Force) {
    Write-Host '  --health degraded (see JSON above) — fix it or rerun with -Force' -ForegroundColor Yellow
    Exit-Sara 1
}

if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) {
    Write-Host ("  ERROR: :{0} occupied — teardown first or pick -Port" -f $p) -ForegroundColor Red
    Exit-Sara 1
}

Write-Host '=== SARA: launching windows ===' -ForegroundColor Cyan
$coreProc = Start-Child "[SARA Core :$p]" ("Set-Location -LiteralPath '{0}'; `$env:PORT='{1}'; .venv\Scripts\python.exe -m src.main" -f $RootEsc, $p)
$bridgeProc = Start-Child '[SARA PC Bridge]' ("Set-Location -LiteralPath '{0}'; .venv\Scripts\python.exe -m bridge.daemon" -f $RootEsc)

Write-Host ("  core window (PID {0}, PORT={1}) launched — direct venv python (no make shell)" -f $coreProc.Id, $p)
Write-Host ("  bridge window (PID {0}) launched" -f $bridgeProc.Id)

# --- the verification pass (the honesty contract) ------------------------------
Write-Host '=== SARA: verifying ===' -ForegroundColor Cyan

$coreUp = Wait-Health $p 25
if ($coreUp) {
    Write-Host ("  core :{0} healthy (/health ok + bridge WSS)" -f $p) -ForegroundColor Green
} else {
    Write-Host ("  core :{0} NOT healthy — check the [SARA Core] window for errors" -f $p) -ForegroundColor Red
}

$dialPid = Test-BridgeDial $p 15
if ($dialPid) {
    Write-Host ("  bridge daemon PID {0} holds a live dial to core :{1}" -f $dialPid, $p) -ForegroundColor Green
} else {
    $bridgeAlive = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'bridge\.daemon' }
    if ($bridgeAlive) {
        Write-Host '  bridge process alive but no dial seen — check its window (token? URL?)' -ForegroundColor Yellow
    } else {
        Write-Host '  bridge daemon never started — check the [SARA PC Bridge] window' -ForegroundColor Red
    }
}

if ($coreUp -and $dialPid) {
    Write-Host '=== SARA: cycle OK — test Sara on Telegram now ===' -ForegroundColor Green
    Exit-Sara 0
} else {
    Write-Host '=== SARA: cycle INCOMPLETE — see the red lines above ===' -ForegroundColor Yellow
    Exit-Sara 2
}
