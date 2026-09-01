@echo off
rem Double-click launcher for sara.ps1 (picks pwsh 7 when installed, else 5.1)
setlocal
set "PS=powershell"
where pwsh >nul 2>nul && set "PS=pwsh"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sara.ps1" %*
pause
