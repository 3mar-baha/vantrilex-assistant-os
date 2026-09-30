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
if /i "%~1"=="-Trace" (
  start "SARA Shadow Tracer" "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\live_shadow_tracer.py" %2 %3 %4 %5
  exit /b %ERRORLEVEL%
)
rem --tracer is the double-dash spelling of -Trace. Batch has no function to share
rem one command between two `if` blocks, so the command line is repeated verbatim;
rem tests/test_launcher_flags.py holds the two bodies byte-identical, which is what
rem keeps the alias from drifting into a second implementation.
rem NOTE: do NOT fold these two into `if /i "%~1"=="-Trace" if /i "%~1"=="--tracer" (`
rem -- cmd reads chained `if`s as a conjunction, so that block would never run.
if /i "%~1"=="--tracer" (
  start "SARA Shadow Tracer" "%~dp0.venv\Scripts\python.exe" "%~dp0scripts\live_shadow_tracer.py" %2 %3 %4 %5
  exit /b %ERRORLEVEL%
)
if /i "%~1"=="-Chat" (
  "%~dp0.venv\Scripts\python.exe" -m src.bot_shell %2 %3 %4 %5
  exit /b %ERRORLEVEL%
)
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sara.ps1" %*
pause
