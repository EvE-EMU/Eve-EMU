# Start test.eve-emu.com stack (isolated DB, shared production Caddy on eve_emu_edge).
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root

$envFile = Join-Path $Root '.env.test'
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root '.env.test.example') $envFile
    Write-Host 'Created .env.test from example - set ESI_* and POSTGRES_PASSWORD before production use.'
}

python (Join-Path $PSScriptRoot 'patch_test_env.py')

$aaRoot = Join-Path $Root 'allianceauth'
if (Test-Path $aaRoot) {
    $env:ALLIANCEAUTH_ROOT = $aaRoot
    python (Join-Path $Root 'deploy\aa_docker\patch_allianceauth_providers_compat.py')
}

# Production Caddy must own eve_emu_edge (compose-managed network).
docker compose up -d caddy

$services = @(
    'db', 'redis', 'wikijs',
    'aa-web', 'aa-worker', 'aa-beat',
    'core-api', 'core-web', 'market-api', 'market-web'
)

docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test up -d --build @services

Write-Host 'Waiting for aa-web health...'
$deadline = (Get-Date).AddMinutes(12)
do {
    Start-Sleep -Seconds 5
    $h = docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test ps aa-web --format json 2>$null | ConvertFrom-Json
    if ($h.Health -eq 'healthy') { break }
} while ((Get-Date) -lt $deadline)

docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test exec -T aa-web python manage.py migrate --noinput
docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test exec -T aa-web python manage.py migrate moonrentals --noinput

docker compose up -d caddy
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile 2>$null

Write-Host ''
Write-Host 'Test stack up.'
Write-Host '  Site: https://test.eve-emu.com/'
Write-Host '  Auth: https://auth.test.eve-emu.com/'
Write-Host '  Moon rentals: https://auth.test.eve-emu.com/moonmining/rentals/'
