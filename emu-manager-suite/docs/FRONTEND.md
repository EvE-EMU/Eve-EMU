# EMU Manager Suite — Frontend

## Stack

- **Next.js 15** App Router
- **React 19** Server Components for data pages
- **Tailwind CSS 3** + custom EVE/propaganda tokens
- **Recharts** for dashboard charts
- **TanStack Table** (installed; wire on moons page when interactivity needed)

## Routes

| Path | Page | Data source |
|------|------|-------------|
| `/` | Command dashboard | `GET /v1/dashboard` |
| `/moons` | Mining log + invoices | `/v1/moons/*` |
| `/templates` | Template gallery | `/v1/templates` |
| `/settings` | Directorate config | `/v1/settings` |

External: `/docs` → FastAPI Swagger (same host, proxied by Caddy)

## Data fetching

All API calls go through `src/lib/api.ts`:

- Runs on **server only** (RSC / Server Components)
- Uses `EMUMS_API_URL` + `EMUMS_API_KEY` from environment
- Never use `NEXT_PUBLIC_*` for the API key

Revalidation: `next: { revalidate: 30 }` on fetches for balance of freshness vs load speed.

## Layout

`AppShell` provides:

- Sticky header with product title
- Responsive nav
- Footer attribution

Pages only render content inside `<main>`.

## Performance

- `output: "standalone"` in `next.config.ts` for slim Docker image
- `compress: true`, `poweredByHeader: false`
- Charts lazy-render client-side only in `Charts.tsx` (`"use client"`)
- Minimize client JS: pages are async server components except charts/nav

## Mobile

- Touch-friendly nav wraps on narrow screens
- Tables scroll horizontally
- KPI tiles 2-up on phones

See `docs/THEME.md` for visual specification.
