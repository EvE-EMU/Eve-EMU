# EMU Manager Suite — Deployment

## Hostname

**Production:** `https://emums.eve-emu.com`

DNS: `emums.eve-emu.com` → same edge IP as `eve-emu.com` (A record to your Caddy host).

Production apex (`eve-emu.com`) does **not** serve EMUMS.

## Docker Compose

From repository root:

```bash
docker network create eve_emu_edge 2>/dev/null || true

docker compose \
  -f docker-compose.yml \
  -f docker-compose.emums.yml \
  up -d --build emums-mysql emums-api emums-web

# Reload Caddy after Caddyfile changes
docker compose restart caddy
```

## Services

| Service | Container | Port |
|---------|-----------|------|
| emums-mysql | eve-emu-emums-mysql | 3306 |
| emums-api | eve-emu-emums-api | 8020 |
| emums-web | eve-emu-emums-web | 3020 |

## Environment variables

Add to `.env` (or export before `up`):

```bash
EMUMS_API_KEY=emums-dev-key-change-me
EMUMS_MYSQL_ROOT_PASSWORD=emums-root-change-me
EMUMS_MYSQL_PASSWORD=emums
```

| Variable | Service | Description |
|----------|---------|-------------|
| `EMUMS_API_KEY` | api, web | Shared secret for API |
| `EMUMS_DATABASE_URL` | api | SQLAlchemy URL (set in compose) |
| `EMUMS_PUBLIC_BASE_URL` | api | CORS + OpenAPI server URL |
| `EMUMS_SEED_DEMO_DATA` | api | `1` = seed charts on first boot |
| `EMUMS_API_URL` | web (server) | Internal API base, e.g. `http://emums-api:8020/v1` |

## Health checks

```bash
curl -s https://emums.eve-emu.com/v1/health
curl -sI https://emums.eve-emu.com/
```

## Uptime notes

- `restart: unless-stopped` on all EMUMS services
- MySQL healthcheck gates API startup
- Next.js `output: standalone` for minimal runtime image
- API uses `pool_pre_ping` on MySQL connections
- GZip middleware on API responses >500 bytes
