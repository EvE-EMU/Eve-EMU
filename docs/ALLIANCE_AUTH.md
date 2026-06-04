# Alliance Auth (v5) in EVE-EMU

This repository vendors **[Alliance Auth](https://allianceauth.readthedocs.io/en/latest/)** as a **[Git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules)** at **`allianceauth/`**, pinned to upstream tag **`v5.1.2`** ([release notes](https://gitlab.com/allianceauth/allianceauth/-/releases/v5.1.2): translation updates, corporation populate fix, corp shares integer fix, django-esi minimum tag).

Canonical upstream source: **https://gitlab.com/allianceauth/allianceauth** (the GitHub mirror is stale).

## Running full Alliance Auth in this repo (Docker)

The **`aa-web`**, **`aa-worker`**, and **`aa-beat`** images are built from **`docker/django-aa/Dockerfile`**, which:

1. **`pip install -e /opt/allianceauth`** (Git submodule at **`allianceauth/`**, pinned in **`.gitmodules`**).
2. Runs **`allianceauth start eve_auth .`** to materialize the upstream project template under **`/app/site/`** in the image.
3. Overwrites **`eve_auth/settings/local.py`** with **`deploy/aa_docker/local.py`** (PostgreSQL, Redis cache + Celery broker, **`industry_suite`** in **`INSTALLED_APPS`**, WhiteNoise, env-driven ESI).

Root Compose runs **`caddy`**: **`https://auth.<DOMAIN_NAME>`** → **`aa-web:8080`**, **`https://<DOMAIN_NAME>`** → **core-web** (public site). Set **`AA_SITE_URL`** to the auth URL (e.g. **`https://auth.eve-emu.com`**).

Before **`docker compose build aa-web`** (or any **`aa-*`** service), run:

```bash
git submodule update --init --recursive allianceauth
cd allianceauth && git checkout v5.1.2
```

Configure root **`.env`** (see **`.env.example`**):

- **`AA_SITE_URL`** — public base URL of the auth site (no trailing slash), e.g. **`https://auth.eve-emu.com`**. For local-only HTTP without Caddy, set an explicit **`http://…`** URL that matches how you reach the app.
- **`ESI_CLIENT_ID`** / **`ESI_CLIENT_SECRET`** — same EVE developer app as **`core-api`** (or a dedicated app). **`ESI_CALLBACK_URL`** must match CCP **character-for-character** (default **`https://auth.<domain>/sso/callback`** — **no trailing slash**). Add **both** `…/sso/callback` and `…/sso/callback/` on the CCP app only if you intentionally use two URLs; this stack normalizes to **no** trailing slash (see [Alliance Auth installation](https://allianceauth.readthedocs.io/en/v5.0.1/installation/index.html)).
- **`AA_DJANGO_SECRET_KEY`**, **`POSTGRES_*`**, **`REDIS_URL`** — same Postgres role/database as **`POSTGRES_DB_AA`** (`eve_emu_aa` by default).

On first start, **`docker/django-aa/entrypoint.py`** runs **`repair_indy_hub_migrations.py`** (records Indy Hub `0023` when columns already exist), then **`manage.py migrate`** and **`collectstatic`** before Gunicorn (Alliance Auth touches Redis during `django.setup()`, so static collection is not done at image build time).

**Indy Hub** is pinned at **`indy-hub==1.17.2`** ([PyPI](https://pypi.org/project/indy-hub/1.17.2/)). **Indy Hub on PostgreSQL:** upstream migrations `0023`, `0026`, `0049`, and `0050` assume MySQL/SQLite for some schema steps; patched copies live under **`deploy/aa_docker/patches/indy_hub/`** and are copied into the **`aa-*`** image at build time. **`repair_indy_hub_migrations.py`** (runs before migrate on web boot) fixes partial states. If migrate still fails, rebuild **`aa-web`** and run:

```bash
docker compose exec aa-web python /app/deploy/aa_docker/repair_indy_hub_migrations.py
docker compose exec aa-web python manage.py migrate
```

The legacy minimal Django package under **`deploy/django_eve_emu/`** is kept for reference and local experiments; the Compose **`aa-*`** stack uses the generated **`eve_auth`** project described above.

## Bundled AA extensions (Docker image)

Community apps are installed from **`deploy/aa_docker/requirements-aa-extension-deps.txt`** (shared libraries) and **`deploy/aa_docker/requirements-aa-extension-apps.txt`** (plugin wheels, `--no-deps` for AA 5.x), and wired by **`deploy/aa_docker/extensions/`** (called from **`deploy/aa_docker/local.py`**).

| Env | Default | Meaning |
|-----|---------|---------|
| **`AA_EXTENSIONS_ENABLED`** | `1` | Install all bundled community packages and enable every app label listed below (except GraphQL). |
| **`AA_EXTENSIONS_GRAPHQL`** | `0` | Also enable GraphQL (`/graphql/` needs extra URL wiring — set `1` only if you add routes). |
| **`AA_USE_MODELTRANSLATION`** | `1` | Prepend `modeltranslation` (required by fittings, sov-timer, etc.). |
| **`AA_ESI_COMPATIBILITY_DATE`** | `2025-12-16` | Passed to legacy ESI shims for django-eveuniverse apps. |

**Slim bundle** (default when **`AA_EXTENSIONS_ENABLED=1`**): core ops apps only. **Removed** from install (see `deploy/aa_docker/extensions/apps.py` → `SLIM_REMOVED_APP_LABELS`): Killstats, Metenox, AA-SRP (ship replacement), AFAT (fleet activity tracking), Skillfarm, Moon Tsar, Mining Taxes moon-ore report extension (`miningtaxes_ext`), Moon pop schedule (`moon_rentals`, was `/miningtaxes/schedule/`).

**Retained** (eve-emu customizations depend on them): [Moon Mining](https://apps.allianceauth.org/apps/detail/aa-moonmining) + **moon rentals** patch, [Mining Taxes](https://gitlab.com/arctiru/aa-miningtaxes) (`aa-miningtaxes`), [Buyback Program](https://apps.allianceauth.org/apps/detail/aa-buybackprogram) + **`buyback_v2`** (tiered public pricing), [Standings Sync](https://apps.allianceauth.org/apps/detail/aa-standingssync), [Structures](https://apps.allianceauth.org/apps/detail/aa-structures), [Structure Timers II](https://apps.allianceauth.org/apps/detail/aa-structuretimers), [Indy Hub](https://apps.allianceauth.org/apps/detail/indy-hub), [Market Manager](https://apps.allianceauth.org/apps/detail/aa-market-manager), [Kill Tracker](https://apps.allianceauth.org/apps/detail/aa-killtracker), [Intel Tool](https://apps.allianceauth.org/apps/detail/aa-intel-tool), [Sov Timer](https://apps.allianceauth.org/apps/detail/aa-sov-timer), [CorpTools](https://apps.allianceauth.org/apps/detail/allianceauth-corptools), [Member Audit](https://gitlab.com/ErikKalkoken/aa-memberaudit), [Ledger](https://apps.allianceauth.org/apps/detail/aa-ledger) **3.0.1**, [Fleet Pings](https://apps.allianceauth.org/apps/detail/aa-fleetpings), and the rest of the non-removed list in `requirements-aa-extension-apps.txt`.

**Dependency bumps** (slim image): `allianceauth-app-utils>=1.32.1`, `django-oauth-toolkit>=3.3`, `aa-ledger==3.0.1`.

Also enabled in the image: [Discord bot](https://apps.allianceauth.org/apps/detail/allianceauth-discordbot) (`aa-discordbot` Compose service), [Discord Notify](https://apps.allianceauth.org/apps/detail/aa-discordnotify) (needs [Discord Proxy](https://gitlab.com/ErikKalkoken/discordproxy)), [Wiki.js](https://apps.allianceauth.org/apps/detail/allianceauth-wiki-js) (`wikijs` Compose service + [WIKIJS.md](./WIKIJS.md)), [Slate theme](https://apps.allianceauth.org/apps/detail/aa-theme-slate), [Skip Email](https://apps.allianceauth.org/apps/detail/aa-skip-email). **YouTrack** at `pm.<DOMAIN_NAME>` uses [allianceauth-oidc-provider](https://github.com/Solar-Helix-Independent-Transport/allianceauth-oidc-provider) for SSO — see [YOUTRACK.md](./YOUTRACK.md). Optional: [GraphQL](https://apps.allianceauth.org/apps/detail/allianceauth-graphql) via **`AA_EXTENSIONS_GRAPHQL=1`**.

### Upgrade to Alliance Auth v5.1.2 (slim bundle)

```bash
git submodule update --init allianceauth
cd allianceauth && git checkout v5.1.2 && cd ..
docker compose build aa-web aa-worker aa-beat
docker compose up -d aa-web aa-worker aa-beat
docker compose exec aa-web python manage.py migrate
```

Follow upstream [updating guidance](https://allianceauth.readthedocs.io/en/latest/installation/allianceauth.html#updating) if you maintain a forked `local.py` beyond `deploy/aa_docker/local.py`.

### Permissions matrix (states, groups, apps)

Live export: **[PERMISSIONS_MATRIX.md](./PERMISSIONS_MATRIX.md)** (markdown) and **[PERMISSIONS_MATRIX.csv](./PERMISSIONS_MATRIX.csv)** (Excel). Regenerate with `deploy/aa_docker/scripts/permissions_matrix.py` (see header in the markdown file).

**States** (Member / Blue / Guest) auto-assign from main character. **Groups** (Members, Director, D1, …) are joined manually or via Secure Groups. **Discord roles** mirror Django **group names** on the False Gods server—they are not separate AA permissions.

### Alliance Auth Discord service (`/services/` → Discord)

This is **not** `aa-discordbot` or webhooks — it is Alliance Auth’s built-in **Services → Discord** (member OAuth link, role sync, admin “link server”). **`deploy/aa_docker/extensions`** adds `allianceauth.services.modules.discord` to `INSTALLED_APPS` when **`DISCORD_BOT_TOKEN`** and **`DISCORD_GUILD_ID`** are set (disable with **`AA_DISCORD_SERVICE_ENABLED=0`**). On boot, **`AA_DISCORD_GRANT_STATE_ACCESS=1`** (default) grants **`discord.access_discord`** to the **Member** and **Blue** states so the tile appears on `/services/`.

1. In the [Discord Developer Portal](https://discord.com/developers/applications): OAuth2 redirect **`https://auth.<domain>/discord/callback/`**, copy **Client ID** → `DISCORD_APP_ID` and **Client Secret** → `DISCORD_APP_SECRET` (not the bot token).
2. Rebuild and recreate **`aa-web`** / **`aa-worker`**, then run **`migrate`** so the `discord` app tables exist.
3. **Admin → Authentication and Authorization → States** (or Groups): grant permission **`Can access the Discord service`** under app **discord** (`discord.access_discord`).
4. Superuser: open **`https://auth.<domain>/discord/add_bot/`** to invite the bot and link the guild (or use **Services** when Discord appears for members).

After **`docker compose build aa-web aa-worker aa-beat`** and **`docker compose up -d`**, migrations run on **`aa-web`** boot. One-time data loads (run as needed):

```bash
docker compose exec aa-web python manage.py esde_load_sde
docker compose exec aa-web python manage.py sync_sde_compat   # required once for Indy Hub UI
docker compose exec aa-web python manage.py packagemonitorcli refresh
docker compose exec aa-web python manage.py setup_securegroup_task
docker compose exec aa-web python manage.py memberaudit_load_eve
docker compose exec aa-web python manage.py timezones_load_tz_data
docker compose exec aa-web python manage.py moonmining_load_eve
docker compose exec aa-web python manage.py structuretimers_load_eve
docker compose exec aa-web python manage.py buybackprogram_load_data
docker compose exec aa-web python manage.py buybackprogram_load_prices
docker compose exec aa-web python manage.py buyback_v2_enable_programs
docker compose exec aa-web python manage.py sovtimer_load_initial_data
docker compose exec aa-web python manage.py corptools ct_setup
docker compose exec aa-web python manage.py miningtaxes_preload_prices
```

Optional: **`AA_PACKAGE_MONITOR_REFRESH_ON_BOOT=1`** (slow; disable after first boot). **`AA_TASKMONITOR_ENABLED=0`** disables Task Monitor UI logging.

**Package Monitor “Update Available”** compares installed wheels to PyPI (and git tags for VCS deps). Shared pins live in **`deploy/aa_docker/requirements-aa-extension-deps.txt`** (`click`, `django-eveuniverse`, etc.). After changing that file, rebuild and refresh:

```bash
docker compose build aa-web aa-worker aa-beat
docker compose up -d aa-web aa-worker aa-beat
docker compose exec aa-web python manage.py packagemonitorcli refresh
```

Equivalent to the UI “install all outdated” command for the two common deps:

```bash
docker compose exec aa-web pip install "click>=8.4.1,<9" \
  "django-eveuniverse==2.0.0"
docker compose exec aa-web python manage.py packagemonitorcli refresh
```

Prefer the **rebuild** path so **`aa-worker`** / **`aa-beat`** stay in sync with **`aa-web`**.

### Corp project Discord routing

When a corporation **project** is opened or completed, EVE sends character notifications that **CorpTools** stores. This stack can post those events to **different Discord channels** based on the **project name** (case-insensitive substring match).

Configure in root **`.env`** (requires **CorpTools** and **`aa-beat`**):

| Variable | Meaning |
|----------|---------|
| **`AA_CORP_PROJECT_DISCORD_ROUTES`** | Comma-separated `pattern:destination`. **Pattern** must appear inside the EVE **goal_name** (case-insensitive). Example goal names: `D0 Manufacturing \| Maulus` → use patterns `d0 manufacturing`, `d1 manufacturing`, and `d2 manufacturing`. **Use [webhook URLs](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) for D1/D2** so alerts include a **Claim** button; channel IDs only post a sheet link in the embed (needs **`aa-discordbot`**). First match wins. |
| **`AA_CORP_PROJECT_CLAIM_SHEET_URL`** | Google Sheet for **D1/D2** **Confirm availability** button (open projects only). **D0** has no button. |
| **`AA_CORP_PROJECT_DISCORD_DEDUPE_BY_GOAL`** | Default `1` — one Discord message per `goal_id` + event (opened/completed/…) even when CorpTools stores duplicate notification rows. |
| **`AA_CORP_PROJECT_DISCORD_DEFAULT_WEBHOOK_URL`** | Optional fallback webhook for unmatched project names. |
| **`AA_CORP_PROJECT_DISCORD_DEFAULT_CHANNEL_ID`** | Optional fallback channel ID (requires bot in channel). |
| **`AA_CORP_PROJECT_DISCORD_POLL_SECONDS`** | How often Celery checks **new** and **completed** projects (default **`1800`** = 30 min). |
| **`AA_CORP_PROJECT_DISCORD_EVENT_LOOKBACK_MINUTES`** | Notification lookback per 30‑min run (default **`45`**). |
| **`AA_CORP_PROJECT_DISCORD_DAILY_HOUR`** / **`DAILY_MINUTE`** / **`DAILY_TZ`** | Daily **open project** digest (default **`14:30`** **`America/New_York`**). Progress + **Confirm availability** on D1/D2. |
| **`AA_CORP_PROJECT_DISCORD_ENABLED`** | Set `0` to disable without removing routes. |
| **`AA_CORP_PROJECT_DISCORD_ESI_TOKEN_ID`** | Optional django-esi token pk with `read_projects` (e.g. sevey). |
| **`AA_ESI_COMPATIBILITY_DATE`** | ESI header for corp projects (default **`2026-05-19`** in `corp_project_discord`). |

Implementation: **`deploy/aa_docker/corp_project_discord.py`**.

Celery beat (requires **`aa-beat`**):

| Task | Schedule | What it posts |
|------|----------|----------------|
| `dispatch_corp_project_created_discord_alerts` | Every 30 min | **Project created** (D1/D2: **Confirm availability** button) |
| `dispatch_corp_project_completed_discord_alerts` | Every 30 min | **Completed / closed / expired** (no button) |
| `dispatch_corp_project_daily_digest` | Daily 2:30 PM Eastern | **Still-open** projects + progress + **Confirm availability** (D1/D2) |

Manual test:

```bash
docker compose exec aa-worker python manage.py shell -c "from corp_project_discord import process_corp_project_created_alerts; print(process_corp_project_created_alerts())"
docker compose exec aa-worker python manage.py shell -c "from corp_project_discord import process_corp_project_completed_alerts; print(process_corp_project_completed_alerts())"
docker compose exec aa-worker python manage.py corp_project_discord_daily --force
```

**Webhooks (recommended for D1/D2 button):** channel → Integrations → Webhooks. Embeds include ESI **Progress**, qty, and ISK when `esi-corporations.read_projects.v1` is on a corp token (Charlink).

**First-time backfill** (post every **still-open** D0/D1 project once — created in CorpTools, not completed/closed):

```bash
# Preview
docker compose exec aa-worker python manage.py corp_project_discord_backfill --dry-run

# Post (after AA_CORP_PROJECT_DISCORD_ROUTES uses patterns like d0 manufacturing / d1 manufacturing)
docker compose exec aa-worker python manage.py corp_project_discord_backfill
```

Optional: `--days 90` (limit history), `--force` (ignore dedupe cache). Default lookback: **`AA_CORP_PROJECT_DISCORD_BACKFILL_DAYS`** (365) in `.env`.

(`manage.py` lives in `/app/site` in the image; the worker container’s working directory is already set there.)

### Corp stock orders (`corp_orders`)

Officer/director **item exchange** quotes for corp stock buys (Janice + PushX Jita → Badivefi). See **[CORP_ORDERS.md](./CORP_ORDERS.md)**. Menu: **Corp stock orders** at `/corp-orders/`.

### Mining Taxes (`miningtaxes`)

[aa-miningtaxes](https://gitlab.com/arctiru/aa-miningtaxes) — stock Alliance Auth app: corp moon observer logs, character ledgers, **ISK tax balances**, ore prices, and monthly notifications.

| Setting | Eve-EMU default | Purpose |
|--------|-----------------|---------|
| `AA_MININGTAXES_CELERY` | `1` | Daily ESI sync (`update_daily`) |
| `AA_MININGTAXES_NOTIFY_ENABLED` | `1` | Tax-due ping (2nd of month) + interest (15th) via Celery beat |
| `MININGTAXES_*` | *(package defaults)* | Only set in `.env` when you need overrides (Fuzzwork pricing, wallet division, etc.) |

The custom **`miningtaxes_ext`** moon-ore report app is **not** in the slim bundle. UI uses upstream templates (**Mining Taxes** nav, tax summary, full ledger).

```bash
docker compose exec aa-web python manage.py miningtaxes_preload_prices
```

### Moon pop schedule (`moon_rentals`) — removed

The legacy **`/miningtaxes/schedule/`** and **`/miningtaxes/import/`** pages (app `moon_rentals`) are **disabled** in the slim bundle. Use **aa-moonmining** extractions/calendar and **EMU Moons** for owned-structure pops and tax invoicing instead (see [EMU_MOONS.md](./EMU_MOONS.md)).

### Moon renter management (`moonrentals`) — not deployed

The **lease / renter** submodule (`moonmining.rentals`, app label `moonrentals`) is **not** installed in this stack. Source remains under `deploy/aa_docker/patches/moonmining/rentals/` for reference only.

Use **aa-moonmining** for surveys/extractions and **EMU Moons** for tax invoicing on corp-owned moons.

### EMU Moons + Member Mining reports

See **[EMU_MOONS.md](./EMU_MOONS.md)**. After deploy, migrate and seed structure classes (public by default; private only when the structure name contains `PRIVATE` or you assign an owner in `/emu-moons/admin/settings/`):

```bash
docker compose exec aa-web python manage.py migrate emu_moons
docker compose exec aa-web python manage.py emu_moons_seed
docker compose exec aa-web python manage.py moonmining_sync_reports
```

`/moonmining/reports` → **Member Mining** needs corp mining observer data. The sync command requires **director** characters on moonmining **Owners** and **miningtaxes** admin characters with `esi-industry.read_corporation_mining.v1`. If corp ESI returns 403, fix roles/tokens; the report API also falls back to existing `AdminMiningObsLog` rows for miners on Alliance Auth.

### Moon Tsar (`moon_tsar`)

Unified **post-pop tax billing**, **Discord reminders**, **Tsar dashboard**, **heatmap**, and **renter portal**. Uses Alliance Auth login (SSO) — not a separate app server. See **[MOON_TSAR.md](./MOON_TSAR.md)** for full design.

| URL | Role |
|-----|------|
| `/moon-tsar/` | Moon Tsar dashboard (schedule, m³, ISK) |
| `/moon-tsar/settings/` | Per-ore tax rates + module settings |
| `/moon-tsar/bill/<uuid>/` | Member invoice + payment reference |
| `/moon-tsar/renter/` | Private renter / POC portal |

```bash
docker compose up -d --build aa-web aa-worker aa-beat
docker compose exec aa-web python manage.py migrate moon_tsar
```

Grant group permissions: `moon_tsar.view_dashboard`, `moon_tsar.manage_settings`, `moon_tsar.view_own_bills`, `moon_tsar.view_renter_portal`.

| Env | Default |
|-----|---------|
| `AA_MOON_TSAR_CELERY` | `1` |
| `AA_MOON_TSAR_TRACKING_HOURS` | `20` (post-pop ledger window) |

Integrates **miningtaxes** observer ledger, **moonmining** extractions, and corp wallet phrase matching (same pattern as buyback).

### Buyback v2 (Janice line pricing)

The stock [Buyback Program](https://apps.allianceauth.org/apps/detail/aa-buybackprogram) UI and contracts are unchanged. **`buyback_v2`** adds per-program rules in Django admin (**Buyback v2 pricing profiles**):

- **Janice** as the price source when **`BUYBACKPROGRAM_PRICE_JANICE_API_KEY`** is set (see [Janice API](https://janice.e-351.com/api/rest/docs/index.html)).
- **Line-by-line** choice between reprocess (refined minerals from SDE + Janice material prices) and normal market price.
- **Variant selection**: prefer reprocess unless market is cheaper (default), legacy max-of-all, corp minimum, reprocess-only, or market-only.
- **Price basis**: program Buy/Sell/Split, or force buy / sell / split; **Jita buy %** scales the final line price.

Set `BUYBACKPROGRAM_PRICE_METHOD=Janice` and `BUYBACKPROGRAM_PRICE_JANICE_API_KEY` in the environment. After deploy, run **`buyback_v2_enable_programs`** once so existing programs get a profile.

**Guns-R-Us buyback locations:** Import all corp structures from ESI (`GET /corporations/98633922/structures/`) using the Rexan / `AA_GUNS_R_US_CORP_TOKEN_ID` token (same as aa-structures):

```bash
docker compose exec aa-web python manage.py buyback_sync_guns_structures --ensure-v2-profiles
```

This creates **`buybackprogram.Location`** rows (name, `structure_id`, solar system) and attaches them to every buyback program. Use `--no-attach` to only refresh locations, or `--program-id 2` to limit which programs get the new sites. Rebuild **`aa-web`** after changing `buyback_v2/`.

**Character dockable structures (e.g. sevey):** ESI has no official “all dockable structures” list; the sync probes public structures with the character token and searches each buyback system name:

```bash
docker compose exec aa-web python manage.py buyback_sync_character_structures --character sevey
```

Uses **sevey**’s token (`esi-universe.read_structures.v1`). First run may take several minutes while public structure IDs are checked.

**Standing Fleet Tracker** (`/standing-fleet/`): polls linked characters’ fleets via ESI, scores standing-fleet hours, home-defence kill bonuses, and sov-roam penalties. See `standing_fleet_tracker/README.md` and env vars `SFT_*` in `.env.example`.

**Tiered pricing:** In admin, open a program’s **Buyback v2 pricing profile** → add **Pricing tiers** (e.g. `0.9000` = 90%) and **rules** (corporation ID, alliance ID, or character ID). Higher **priority** wins. Mark one tier **default** for logged-in users with no rule match. Enable **public calculator** and set **public multiplier** (or add a tier with **Is public**) for no-login quotes at **`/buyback-public/`** (sidebar: *Public buyback prices*).

Each app needs **permissions**, **ESI scopes** on your CCP application, and sometimes **director tokens**—see the linked app pages on [apps.allianceauth.org](https://apps.allianceauth.org).

**Auto groups by corp + Director title/role:** use **Secure Groups** + **CorpTools** filters (already in the Docker image). Step-by-step: [SECURE_GROUPS_BY_TITLE.md](./SECURE_GROUPS_BY_TITLE.md). Run `setup_securegroup_task` and `corptools ct_setup` once; add `esi-characters.read_corporation_roles.v1` and `esi-characters.read_titles.v1` on your CCP app and Charlink.

**Market Manager:** After deploy, configure **Admin → Marketmanager → Public configs** (select regions, e.g. The Forge), then run `docker compose exec aa-web python manage.py shell -c "from marketmanager.tasks import fetch_public_market_orders; fetch_public_market_orders.delay()"`. The browser shows orders only after you **search an item** (3+ characters) and pick a region. Structure admin add was broken on `eve_sde` field names (`group` vs `item_group`) — fixed via `deploy/aa_docker/patches/marketmanager/` (rebuild `aa-web`).

### False Gods corp ESI token (Lamaashtu #58)

CorpTools and Market Manager normally pick the first corp character token whose ESI roles include **`Director`**. On the private EVE server, role names often differ (e.g. **`Config_Starbase_Equipment`** instead of **`Director`**), so corp structure/starbase sync never runs.

Set **`AA_FALSE_GODS_CORP_TOKEN_ID=58`** (django-esi token for **Lamaashtu**, corp **98799892**) in **`.env`** or Compose defaults. At boot, **`deploy/aa_docker/corptools_corp_token.py`** pins that token for CorpTools and Market Manager corp tasks when scopes match, skipping the Alliance Auth role check.

**ESI still enforces roles server-side.** Lamaashtu must hold **Director** (structures/starbases) or **Station_Manager** (structures only) in False Gods in-game; otherwise ESI returns `403 Character does not have required role(s)` even with the token override.

After rebuild **`aa-web`** + **`aa-worker`**, kick an initial CorpTools pull:

```powershell
docker compose exec aa-web python manage.py shell -c "from corptools.tasks.corporation.structures import corp_structure_update, corp_starbase_update; corp_structure_update.delay(98799892, force_refresh=True); corp_starbase_update.delay(98799892, force_refresh=True)"
```

Token admin: `https://auth.eve-emu.com/admin/esi/token/58/change/`. For other corps, use **`AA_CORP_TOKEN_OVERRIDES=corp_id:token_pk`** (comma-separated).

### aa-structures (`/structures/list`)

The **Structures** app ([aa-structures](https://aa-structures.readthedocs.io/en/latest/operations.html)) is separate from CorpTools. It needs:

1. **Celery Beat** entries for `structures.tasks.update_all_structures` and `structures.tasks.fetch_all_notifications` (added in `deploy/aa_docker/extensions/celerybeat.py`).
2. **Structure owners** on `aa-web` boot when `AA_ENSURE_STRUCTURE_OWNER=1` (`deploy/aa_docker/structures_corp_token.py`):
   - **False Gods** (`98799892`): `AA_FALSE_GODS_CORP_TOKEN_ID` (default token 58).
   - **Guns-R-Us** (`98633922`, moon athanors): `AA_STRUCTURES_AUTH_CHARACTER=Rexan Darkstar` (resolves latest django-esi token for that character), or set `AA_GUNS_R_US_CORP_TOKEN_ID` explicitly.
3. **ESI scopes** on your CCP app (see aa-structures install docs): `esi-corporations.read_structures.v1`, `esi-universe.read_structures.v1`, `esi-characters.read_notifications.v1`, `esi-assets.read_corporation_assets.v1`, plus starbase/customs scopes if enabled.
4. **Director** (or token override) for structure corp API calls — Rexan must log in on auth with aa-structures scopes if sync returns 403.

One-time (or set `AA_STRUCTURES_LOAD_EVE=1` on next `aa-web` boot):

```powershell
docker compose exec aa-web python manage.py structures_load_eve
```

Force a sync after deploy:

Force a sync after deploy (Guns-R-Us / Rexan Darkstar):

```powershell
docker compose exec aa-web python manage.py shell -c "from structures.tasks import update_all_for_owner; from structures.models import Owner; o=Owner.objects.filter(corporation__corporation_id=98633922).first(); update_all_for_owner.delay(o.pk) if o else print('no owner')"
```

False Gods:

```powershell
docker compose exec aa-web python manage.py shell -c "from structures.tasks import update_all_for_owner; from structures.models import Owner; o=Owner.objects.filter(corporation__corporation_id=98799892).first(); update_all_for_owner.delay(o.pk) if o else print('no owner')"
```

Rebuild **`aa-web`**, **`aa-worker`**, and **`aa-beat`** so beat schedule and token patches load.

#### HR / membership Discord channel (joins, applications)

Messages like **“Eveeno joins False Gods”** / **“is now a member of False Gods”** are **`CharAppAcceptMsg`** alerts from **[aa-structures](https://aa-structures.readthedocs.io/)**, not corp project routing. They are sent to every Owner webhook whose **notification types** include that event — often a catch-all webhook (e.g. **ALL WEBHOOKS TESTING**).

To forward HR events to a **dedicated channel**:

1. In Discord: HR channel → **Integrations** → **Webhooks** → copy URL.
2. In `.env`:

   ```env
   AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/…
   # Optional: remove HR types from this catch-all (default name matches your setup)
   AA_STRUCTURES_STRIP_HR_FROM_WEBHOOK_NAMES=ALL WEBHOOKS TESTING
   ```

3. Rebuild and restart **`aa-web`** (sync on boot) or run once:

   ```powershell
   docker compose exec aa-worker python manage.py structures_hr_webhook_sync
   docker compose exec aa-worker python manage.py structures_hr_webhook_sync --dry-run
   ```

Implementation: **`deploy/aa_docker/structures_hr_webhook.py`**. Default HR types: `CharAppAcceptMsg`, `CharLeftCorpMsg`, `CorpAppNewMsg`, `CorpAppInvitedMsg`, `CharAppRejectMsg`, `CorpAppRejectCustomMsg`, `CharAppWithdrawMsg`. Override with **`AA_STRUCTURES_HR_NOTIFICATION_TYPES`** (comma-separated).

You can also edit webhooks under **Structures → Webhooks** in Alliance Auth admin; env sync is idempotent and safe to re-run after deploy.

### Indy Hub (`/indy_hub/esi/`, `/indy_hub/corporation-bp/`)

Corp blueprint/job sync normally uses the logged-in user's characters and ESI role names **`DIRECTOR`** / **`FACTORY_MANAGER`**. With **`AA_FALSE_GODS_CORP_TOKEN_ID=58`**, **`deploy/aa_docker/indy_hub_corp_token.py`** forces **False Gods** (98799892) to use **Lamaashtu's** django-esi token (#58) for:

- the corp row on **`/indy_hub/esi/`**
- Celery corp blueprint/job sync (including manual refresh on **`/indy_hub/corporation-bp/`**)
- corp manager visibility on the corporation blueprint list (same token as CorpTools below)

This is the **same** env override as CorpTools structures (**`corptools_corp_token.py`**).

### CorpTools audit structures (`/audit/r/corp/structures`)

The audit UI reads synced **`Structure`** rows from the database. Population uses **`get_corp_token`** in CorpTools Celery tasks (`corp_structure_update`, etc.), which **`corptools_corp_token.py`** pins to token **#58** when **`AA_FALSE_GODS_CORP_TOKEN_ID=58`** is set. Rebuild **`aa-web`** and **`aa-worker`**, then kick a pull (see False Gods corp ESI token section above).

Rebuild **`aa-web`** and **`aa-worker`** after changing the override. Confirm token **#58** includes Indy Hub corp scopes such as `esi-corporations.read_blueprints.v1`, `esi-industry.read_corporation_jobs.v1`, `esi-characters.read_corporation_roles.v1`, and CorpTools structure scopes such as `esi-corporations.read_structures.v1` (plus material-exchange corp scopes if you use that module).

**Django 5:** Indy Hub still uses ``django.utils.timezone.utc`` (removed in Django 5). ``deploy/aa_docker/indy_hub_django_compat.py`` restores it at boot. If [`/indy_hub/corporation-bp/?refresh=1`](https://auth.eve-emu.com/indy_hub/corporation-bp/?refresh=1) shows ``timezone`` has no attribute ``utc``, rebuild **`aa-web`** and **`aa-worker`**.

Manual corp blueprint refresh (users with **`can_manage_corp_bp_requests`**):

```powershell
docker compose exec aa-web python manage.py shell -c "from indy_hub.tasks.industry import request_manual_refresh, MANUAL_REFRESH_KIND_BLUEPRINTS; from django.contrib.auth import get_user_model; u=get_user_model().objects.filter(is_superuser=True).first(); print(request_manual_refresh(MANUAL_REFRESH_KIND_BLUEPRINTS, u.pk, scope='corporation', priority=5) if u else 'no user')"
```

The account must have **`indy_hub.can_manage_corp_bp_requests`**. `(True, None, None)` means the Celery task was queued. `(False, None, 'inactive_or_missing_scope')` before rebuild means the user failed Indy Hub’s “active” check (personal `esi-location.read_online.v1`); after rebuild, corp managers with token **#58** skip that check for `scope='corporation'`.

## Django project naming (`eve_emu` vs `allianceauth`)

The **Git submodule directory** is intentionally named **`allianceauth/`** so `git submodule` URLs and upstream docs stay recognizable.

For **your fork** and Django **settings module**, EvE-EMU recommends a **separate Python project package** name that is not the upstream **`allianceauth`** Django app tree. The Docker **`aa-*`** images use the Alliance Auth CLI default project name **`eve_auth`** (see **`eve_auth.settings.local`**). Do **not** blindly rename upstream’s internal `allianceauth` **PyPI / Django app package** strings inside the submodule unless you are maintaining a deliberate fork of that codebase; instead, add EvE-EMU–specific Django apps (for example the **`industry_suite`** app at the repository root) to `INSTALLED_APPS` in **your** project settings (see **`deploy/aa_docker/local.py`**).

```python
# Example only — your AA project’s settings.py
INSTALLED_APPS = [
    # … Alliance Auth and dependencies …
    "industry_suite",
]
```

Point `PYTHONPATH` (or your packaging layout) at the repository root so `import industry_suite` resolves.

## License

Alliance Auth is **GPLv2**. If you ship a combined product that includes AA, comply with the GPL (this submodule preserves upstream history and the `LICENSE` file under `allianceauth/`).

## Fork for your org

1. On GitLab (or GitHub if you mirror), **fork** `allianceauth/allianceauth` to your namespace.
2. In this repo, point the submodule at your fork:

   ```bash
   git config submodule.allianceauth.url https://gitlab.com/<you>/allianceauth.git
   # or edit .gitmodules then:
   git submodule sync
   ```

3. Optionally create a branch on your fork (e.g. `eve-emu-patches`) and set the submodule to track that branch instead of detached tags—then merge upstream `v5.x` releases as needed.

## Running AA locally (recommended: Linux or Docker)

Upstream targets **Linux** (see PyPI classifiers). On Windows, use **WSL2** or **Docker** rather than native installs.

High-level steps (details in [Alliance Auth installation docs](https://allianceauth.readthedocs.io/en/v5.0.1/installation/index.html)):

1. **Python 3.10–3.13**, **PostgreSQL**, **Redis**, **Celery** worker + beat (AA expects them).
2. Create a **Django project** that installs `allianceauth` from the submodule path or from PyPI at the same version as the tag you use.
3. Configure **EVE developer application** (SSO client id/secret) and callback URLs per AA settings.
4. Run migrations, collectstatic, and serve with **gunicorn** + reverse proxy (see [Gunicorn](https://allianceauth.readthedocs.io/en/v5.0.1/installation/gunicorn.html) / [NGINX](https://allianceauth.readthedocs.io/en/v5.0.1/installation/nginx.html) in the docs).

Container-oriented install: [Installation — Containerized / Docker](https://allianceauth.readthedocs.io/en/v5.0.1/installation-containerized/docker.html).

## Relationship to `core/` (FastAPI) and `core-web/` (Next.js)

| Component | Role |
|-----------|------|
| **`allianceauth/`** | Primary **alliance-style** web portal (users, groups, services, community apps)—closest to “main app” for org operations. |
| **`core/`** | **FastAPI** API: SDE, Discord-bot plugin routes, optional shared SSO/token store for bots—keep as a **service** other clients call. |
| **`core-web/`** | Optional **Next.js** shell for custom pages that call `core/` if you do not implement those inside AA apps. |

Integrating AA with `core/` deeply (single sign-on, one user table) is **non-trivial**: AA uses **Django** + **django-esi**; `core/` uses its own models and EVE SSO flow. Practical phases:

1. **Side-by-side:** Deploy AA for humans; keep `core/` for APIs and the Discord bot; accept two EVE apps or two callback URLs until you unify.
2. **Later:** Add a small bridge (e.g. shared Redis events, or HTTP webhooks from AA to `core/`) only where you need cross-system truth.

## Upgrading Alliance Auth (v5.0.1)

EvE-EMU pins upstream **[Alliance Auth v5.0.1](https://gitlab.com/allianceauth/allianceauth/-/releases/v5.0.1)** via the **`allianceauth/`** Git submodule (commit on tag **`v5.0.1`**). The Docker image installs it editable from **`/opt/allianceauth`** and applies upstream’s **`allianceauth update`** step to refresh **`eve_auth/settings/base.py`** at image build time; your overrides stay in **`deploy/aa_docker/local.py`** (copied over **`eve_auth/settings/local.py`**).

### First-time / ensure submodule is on v5.0.1

```bash
git submodule update --init allianceauth
cd allianceauth
git fetch --tags origin
git checkout v5.0.1
cd ..
git add allianceauth
git commit -m "Pin allianceauth submodule to v5.0.1"
```

### Docker upgrade (matches [upstream updating](https://allianceauth.readthedocs.io/en/latest/installation/allianceauth.html#updating))

1. Check out the desired tag in **`allianceauth/`** (e.g. **`v5.0.1`**).
2. Rebuild and restart **`aa-*`** services (re-runs **`pip install -e`**, **`allianceauth update`**, migrate on **`aa-web`** boot):

```bash
docker compose build aa-web aa-worker aa-beat aa-discordbot
docker compose up -d aa-web aa-worker aa-beat aa-discordbot
```

3. Verify and refresh static data as needed:

```bash
docker compose exec aa-web python manage.py check
docker compose exec aa-web python manage.py sync_sde_compat   # Indy Hub after major upgrades
docker compose exec aa-web python manage.py packagemonitorcli refresh
```

Read [release notes](https://gitlab.com/allianceauth/allianceauth/-/releases) before moving past **v5.0.1**; extension wheels in **`deploy/aa_docker/requirements-aa-extension-*.txt`** are tested against AA 5.x.

### Bare-metal equivalent

Upstream steps: `pip install -U allianceauth`, `allianceauth update <project>`, `manage.py migrate`, `collectstatic --noinput`, restart Gunicorn/Celery — see the [installation guide](https://allianceauth.readthedocs.io/en/latest/installation/allianceauth.html#updating).

## Updating the submodule to a newer AA release

```bash
cd allianceauth
git fetch --tags origin
git checkout v5.0.2   # example newer tag
cd ..
git add allianceauth
git commit -m "Bump allianceauth submodule to v5.0.2"
```

Then follow **Docker upgrade** above.

## Submodule clone for new developers

After `git clone` of eve-emu:

```bash
git submodule update --init --recursive
```

If you skipped submodules at clone time:

```bash
git submodule update --init allianceauth
```
