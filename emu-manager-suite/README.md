# EMU Manager Suite (EMUMS)

Coalition operations desktop for EvE EMU — finance, industry, intelligence, storefront, and administration in one EVE-client-style workspace.

**Production:** [https://emums.eve-emu.com](https://emums.eve-emu.com)

EMUMS is a **standalone** FastAPI + Next.js app. It does **not** require Alliance Auth in-process; it uses **EVE SSO / ESI**, **zKillboard**, **Janice**, and its own **MySQL** audit/store tables. Production runs with `EMUMS_SEED_DEMO_DATA=0` (no static demo fixtures).

---

## Features

### Neocom sections

| Section | Tools |
|---------|--------|
| **Activities** | Killboard, SRP, ratting tax, moon productivity / observer / extraction views |
| **Finance** | Buyback, appraisal, refine vs sell, market tracker/browser, corp market, P&I, invoices, project costing |
| **Industry** | Build planner (warehouse stock + max stock), blueprints, industry jobs, **storefront**, PI |
| **Inventory** | Authed structures, corp market, storefront |
| **Personal** | Character audit (skills, assets, wallet, mail, contracts, clones), interaction audit, webhooks |
| **Ship** | Route map, route bookmarks, route planner, wormhole map |
| **Social** | HR directorate, service links, message templates |
| **EMU Services** | Coalition hub, infrastructure, identity/RBAC, security audit |
| **Utilities** | **Awesome Tool Suite** (see below), Knowledge & SDE, About |
| **Settings** | Display, org settings, moon tax config, users & permissions |

### Awesome EVE Tool Suite

Combined and expanded from [awesome-eve](https://github.com/devfleet/awesome-eve) community tools, all on live data:

| Tool | Inspired by |
|------|-------------|
| Intel Paste | PySpy, Eve411, Eve Squadron |
| Trade Margins | EVE Trade, EveMarketTool, Priceall |
| Haul Finder | EVE Trade, Adam4EVE |
| Gate Camp Route | Gate Camp Check, Eden Navigator |
| Corp Who | EveWho, SeAT |
| Battle Report | brcat / zKill |
| Structure Board | Upwell.gg, SeAT structures |
| Ship Compare | Pyfa, Theorycrafter |
| Insurance Check | Eve Insurance Fraud |
| Skill Queues | SkillQ, Cerebral |

Plus deep links into Build Planner, Character Audit, Maps, PI, SRP, and SDE browser.

### Storefront

Corp hangar catalog with:

- Live stock from ESI-synced corp hangar assets
- Pricing cascade: override → Janice split → sell → buy → market aggregates
- Kits with stock derived from components
- Search, category filters, cart (+/− / max), WTB contract instructions, mail/Discord staff notify

### Data principles

- **No static demo rows in production** (`EMUMS_SEED_DEMO_DATA=0`)
- Character data from **SSO + periodic audit sync** (assets, skills, wallet, mail, jobs, PI)
- Markets via **Janice** and/or **ESI / market-api**
- Kill intel via **zKillboard**
- Universe/SDE via local **SDE SQLite** + ESI type detail

Moon **rental** UI is removed for now; backend rental modules may remain dormant for a future return.

---

## Quick start

```bash
# From eve-emu repo root
docker network create eve_emu_edge 2>/dev/null || true

docker compose -f docker-compose.yml -f docker-compose.emums.yml \
  up -d --build \
  emums-mysql emums-redis emums-api emums-web \
  emums-celery-worker emums-celery-beat
```

| Service | URL / port |
|---------|------------|
| Web UI | https://emums.eve-emu.com (local: http://localhost:3020) |
| API | https://emums.eve-emu.com/api → FastAPI `:8020` |
| OpenAPI | `/docs` on the API (when enabled) |

Default API key (change in production): `EMUMS_API_KEY` (see `.env` / `docker-compose.emums.yml`).

---

## Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI, Pydantic v2, SQLAlchemy 2 async |
| DB | MySQL 8 |
| Migrations | Alembic |
| Workers | Celery (audit sync, moons, rentals beat) |
| Cache | Redis |
| UI | Next.js 15, React, Tailwind |
| Edge | Caddy (TLS + routing) |

---

## Project layout

```
emu-manager-suite/
├── backend/                 # FastAPI app (port 8020)
│   ├── app/
│   │   ├── api/v1/          # REST routers
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic (storefront, suite, audit, …)
│   │   ├── tasks/           # Celery tasks
│   │   └── schemas/         # Pydantic I/O
│   ├── alembic/             # Migrations
│   └── Dockerfile
├── frontend/                # Next.js UI (port 3020)
│   ├── src/app/             # App router + BFF API routes
│   ├── src/components/      # Desktop, tools, storefront, suite
│   └── src/lib/             # API client, nav, permissions
├── docs/                    # Architecture, API, deploy, theme
└── README.md                # This file
```

Compose overlay: `docker-compose.emums.yml` at the eve-emu repo root.

---

## Configuration (selected)

| Variable | Purpose |
|----------|---------|
| `EMUMS_DATABASE_URL` | MySQL async URL |
| `EMUMS_REDIS_URL` | Redis |
| `EMUMS_API_KEY` | Service-to-service / BFF key |
| `EMUMS_SSO_CLIENT_ID` / `SECRET` | EVE SSO |
| `EMUMS_SSO_CALLBACK_URL` | SSO return URL |
| `EMUMS_SESSION_SECRET` | Cookie sessions |
| `EMUMS_SEED_DEMO_DATA` | `0` in production |
| `EMUMS_JANICE_API_KEY` | Market pricing |
| `EMUMS_SDE_SQLITE_PATH` | Map / type SDE |
| `EMUMS_MARKET_API_INTERNAL_URL` | Structure market cache |
| `EMUMS_BOOTSTRAP_ADMIN_*` | Initial admin characters |

Full list: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design |
| [docs/API.md](docs/API.md) | REST surface |
| [docs/FRONTEND.md](docs/FRONTEND.md) | UI structure |
| [docs/THEME.md](docs/THEME.md) | Visual system |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker / env |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local workflow |

---

## Development notes

- Frontend BFF routes under `frontend/src/app/api/**` proxy to FastAPI with `X-EMUMS-Key` + session cookie.
- Neocom windows are registered in `frontend/src/lib/tools/nav.ts` and mounted from `UnifiedDesktop.tsx`.
- Awesome suite backend: `backend/app/services/awesome_suite.py`; routes under `/v1/tools/suite/*`.
- Storefront backend: `backend/app/services/storefront.py`.

Rebuild after code changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.emums.yml \
  build emums-api emums-web \
  && docker compose -f docker-compose.yml -f docker-compose.emums.yml \
  up -d emums-api emums-web emums-celery-worker
```

---

## Version

**0.2.1** — Storefront ecommerce pass, structure fuel board, moon mining timing, cleanup.

---

## License

Same as the parent EVE-EMU repository.
