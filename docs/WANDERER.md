# Wanderer (EVE mapper) — `wh.<DOMAIN>`

[Wanderer Community Edition](https://github.com/wanderer-industries/community-edition) is an EVE Online mapper (Pathfinder-style), integrated into the root Compose stack and exposed at **`https://wh.<DOMAIN_NAME>`** (e.g. **`https://wh.eve-emu.com`**) via Caddy.

Upstream: [wanderer-industries/wanderer](https://github.com/wanderer-industries/wanderer) · CE images: `wandererltd/community-edition`.

## Services

| Compose service | Image | Role |
|-----------------|-------|------|
| **wanderer** | `wandererltd/community-edition:latest` | Phoenix app (port **8000**) |
| **wanderer-route-builder** | `wandererltd/eve-route-builder:main` | Route calculation |
| **wanderer-kills** | `wandererltd/wanderer-kills:latest` | Killmail / kills WebSocket service |

Postgres database **`wanderer`** is created on first DB volume init (`deploy/postgres/initdb/03-create-wanderer-db.sql`). Wanderer does **not** use a separate Postgres container.

## DNS and Caddy

Add **`wh.eve-emu.com`** (or **`wh.<DOMAIN_NAME>`**) as an **A/AAAA** record to the same host as **`eve-emu.com`**.

Caddy block: `wh.{$SITE_HOST}` → `wanderer:8000` (see `docker/caddy/Caddyfile`).

## `.env` configuration

Add to your root **`.env`** (generate secrets once):

```bash
# Public URL (must match Caddy hostname)
WANDERER_URL=https://wh.eve-emu.com

# openssl rand -base64 48  (run twice)
WANDERER_SECRET_KEY_BASE=
WANDERER_CLOAK_KEY=

# EVE SSO — separate CCP application recommended (see below)
WANDERER_EVE_CLIENT_ID=
WANDERER_EVE_CLIENT_SECRET=

# Optional; defaults to wanderer
# POSTGRES_DB_WANDERER=wanderer
```

### EVE Developer application

Create an application at [developers.eveonline.com](https://developers.eveonline.com/) (or reuse credentials only if callbacks allow multiple URLs).

- **Callback URL:** `https://wh.eve-emu.com/auth/eve/callback` (must match **`WANDERER_URL`** + `/auth/eve/callback`)
- **Permissions** (from [CE docs](https://github.com/wanderer-industries/community-edition)):  
  `esi-location.read_location.v1`, `esi-location.read_ship_type.v1`, `esi-search.search_structures.v1`, `esi-ui.write_waypoint.v1`, `esi-location.read_online.v1`

This callback is **not** Alliance Auth (`auth.*`) or FastAPI core (`/v1/auth/eve/callback`).

## Deploy

```bash
# New DB only on fresh Postgres volume — existing installs:
docker compose exec db psql -U eve -d postgres -c "CREATE DATABASE wanderer OWNER eve;"

docker compose pull wanderer wanderer-route-builder wanderer-kills
docker compose up -d wanderer-route-builder wanderer-kills wanderer
docker compose up -d --force-recreate caddy
```

First start runs DB migrations inside the **wanderer** container (can take 1–2 minutes). Check logs:

```bash
docker compose logs -f wanderer
```

## Local / no TLS

For LAN testing without `wh.eve-emu.com` DNS, add a hosts entry or use Compose port publish (not enabled by default). Set:

```env
WANDERER_URL=http://localhost:8000
```

and temporarily publish **`8000:8000`** on **wanderer** (not recommended for production).

## Notes

- Wanderer data lives in Postgres database **`wanderer`**; back it up with your other DBs.
- Upgrades: `docker compose pull` on the three images, then `docker compose up -d wanderer`.
- CE support: [GitHub discussions](https://github.com/orgs/wanderer-industries/discussions/4).
