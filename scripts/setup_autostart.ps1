# setup_autostart.ps1 — register (or remove) SARA Windows-logon auto-start.
# Idempotent: re-running updates the trigger in place.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_autostart.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_autostart.ps1 -Mode Shortcut
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_autostart.ps1 -Remove
#   .\sara.bat -InstallAutoStart
#
# Token bootstrap note: silent logon boots cannot complete an interactive
# Google OAuth dance. The encrypted grant (vault/State/google_token.json.enc)
# must exist from a prior interactive run of `.venv\Scripts\python.exe -m
# src.google_auth`; sara.ps1's --health gate reports the Google row every
# boot and prints the renewal hint when it degrades.
param(
    [ValidateSet('Task', 'Shortcut')]
    [string]$Mode = 'Task',
    [string]$TaskName = 'SARA Assistant OS',
    [int]$DelaySeconds = 30,
    [ValidateSet('Highest', 'Limited')]
    [string]$RunLevel = 'Highest',
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Task registration/removal needs elevation; Shortcut mode does not (APPDATA).
# Removal elevates only when a task actually exists (no pointless UAC).
# Self-elevate so `sara.bat -InstallAutoStart` stays 1-click (one UAC prompt).
$needsAdmin = ($Mode -eq 'Task')
if ($Remove) {
    $needsAdmin = [bool](Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)
}
if ($needsAdmin -and -not (Test-Admin)) {
    $fwd = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" " +
        "-Mode $Mode -TaskName `"$TaskName`" -DelaySeconds $DelaySeconds -RunLevel $RunLevel"
    if ($Remove) { $fwd += ' -Remove' }
    Write-Host '  administrator rights required — relaunching elevated...' -ForegroundColor Yellow
    $elev = Start-Process powershell.exe -ArgumentList $fwd -Verb RunAs -Wait -PassThru
    exit $elev.ExitCode
}

function Remove-AutoStart {
    $removed = $false
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host ("  removed scheduled task '{0}'" -f $TaskName)
        $removed = $true
    }
    $lnk = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\SARA Assistant OS.lnk'
    if (Test-Path -LiteralPath $lnk) {
        Remove-Item -LiteralPath $lnk -Force
        Write-Host '  removed Startup shortcut'
        $removed = $true
    }
    if (-not $removed) { Write-Host '  nothing registered (already clean)' }
}

if ($Remove) { Remove-AutoStart; exit 0 }

# fresh state first: never stack duplicate triggers across modes
Remove-AutoStart | Out-Null

if ($Mode -eq 'Shortcut') {
    $shell = New-Object -ComObject WScript.Shell
    $lnkPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\SARA Assistant OS.lnk'
    $sc = $shell.CreateShortcut($lnkPath)
    $sc.TargetPath = Join-Path $Root 'sara.bat'
    $sc.WorkingDirectory = $Root
    $sc.WindowStyle = 7  # minimized: quiet logon, consoles still reachable
    $sc.Description = 'SARA full stack (OmniRoute + Core + Bridge) at logon'
    $sc.Save()
    Write-Host ("  Startup shortcut installed: {0}" -f $lnkPath) -ForegroundColor Green
    exit 0
}

# Task Scheduler: AtLogOn + delay (network settles) + working dir = repo root.
# Calls sara.ps1 directly (sara.bat ends in `pause`, which would hang a logon window).
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument ("-NoProfile -ExecutionPolicy Bypass -File ""{0}""" -f (Join-Path $Root 'sara.ps1')) `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$trigger.Delay = ("PT{0}S" -f $DelaySeconds)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel $RunLevel
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description 'SARA full stack at logon' -Force | Out-Null
Write-Host ("  scheduled task '{0}' installed (AtLogOn {1}, +{2}s, {3})" -f $TaskName, $env:USERNAME, $DelaySeconds, $RunLevel) -ForegroundColor Green

# token-cache roll call: silent boots need the grant to already exist
$cache = Join-Path $Root 'vault\State\google_token.json.enc'
if (Test-Path -LiteralPath $cache) {
    Write-Host '  Google token cache present — logon boots stay fully silent' -ForegroundColor Green
} else {
    Write-Host '  Google token cache MISSING — run once interactively:' -ForegroundColor Yellow
    Write-Host '    .venv\Scripts\python.exe -m src.google_auth' -ForegroundColor Yellow
}
