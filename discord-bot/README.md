# EvE-EMU Discord bot (standalone)

This folder was split from the main EvE-EMU monorepo so the **mining / structure timer / linking** bot can live and ship on its own.

## What lives here

- **`bot/eve_mining_timer_bot.py`** — the Discord application (slash commands, `/eve-link`, structure timers, optional heartbeats to your API, etc.). Run it with Python 3.11+.

## Python dependencies

```bash
cd bot
python -m venv .venv
.\.venv\Scripts\activate   # Windows
pip install -r ../requirements.txt
python eve_mining_timer_bot.py
```

Configure with environment variables as documented in the script header (Discord token, optional `MINING_BOT_DASHBOARD_PUSH_URL` + `MINING_BOT_DASHBOARD_TOKEN`, `EVEEMU_API_BASE_URL`, etc.). You can put secrets in `bot/.env` (see `python-dotenv` — `EVE_DISCORD_BOT_TOKEN=...`); that file is gitignored. In **cmd.exe**, set `set EVE_DISCORD_BOT_TOKEN=...` before `python`; `$env:...` only works in **PowerShell**.

## API integration

The bot can POST heartbeats and call operator endpoints on your **EvE-EMU FastAPI** instance. Those routes remain in the main repo under:

`backend/app/routes/discord_bot_dashboard.py`  
(prefix **`/integrations/mining-discord-bot`**)

Deploy the API with `MINING_BOT_DASHBOARD_TOKEN` set, and point the bot at the same origin.

## Operator dashboard UI

The browser dashboard that used to live at **`/ops/discord-bot`** was removed from the main Next.js app during the auth reset. To run it again:

1. Restore the last revision of `web/src/app/ops/discord-bot/page.tsx` from git history.
2. Drop it into a small standalone Next.js (or Vite) app.
3. Set `NEXT_PUBLIC_API_BASE_URL` (or your existing `clientApiBase` equivalent) to the API origin that serves `/integrations/mining-discord-bot/*`.

Alternatively, use **Bearer `MINING_BOT_DASHBOARD_TOKEN`** against `GET /integrations/mining-discord-bot/status` from any HTTP client or Grafana.

## Discord linking (`/eve-link`)

That flow previously depended on **`/auth/discord/*`** routes in the main API and cookies on the website. Those routes were removed with the auth strip. If you still need link codes, either:

- Re-introduce a minimal Discord-link API in this project, or  
- Restore the specific routers from git history on the main API.
