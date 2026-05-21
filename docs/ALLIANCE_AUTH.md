# Alliance Auth (v5) in EVE-EMU

This repository vendors **[Alliance Auth](https://allianceauth.readthedocs.io/en/v5.0.1/)** as a **[Git submodule](https://git-scm.com/book/en/v2/Git-Tools-Submodules)** at **`allianceauth/`**, pinned to upstream tag **`v5.0.1`** (Django-based auth hub for EVE organizations: services, groups, fleet tools, SRP apps, etc.—see the [official overview](https://allianceauth.readthedocs.io/en/v5.0.1/)).

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
```

Configure root **`.env`** (see **`.env.example`**):

- **`AA_SITE_URL`** — public base URL of the auth site (no trailing slash), e.g. **`https://auth.eve-emu.com`**. For local-only HTTP without Caddy, set an explicit **`http://…`** URL that matches how you reach the app.
- **`ESI_CLIENT_ID`** / **`ESI_CLIENT_SECRET`** — same EVE developer app as **`core-api`** (or a dedicated app). **`ESI_CALLBACK_URL`** must match CCP **character-for-character** (default **`https://auth.<domain>/sso/callback`** — **no trailing slash**). Add **both** `…/sso/callback` and `…/sso/callback/` on the CCP app only if you intentionally use two URLs; this stack normalizes to **no** trailing slash (see [Alliance Auth installation](https://allianceauth.readthedocs.io/en/v5.0.1/installation/index.html)).
- **`AA_DJANGO_SECRET_KEY`**, **`POSTGRES_*`**, **`REDIS_URL`** — same Postgres role/database as **`POSTGRES_DB_AA`** (`eve_emu_aa` by default).

On first start, **`docker/django-aa/entrypoint.py`** runs **`repair_indy_hub_migrations.py`** (records Indy Hub `0023` when columns already exist), then **`manage.py migrate`** and **`collectstatic`** before Gunicorn (Alliance Auth touches Redis during `django.setup()`, so static collection is not done at image build time).

**Indy Hub on PostgreSQL:** upstream migrations `0023`, `0026`, `0049`, and `0050` assume MySQL/SQLite for some schema steps; patched copies live under **`deploy/aa_docker/patches/indy_hub/`** and are copied into the **`aa-*`** image at build time. **`repair_indy_hub_migrations.py`** (runs before migrate on web boot) fixes partial states. If migrate still fails, rebuild **`aa-web`** and run:

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

**Bundled extensions** (enabled when **`AA_EXTENSIONS_ENABLED=1`**): [Standings Sync](https://apps.allianceauth.org/apps/detail/aa-standingssync), [Structures](https://apps.allianceauth.org/apps/detail/aa-structures), [Structure Timers II](https://apps.allianceauth.org/apps/detail/aa-structuretimers), [Moon Mining](https://apps.allianceauth.org/apps/detail/aa-moonmining), [Metenox](https://apps.allianceauth.org/apps/detail/aa-metenox), [Buyback Program](https://apps.allianceauth.org/apps/detail/aa-buybackprogram), [Indy Hub](https://apps.allianceauth.org/apps/detail/indy-hub), [Market Manager](https://apps.allianceauth.org/apps/detail/aa-market-manager), [Kill Tracker](https://apps.allianceauth.org/apps/detail/aa-killtracker), [Killstats](https://apps.allianceauth.org/apps/detail/aa-killstats), [Intel Tool](https://apps.allianceauth.org/apps/detail/aa-intel-tool), [Sov Timer](https://apps.allianceauth.org/apps/detail/aa-sov-timer), [CorpTools](https://apps.allianceauth.org/apps/detail/allianceauth-corptools), [Secure Groups](https://apps.allianceauth.org/apps/detail/allianceauth-securegroups), [Blacklist](https://apps.allianceauth.org/apps/detail/allianceauth-blacklist), [Contacts](https://apps.allianceauth.org/apps/detail/aa-contacts), [Alumni](https://apps.allianceauth.org/apps/detail/aa-alumni), [Inactivity](https://apps.allianceauth.org/apps/detail/aa-inactivity), [AA-SRP](https://apps.allianceauth.org/apps/detail/aa-srp), [AFAT](https://apps.allianceauth.org/apps/detail/allianceauth-afat), [Fleet Pings](https://apps.allianceauth.org/apps/detail/aa-fleetpings), [Fittings](https://apps.allianceauth.org/apps/detail/fittings), [Timezones](https://apps.allianceauth.org/apps/detail/aa-timezones), [Ledger](https://apps.allianceauth.org/apps/detail/aa-ledger), [Skillfarm](https://apps.allianceauth.org/apps/detail/aa-skillfarm), [CharLink](https://apps.allianceauth.org/apps/detail/aa-charlink), [ESI Status](https://apps.allianceauth.org/apps/detail/aa-esi-status), [Routing](https://apps.allianceauth.org/apps/detail/aa-routing), [Top](https://apps.allianceauth.org/apps/detail/aa-top), [Package Monitor](https://apps.allianceauth.org/apps/detail/aa-package-monitor), [Task Monitor](https://apps.allianceauth.org/apps/detail/aa-taskmonitor), [Celery Analytics](https://apps.allianceauth.org/apps/detail/allianceauth-celeryanalytics).

Also enabled in the image: [Discord bot](https://apps.allianceauth.org/apps/detail/allianceauth-discordbot) (`aa-discordbot` Compose service), [Discord Notify](https://apps.allianceauth.org/apps/detail/aa-discordnotify) (needs [Discord Proxy](https://gitlab.com/ErikKalkoken/discordproxy)), [Wiki.js](https://apps.allianceauth.org/apps/detail/allianceauth-wiki-js) (`wikijs` Compose service + [WIKIJS.md](./WIKIJS.md)), [Slate theme](https://apps.allianceauth.org/apps/detail/aa-theme-slate), [Skip Email](https://apps.allianceauth.org/apps/detail/aa-skip-email). Optional: [GraphQL](https://apps.allianceauth.org/apps/detail/allianceauth-graphql) via **`AA_EXTENSIONS_GRAPHQL=1`**.

After **`docker compose build aa-web aa-worker aa-beat`** and **`docker compose up -d`**, migrations run on **`aa-web`** boot. One-time data loads (run as needed):

```bash
docker compose exec aa-web python manage.py esde_load_sde
docker compose exec aa-web python manage.py sync_sde_compat   # required once for Indy Hub UI
docker compose exec aa-web python manage.py packagemonitorcli refresh
docker compose exec aa-web python manage.py setup_securegroup_task
docker compose exec aa-web python manage.py timezones_load_tz_data
docker compose exec aa-web python manage.py moonmining_load_eve
docker compose exec aa-web python manage.py structuretimers_load_eve
docker compose exec aa-web python manage.py buybackprogram_load_data
docker compose exec aa-web python manage.py buybackprogram_load_prices
docker compose exec aa-web python manage.py buyback_v2_enable_programs
docker compose exec aa-web python manage.py sovtimer_load_initial_data
docker compose exec aa-web python manage.py corptools ct_setup
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
docker compose exec aa-web pip install "click>=8.4.0,<9" \
  "django-eveuniverse @ git+https://gitlab.com/ErikKalkoken/django-eveuniverse.git@2.0.0a7"
docker compose exec aa-web python manage.py packagemonitorcli refresh
```

Prefer the **rebuild** path so **`aa-worker`** / **`aa-beat`** stay in sync with **`aa-web`**.

### Corp stock orders (`corp_orders`)

Officer/director **item exchange** quotes for corp stock buys (Janice + PushX Jita → Badivefi). See **[CORP_ORDERS.md](./CORP_ORDERS.md)**. Menu: **Corp stock orders** at `/corp-orders/`.

### Buyback v2 (Janice line pricing)

The stock [Buyback Program](https://apps.allianceauth.org/apps/detail/aa-buybackprogram) UI and contracts are unchanged. **`buyback_v2`** adds per-program rules in Django admin (**Buyback v2 pricing profiles**):

- **Janice** as the price source when **`BUYBACKPROGRAM_PRICE_JANICE_API_KEY`** is set (see [Janice API](https://janice.e-351.com/api/rest/docs/index.html)).
- **Line-by-line** choice between reprocess (refined minerals from SDE + Janice material prices) and normal market price.
- **Variant selection**: prefer reprocess unless market is cheaper (default), legacy max-of-all, corp minimum, reprocess-only, or market-only.
- **Price basis**: program Buy/Sell/Split, or force buy / sell / split; **Jita buy %** scales the final line price.

Set `BUYBACKPROGRAM_PRICE_METHOD=Janice` and `BUYBACKPROGRAM_PRICE_JANICE_API_KEY` in the environment. After deploy, run **`buyback_v2_enable_programs`** once so existing programs get a profile.

**Standing Fleet Tracker** (`/standing-fleet/`): polls linked characters’ fleets via ESI, scores standing-fleet hours, home-defence kill bonuses, and sov-roam penalties. See `standing_fleet_tracker/README.md` and env vars `SFT_*` in `.env.example`.

**Tiered pricing:** In admin, open a program’s **Buyback v2 pricing profile** → add **Pricing tiers** (e.g. `0.9000` = 90%) and **rules** (corporation ID, alliance ID, or character ID). Higher **priority** wins. Mark one tier **default** for logged-in users with no rule match. Enable **public calculator** and set **public multiplier** (or add a tier with **Is public**) for no-login quotes at **`/buyback-public/`** (sidebar: *Public buyback prices*).

Each app needs **permissions**, **ESI scopes** on your CCP application, and sometimes **director tokens**—see the linked app pages on [apps.allianceauth.org](https://apps.allianceauth.org).

**Auto groups by corp + Director title/role:** use **Secure Groups** + **CorpTools** filters (already in the Docker image). Step-by-step: [SECURE_GROUPS_BY_TITLE.md](./SECURE_GROUPS_BY_TITLE.md). Run `setup_securegroup_task` and `corptools ct_setup` once; add `esi-characters.read_corporation_roles.v1` and `esi-characters.read_titles.v1` on your CCP app and Charlink.

**Market Manager:** After deploy, configure **Admin → Marketmanager → Public configs** (select regions, e.g. The Forge), then run `docker compose exec aa-web python manage.py shell -c "from marketmanager.tasks import fetch_public_market_orders; fetch_public_market_orders.delay()"`. The browser shows orders only after you **search an item** (3+ characters) and pick a region. Structure admin add was broken on `eve_sde` field names (`group` vs `item_group`) — fixed via `deploy/aa_docker/patches/marketmanager/` (rebuild `aa-web`).

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
