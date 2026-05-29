@echo off
REM Double-click to start the EvE-EMU Docker stack.
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-EveEmu.ps1" %*
if errorlevel 1 exit /b %errorlevel%
