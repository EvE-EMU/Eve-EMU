# Start the EvE-EMU Docker stack (production). Run from repo root or double-click Start-EveEmu.cmd.
#
#   .\Start-EveEmu.ps1
#   .\Start-EveEmu.ps1 -InstallStartup    # add shortcut to Windows logon (Startup folder)
#   .\Start-EveEmu.ps1 -Quiet             # no extra output (for Startup)

param(
    [switch]$InstallStartup,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
if (-not (Test-Path (Join-Path $Root 'docker-compose.yml'))) {
    throw "docker-compose.yml not found in $Root"
}

function Write-Info([string]$Message) {
    if (-not $Quiet) {
        Write-Host $Message
    }
}

function Install-StartupShortcut {
    $ps1 = Join-Path $Root 'Start-EveEmu.ps1'
    $startup = [Environment]::GetFolderPath('Startup')
    $lnkPath = Join-Path $startup 'Start EvE-EMU.lnk'
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnkPath)
    $sc.TargetPath = (Get-Command powershell.exe).Source
    $sc.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ps1`" -Quiet"
    $sc.WorkingDirectory = $Root
    $sc.Description = 'Start EvE-EMU Docker stack on logon'
    $sc.WindowStyle = 7
    $sc.Save()
    Write-Host "Installed Startup shortcut: $lnkPath"
}

if ($InstallStartup) {
    Install-StartupShortcut
    exit 0
}

Set-Location $Root

if (-not (Test-Path (Join-Path $Root '.env'))) {
    Write-Info 'No .env found — copy .env.example to .env and configure secrets first.'
    if (-not $Quiet) {
        Read-Host 'Press Enter to exit'
    }
    exit 1
}

Write-Info 'Waiting for Docker…'
$dockerReady = $false
for ($i = 0; $i -lt 90; $i++) {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $dockerReady) {
    Write-Info 'Docker is not available. Start Docker Desktop, then run this script again.'
    if (-not $Quiet) {
        Read-Host 'Press Enter to exit'
    }
    exit 1
}

$aaRoot = Join-Path $Root 'allianceauth'
if (Test-Path $aaRoot) {
    $env:ALLIANCEAUTH_ROOT = $aaRoot
    $compat = Join-Path $Root 'deploy\aa_docker\patch_allianceauth_providers_compat.py'
    if (Test-Path $compat) {
        python $compat 2>$null
    }
}

Write-Info 'Starting EvE-EMU (docker compose up -d)…'
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Info 'docker compose up failed.'
    if (-not $Quiet) {
        Read-Host 'Press Enter to exit'
    }
    exit $LASTEXITCODE
}

Write-Info 'Done. Sites come up after aa-web is healthy (1–3 min).'
Write-Info '  docker compose ps'
Write-Info '  https://auth.eve-emu.com/  https://eve-emu.com/'

if (-not $Quiet) {
    Read-Host 'Press Enter to close'
}
