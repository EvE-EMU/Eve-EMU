# Reinstall stock aa-miningtaxes from PyPI (no eve-emu template overrides).
# Run from repo root: .\deploy\aa_docker\scripts\reinstall_miningtaxes.ps1

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\..\.."))

Write-Host "Reinstalling aa-miningtaxes==2.0.1 in aa-web..."
docker compose exec -T aa-web pip install --no-cache-dir --force-reinstall --no-deps "aa-miningtaxes==2.0.1"

Write-Host "Migrate + collectstatic..."
docker compose exec -T aa-web python manage.py migrate miningtaxes --noinput
docker compose exec -T aa-web python manage.py collectstatic --noinput

Write-Host "Optional: preload ore prices (first-time / after wipe)..."
docker compose exec -T aa-web python manage.py miningtaxes_preload_prices 2>$null

Write-Host "Restarting AA services..."
docker compose restart aa-web aa-worker aa-beat

Write-Host "Done. Open /miningtaxes/ — stock Mining Taxes UI (tax summary, ore prices, FAQ)."
