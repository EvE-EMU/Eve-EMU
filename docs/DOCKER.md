# Unified Docker stack (EvE-EMU)

See the repository root **`docker-compose.yml`**, **`.env.example`**, and **`setup.sh`**.

## Operational checklist

1. **Alliance Auth submodule**  
   Run **`git submodule update --init allianceauth`** before the first **`docker compose build`**.  
   If the submodule directory is missing when Compose starts, Docker can create an **empty** `./allianceauth` mount target, and the optional **`PYTHONPATH`** hook in **`docker/django-aa/entrypoint.py`** will not see a real package tree.

2. **Postgres extra databases**  
   On first volume init, **`deploy/postgres/initdb/`** creates **`eve_emu_aa`**, **`wikijs`**, and **`wanderer`** (owner **`eve`**). If you change **`POSTGRES_USER`**, update those SQL files (or create DBs manually on existing volumes — see **docs/WANDERER.md** / **docs/WIKIJS.md**).

3. **Discord and EVE SSO**  
   Set **`DISCORD_BOT_TOKEN`** and **`ESI_CLIENT_ID`** / **`ESI_CLIENT_SECRET`** (and a correct **`ESI_CALLBACK_URL`**) in the root **`.env`** before expecting **`emu-bot`** or **`core-api`** SSO flows to work.

4. **`CORE_TOKEN_ENCRYPTION_KEY`**  
   **`./setup.sh`** runs **`deploy/patch_root_env.py`**, which needs **`cryptography`** on the host to generate a Fernet key. Install it (`pip install cryptography` or use a venv), or set **`CORE_TOKEN_ENCRYPTION_KEY`** manually in **`.env`** (see **`core/.env.example`** for the one-liner).

5. **Moon tax default from Compose**  
   Root **`MINING_TAX_RATE`** is passed into the **`core-api`** container as **`CORE_MOON_TAX_PERCENT_OF_OWED_VALUE`** (see **`docker-compose.yml`**). Adjust in **`.env`** for deployment-wide defaults; prefer DB-backed overrides later for director-editable policy.

## Services (root Compose)

| Service | Role |
|---------|------|
| **db** | Postgres: core DB (`POSTGRES_DB_CORE`) + AA DB (`POSTGRES_DB_AA`, created on first init). |
| **redis** | Broker/backend for Celery and general caching patterns. |
| **core-api** | FastAPI **`core/`** (canonical EVE SSO callback host). |
| **core-web** | Next.js **`core-web/`** (standalone image). |
| **emu-bot** | Discord bot; **`DISCORD_*`** in **`.env`** mapped to **`EVE_*`** in the container. |
| **aa-web** | **Alliance Auth** (Gunicorn, plain HTTP on **8080** inside the Compose network only — not published to the host by default). |
| **wanderer** | [Wanderer CE](https://github.com/wanderer-industries/wanderer) EVE mapper + **wanderer-route-builder** + **wanderer-kills**; DB **`wanderer`**. |
| **caddy** | **Reverse proxy** on **80**/**443**: **`https://<DOMAIN_NAME>`** → **core-web**; **`https://auth.<DOMAIN_NAME>`** → **aa-web**; **`https://wiki.<DOMAIN_NAME>`** → **wikijs**; **`https://wh.<DOMAIN_NAME>`** → **wanderer**. |
| **aa-worker** | Celery worker: **`celery -A eve_auth worker`**. |
| **aa-beat** | Celery beat: **`celery -A eve_auth beat`** (django-celery-beat schedules from AA). |

## Public hostnames

| URL | Service |
|-----|---------|
| **`https://eve-emu.com`** ( **`DOMAIN_NAME`** ) | Public site (**core-web**) |
| **`https://auth.eve-emu.com`** | Alliance Auth (**aa-web**) — set **`AA_SITE_URL`** |
| **`https://wiki.eve-emu.com`** | Wiki.js |
| **`https://wh.eve-emu.com`** | Wanderer (EVE mapper) — [WANDERER.md](./WANDERER.md) |

**`AA_SITE_URL`** configures Django (links, CSRF, SSO callback **`{AA_SITE_URL}/sso/callback/`**). It does **not** open firewall ports.

The stack publishes **`caddy`** on host **`80`** and **`443`**. **Caddy** proxies **`auth.<DOMAIN_NAME>`** to **`aa-web:8080`** (Gunicorn, internal only). **`aa-web`** is not published on host `8080` by default.

### HTTP 502 from Caddy after restarting `aa-web`

On each **`aa-web`** start, the entrypoint runs **migrate** and **collectstatic** (~20–60s) before **Gunicorn** listens on **8080**. Caddy returns **502** if it proxies during that window or still targets an old container IP.

1. Wait until **`aa-web`** is healthy: `docker compose ps aa-web` should show **`(healthy)`**.
2. After recreating **`aa-web`**, restart Caddy so it picks up the new upstream: `docker compose up -d --force-recreate caddy` (or `docker compose restart caddy`).
3. Compose now gates **`caddy`** on **`aa-web`** health and re-resolves **`aa-web`** via Docker DNS in **`docker/caddy/Caddyfile`**.

To serve production hostnames:

1. **DNS** — **`eve-emu.com`**, **`auth.eve-emu.com`**, **`wiki.eve-emu.com`**, and **`wh.eve-emu.com`** (A/AAAA) → your public IP. **`DOMAIN_NAME=eve-emu.com`** in **`.env`**.
2. **Firewall** — Allow **80** and **443** inbound to the Docker host.
3. **Router** — Forward **WAN 80/443 → LAN:80/443** on the Docker host (not `8080` unless debugging without Caddy).
4. **Alliance Auth** — **`AA_SITE_URL=https://auth.eve-emu.com`**, **`AA_ALLOWED_HOSTS=auth.eve-emu.com`**. CCP callback (one URL): **`https://auth.eve-emu.com/sso/callback/`**. Rebuild **core-web** after changing **`AA_SITE_URL`** so the public site link is correct.
5. Check **`docker compose logs caddy`** if HTTPS fails (Let’s Encrypt needs reachable **80**/**443**).

