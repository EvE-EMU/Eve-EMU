# EVE-EMU Discord bot

Python bot for **EVE-EMU**: **mining anomaly timers** (`/miner`), **moon timer alerts** from a public Google Sheet CSV, and **slash shortcuts** (`/help`, `/about`, `/admin …`, `/srp`, `/auth`, `/mumble`, `/intel`, `/buyback`). Slash command replies are **ephemeral** (only the person who ran the command sees them in that channel). There is **no** API or dashboard integration in this build.

**Community Discord:** [discord.gg/DHMTKsMNbp](https://discord.gg/DHMTKsMNbp)

---

## Run (quick)

1. **Python 3.11+**
2. From repo: `cd discord-bot/bot` → create venv → `pip install -r ../requirements.txt`
3. Copy **`example.env`** to **`.env`** in the same folder as `eve_mining_timer_bot.py`, set **`EVE_DISCORD_BOT_TOKEN`**, then: `python eve_mining_timer_bot.py`

Secrets stay in **`.env`** (gitignored). Env reference: **`bot/example.env`** and the module docstring in **`bot/eve_mining_timer_bot.py`**.

---

## Discord setup: intents, invite, and permissions

### Privileged gateway intents (Developer Portal)

The bot sets **`guilds`** only among optional toggles and leaves **`members`**, **`messages`**, and **`message_content`** off (`eve_mining_timer_bot.py` → `build_bot`). You do **not** need **Message Content Intent**, **Server Members Intent**, or **Presence Intent** for this build.

### Bot invite URL (OAuth2 scopes)

- **Scopes:** `bot` and **`applications.commands`** (slash commands).

### Permissions

| Permission | Used for |
|------------|----------|
| **Use Slash Commands** | Run `/help`, `/miner`, etc. |
| **Send Messages** | Ephemeral slash followups; mining/moon alert channels if configured. |
| **Attach Files** | `/mumble` GIF, belt images in ephemeral followups, DMs, and mining alert channel. |

**Mining belt is due:** the author still gets a **DM** (no interaction available for ephemeral). If **`EVE_MINING_PING_CHANNEL_ID`** is set, the bot also posts in that channel, with optional **`@here`** when **`EVE_MINING_PING_HERE=1`**. Grant **Mention @here** in that channel if you use **`@here`**.

**Moon:** set **`EVE_MOON_TIMERS_CHANNEL_ID`** to post in a text channel; **`EVE_MOON_TIMERS_PING_HERE=1`** adds **`@here`** to that channel message. You can set **`EVE_MOON_TIMERS_NOTIFY_USER_ID`** at the same time for a plain-text **DM** copy (no **`@here`** in DMs).

---

## Slash commands

| Command | What it does |
|--------|----------------|
| **`/help`** | Command list + Discord invite (ephemeral). |
| **`/about`** | Credits (**Sevey**) + invite (ephemeral). |
| **`/admin notes`** | Manual operator instructions (ephemeral). |
| **`/admin restart`** | Runs `docker compose restart` when **`EVE_DOCKER_*`** env is set (ephemeral output). |
| **`/admin rebuild`** | `docker compose build --no-cache` then `up -d` for the service (ephemeral). |
| **`/miner timer`** | Ore respawn from **pop time** (system, anomaly name, UTC). Durations are **inferred from the anomaly name**; **Large / Enormous Mercoxit** use fixed **8h / 12h**. |
| **`/miner respawns`** | Timers in **±10 hours** (EVE/UTC) (ephemeral). |
| **`/srp`**, **`/auth`**, **`/mumble`**, **`/intel`**, **`/buyback`** | Static links / guides (`/mumble` can attach a PTT GIF if configured). |

**`/admin restart`** and **`/admin rebuild`** run **`docker compose`** on the host where the bot process runs (`docker` must be on `PATH`, with access to the compose project in **`EVE_DOCKER_COMPOSE_DIR`**). If the bot is **inside** the container it restarts, the ephemeral reply may not show; check **`docker compose logs`**. See **`example.env`** (`EVE_DOCKER_ADMIN_ENABLED`, `EVE_DOCKER_COMPOSE_SERVICE`, etc.).

---

## Mining timers and reminders

- **`eve_time`** = when the belt was **popped**. Respawn = pop + duration.
- Bands: **`EVE_T1_RESPAWN_HOURS`**, **`EVE_T2_RESPAWN_HOURS`**, **`EVE_T3_RESPAWN_HOURS`** (default **1h / 4h 20m / 10h**).
- **`EVE_MINING_PING_LEAD_MINUTES`** (default **30**): **DM** the person who set the timer that many minutes **before** respawn; **`0`** = at respawn.
- **`EVE_MINING_PING_CHANNEL_ID`** (optional): also post belt alerts (and optional belt images) in this text channel; use **`EVE_MINING_PING_HERE`** (default on) for **`@here`** in that channel.
- **`/miner timer` system autocomplete:** optional **ESI sovereignty** — set **`EVE_SYSTEM_NAMES_SOV_ALLIANCE_ID`** (or **`EVE_SYSTEM_NAMES_SOV_ALLIANCE_NAME`** for [GetSovereigntyMap](https://developers.eveonline.com/api-explorer#/operations/GetSovereigntyMap)–style filtering). The bot refreshes that list on a timer (default **24h**, **`EVE_SYSTEM_NAMES_SOV_REFRESH_HOURS`**). Names come from **`mapSolarSystems`** CSV (**`EVE_SYSTEM_NAMES_CSV_*`**); if sovereignty is unset or yields no names, the full CSV list is used as before.
- State: `data/mining_timers.json` (override: `EVE_MINING_TIMER_STATE_FILE`).

---

## Moon timer alerts (optional)

Configured with **`EVE_MOON_TIMERS_*`** (see **`example.env`**). **`EVE_MOON_TIMERS_CHANNEL_ID`** posts to that channel; **`EVE_MOON_TIMERS_PING_HERE`** controls **`@here`** on the channel post. **`EVE_MOON_TIMERS_NOTIFY_USER_ID`** sends the same summary by **DM** (no **`@here`**); you can use **channel + notify** together.

Uses the public **[Moon Timers – FALSE GODS](https://docs.google.com/spreadsheets/d/1cDtuFQivlumB_HNZGVXWmZaHcPomFZT6r_zAe_G6VhY/edit?usp=sharing)** sheet tab **`moon_timers`** by default when a moon destination (notify user and/or channel) is configured.

---

## Configuration reference

- **`bot/example.env`** — all bot-side variables for this build.

For moon CSV, the sheet must be viewable as described in **`eve_mining_timer_bot.py`** (module docstring).
