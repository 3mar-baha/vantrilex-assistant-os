# M3 (master directive 2026-09-05 §2-B): the station boot script.
# Launched by the CORE through the bridge's whitelisted app entry (never a
# raw shell): starts OmniRoute, the Sara runner, and the workspace apps.
# Idempotent-ish: each step checks-before-starts so a second boot is quiet.

$ErrorActionPreference = "Continue"
$projectRoot = "C:\Projects\Git-hub\Vantrilex Assistant OS\Vantrilex Assistant OS - Architecture & Docs"

Set-Location $projectRoot

# 1) OmniRoute gateway — the brain's local router (localhost:20128/v1)
$omni = Get-Process -Name "omniroute" -ErrorAction SilentlyContinue
if (-not $omni) {
    Start-Process cmd.exe -ArgumentList "/c", "omniroute run" -WindowStyle Minimized
}

# 2) Sara & the bridge runners — the multi-agent launcher (46/46 self-test)
$sara = Get-Process -Name "pwsh" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like "*sara*" }
if (-not $sara) {
    Start-Process powershell.exe -ArgumentList "-ExecutionPolicy", "Bypass", "-File", ".\sara.ps1" -WindowStyle Minimized
}

# 3) VS Code at the project path
code $projectRoot

# 4) Obsidian at the vault path
Start-Process obsidian://open?path="$projectRoot\vault"

Write-Output "station boot complete"
