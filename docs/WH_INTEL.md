# WH Intel overlay — `https://wh.<DOMAIN>/intel/`

RIFT-style intel map companion for [Wanderer](WANDERER.md): ingests **intel.womp** and **OnlyQuerious** chat from your local EVE client logs, draws **5-minute system rings**, links **character portraits**, supports **gate bubble** markers on jump lines, and **sov tags** on systems.

Wanderer CE itself is unchanged; this runs at **`/intel/`** on the same `wh.*` host.

## Deploy

```powershell
# Postgres DB (only auto-created on a fresh db volume; run once if wh-intel crashes on startup):
docker compose exec db psql -U eve -d postgres -c "CREATE DATABASE eve_emu_wh_intel OWNER eve;"

docker compose build wh-intel
docker compose up -d wh-intel
docker compose up -d --force-recreate caddy
```

If `wh-intel` was already running before you added the DB, restart it after `CREATE DATABASE`.

Open **`https://wh.eve-emu.com/intel/`**.

## Local chat tailer (Windows)

EVE writes chat logs under:

`C:\Users\BDD\Documents\EVE\logs\Chatlogs`

Run on your gaming PC (not in Docker). **Keep the window open** while you play.

**Easiest (no PowerShell script policy):**

```cmd
wh_intel\scripts\run_intel_tailer.cmd
```

Or double-click `run_intel_tailer.cmd` in Explorer.

**PowerShell** (if `.ps1` is blocked, use Bypass or the `.cmd` above):

```powershell
pip install httpx
python wh_intel\scripts\intel_chat_tailer.py --api https://wh.eve-emu.com/intel/api/v1/ingest
```

Channels default to **`intel.womp`** and **`OnlyQuerious`**. Override with `--channels`.

The tailer must attach the log file’s `Channel: …` header to each POST (EVE only writes that header when you switch channels). **Restart the tailer** after pulling repo updates so single-line intel is sent immediately, not batched to 6 lines.

### Parsed format

Input line:

```text
[00:25:12] sevey > <url=showinfo:1375//95187887>Prime Shacks</url>  <url=showinfo:5//30004019>3-FKCZ</url>
```

The speaker (`sevey >`) is stripped. **Prime Shacks** gets a portrait link; **3-FKCZ** gets a pulsing ring for 5 minutes.

## Map features

| Feature | How |
|---------|-----|
| System rings | Auto from ingested intel; TTL `WH_INTEL_RING_TTL_SECONDS` (default 300) |
| Character portraits | EVE image server from showinfo character IDs |
| Gate bubbles | Click a green jump line → choose `from` or `to` side |
| Sov tags | Auto from ESI sovereignty map for `WH_INTEL_SOV_ALLIANCE_IDS` (default WOMP `99010468`); manual tags via API |
| Multiple tags | POST `/intel/api/v1/tags` per system |

## API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/intel/api/v1/ingest` | Raw chat log chunk |
| GET | `/intel/api/v1/overlay` | Map JSON (systems, jumps, rings, bubbles, tags) |
| POST | `/intel/api/v1/bubbles` | Gate bubble |
| POST | `/intel/api/v1/tags` | Manual tag |
| POST | `/intel/api/v1/sov/refresh` | Force sov tag refresh |

## `.env`

```env
WH_INTEL_PUBLIC_BASE_URL=https://wh.eve-emu.com/intel
WH_INTEL_CHANNELS=intel.womp,OnlyQuerious
WH_INTEL_SOV_ALLIANCE_IDS=99010468
# Optional: Fuzzwork sqlite for accurate map x/y (mount into container)
# WH_INTEL_SDE_SQLITE_PATH=/data/sqlite-latest.sqlite
POSTGRES_DB_WH_INTEL=eve_emu_wh_intel
```

## Wanderer auto-sync (recommended)

Intel can push into your **False-Gods** Wanderer map (`slug: false-gods`) so pilots see updates on the main mapper at **`https://wh.eve-emu.com/false-gods`**, not only on `/intel/`.

### One-time setup

1. Open Wanderer → **False-Gods** map → **Settings**.
2. Copy the **Map API token** (Bearer token).
3. Add to root `.env`:

```env
WH_INTEL_WANDERER_SYNC=1
WH_INTEL_WANDERER_MAP_SLUG=false-gods
WH_INTEL_WANDERER_API_TOKEN=paste-token-here
```

4. Rebuild/restart:

```powershell
docker compose up -d --build wh-intel
```

### What syncs where

| Intel feature | Wanderer target | Mechanism |
|---------------|-----------------|-----------|
| Chat intel (5 min) | `map_system_v1.status = dangerousPrimary (5)` | `PUT /api/maps/false-gods/systems/{solar_system_id}` |
| Character names | `map_system_v1.description` | Portrait URLs + names from showinfo |
| Multiple tags | `map_system_v1.labels` JSON | Merged (`intel:intel.womp`, `sov:…`, manual) |
| Gate bubble | `map_chain_v1.custom_info` | `PATCH /api/maps/.../connections?source=&target=` → `BUBBLE:from` / `BUBBLE:to` |
| TTL expiry | status cleared to `unknown (0)` | Background job every 30s |

### Important limits

- Wanderer has **no public REST API for map pings** (the animated ring). Pings are LiveView-only. The bridge uses **system status + description** instead — the system turns **red/hostile** for 5 minutes, then clears.
- Optional `WH_INTEL_WANDERER_DB_PING_SYNC=1` inserts into `map_pings_v1` but **does not** live-broadcast to open map tabs (no Phoenix event). Prefer the API status path.
- Your map’s `public_api_key` in Postgres may be empty until you generate it in Wanderer UI — the token from **Map Settings** is what you need.

### Data flow

```text
EVE Chatlogs (PC) → intel_chat_tailer.py → wh-intel /ingest
                                              ├→ eve_emu_wh_intel (overlay /intel/)
                                              └→ Wanderer API → wanderer DB → map UI
```

See also [Wanderer Systems API](https://wanderer.ltd/news/systems-connections-api).

## Notes

- First boot loads jump graph from ESI (`universe/system_jumps/`) if no SDE SQLite is mounted (can take ~1 minute).
- For best map layout, mount [Fuzzwork SQLite](https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2) and set `WH_INTEL_SDE_SQLITE_PATH`.
- Use **`/intel/`** for RIFT-style rings/portraits; use **Wanderer** for corp map ops — with sync enabled, intel hits both.
