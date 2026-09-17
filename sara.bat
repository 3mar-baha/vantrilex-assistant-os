@echo off
rem Double-click launcher for sara.ps1 (picks pwsh 7 when installed, else 5.1)
setlocal
set "PS=powershell"
where pwsh >nul 2>nul && set "PS=pwsh"
if /i "%~1"=="-InstallAutoStart" (
  "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_autostart.ps1" %2 %3 %4 %5
  pause
  exit /b %ERRORLEVEL%
)
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sara.ps1" %*
pause
