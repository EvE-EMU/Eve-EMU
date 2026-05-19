# EVE-EMU Core — web (Next.js)

Optional **browser** UI for **EvE-EMU** with an **industrial-focused dark console** at **`/industrial`** (logistics calculator, notification toggle prototype, and placeholders for moon taxes and BPC flows that call **`core/`** once authenticated).

For an **Alliance Auth–style** main app (groups, services, fleet/SRP ecosystem), use the **`allianceauth/`** submodule and **`docs/ALLIANCE_AUTH.md`**. Add the repo-root Django app **`industry_suite`** to `INSTALLED_APPS` for coalition industrial models. The **`core/`** folder remains the **FastAPI backend** (REST, SSO, Postgres, bot-only plugin routes). The **Discord bot** is separate and calls `core/` where needed.

## Scripts

```bash
cd core-web
npm install
npm run dev   # uses Turbopack (next dev --turbopack); production still uses next build
```

Open [http://localhost:3000](http://localhost:3000).

## Environment

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_CORE_API_URL` | Public FastAPI base URL (e.g. `https://api.your-domain.example`). Used from the browser for future authenticated calls. |
| `CORE_WEB_BASE_PATH` | **Build-time** optional subpath (e.g. `/core`) so the app is served under `https://host/core/...`. Must match your reverse proxy. Omit for root `/`. |

Copy `.env.local.example` to `.env.local` for local overrides.

## Architecture

```
Discord users  →  Discord bot  →  FastAPI (core/)  ←  Next.js (core-web/)  ←  Browser users
                     ↑                    ↑
              EVE_CORE_BOT_SECRET    cookies / SSO
```

Build the product UX here; keep privileged **bot** traffic on server-side routes in `core/` with `Authorization: Bearer`.
