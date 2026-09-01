# PostToolUse (ecc prettier-hook pattern, ruff edition): format + lint-fix every edited .py
$data = [Console]::In.ReadToEnd() | ConvertFrom-Json
$path = $data.tool_input.file_path
if ($path -and $path.EndsWith('.py') -and (Test-Path $path)) {
    $py = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
    if (Test-Path $py) {
        & $py -m ruff format $path 2>$null | Out-Null
        & $py -m ruff check --fix --quiet $path 2>$null | Out-Null
    }
}
exit 0
