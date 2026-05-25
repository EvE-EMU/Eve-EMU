@echo off
REM Bypass PowerShell execution policy for this repo script only.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix-listen-port-8080.ps1" %*
