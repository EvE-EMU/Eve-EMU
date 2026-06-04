# Test environment (`test.eve-emu.com`)

Isolated Alliance Auth + core site for staging (aa-moonmining surveys/extractions; **moonrentals** renter module not deployed).

Production Caddy on the same host terminates TLS and proxies to the test containers on Docker network `eve_emu_edge`.

## DNS

Point these records at the same host as production:

| Host | Purpose |
|------|---------|
| `test.eve-emu.com` | Core web + market tools |
| `auth.test.eve-emu.com` | Alliance Auth |
| `wiki.test.eve-emu.com` | Wiki.js (optional) |

## One-time setup

```powershell
cd C:\Users\BDD\Documents\GitHub\eve-emu
Copy-Item .env.test.example .env.test
# Edit .env.test: POSTGRES_PASSWORD, ESI_*, AA_DJANGO_SECRET_KEY (or run bootstrap script)

# Alliance Auth 5.1.x provider compat (host submodule file; mount is read-only in container)
$env:ALLIANCEAUTH_ROOT = "$PWD\allianceauth"
python deploy\aa_docker\patch_allianceauth_providers_compat.py

docker network create eve_emu_edge
```

Add to your CCP developer application:

- `https://auth.test.eve-emu.com/sso/callback`

## Start test stack

```powershell
.\deploy\test\bootstrap.ps1
```

Or manually:

```powershell
docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test up -d --build `
  db redis wikijs aa-web aa-worker aa-beat core-api core-web market-api market-web

docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test exec aa-web python manage.py migrate
```

Reload production Caddy after the first test deploy (picks up `eve_emu_edge` + test routes):

```powershell
docker compose up -d caddy
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Stop test stack

```powershell
docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.test down
```

Volumes `eve_emu_test_*` keep the test database; add `-v` to wipe.

## Notes

- Production and test run as separate Compose projects (`eve-emu` vs `eve-emu-test`).
- Test does not publish ports 80/443; only production `caddy` binds them.
- Optional services (`wanderer`, `youtrack`, `emu-bot`, `aa-discordbot`) are disabled unless you pass `--profile test-heavy`.
