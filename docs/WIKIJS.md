# Wiki.js + Alliance Auth services

Wiki.js runs as a Compose service and is linked to the **Wiki.JS** entry on Alliance Auth Services (`https://auth.<your-domain>/services/`) via the [allianceauth-wiki-js](https://apps.allianceauth.org/apps/detail/allianceauth-wiki-js) plugin (already in the `aa-web` image).

## Architecture

| Component | Role |
|-----------|------|
| `wikijs` container | [Wiki.js](https://wiki.js.org/) on port 3000 |
| `wiki.<DOMAIN_NAME>` | Public URL (Caddy TLS) — set `WIKIJS_URL` to this |
| `http://wikijs:3000` | Internal GraphQL API — `WIKIJS_API_URL` for `aa-web` |
| `/services/` | Users **Activate** Wiki.JS; AA creates the wiki account and syncs groups |

## First-time setup

### 1. DNS

Add **`wiki.eve-emu.com`** (or `wiki.<your DOMAIN_NAME>`) pointing at the same host as the main site so Caddy can obtain a certificate.

### 2. Start Wiki.js

```bash
docker compose up -d wikijs
```

On a **new** Postgres volume, database `wikijs` is created automatically. If the DB volume already existed before Wiki.js was added:

```bash
docker compose exec db psql -U eve -d postgres -c "CREATE DATABASE wikijs OWNER eve;"
```

### 3. Complete the Wiki.js setup wizard

Open **`https://wiki.<your-domain>`** (e.g. https://wiki.eve-emu.com).

- Use **PostgreSQL** (already configured by Compose).
- Set the **Site URL** to the same public URL (`https://wiki.eve-emu.com`).
- Create the initial admin user (email should match what users will use in AA if possible).

### 4. Create a Wiki.js API key

In Wiki.js: **Administration → API → Create API key**

- Name: `Alliance Auth`
- Full access, long expiry
- Copy the key once (it is not shown again).

Add to root `.env`:

```env
WIKIJS_URL=https://wiki.eve-emu.com
WIKIJS_API_URL=http://wikijs:3000
WIKIJS_API_KEY=<paste-api-key-here>
```

Restart Alliance Auth:

```bash
docker compose up -d aa-web aa-worker
```

`WIKIJS_API_URL` must be reachable from inside `aa-web` (Docker service name `wikijs`, not the public HTTPS URL). This fixes GraphQL errors like `unknown url type: '/graphql'`.

### 5. Alliance Auth permissions

1. **Django Admin → Authentication → Permissions** — ensure users have **`wikijs | wiki js | Can access the WikiJS service`** (`access_wikijs`), or add it to their auth groups / states.
2. For wiki **administrators**, create a Django auth group named **`Administrators`** and assign it to those users ([plugin FAQ](https://apps.allianceauth.org/apps/detail/allianceauth-wiki-js)).
3. Enable the service for the right **states** under **Services** configuration in AA if you use state-restricted services.

### 6. User flow

1. Log in to Alliance Auth.
2. Open **Services** → **Wiki.JS** → **Activate**.
3. Set password when prompted (or use reset/set password actions).
4. Open the wiki link; log in with the email/password managed by AA.

## Local / dev without a wiki subdomain

```env
WIKIJS_PUBLISH_PORT=3080
WIKIJS_URL=http://localhost:3080
WIKIJS_API_URL=http://wikijs:3000
```

Publish port is optional; Caddy is not required for local Wiki.js access.

## EVE SDE reference (full import)

The `sde_wiki` app can publish the **entire django-eveonline-sde** database into Wiki.js under **`/sde`**, with an EVE **ESI / Swagger UI** dark theme.

### Prerequisites

1. SDE loaded in Postgres: `docker compose exec aa-web python manage.py esde_load_sde`
2. Wiki.js API key configured (`WIKIJS_API_URL`, `WIKIJS_API_KEY`) — see above.
3. Rebuild `aa-web` after pulling changes that add `sde_wiki`.

### Apply ESI theme

```bash
docker compose exec aa-web python manage.py wikijs_apply_esi_theme
```

This sets Wiki.js **dark mode** and injects custom CSS (colors/fonts similar to [esi.evetech.net/ui](https://esi.evetech.net/ui/)). You can tweak `sde_wiki/assets/eve-esi-theme.css` and re-run the command.

### Purge SDE pages (start fresh)

If import shows hundreds of `already exists at the same path (6002)` errors, purge and re-import:

```bash
docker compose build aa-web && docker compose up -d aa-web
docker compose exec aa-web python manage.py wikijs_purge_sde
docker compose exec aa-web python manage.py wikijs_purge_sde --force
# If the API reports only a few pages but the wiki still has thousands of /sde pages:
docker compose exec aa-web python manage.py wikijs_purge_sde --via-db --force
docker compose exec aa-web python manage.py wikijs_import_sde --fast
```

### Import SDE pages

**SDE data is already local** — the importer reads Django `eve_sde` tables in Postgres (load once with `esde_load_sde`). What is slow is **Wiki.js GraphQL** (one HTTP call per page). Use **`--via-db`** to batch-insert into the Wiki.js database instead.

**Recommended (fast + via-db):** ~10k pages, no per-page GraphQL:

```bash
docker compose build aa-web && docker compose up -d aa-web
# One-time: load SDE into Alliance Auth Postgres (downloads JSONL from CCP if needed)
docker compose exec aa-web python manage.py esde_load_sde
docker compose exec aa-web python manage.py wikijs_purge_sde --via-db --force
docker compose exec aa-web python manage.py wikijs_apply_esi_theme
docker compose exec aa-web python manage.py wikijs_import_sde --fast --via-db
docker compose exec aa-web python manage.py wikijs_render_sde
```

Typical runtime: import a few minutes; **render** ~30–90 min for ~50k pages (required — pages are blank without it).

Slower GraphQL path: `wikijs_import_sde --fast --turbo` (8 parallel HTTP writers).

**After a fast import**, add detail pages (systems, items, dogma) and fix index links:

```bash
docker compose exec aa-web python manage.py wikijs_import_sde --remainder --via-db
docker compose exec aa-web python manage.py wikijs_render_sde
```

Expect ~65k additional pages. Use `--published-types-only` to omit unpublished item types.

```bash
# Full import (every item type + dogma detail page — hours even with optimizations)
docker compose exec aa-web python manage.py wikijs_import_sde

# Resume / skip pages already in wiki (default)
docker compose exec aa-web python manage.py wikijs_import_sde --fast

# If turbo hits pageTree FK errors, retry with one writer + settle delay:
docker compose exec aa-web python manage.py wikijs_import_sde --fast --workers 1 --tree-settle-ms 75

# Sections only
docker compose exec aa-web python manage.py wikijs_import_sde --fast --section map
docker compose exec aa-web python manage.py wikijs_import_sde --section types --update-existing

# Full import, published types only (~smaller than 52k type pages)
docker compose exec aa-web python manage.py wikijs_import_sde --published-types-only
```

**Speed optimizations (built in):** `--via-db` batch SQL writes; `--fast` skips per-type, per-system, and dogma detail pages; `--turbo` parallel GraphQL (when not using `--via-db`); tree rebuild once at end.

**Structure:**

| Path | Content |
|------|---------|
| `/sde` | SDE home, build number, links |
| `/sde/map/regions`, `.../constellations/<id>`, `.../systems/<id>` | Universe (`systems` only on full import) |
| `/sde/types/categories`, `groups`, `market-groups`, `items/<type_id>` | Types |
| `/sde/dogma/attributes`, `effects` | Dogma |
| `/sde/industry/blueprints/<type_id>` | Blueprint activities |

By default, existing pages are **skipped** so you can resume a long import. Use `--update-existing` to refresh content.

Options: `--fast`, `--via-db`, `--turbo`, `--workers`, `--tree-settle-ms` (default 0), `--db-batch-size`, `--section`, `--dry-run`, `--throttle-ms`, `--progress-interval`, `--published-types-only`, `--render`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Services shows Wiki.JS but activate fails | `WIKIJS_API_KEY` set? `WIKIJS_API_URL=http://wikijs:3000`? `docker compose logs aa-web` |
| `unknown url type: '/graphql'` | `WIKIJS_API_URL` empty or wrong — use internal `http://wikijs:3000` |
| 502 on wiki subdomain | `docker compose ps wikijs`; wait for DB; check `docker compose logs wikijs` |
| “Page has no rendered version” on /sde | After `--via-db` import, run `python manage.py wikijs_render_sde` |
| Lost wiki admin | Add AA group **`Administrators`** to your user |
