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
    # port-true teardown: whoever touches the port dies, whatever its exe name
    # or CLI visibility (stale node.exe gateway, blank-CLI worker children —
    # the 2026-09-17 lesson: socket owners aren't always the named parents).
    # Listen AND Established: orphaned dial children linger past their parents.
    $owners = Get-NetTCPConnection -LocalPort $portNum -State Listen, Established `
        -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $owners) {
        if ($id -le 0) { continue }  # PID 0 = kernel TimeWait rows, not a process
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

function Test-CoreHealth([int]$portNum) {
    # Handshake-shaped /health probe (2026-09-17 live lesson): :$Port is a
    # websockets opening-handshake server — a PLAIN http GET never reaches
    # process_request and dies as InvalidMessage/EOFError tracebacks in the
    # core window. A complete Upgrade-handshake request to /health parses
    # cleanly, hits health_responder (200 {"status":"ok"}), and the server
    # aborts-after-response with zero log spam. Single attempt, no throw.
    $client = New-Object Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $portNum, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(1500)) { return $false }
        $client.EndConnect($iar)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 1500
        $stream.WriteTimeout = 1500
        $req = "GET /health HTTP/1.1`r`nHost: 127.0.0.1:$portNum`r`n" +
            "Upgrade: websocket`r`nConnection: Upgrade`r`n" +
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==`r`n" +
            "Sec-WebSocket-Version: 13`r`n`r`n"
        $bytes = [Text.Encoding]::ASCII.GetBytes($req)
        $stream.Write($bytes, 0, $bytes.Length)
        $buf = New-Object byte[] 4096
        $text = ''
        while ($text.Length -lt 4096) {
            try { $n = $stream.Read($buf, 0, $buf.Length) } catch { break }
            if ($n -le 0) { break }  # server closed after its 200 — the clean path
            $text += [Text.Encoding]::ASCII.GetString($buf, 0, $n)
            # break only on the FULL match — headers and body may split segments
            if (($text -match 'HTTP/1\.1 200') -and ($text -match '"status"\s*:\s*"ok"')) { break }
        }
        return ($text -match 'HTTP/1\.1 200' -and $text -match '"status"\s*:\s*"ok"')
    } catch { return $false } finally { $client.Close() }
}

function Wait-Health([int]$portNum, [int]$seconds = 25) {
    # reactive poll over the handshake-shaped probe (200 ms cadence)
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-CoreHealth $portNum) { return $true }
        Start-Sleep -Milliseconds 200
    }
    return $false
}

function Test-BridgeDial([int]$corePort, [int]$seconds = 30) {
    # TUPLE-anchored (2026-09-17 live lesson): the ESTABLISHED bridge<->core
    # pair exists, but both endpoint PIDs are blank-CLI worker children, NOT
    # the bridge.daemon/src.main parents — PID-anchored matching misses the
    # real dial. :$corePort serves ONLY bridge WSS + /health, so any
    # ESTABLISHED loopback tuple touching it IS the live bridge dial.
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        $dial = Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
            Where-Object { ($_.RemotePort -eq $corePort -or $_.LocalPort -eq $corePort) -and
                ($_.LocalAddress -match '^(127\.|::1)') }
        if ($dial) { return $true }
        Start-Sleep -Milliseconds 250
    }
    return $false
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
$healthRaw = & "$Root\.venv\Scripts\python.exe" -m src.main --health 2>&1 | Out-String
Write-Host $healthRaw.Trim()
try { $healthJson = $healthRaw | ConvertFrom-Json } catch { $healthJson = $null }
if ($healthJson -and $healthJson.google -ne 'ok') {
    # live 2026-09-17: expired refresh grant surfaces as HTTP 400 in core logs.
    # Test user (omarbaha224@gmail.com) is authorized in Google Cloud Console —
    # renew with: .venv\Scripts\python.exe -m src.google_auth
    Write-Host '  Google row not ok — refresh the grant:' -ForegroundColor Yellow
    Write-Host '    .venv\Scripts\python.exe -m src.google_auth' -ForegroundColor Yellow
}
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

$dialUp = Test-BridgeDial $p 30
if ($dialUp) {
    Write-Host ("  live bridge<->core socket on :{0} (handshake path proven)" -f $p) -ForegroundColor Green
} else {
    $bridgeAlive = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'bridge\.daemon' }
    if ($bridgeAlive) {
        Write-Host '  bridge process alive but no dial seen — check its window (token? URL?)' -ForegroundColor Yellow
    } else {
        Write-Host '  bridge daemon never started — check the [SARA PC Bridge] window' -ForegroundColor Red
    }
}

if ($coreUp -and $dialUp) {
    Write-Host '=== SARA: cycle OK — test Sara on Telegram now ===' -ForegroundColor Green
    Exit-Sara 0
} else {
    Write-Host '=== SARA: cycle INCOMPLETE — see the red lines above ===' -ForegroundColor Yellow
    Exit-Sara 2
}
