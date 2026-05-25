# Keep this window open while playing — forwards EVE chat logs to wh-intel.
# If scripts are blocked, use run_intel_tailer.cmd or:
#   powershell -ExecutionPolicy Bypass -File .\wh_intel\scripts\run_intel_tailer.ps1
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path "$RepoRoot\wh_intel\scripts\intel_chat_tailer.py")) {
    $RepoRoot = Split-Path $PSScriptRoot -Parent
}
Set-Location $RepoRoot

$ChatDir = Join-Path $env:USERPROFILE "Documents\EVE\logs\Chatlogs"
if (-not (Test-Path $ChatDir)) {
    Write-Host "EVE chat folder not found: $ChatDir"
    Write-Host "Set EVE_CHATLOGS to your Chatlogs path, or fix --dir below."
}

$Api = $env:WH_INTEL_INGEST_URL
if (-not $Api) { $Api = "https://wh.eve-emu.com/intel/api/v1/ingest" }

Write-Host "Repo: $RepoRoot"
Write-Host "API:  $Api"
Write-Host "Logs: $ChatDir"
Write-Host ""
Write-Host "You should see 'ingested N ping(s)' when intel hits. Ctrl+C to stop."
Write-Host ""

python "$RepoRoot\wh_intel\scripts\intel_chat_tailer.py" --api $Api --dir $ChatDir
