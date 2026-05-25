@echo off
setlocal
cd /d "%~dp0..\.."

set "CHATDIR=%USERPROFILE%\Documents\EVE\logs\Chatlogs"
if defined EVE_CHATLOGS set "CHATDIR=%EVE_CHATLOGS%"

if not defined WH_INTEL_INGEST_URL set "WH_INTEL_INGEST_URL=https://wh.eve-emu.com/intel/api/v1/ingest"

echo Repo: %CD%
echo API:  %WH_INTEL_INGEST_URL%
echo Logs: %CHATDIR%
echo.
echo Keep this window open while playing. You should see "ingested N ping(s)" on intel.
echo.

python "%CD%\wh_intel\scripts\intel_chat_tailer.py" --api "%WH_INTEL_INGEST_URL%" --dir "%CHATDIR%"
pause