### Home LAN + router port forward (e.g. Windows `192.168.50.x`)

- **Caddy** listens on the Docker host at **`0.0.0.0:80`** and **`0.0.0.0:443`**. Forward the router’s **WAN 80** and **WAN 443** to **`192.168.50.24:80`** and **`192.168.50.24:443`** (your Wi‑Fi address), not to an old **`…:8080`** rule unless you add a separate direct publish for debugging.
- **`DOMAIN_NAME`** must match the hostname users type (e.g. **`eve-emu.com`**). **`www`** is not included automatically; extend **`docker/caddy/Caddyfile`** if you need **`www`**.
- Use **`AA_SITE_URL=https://auth.eve-emu.com`** once HTTPS works; **`http://`** is only for setups without TLS on Caddy.

### `ERR_CONNECTION_TIMED_OUT` (not “refused”)

A **timeout** usually means the SYN never got a reply: traffic was **dropped** or sent to the **wrong place**, not that the app answered “no.”

1. **Confirm the forward targets Caddy** — Prefer **WAN 80 → LAN `192.168.50.24:80`** and **WAN 443 → LAN `192.168.50.24:443`**. **`aa-web`** is only reachable on **`8080` inside the Compose network** (Caddy → `aa-web:8080`).
2. **Windows Defender Firewall** — Allow **inbound** TCP **80** and **443** for Docker Desktop / WSL as applicable.
3. **Public IP / CGNAT** — From a phone on **cellular** (not Wi‑Fi), try `http://YOUR_WAN_IP:80`. If it always times out, your ISP may use **CGNAT** (no inbound IPv4); port forwarding will not work without IPv6, a tunnel (Cloudflare Tunnel, Tailscale Funnel), or a VPS.
4. **Double NAT** — If the “router” you configure is not the one that actually holds the public IP, forwards never hit your PC.

## Alliance Auth + `core/` SSO

Alliance Auth uses **`AA_SITE_URL`** and **`ESI_CALLBACK_URL`** (see **`.env.example`**). Register **`{AA_SITE_URL}/sso/callback/`** on your CCP app (must match character-for-character). FastAPI **`core-api`** uses a separate path—see **`docs/ALLIANCE_AUTH.md`**.
