# EvE-EMU Discord bot

Python bot for **INDEX / WOMP**–style EVE communities: **mining anomaly timers**, **moon sheet pings**, comms shortcuts, and optional hooks into the **EvE-EMU** API.

**Community Discord:** [discord.gg/DHMTKsMNbp](https://discord.gg/DHMTKsMNbp)

---

## Run (quick)

1. **Python 3.11+**
2. From repo: `cd discord-bot/bot` → create venv → `pip install -r ../requirements.txt`
3. Copy **`example.env`** to **`.env`** in the same folder as `eve_mining_timer_bot.py`, set **`EVE_DISCORD_BOT_TOKEN`**, then: `python eve_mining_timer_bot.py`

Secrets stay in **`.env`** (gitignored). Full env list: **`bot/example.env`** and the module docstring in **`bot/eve_mining_timer_bot.py`**.

---

## Slash commands

| Command | What it does |
|--------|----------------|
| **`/miner timer`** | Ore respawn from **pop time** (system, anomaly name, UTC). Duration is **inferred from the anomaly name** (e.g. Small/Medium → short band, Average → middle, Large/Enormous/Colossal → long band, **Type A/B/C … Belt** → A/B/C crystal band). **Large / Enormous Mercoxit** use fixed **8h / 12h**. Autocomplete for systems and anomaly names when configured. |
| **`/miner respawns`** | Timers whose respawn falls in **±10 hours** (EVE/UTC). |
| **`/website`** | Alliance **EvE-EMU** site URL. |
| **`/help`** | Slash + text command summary (includes Discord invite). |
| **`/eve-link`** | Link Discord to EvE-EMU with a **one-time code** (requires API link route). |

> **`/structure`** (new timer + admin panel) exists in code but is **not** on the slash tree right now; structure **feed** embeds from the API still work when configured.

---

## Text commands (no slash permissions)

| Command | What it does |
|--------|----------------|
| **`!miner timer`** | Same as **`/miner timer`**. Optional leading **`T1`/`T2`/`T3`** overrides inferred band. |
| **`!miner respawns`** | Same as **`/miner respawns`** (`**!miner resawns**` typo accepted). |
| **`!help`** | Lists text commands + EvE-EMU Discord link. |
| **`!srp`**, **`!auth`**, **`!mumble`**, **`!intel`**, **`!buyback`** | Static links / guides (`!mumble` can attach a PTT GIF if configured). |
| **`!eve-link`** + code | In-channel link flow. |
| **`!popejoy`** | Hard-coded joke line. |
| **`!testping`** | Preview mining ping layout for a belt / anomaly label. |

---

## Mining timers and `@here` pings

- **`eve_time`** is when the belt was **popped** (cleared). Respawn = pop + duration.
- Default bands (**T1 / T2 / T3** hours): **1h**, **4h 20m**, **10h** — tune with **`EVE_T1_RESPAWN_HOURS`**, **`EVE_T2_RESPAWN_HOURS`**, **`EVE_T3_RESPAWN_HOURS`** (float or **`H:MM`**, e.g. `4:20`).
- **`EVE_MINING_PING_LEAD_MINUTES`** (default **30**): ping that many minutes **before** respawn; **`0`** = ping at respawn.
- State file: **`data/mining_timers.json`** (override with **`EVE_MINING_TIMER_STATE_FILE`**).
- Optional **belt ping images** and Griemeer-style extras when paths / env images are set.

---

## Moon timer pings (optional, no EvE-EMU API)

- Polls tab **`moon_timers`** on the public sheet **[Moon Timers – FALSE GODS](https://docs.google.com/spreadsheets/d/1cDtuFQivlumB_HNZGVXWmZaHcPomFZT6r_zAe_G6VhY/edit?usp=sharing)** as CSV (Google **`gviz`** export).
- Enable with **`EVE_MOON_TIMERS_CHANNEL_ID`** (Discord text channel). If **`EVE_MOON_TIMERS_CSV_URL`** is unset, the bot uses the default gviz URL for that sheet + tab.
- **`EVE_MOON_TIMERS_LEAD_MINUTES`** (default **30**), **`EVE_MOON_TIMERS_POLL_SECONDS`** (default **300**, min **120**), **`EVE_MOON_TIMERS_PING_HERE`** (default **1**; set **`0`** to omit `@here` from the message body).
- Dedupe state: **`data/moon_timer_pings.json`** (override **`EVE_MOON_TIMERS_PING_STATE_FILE`**).
- Rows must include a **parseable UTC/EVE datetime** in **`Next Timer`** (or another time-like column). Renter / rent / value columns are ignored. Empty timer cells → no ping for that row.
- Sheet sharing: **Anyone with the link can view** so CSV fetch works without Google auth.

---

## Member welcome (optional)

First-time joiners in a configured guild can get a single **welcome** message in a set channel (tracked on disk so it is not spammed).

---

## API-backed features (when `EVEEMU_API_BASE_URL` + `MINING_BOT_DASHBOARD_TOKEN` are set)

| Feature | Summary |
|--------|---------|
| **Dashboard heartbeat** | POST bot status to the mining integration URL. |
| **Industry watch DMs** | API returns queued messages → user DMs. |
| **Structure timer board** | API tick → **embeds** in the configured channel (sheet + corp ESI on server). |
| **Market / stocker alerts** | **Embeds** (+ optional role ping) from market-watch payloads. |
| **Account notifications** | **DMs** from API tick. |
| **Buyback admin alerts** | Channel posts for buyback admin events. |
| **Corporation projects** | Corp project updates from ESI via API + bot channel routing. |

---

## Configuration reference

- **`bot/example.env`** — commented template for all bot-side variables.
- **`bot/eve_mining_timer_bot.py`** (module docstring at top) — authoritative list and API-side env names that live on the server.

For **Google Sheets** used by moon timers, prefer publishing / link sharing as documented above; structure timer CSV URLs are configured on the **API**, not in this README.
