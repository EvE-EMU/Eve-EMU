# EMU Manager Suite — Architecture

## Purpose

EMUMS is a **standalone product framework** for EVE industrial/coalition management tools. It forks the **EMU Moons** domain (mining logs, invoices, tax rules, message templates) but runs as its own stack:

- **No Alliance Auth** — API key auth today; SSO module slot documented for later
- **MySQL** — isolated database (`emums` on `emums-mysql`)
- **OpenAPI** — every feature exposed as REST first; UI consumes the same API
**Production host** — `https://emums.eve-emu.com` (standalone, no Alliance Auth)

Future modules (ERP, commerce, rentals, fleet) should follow the same pattern: `app/api/v1/<module>.py`, SQLAlchemy models, Next.js route under `frontend/src/app/<module>/`.

## Topology

```
Browser → Caddy (TLS) → emums-web (Next.js :3020)
                      → emums-api (FastAPI :8020) → emums-mysql (:3306)
```

Caddy routes on `emums.eve-emu.com`:

| Path | Service |
|------|---------|
| `/v1/*`, `/docs`, `/openapi.json` | emums-api |
| everything else | emums-web |

## Backend layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| Config | `app/config.py` | `EMUMS_*` env vars |
| Models | `app/models/` | SQLAlchemy ORM |
| Schemas | `app/schemas/` | Pydantic I/O |
| API | `app/api/v1/` | HTTP routers |
| Services | `app/services/` | Business logic, Jinja render, dashboard aggregation |
| Auth | `app/auth/deps.py` | `X-EMUMS-Key` validation |
| DB | `app/db/` | Async engine, startup `create_all` + demo seed |

## Frontend layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| App shell | `src/components/AppShell.tsx` | Nav, responsive header |
| Theme | `src/app/globals.css`, `docs/THEME.md` | EVE panels + propaganda |
| Data | `src/lib/api.ts` | **Server-only** fetch with API key |
| Pages | `src/app/*/page.tsx` | RSC pages (dashboard, moons, templates, settings) |
| Charts | `src/components/Charts.tsx` | Recharts wrappers |

## Template system

Templates live in `emums_message_templates`:

- **channel**: `mail` | `discord` | `report` | `ui`
- **body/subject**: Jinja2 strings
- **variables_json**: documented placeholders
- **POST /v1/templates/{id}/render**: preview with sample data

This mirrors EMU Moons mail templates but is channel-agnostic for the ecosystem.

## Extension checklist (new module)

1. Add SQLAlchemy models + Pydantic schemas
2. Add `app/api/v1/<module>.py` and register in `router.py`
3. Add service module if logic exceeds ~40 lines
4. Add Next.js page + nav link in `AppShell.tsx`
5. Document endpoints in `docs/API.md`
6. Add demo seed rows if visual-first iteration is needed

## Fork lineage

| EMU Moons (Django/AA) | EMUMS (standalone) |
|-----------------------|---------------------|
| `EmuCorpMiningLog` | `MiningLog` |
| `EmuInvoice` | `Invoice` |
| `StructureTaxRateRule` | `StructureTaxRule` |
| `EmuMoonsSettings` | `OrgSettings` |
| Mail template fields on settings | `MessageTemplate` table |
| Celery sync tasks | Future: `app/workers/` + Redis |

Source reference: `deploy/aa_docker/emu_moons/`
