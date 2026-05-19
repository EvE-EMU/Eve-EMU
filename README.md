# EvE-EMU

**EvE-EMU** is an EVE Online organization stack pivoted toward **industrial planning**, **PvP support**, and **automation**, with **Discord (Emu-Bot)** as a primary day-to-day interface and **Alliance Auth (AA)** as the stable Django hub for accounts, groups, and services.

## What lives in this repository

| Area | Role |
|------|------|
| **`core/`** | **FastAPI** service: EVE SSO, encrypted token storage, SDE, moon-tax and finance plugin APIs, Discord bot–authenticated routes. |
| **`discord-bot/`** | **Emu-Bot**: slash commands, timers, optional core linking, ticket **pre-flight**, and org-specific shortcuts. |
| **`core-web/`** | Optional **Next.js** UI (industrial “dark” shell) for dashboards and calculators that call `core/`. |
| **`industry_suite/`** | **Django app** intended to be installed into your AA project: coalition industrial **projects**, **sub-orders**, and **BPC** index models (extend with Celery + `django-eveuniverse` / ESI client). |
| **`allianceauth/`** (submodule) | Upstream **Alliance Auth** — required to build **`aa-*`** Docker images; runtime project package is **`eve_auth`** with settings in **`deploy/aa_docker/local.py`** (see **`docs/ALLIANCE_AUTH.md`**). |

Heavy ESI pulls (moon ledgers, market prices, corp industry) should run in **Celery** workers in the AA deployment, not in Discord gateway code.

## Quick links

- **Alliance Auth in this repo:** `docs/ALLIANCE_AUTH.md`
- **Security expectations (ESI tokens, webhooks):** `SECURITY.md`
- **Privacy / terms:** `PRIVACY.md`, `TERMS.md`
- **License:** `LICENSE.md` (AGPL-3.0-only for EvE-EMU–origin code; third-party licenses apply to bundled components)

- **Docker (Compose, env, Celery):** `docs/DOCKER.md`

## Unified Docker stack

From the repository root: copy **`.env.example`** to **`.env`**, fill ESI/Discord values, then run **`./setup.sh`** (Git Bash / WSL / Linux). That script generates missing secrets, builds images, applies FastAPI schema init + Django `industry_suite` migrations, and starts **`docker-compose.yml`**. Operational details (submodule, tokens, Fernet key, moon tax mapping, **`aa-beat`**) are in **`docs/DOCKER.md`**; **`.env.example`** documents how variables map into **`CORE_*`** / **`EVE_*`** inside containers.

## Roadmap (high level)

- **Industrial Command:** corp/coalition build plans split into sub-orders; claims via Discord + web; ESI-backed status sync.
- **Emu-Bot:** industrial alerts, killmail routing, EVE title → Discord role mapping (alongside existing core rank sync).
- **Web:** moon tax tooling, BPC request index, logistics calculator, per-user Discord alert toggles (see `core-web/src/app/industrial/`).

Contributions welcome; open an issue before large architectural changes.
