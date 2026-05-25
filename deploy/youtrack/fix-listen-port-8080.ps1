# Reset YouTrack to HTTP :8080 behind Caddy (fixes "listen port 8443" / browser not accessible).
# Caddy on https://pm.<domain> terminates TLS; YouTrack must listen on 8080 inside the container.
param(
    [string]$BaseUrl = $(if ($env:YOUTRACK_URL) { $env:YOUTRACK_URL } else { "https://pm.eve-emu.com" }),
    [string]$ImageTag = $(if ($env:YOUTRACK_VERSION) { $env:YOUTRACK_VERSION } else { "2026.1.13570" })
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $repoRoot

Write-Host "Stopping youtrack..."
docker compose stop youtrack

$volume = "eve-emu_eve_emu_youtrack_conf"
$volCheck = docker volume inspect $volume 2>$null
if (-not $volCheck) {
    $volume = "eve_emu_youtrack_conf"
    docker volume inspect $volume | Out-Null
}

Write-Host "Configuring listen-port=8080 base-url=$BaseUrl on volume $volume ..."
docker run --rm `
    -v "${volume}:/opt/youtrack/conf" `
    "jetbrains/youtrack:$ImageTag" `
    configure --listen-port=8080 --base-url=$BaseUrl

Write-Host "Starting youtrack..."
docker compose up -d youtrack

Pop-Location
Write-Host ""
Write-Host "Open: $BaseUrl"
Write-Host "Caddy proxies to youtrack:8080 (not 8443)."
