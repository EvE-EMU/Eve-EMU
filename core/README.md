# EVE-EMU **Core**

Central platform service: **authentication** (EVE SSO + eve-emu sessions), **SDE** access, **EVE image URLs**, **Postgres**, and a **stable OpenAPI** surface for other apps (`fleet-tracker`, bots, etc.).

**Alliance-style main web portal:** use **[Alliance Auth v5](https://allianceauth.readthedocs.io/en/v5.0.1/)** from the **`allianceauth/`** Git submodule (Django). See **`docs/ALLIANCE_AUTH.md`**. **`core-web/`** (Next.js) is optional for custom pages that call this API; **`core/`** remains the **FastAPI backend** for SDE, Discord bot plugins, and related services.

- **OpenAPI**: served at `/openapi.json`, interactive docs at `/docs` (disable in production if desired).
- **Plugin API**: versioned under **`/v1/...`** — keep compatibility; extend with new routes or `/v2` when breaking.

## EVE Online SDE (static data) in **core**

All SDE used by eve-emu tools should be **read from core** (Postgres + **`/v1/sde/...`**) so plugins stay small and data stays consistent.

### Tables (created automatically)

| Table | Source (Fuzzwork SQLite) | API |
|-------|---------------------------|-----|
| `sde_inv_groups` | `invGroups` | `GET /v1/sde/groups/{group_id}`, `GET /v1/sde/groups/{group_id}/types` |
| `sde_types` | `invTypes` | `GET /v1/sde/types/{type_id}`, `GET /v1/sde/types?q=` |
| `sde_map_solar_systems` | `mapSolarSystems` | `GET /v1/sde/systems/{id}`, `GET /v1/sde/systems/by-name/{name}`, `GET /v1/sde/systems?q=` |

Type responses include **`icon_url`** and **`render_url`** pointing at **`images.evetech.net`** (see `app/media/evetech.py`).

### One-time import (Fuzzwork dump)

1. Download and decompress the SQLite SDE, e.g. from [Fuzzwork dump — sqlite-latest](https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2).
2. Ensure Postgres is running and **`CORE_DATABASE_URL`** matches (same as the API).
3. Start **core** once so `create_all` runs **or** run migrations later — tables `sde_*` must exist.
4. Run:

```bash
cd core
set PYTHONPATH=.
set CORE_DATABASE_URL=postgresql+asyncpg://eve:eve@localhost:5432/eve_emu_core
python scripts/import_sde_sqlite.py --sqlite C:\path\to\sqlite-latest.sqlite
```

Default **`--replace`** truncates `sde_*` before load. Use **`--no-replace`** only if you know rows will not conflict.

5. Check **`GET /v1/sde/status`** for row counts.

To add more SDE (regions, constellations, dogma, etc.), extend **`app/sde/models.py`**, the importer, and **`/v1/sde`** routes in the same pattern.

## EVE Image server (EVE Tech / `images.evetech.net`)

Use **HTTPS** image URLs from CCP’s CDN (tenant `tranquility` where applicable). Helpers live in `app/media/evetech.py` (type icons, character portraits, corporation logos, alliance logos).

Docs: [EVE Developer documentation](https://developers.eveonline.com/) (image patterns are stable and widely used by third-party tools).

## Authentication

- **EVE SSO** (OAuth2): users prove a Tranquility character; `core` exchanges the code, stores **refresh token** encrypted in Postgres (`app/db/token_store.py`), issues **eve-emu session** (e.g. HTTP-only cookie + server-side session, or JWT for APIs). Set **`CORE_TOKEN_ENCRYPTION_KEY`** so ciphertext survives restarts and remains decryptable.
- **Plugin trust**: browser → `core`; other services use **service tokens** or **mTLS** (to be defined) calling **`/v1/...`** with reduced scopes.

Implementations belong in `app/auth/` (routes, token storage, middleware).

### Multi-character identity (“still the same person”)

Design intent:

1. **Stable eve-emu user** — table **`core_users`**: one UUID (`id`) per linked EVE paying account. That UUID is what plugins should store as “who logged in”; it does not change when a character renames.
2. **Same EVE account, many characters** — after token exchange, decode the SSO JWT and read the **`owner`** claim (CCP’s *owner hash*). Every character on the same paying account shares the same `owner` value. On callback, look up **`eve_linked_characters`** by `owner_hash`; if any row exists, attach the new `character_id` to that **`core_users`** row; otherwise create a **`core_users`** row and link the character.
3. **Display names vs keys** — persist **`character_id`** (integer from ESI / SSO) as the primary key for a linked character; keep **`character_name`** for UI and refresh it whenever you refresh the access token or call **`GET /characters/{character_id}/`** so renames do not break identity (“x y z is still x”).
4. **Main character** — **`core_users.main_character_id`** points at one row in **`eve_linked_characters`**. The first successful login for a new **`core_users`** row sets `main_character_id` to that character. A signed-in user can call an API (e.g. `PATCH /v1/me/main`) to set `main_character_id` to another linked character on the same user (validate ownership before updating).
5. **Tokens** — **`eve_oauth_tokens`** stays one row per character that has granted refresh access; **`owner_user_id`** ties that row to **`core_users.id`** for server-side ESI on behalf of the account owner.

Tables: `core_users`, `eve_linked_characters`, `eve_oauth_tokens` (see `app/db/models.py`).

### Discord bot integration (link + False Gods rank)

- **`core_users.discord_user_id`** stores the Discord snowflake once SSO completes.
- **`discord_pending_sso_links`** holds short-lived rows created by **`POST /v1/integrations/discord/prepare-link`** (Bearer **`CORE_DISCORD_BOT_SECRET`**). The returned URL points at **`GET /v1/auth/eve/start?link_id=…`**, which sends that UUID as CCP **`state`**; **`GET /v1/auth/eve/callback`** exchanges the code and links EVE + Discord.
- **False Gods rank**: set **`CORE_FALSE_GODS_CORPORATION_ID`** and **`CORE_FG_RANK_ROLES_JSON`** (corporation role id → slug + weight). CEO is detected via public ESI **`/corporations/{id}/`**. **`POST /v1/integrations/discord/sync-roles`** returns **`rank_key`** for the bot to map to guild roles.
- **Moon mining taxes**: set **`CORE_MOON_TAX_ASSIGNEE_ID`** (character or corporation id contracts must use as **assignee**), optional **`CORE_MOON_TAX_PERCENT_OF_OWED_VALUE`** and **`CORE_MOON_TAX_PAYMENT_INSTRUCTIONS`**. **`POST /v1/plugins/moon-taxes/summary`** compares the character **mining ledger** to **item_exchange** contracts you issued to that assignee (optional **assets** snapshot for mined types). Linked SSO tokens need **mining**, **contracts**, and (if using assets) **assets** scopes.

## Databases

- **Postgres** (primary): users, SSO tokens, SDE tables, CMS content, audit logs.
- Set **`CORE_DATABASE_URL`** (async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@db:5432/eve_emu_core`).

## Token persistence (container restarts)

- **EVE refresh tokens** (and optional access tokens) are stored in Postgres table **`eve_oauth_tokens`**, encrypted with **Fernet** using **`CORE_TOKEN_ENCRYPTION_KEY`** (see `app/services/token_cipher.py`, `app/db/token_store.py`).
- **Docker**: the bundled **`docker-compose.yml`** mounts a **named volume** (`eve_emu_core_pg`) for Postgres data. Restarting or recreating the **`core`** container does **not** clear tokens as long as the **db** volume is kept.
- **Do not** run `docker compose down -v` in production unless you intend to wipe the database (that removes named volumes and all tokens).
- **Kubernetes / Swarm**: bind the same persistent volume claim to Postgres, or use a managed database outside the cluster.
- **Key rotation**: changing `CORE_TOKEN_ENCRYPTION_KEY` invalidates existing ciphertext; plan a migration or re-login flow.

## Running locally

```bash
cd core
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set CORE_DATABASE_URL=postgresql+asyncpg://eve:eve@localhost:5432/eve_emu_core
uvicorn app.main:app --reload --port 8000
```

Docker: see **`docker-compose.yml`** in this directory.

## Environment

See **`.env.example`**.
