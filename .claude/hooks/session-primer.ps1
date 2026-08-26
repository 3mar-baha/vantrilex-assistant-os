# SessionStart hook — prime mission + phase context before any action.
$root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Write-Output "[primer] Vantrilex Assistant OS v1.1.0 - Sara | owner-only | `$0.00/month | VPS-primary + outbound-only PC bridge"
$state = Join-Path $root ".claude/PHASE-STATE.md"
if (Test-Path $state) { Get-Content $state -Encoding UTF8 }
else { Write-Output "[primer] WARNING: .claude/PHASE-STATE.md missing - rebuild phase state before acting." }
