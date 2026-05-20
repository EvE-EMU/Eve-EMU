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

# Session signing — at least 64 characters (e.g. openssl rand -base64 64)
WANDERER_SECRET_KEY_BASE=
# Encrypts stored EVE tokens (AES-256-GCM) — must decode to exactly 32 bytes:
#   openssl rand -base64 32
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
- **Permissions** — enable these on the CCP app (do **not** add `esi-search.search_structures.v1`; CCP removed it and login fails with `invalid_scope`):
  - `esi-location.read_location.v1`
  - `esi-location.read_ship_type.v1`
  - `esi-location.read_online.v1`
  - `esi-ui.write_waypoint.v1`

The Compose **`wanderer`** service runs `sed` on boot to strip the obsolete scope from **`runtime.exs`** and **`sys.config`** (the release bakes scopes into `sys.config`; patching only `runtime.exs` is not enough).

This callback is **not** Alliance Auth (`auth.*`) or FastAPI core (`/v1/auth/eve/callback`).

### `invalid_scope` / `esi-search.search_structures.v1`

CCP no longer accepts **`esi-search.search_structures.v1`**. Upstream CE still requests it; this repo patches it out at container start. After pulling compose changes:

```bash
docker compose up -d --force-recreate wanderer
```

Remove that scope from your app on [developers.eveonline.com](https://developers.eveonline.com/) if you added it manually.

## Deploy

```bash
# New DB only on fresh Postgres volume — existing installs:
docker compose exec db psql -U eve -d postgres -c "CREATE DATABASE wanderer OWNER eve;"

docker compose pull wanderer wanderer-route-builder wanderer-kills
docker compose up -d wanderer-route-builder wanderer-kills wanderer
# Required after adding `wh.*` to the Caddyfile so Let's Encrypt issues a cert for wh.<domain>
docker compose up -d --force-recreate caddy
```

### `ERR_SSL_PROTOCOL_ERROR` on `https://wh.<domain>`

Usually one of:

1. **Wanderer stack not running** — `docker compose ps wanderer` should show **Up**. Start with the commands above.
2. **Caddy started before the `wh.*` site block existed** — Caddy had no TLS cert for `wh.eve-emu.com` yet. Run `docker compose up -d --force-recreate caddy` and check `docker compose logs caddy | grep wh.`.
3. **Postgres `wanderer` database missing** (existing volume) — create it (see above), then `docker compose restart wanderer`.

DNS for **`wh.<DOMAIN_NAME>`** must point at the same host as **`auth.<DOMAIN_NAME>`** (A/AAAA to your public IP).

### HTTP 500 on `/welcome` (`secret_key_base` too short)

Wanderer logs:

```text
cookie store expects conn.secret_key_base to be at least 64 bytes
```

**Fix:** set **`WANDERER_SECRET_KEY_BASE`** in root **`.env`** (non-empty, ≥64 characters), then:

```bash
docker compose up -d --force-recreate wanderer
```

Check (length only, not the secret):

```bash
docker compose exec wanderer sh -c 'test ${#SECRET_KEY_BASE} -ge 64 && echo OK || echo TOO_SHORT'
```

### HTTP 500 on `/auth/eve/callback` (`Unknown cipher or invalid key size`)

EVE login can succeed (you get a `code=` in the URL) but Wanderer crashes when saving your character tokens. Logs show:

```text
[AuthController] SSO callback SUCCESS ...
Unknown cipher or invalid key size
```

**Cause:** **`WANDERER_CLOAK_KEY`** is not a valid AES-256 key. Do **not** reuse `openssl rand -base64 64` here — that decodes to 48 bytes. Use a **32-byte** key:

```bash
openssl rand -base64 32
```

Paste into **`WANDERER_CLOAK_KEY`**, then `docker compose up -d --force-recreate wanderer`, and log in with EVE again (the old callback URL is one-time).

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
